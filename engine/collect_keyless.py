#!/usr/bin/env python3
"""Бесключевой сбор кандидатов-находок для радара (только stdlib).

Собирает кандидатов про тему радара из БЕСКЛЮЧЕВЫХ источников, доступных
из чистого Python в GitHub Actions (никаких API-ключей, никакого requests):

  * Hacker News через Algolia API (search_by_date, story).
  * GitHub Search API (repositories, sort=updated) — без токена (лимит 10 req/min).
  * YouTube RSS-ленты каналов из radars/<slug>/sources.json (channel_id).

Каждый кандидат приводится к формату find.schema.json (лёгкий этап):
  id (sha1 нормализованного url [:12]), date_found, title, summary, details="",
  tags (1-3 из taxonomy, угаданные по ключевым словам), source_url,
  source_platform, author, published_at (YYYY-MM-DD), confidence="low".

Фильтр свежести: только записи не старше freshness_days от целевой даты.
Кандидаты собираются с запасом (НЕ режутся до daily_target — это делает
engine/postprocess_finds.py). Результат — массив в
radars/<slug>/data/finds/<DATE>.json (перезапись; postprocess дедупит).

Использование:
    python3 engine/collect_keyless.py <slug> [YYYY-MM-DD]
    python3 engine/collect_keyless.py claude-code
    python3 engine/collect_keyless.py claude-code 2026-07-01
"""
import sys
import os
import json
import re
import time
import hashlib
import datetime
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

UA = "radar-collect-keyless/1.0 (+https://radar.local; stdlib-only)"

# Ключевые слова тега -> тег taxonomy. Первый найденный порядок сохраняется.
TAG_KEYWORDS = [
    ("subagents", ["subagent", "sub-agent", "sub agent", "multi-agent", "multi agent", "swarm", "agent team", "orchestrat"]),
    ("hooks", ["hook", "hooks"]),
    ("mcp", ["mcp", "model context protocol"]),
    ("skills", ["skill", "skills", "agent skill"]),
    ("slash-commands", ["slash command", "slash-command", "/command", "custom command"]),
    ("workflows", ["workflow", "pipeline", "playbook"]),
    ("automation", ["automat", "autonomous", "auto-", "cron", "scheduler"]),
    ("ci-cd", ["ci/cd", "ci-cd", "cicd", "github action", "gitlab ci", "pipeline ci", "continuous integration", "continuous deployment"]),
    ("testing", ["test", "testing", "unit test", "e2e", "pytest", "coverage"]),
    ("refactoring", ["refactor", "refactoring", "migrate", "migration", "codemod"]),
    ("prompting", ["prompt", "prompting", "prompt engineering", "system prompt"]),
    ("cost-tokens", ["token", "tokens", "cost", "pricing", "cheaper", "budget", "context window"]),
    ("ide-integration", ["vscode", "vs code", "jetbrains", "neovim", "vim", "ide", "editor", "cursor"]),
    ("case-study", ["case study", "case-study", "how we", "we built", "in production", "postmortem", "lessons"]),
]


def repo_root():
    """Корень репозитория — родитель каталога engine/."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm_url(u):
    """Грубая нормализация URL для стабильного id/дедупа."""
    u = (u or "").strip().lower()
    u = re.split(r"[?#]", u, maxsplit=1)[0]
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def find_id(url):
    return hashlib.sha1(norm_url(url).encode("utf-8")).hexdigest()[:12]


def http_get_json(url, retries=3):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            sys.stderr.write(f"[collect_keyless] HTTP {e.code} {url} (попытка {attempt+1}/{retries})\n")
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
            sys.stderr.write(f"[collect_keyless] {url} -> {type(e).__name__} (попытка {attempt+1}/{retries})\n")
            time.sleep(2 * (attempt + 1))
    return None


def http_get_text(url, retries=3):
    headers = {"User-Agent": UA, "Accept": "application/atom+xml, application/xml, text/xml"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            sys.stderr.write(f"[collect_keyless] HTTP {e.code} {url} (попытка {attempt+1}/{retries})\n")
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            sys.stderr.write(f"[collect_keyless] {url} -> {type(e).__name__} (попытка {attempt+1}/{retries})\n")
            time.sleep(2 * (attempt + 1))
    return None


# Маркеры релевантности теме. Находка без хотя бы одного — отсеивается как шум
# (машсбор с HN/YouTube тянет много не по теме: игры, книги, общие AI-новости).
RELEVANCE_MARKERS = (
    "claude code", "claude-code", "claudecode", "claude desktop",
    "anthropic", "mcp", "subagent", "sub-agent", "agentic",
    "claude api", "claude sdk", "slash command", "claude skill",
    "claude sonnet", "claude opus", "claude agent",
)


def is_relevant(title, summary):
    """True, если находка про Claude Code / агентную разработку.

    ВАЖНО: судим по ЗАГОЛОВКУ, а не по summary — для YouTube summary шаблонное
    («Видео про Claude Code»), оно даёт ложную релевантность. Заголовок обязан
    сам содержать признак темы."""
    t = (title or "").lower()
    if any(m in t for m in RELEVANCE_MARKERS):
        return True
    # 'claude' + инженерный признак в самом заголовке
    if "claude" in t and any(k in t for k in
                             ("code", "agent", "cli", "tool", "workflow", "hook",
                              "skill", "plugin", "terminal", "repo", "commit", "sdk",
                              "desktop", "mcp")):
        return True
    return False


def guess_tags(text, taxonomy):
    """1-3 тега из taxonomy по ключевым словам в тексте. Пусто -> ['tips']."""
    t = (text or "").lower()
    tax = set(taxonomy)
    tags = []
    for tag, kws in TAG_KEYWORDS:
        if tag not in tax:
            continue
        if any(kw in t for kw in kws):
            tags.append(tag)
        if len(tags) >= 3:
            break
    if not tags:
        tags = ["tips"] if "tips" in tax else ([taxonomy[0]] if taxonomy else ["tips"])
    return tags


def parse_iso_date(s):
    """Достать YYYY-MM-DD из ISO/timestamp-строки; None если не вышло."""
    if not s:
        return None
    s = str(s)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    # Unix timestamp?
    try:
        ts = int(float(s))
        if ts > 10_000_000:
            return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return None


def within_freshness(published_at, target_date, freshness_days):
    if not published_at:
        return False
    try:
        pub = datetime.date.fromisoformat(published_at)
        tgt = datetime.date.fromisoformat(target_date)
    except ValueError:
        return False
    delta = (tgt - pub).days
    # Свежесть: не старше freshness_days. Будущие даты (delta<0) не режем —
    # RSS иногда отдаёт TZ-сдвиг; ограничим разумным окном вперёд.
    return -2 <= delta <= freshness_days


def truncate(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Источники
# ---------------------------------------------------------------------------

def collect_hn(query, taxonomy, target_date, freshness_days, date_found):
    """Hacker News через Algolia (search_by_date, story, points>2)."""
    out = []
    q = urllib.parse.quote(query)
    url = (
        "https://hn.algolia.com/api/v1/search_by_date"
        f"?query={q}&tags=story&numericFilters=points%3E2&hitsPerPage=100"
    )
    data = http_get_json(url)
    if not data or "hits" not in data:
        return out
    for hit in data.get("hits", []):
        try:
            object_id = hit.get("objectID")
            title = (hit.get("title") or "").strip()
            if not title:
                continue
            url_hit = hit.get("url")
            source_url = url_hit or (f"https://news.ycombinator.com/item?id={object_id}" if object_id else None)
            if not source_url:
                continue
            published_at = parse_iso_date(hit.get("created_at") or hit.get("created_at_i"))
            if not within_freshness(published_at, target_date, freshness_days):
                continue
            points = hit.get("points") or 0
            comments = hit.get("num_comments") or 0
            author = hit.get("author") or ""
            summary = f"{points} баллов, {comments} комментов на Hacker News."
            fid = find_id(source_url)
            out.append({
                "id": fid,
                "date_found": date_found,
                "title": truncate(title, 140),
                "summary": truncate(summary, 600),
                "details": "",
                "tags": guess_tags(title, taxonomy),
                "source_url": source_url,
                "source_platform": "hn",
                "author": author,
                "published_at": published_at,
                "confidence": "low",
            })
        except Exception as e:  # noqa: BLE001 — один битый hit не роняет сбор
            sys.stderr.write(f"[collect_keyless] HN hit skipped: {type(e).__name__}\n")
            continue
    return out


def collect_github(query, taxonomy, target_date, freshness_days, date_found):
    """GitHub Search API (repositories, sort=updated) — без токена."""
    out = []
    q = urllib.parse.quote(query)
    url = (
        "https://api.github.com/search/repositories"
        f"?q={q}&sort=updated&per_page=30"
    )
    data = http_get_json(url)
    if not data or "items" not in data:
        return out
    for repo in data.get("items", []):
        try:
            full_name = repo.get("full_name") or ""
            html_url = repo.get("html_url")
            if not html_url or not full_name:
                continue
            description = (repo.get("description") or "").strip()
            stars = repo.get("stargazers_count") or 0
            published_at = parse_iso_date(repo.get("pushed_at"))
            if not within_freshness(published_at, target_date, freshness_days):
                continue
            owner = ((repo.get("owner") or {}).get("login")) or ""
            title = f"{full_name}" + (f" — {description}" if description else "")
            summary_bits = []
            if description:
                summary_bits.append(description)
            summary_bits.append(f"★{stars}")
            summary = ". ".join([b for b in [". ".join(summary_bits[:-1]), summary_bits[-1]] if b]) if description else f"GitHub-репозиторий {full_name}. ★{stars}"
            # Проще и предсказуемее:
            summary = (f"{description} ★{stars}" if description else f"GitHub-репозиторий {full_name}. ★{stars}")
            text_for_tags = f"{full_name} {description}"
            out.append({
                "id": find_id(html_url),
                "date_found": date_found,
                "title": truncate(title, 140),
                "summary": truncate(summary, 600),
                "details": "",
                "tags": guess_tags(text_for_tags, taxonomy),
                "source_url": html_url,
                "source_platform": "github",
                "author": owner,
                "published_at": published_at,
                "confidence": "low",
            })
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[collect_keyless] GitHub item skipped: {type(e).__name__}\n")
            continue
    return out


def collect_youtube(sources, taxonomy, target_date, freshness_days, date_found):
    """YouTube RSS-ленты каналов из sources.json (type=youtube_rss, channel_id)."""
    out = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    channel_urls = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        if src.get("type") != "youtube_rss" or not src.get("enabled", True):
            continue
        url = src.get("url")
        if not url:
            cid = src.get("channel_id")
            if cid:
                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        if url and "channel_id=" in url:
            channel_urls.append(url)

    for feed_url in channel_urls:
        try:
            xml_text = http_get_text(feed_url)
            if not xml_text:
                continue
            root = ET.fromstring(xml_text)
            feed_author = ""
            author_el = root.find("atom:author/atom:name", ns)
            if author_el is not None and author_el.text:
                feed_author = author_el.text.strip()
            for entry in root.findall("atom:entry", ns):
                try:
                    title_el = entry.find("atom:title", ns)
                    title = title_el.text.strip() if (title_el is not None and title_el.text) else ""
                    if not title:
                        continue
                    link = None
                    link_el = entry.find("atom:link", ns)
                    if link_el is not None:
                        link = link_el.get("href")
                    if not link:
                        continue
                    pub_el = entry.find("atom:published", ns)
                    published_at = parse_iso_date(pub_el.text if pub_el is not None else None)
                    if not within_freshness(published_at, target_date, freshness_days):
                        continue
                    author = feed_author
                    a_el = entry.find("atom:author/atom:name", ns)
                    if a_el is not None and a_el.text:
                        author = a_el.text.strip()
                    summary = f"Видео на YouTube{(' от ' + author) if author else ''} про Claude Code."
                    out.append({
                        "id": find_id(link),
                        "date_found": date_found,
                        "title": truncate(title, 140),
                        "summary": truncate(summary, 600),
                        "details": "",
                        "tags": guess_tags(title, taxonomy),
                        "source_url": link,
                        "source_platform": "youtube",
                        "author": author,
                        "published_at": published_at,
                        "confidence": "low",
                    })
                except Exception as e:  # noqa: BLE001
                    sys.stderr.write(f"[collect_keyless] YT entry skipped: {type(e).__name__}\n")
                    continue
        except ET.ParseError as e:
            sys.stderr.write(f"[collect_keyless] YT feed parse error {feed_url}: {e}\n")
            continue
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[collect_keyless] YT feed skipped {feed_url}: {type(e).__name__}\n")
            continue
    return out


def dedup(items):
    """Дедуп внутри собранного по id/нормализованному url + отсев нерелевантных."""
    seen_ids, seen_urls, out = set(), set(), []
    dropped = 0
    for x in items:
        fid = x.get("id")
        nu = norm_url(x.get("source_url"))
        if not nu:
            continue
        if fid in seen_ids or nu in seen_urls:
            continue
        if not is_relevant(x.get("title"), x.get("summary")):
            dropped += 1
            continue
        seen_ids.add(fid)
        seen_urls.add(nu)
        out.append(x)
    if dropped:
        sys.stderr.write(f"[collect_keyless] отсеяно нерелевантных: {dropped}\n")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    slug = args[0]
    day = args[1] if len(args) > 1 else datetime.datetime.utcnow().strftime("%Y-%m-%d")

    root = repo_root()
    radar = os.path.join(root, "radars", slug)
    config_path = os.path.join(radar, "radar.config.json")
    sources_path = os.path.join(radar, "sources.json")
    finds_dir = os.path.join(radar, "data", "finds")

    if not os.path.exists(config_path):
        sys.exit(f"Нет конфига радара: {config_path}")
    config = json.load(open(config_path, encoding="utf-8"))
    taxonomy = config.get("taxonomy", [])
    freshness_days = int(config.get("freshness_days", 7))

    os.makedirs(finds_dir, exist_ok=True)

    print(f"Сбор бесключевых кандидатов для '{slug}' за {day} (свежесть ≤ {freshness_days} дн.)")

    all_items = []

    # --- Hacker News (несколько запросов) ---
    hn_items = []
    for q in ["claude code", "claude code mcp", "claude code agent"]:
        try:
            got = collect_hn(q, taxonomy, day, freshness_days, day)
            hn_items.extend(got)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[collect_keyless] HN query '{q}' failed: {type(e).__name__}\n")
    hn_items = dedup(hn_items)
    print(f"  HN: {len(hn_items)}")
    all_items.extend(hn_items)

    # --- GitHub (несколько запросов, пауза от rate limit) ---
    gh_items = []
    for i, q in enumerate(["claude code", "claude-code mcp", "claude code subagents"]):
        try:
            got = collect_github(q, taxonomy, day, freshness_days, day)
            gh_items.extend(got)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[collect_keyless] GitHub query '{q}' failed: {type(e).__name__}\n")
        if i < 2:
            time.sleep(7)  # без токена лимит 10 req/min — держим дистанцию
    gh_items = dedup(gh_items)
    print(f"  GitHub: {len(gh_items)}")
    all_items.extend(gh_items)

    # --- YouTube RSS ---
    yt_items = []
    if os.path.exists(sources_path):
        try:
            sources_doc = json.load(open(sources_path, encoding="utf-8"))
            sources = sources_doc.get("sources", []) if isinstance(sources_doc, dict) else []
            yt_items = collect_youtube(sources, taxonomy, day, freshness_days, day)
            yt_items = dedup(yt_items)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[collect_keyless] sources.json/YouTube failed: {type(e).__name__}\n")
    else:
        print("  YouTube: пропущено (нет sources.json)")
    if yt_items or os.path.exists(sources_path):
        print(f"  YouTube: {len(yt_items)}")
    all_items.extend(yt_items)

    # Общий дедуп между площадками
    all_items = dedup(all_items)

    target_path = os.path.join(finds_dir, f"{day}.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"Итого собрано {len(all_items)} кандидатов -> {target_path}")
    print("Дальше: postprocess_finds (дедуп+обрезка) → translate_finds → build_digest.")


if __name__ == "__main__":
    main()
