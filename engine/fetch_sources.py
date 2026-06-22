#!/usr/bin/env python3
"""
Универсальный сборщик «открытых» источников для Radar: Hacker News, Lobsters, Dev.to, GitHub.
Все они отдают данные БЕЗ логина и БЕЗ платных ключей (проверено живьём, июнь 2026) — это
замена выпавшему Reddit (Reddit в 2026 закрыл self-serve API + блокирует публичный JSON по IP).

Читает источники из radars/<slug>/sources.json по полю type:
  - hn_algolia    — Hacker News Search (Algolia). queries[], min_points.
  - lobsters      — lobste.rs /t/<tag>.json. tags[], match[] (ключевые слова в title/url).
  - devto         — Dev.to (Forem) /api/articles?tag=. tags[], match[], min_reactions, per_page.
  - github_repos  — GitHub Search /search/repositories. queries[], min_stars.

Нормализует в формат find (engine/schema/find.schema.json), фильтрует по свежести
(freshness_days из radar.config.json), дедуплицирует против уже собранных data/finds/*.json,
тегирует по taxonomy. Печатает кандидатов в stdout (JSON) или с --write сливает в файл дня.

Только стандартная библиотека. Запуск:
    python3 engine/fetch_sources.py <slug> [--write] [--today YYYY-MM-DD] [--only hn_algolia,devto]
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Реалистичный браузерный UA: часть площадок отдаёт пустую/заблокированную выдачу дефолтному UA.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def norm_url(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"[#?].*$", "", u)
    u = re.sub(r"/+$", "", u)
    return u


def find_id(url: str) -> str:
    return hashlib.sha1(norm_url(url).encode()).hexdigest()[:12]


def http_get(url: str, accept: str = "application/json", retries: int = 3):
    headers = {"User-Agent": UA, "Accept": accept}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            # 403/429 = rate limit/блок — отступаем и пробуем ещё; прочее логируем и выходим
            sys.stderr.write(f"[fetch_sources] HTTP {e.code} {url} (попытка {attempt+1}/{retries})\n")
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            sys.stderr.write(f"[fetch_sources] {url} -> {type(e).__name__} (попытка {attempt+1}/{retries})\n")
            time.sleep(2 * (attempt + 1))
    return None


def load_known_ids(radar_dir: Path) -> set:
    known = set()
    for fp in (radar_dir / "data" / "finds").glob("*.json"):
        try:
            for f in json.loads(fp.read_text(encoding="utf-8")):
                known.add(f.get("id"))
        except (json.JSONDecodeError, KeyError):
            continue
    return known


def tag_from_text(text: str, taxonomy: list) -> list:
    low = text.lower()
    tags = [t for t in taxonomy if t.replace("-", " ") in low or t in low]
    return tags[:8] or ["tips"]


def matches(text: str, match_words: list) -> bool:
    """Грубый релевантный фильтр: если заданы ключевые слова — хотя бы одно должно встретиться."""
    if not match_words:
        return True
    low = (text or "").lower()
    return any(w.lower() in low for w in match_words)


def in_window(pub: date, today: date, fresh: int) -> bool:
    delta = (today - pub).days
    return 0 <= delta <= fresh


def mk_find(today, url, title, summary, tags, platform, author, pub, score_key, score_val):
    return {
        "id": find_id(url),
        "date_found": today.isoformat(),
        "title": title[:140],
        "summary": summary[:600],
        "details": "",
        "tags": tags,
        "source_url": url,
        "source_platform": platform,
        "author": author or None,
        "published_at": pub.isoformat(),
        "confidence": "low",
        score_key: score_val,  # служебное (с _) поле для приоритизации, убирается при записи
    }


# ---------- сборщики по типам ----------

def collect_hn(src, today, fresh, taxonomy):
    base = src.get("url", "https://hn.algolia.com/api/v1/search_by_date")
    min_points = int(src.get("min_points", 0))
    out = []
    for q in src.get("queries", ["claude code"]):
        params = {"query": q, "tags": "story", "hitsPerPage": 50}
        data = http_get(base + "?" + urllib.parse.urlencode(params))
        if not data:
            continue
        for h in data.get("hits", []):
            url = h.get("url") or (f"https://news.ycombinator.com/item?id={h.get('objectID')}" if h.get("objectID") else None)
            title = (h.get("title") or "").strip()
            if not url or not title:
                continue
            pts = int(h.get("points") or 0)
            if pts < min_points:
                continue
            ts = h.get("created_at_i")
            if not ts:
                continue
            pub = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            if not in_window(pub, today, fresh):
                continue
            comments = h.get("num_comments") or 0
            summary = f"Hacker News: «{title}» — {pts} баллов, {comments} комментариев."
            out.append(mk_find(today, url, title, summary,
                               tag_from_text(title + " " + q, taxonomy), src.get("default_platform", "hn"),
                               h.get("author"), pub, "_score", pts))
    return out


def collect_lobsters(src, today, fresh, taxonomy):
    match = src.get("match", [])
    out = []
    for tag in src.get("tags", ["ai"]):
        data = http_get(f"https://lobste.rs/t/{tag}.json")
        if not isinstance(data, list):
            continue
        for p in data:
            url = p.get("url") or p.get("short_id_url")
            title = (p.get("title") or "").strip()
            if not url or not title:
                continue
            if not matches(title + " " + (p.get("description_plain") or ""), match):
                continue
            created = p.get("created_at")
            if not created:
                continue
            try:
                pub = datetime.fromisoformat(created).date()
            except ValueError:
                continue
            if not in_window(pub, today, fresh):
                continue
            score = int(p.get("score") or 0)
            summary = f"Lobsters (тег {tag}): «{title}» — score {score}, {p.get('comment_count', 0)} комментариев."
            out.append(mk_find(today, url, title, summary,
                               tag_from_text(title, taxonomy), src.get("default_platform", "blog"),
                               (p.get("submitter_user") or None), pub, "_score", score))
    return out


def collect_devto(src, today, fresh, taxonomy):
    base = src.get("url", "https://dev.to/api/articles")
    match = src.get("match", [])
    min_react = int(src.get("min_reactions", 0))
    per_page = int(src.get("per_page", 20))
    out = []
    for tag in src.get("tags", ["ai"]):
        data = http_get(base + "?" + urllib.parse.urlencode({"tag": tag, "per_page": per_page}))
        if not isinstance(data, list):
            continue
        for a in data:
            url = a.get("url")
            title = (a.get("title") or "").strip()
            if not url or not title:
                continue
            text = title + " " + " ".join(a.get("tag_list") or []) + " " + (a.get("description") or "")
            if not matches(text, match):
                continue
            react = int(a.get("positive_reactions_count") or 0)
            if react < min_react:
                continue
            pub_raw = a.get("published_at") or ""
            try:
                pub = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if not in_window(pub, today, fresh):
                continue
            user = (a.get("user") or {}).get("username")
            summary = f"Dev.to: «{title}» — {react} реакций. Теги: {', '.join(a.get('tag_list') or [])}."
            out.append(mk_find(today, url, title, summary,
                               tag_from_text(text, taxonomy), src.get("default_platform", "blog"),
                               user, pub, "_score", react))
    return out


def collect_github(src, today, fresh, taxonomy):
    base = src.get("url", "https://api.github.com/search/repositories")
    min_stars = int(src.get("min_stars", 0))
    out = []
    for q in src.get("queries", ["claude code"]):
        data = http_get(base + "?" + urllib.parse.urlencode({"q": q, "sort": "updated", "order": "desc", "per_page": 20}))
        if not data:
            continue
        for repo in data.get("items", []):
            url = repo.get("html_url")
            name = repo.get("full_name") or ""
            desc = (repo.get("description") or "").strip()
            if not url or not name:
                continue
            stars = int(repo.get("stargazers_count") or 0)
            if stars < min_stars:
                continue
            # свежесть по дате последнего пуша (репо «вечнозелёные», но активность = свежесть)
            pushed = (repo.get("pushed_at") or "")[:10]
            try:
                pub = date.fromisoformat(pushed)
            except ValueError:
                continue
            if not in_window(pub, today, fresh):
                continue
            title = name if not desc else f"{name} — {desc}"
            summary = f"GitHub: репозиторий {name} (★{stars}). {desc}" if desc else f"GitHub: репозиторий {name} (★{stars})."
            out.append(mk_find(today, url, title, summary,
                               tag_from_text(name + " " + desc + " " + q, taxonomy),
                               src.get("default_platform", "github"),
                               (repo.get("owner") or {}).get("login"), pub, "_score", stars))
    return out


COLLECTORS = {
    "hn_algolia": collect_hn,
    "lobsters": collect_lobsters,
    "devto": collect_devto,
    "github_repos": collect_github,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--today")
    ap.add_argument("--only", help="через запятую: ограничить типы источников (для отладки)")
    args = ap.parse_args()

    radar_dir = ROOT / "radars" / args.slug
    if not radar_dir.is_dir():
        sys.stderr.write(f"radar not found: {radar_dir}\n")
        return 1
    cfg = json.loads((radar_dir / "radar.config.json").read_text(encoding="utf-8"))
    fresh = int(cfg.get("freshness_days", 7))
    taxonomy = cfg.get("taxonomy", [])
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()

    sources_fp = radar_dir / "sources.json"
    if not sources_fp.exists():
        sys.stderr.write("sources.json нет — нечего собирать\n")
        return 0
    sources = json.loads(sources_fp.read_text(encoding="utf-8")).get("sources", [])
    only = set(args.only.split(",")) if args.only else None

    known = load_known_ids(radar_dir)
    seen = set(known)
    candidates = []
    per_type = {}
    for src in sources:
        t = src.get("type")
        if t not in COLLECTORS or not src.get("enabled"):
            continue
        if only and t not in only:
            continue
        try:
            found = COLLECTORS[t](src, today, fresh, taxonomy)
        except Exception as e:  # один сбойный источник не валит остальные
            sys.stderr.write(f"[fetch_sources] {t} ({src.get('label')}): {type(e).__name__}: {e}\n")
            continue
        added = 0
        for f in found:
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            candidates.append(f)
            added += 1
        per_type[t] = per_type.get(t, 0) + added

    candidates.sort(key=lambda f: f.get("_score", 0), reverse=True)
    sys.stderr.write(f"[fetch_sources] свежих кандидатов: {len(candidates)} (окно {fresh}д) по типам: {per_type}\n")

    if args.write and candidates:
        out_fp = radar_dir / "data" / "finds" / f"{today.isoformat()}.json"
        existing = json.loads(out_fp.read_text(encoding="utf-8")) if out_fp.exists() else []
        clean = [{k: v for k, v in f.items() if not k.startswith("_")} for f in candidates]
        out_fp.write_text(json.dumps(existing + clean, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        sys.stderr.write(f"[fetch_sources] записано +{len(clean)} в {out_fp}\n")
    else:
        json.dump(candidates, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
