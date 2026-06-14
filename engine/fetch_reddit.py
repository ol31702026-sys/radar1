#!/usr/bin/env python3
"""
Reddit-сборщик для Radar. Обращается к публичному Reddit JSON с явным User-Agent.

ВАЖНО (проверено июнь 2026): Reddit отдаёт 403 не только встроенному WebFetch, но и этому
скрипту, если IP в блоклисте (датацентр/облако/часть WSL-сетей) — смена User-Agent НЕ помогает,
блок по IP/сети. Скрипт корректно ловит 403 и пропускает источник.
Где он РАБОТАЕТ: с домашнего/не-датацентрового IP, через VPN/прокси, или с Reddit OAuth-токеном
(зарегистрировать app: https://www.reddit.com/prefs/apps → script type → client_id/secret).
Для OAuth задай переменные окружения REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (см. fetch_oauth_token).

Читает источники type=reddit_json (enabled) из radars/<slug>/sources.json, фильтрует по
свежести (freshness_days из radar.config.json), дедуплицирует против уже собранных finds и
печатает кандидатов в JSON (по схеме find) в stdout — чтобы collect-finds/скрипт их подхватил.

Только стандартная библиотека. Запуск:
    python3 engine/fetch_reddit.py <slug> [--write]

Без --write: печатает кандидатов в stdout (для ревью человеком / скилла).
С --write: сливает кандидатов в radars/<slug>/data/finds/<today>.json (с дедупом).

Дату «сегодня» можно переопределить через --today YYYY-MM-DD (для тестов/детерминизма).
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

UA = "RadarBot/0.1 (personal knowledge digest; contact: local)"
ROOT = Path(__file__).resolve().parent.parent


def fetch_oauth_token() -> str | None:
    """Если заданы REDDIT_CLIENT_ID/SECRET — получить app-only токен (обходит IP-блок publuc JSON)."""
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    import base64
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token", data=data,
        headers={"Authorization": f"Basic {auth}", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("access_token")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        sys.stderr.write(f"[fetch_reddit] OAuth token error: {e}\n")
        return None


def norm_url(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"[#?].*$", "", u)          # убрать query/anchor (utm и т.п.)
    u = re.sub(r"/+$", "", u)              # хвостовой слэш
    return u


def find_id(url: str) -> str:
    return hashlib.sha1(norm_url(url).encode()).hexdigest()[:12]


def fetch_json(url: str, token: str | None = None, retries: int = 3) -> dict | None:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        # с токеном ходим на oauth.reddit.com
        url = url.replace("https://www.reddit.com", "https://oauth.reddit.com")
        url = url.replace("https://old.reddit.com", "https://oauth.reddit.com")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            sys.stderr.write(f"[fetch_reddit] {url} -> {e} (попытка {attempt+1}/{retries})\n")
            time.sleep(2 * (attempt + 1))
    return None


def load_known_ids(radar_dir: Path) -> set[str]:
    known = set()
    for fp in (radar_dir / "data" / "finds").glob("*.json"):
        try:
            for f in json.loads(fp.read_text(encoding="utf-8")):
                known.add(f.get("id"))
        except (json.JSONDecodeError, KeyError):
            continue
    return known


def post_to_find(p: dict, today: date, taxonomy: list[str]) -> dict | None:
    """Преобразовать Reddit-пост (data.children[].data) в объект find. None если не годится."""
    title = (p.get("title") or "").strip()
    # ссылка на оригинал: внешний url если есть и не на сам reddit-хост, иначе permalink
    url = p.get("url_overridden_by_dest") or p.get("url") or ""
    permalink = "https://www.reddit.com" + p.get("permalink", "")
    source_url = url if url.startswith("http") and "reddit.com" not in url else permalink
    if not title or not source_url:
        return None
    created = p.get("created_utc")
    if not created:
        return None
    pub = datetime.fromtimestamp(created, tz=timezone.utc).date()
    # грубые теги по ключевым словам в заголовке (из taxonomy)
    low = title.lower()
    tags = [t for t in taxonomy if t.replace("-", " ") in low or t in low]
    if not tags:
        tags = ["tips"]
    score = p.get("score", 0)
    sub = p.get("subreddit", "")
    author = p.get("author", "")
    return {
        "id": find_id(source_url),
        "date_found": today.isoformat(),
        "title": title[:140],
        "summary": f"Пост из r/{sub} (score {score}). {title[:300]}",
        "details": "",  # collect-finds/человек дополнит при отборе
        "tags": tags[:8],
        "source_url": source_url,
        "source_platform": "reddit",
        "author": f"u/{author}" if author else None,
        "published_at": pub.isoformat(),
        "confidence": "low",
        "_reddit_score": score,        # служебное поле для приоритезации (убрать при записи в finds)
        "_permalink": permalink,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--write", action="store_true", help="слить в data/finds/<today>.json")
    ap.add_argument("--today", help="YYYY-MM-DD (по умолчанию системная дата)")
    args = ap.parse_args()

    radar_dir = ROOT / "radars" / args.slug
    if not radar_dir.is_dir():
        sys.stderr.write(f"radar not found: {radar_dir}\n")
        return 1

    cfg = json.loads((radar_dir / "radar.config.json").read_text(encoding="utf-8"))
    fresh = int(cfg.get("freshness_days", 7))
    taxonomy = cfg.get("taxonomy", [])
    today = date.fromisoformat(args.today) if args.today else datetime.now().date()

    sources_fp = radar_dir / "sources.json"
    if not sources_fp.exists():
        sys.stderr.write("sources.json нет — нечего собирать\n")
        return 0
    sources = json.loads(sources_fp.read_text(encoding="utf-8")).get("sources", [])
    reddit_sources = [s for s in sources if s.get("type") == "reddit_json" and s.get("enabled")]
    if not reddit_sources:
        sys.stderr.write("нет включённых reddit_json источников (enabled:true)\n")
        return 0

    token = fetch_oauth_token()
    if token:
        sys.stderr.write("[fetch_reddit] использую OAuth-токен (oauth.reddit.com)\n")

    known = load_known_ids(radar_dir)
    seen = set(known)
    candidates = []
    for s in reddit_sources:
        data = fetch_json(s["url"], token=token)
        if not data:
            sys.stderr.write(f"[skip] {s.get('label')} — не удалось получить\n")
            continue
        children = data.get("data", {}).get("children", [])
        for ch in children:
            f = post_to_find(ch.get("data", {}), today, taxonomy)
            if not f:
                continue
            # фильтр свежести
            try:
                delta = (today - date.fromisoformat(f["published_at"])).days
            except ValueError:
                continue
            if delta < 0 or delta > fresh:
                continue
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            candidates.append(f)

    candidates.sort(key=lambda f: f.get("_reddit_score", 0), reverse=True)
    sys.stderr.write(f"[fetch_reddit] свежих кандидатов: {len(candidates)} (окно {fresh}д)\n")

    if args.write and candidates:
        out_fp = radar_dir / "data" / "finds" / f"{today.isoformat()}.json"
        existing = []
        if out_fp.exists():
            existing = json.loads(out_fp.read_text(encoding="utf-8"))
        # очистить служебные поля перед записью
        clean = []
        for f in candidates:
            f = {k: v for k, v in f.items() if not k.startswith("_")}
            clean.append(f)
        merged = existing + clean
        out_fp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        sys.stderr.write(f"[fetch_reddit] записано в {out_fp} (+{len(clean)}, всего {len(merged)})\n")
    else:
        json.dump(candidates, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
