#!/usr/bin/env python3
"""
YouTube-сборщик для Radar через YouTube Data API v3 — поиск по ВСЕМУ YouTube
(не только по подключённым каналам), за окно свежести, с фильтром по просмотрам.

Нужен бесплатный API-ключ Google (см. radars/<slug>/SOURCES.md). Передаётся через env:
    export YOUTUBE_API_KEY=AIza...
Без ключа скрипт ничего не делает и подсказывает, как его получить.

Конфиг поиска — radar.config.json -> youtube_search:
    queries[], min_views, max_per_query, relevance_language

Запуск:
    python3 engine/fetch_youtube.py <slug> [--write] [--today YYYY-MM-DD]

Квота: search.list = 100 ед/запрос, videos.list (статистика) = ~1 ед на пачку.
По умолчанию 10 000 ед/день → ~100 поисков. Наш набор запросов берёт сотни единиц в день.

Только стандартная библиотека.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.googleapis.com/youtube/v3"


def find_id(url: str) -> str:
    return hashlib.sha1(url.lower().encode()).hexdigest()[:12]


def api_get(endpoint: str, params: dict) -> dict | None:
    url = f"{API}/{endpoint}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        sys.stderr.write(f"[fetch_youtube] HTTP {e.code} {endpoint}: {body}\n")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.stderr.write(f"[fetch_youtube] {endpoint}: {e}\n")
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


def tag_from_text(text: str, taxonomy: list[str]) -> list[str]:
    low = text.lower()
    tags = [t for t in taxonomy if t.replace("-", " ") in low or t in low]
    return tags[:8] or ["tips"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--today")
    args = ap.parse_args()

    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.stderr.write(
            "YOUTUBE_API_KEY не задан. Получи бесплатный ключ (см. SOURCES.md):\n"
            "  1) console.cloud.google.com → новый проект\n"
            "  2) APIs & Services → Library → включить 'YouTube Data API v3'\n"
            "  3) Credentials → Create → API key\n"
            "  4) export YOUTUBE_API_KEY=AIza...\n"
        )
        return 2

    radar_dir = ROOT / "radars" / args.slug
    cfg = json.loads((radar_dir / "radar.config.json").read_text(encoding="utf-8"))
    fresh = int(cfg.get("freshness_days", 7))
    taxonomy = cfg.get("taxonomy", [])
    ys = cfg.get("youtube_search", {})
    queries = ys.get("queries", ["Claude Code"])
    min_views = int(ys.get("min_views", 0))
    max_per_query = int(ys.get("max_per_query", 15))
    rel_lang = ys.get("relevance_language")

    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    published_after = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    # окно свежести назад
    from datetime import timedelta
    published_after = (published_after - timedelta(days=fresh)).strftime("%Y-%m-%dT%H:%M:%SZ")

    known = load_known_ids(radar_dir)
    seen = set(known)

    # 1) search.list по каждому запросу → собрать videoId
    video_ids: list[str] = []
    meta: dict[str, dict] = {}
    for q in queries:
        params = {
            "key": key, "part": "snippet", "type": "video", "q": q,
            "order": "date", "maxResults": min(max_per_query, 50),
            "publishedAfter": published_after,
        }
        if rel_lang:
            params["relevanceLanguage"] = rel_lang
        data = api_get("search", params)
        if not data:
            continue
        for it in data.get("items", []):
            vid = it.get("id", {}).get("videoId")
            sn = it.get("snippet", {})
            if not vid or vid in meta:
                continue
            meta[vid] = {
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "published": (sn.get("publishedAt", "") or "")[:10],
                "query": q,
            }
            video_ids.append(vid)

    if not video_ids:
        sys.stderr.write("[fetch_youtube] поиск ничего не вернул в окне свежести\n")
        print("[]")
        return 0

    # 2) videos.list → статистика просмотров (пачками по 50)
    views: dict[str, int] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        data = api_get("videos", {"key": key, "part": "statistics", "id": ",".join(chunk)})
        if not data:
            continue
        for it in data.get("items", []):
            views[it["id"]] = int(it.get("statistics", {}).get("viewCount", 0))

    # 3) собрать находки с фильтром просмотров и дедупом
    candidates = []
    for vid in video_ids:
        m = meta[vid]
        v = views.get(vid, 0)
        if v < min_views:
            continue
        url = f"https://www.youtube.com/watch?v={vid}"
        fid = find_id(url)
        if fid in seen:
            continue
        seen.add(fid)
        candidates.append({
            "id": fid,
            "date_found": today.isoformat(),
            "title": m["title"][:140],
            "summary": f"Видео «{m['title'][:120]}» — канал {m['channel']} ({v:,} просмотров).".replace(",", " "),
            "details": "",
            "tags": tag_from_text(m["title"] + " " + m["query"], taxonomy),
            "source_url": url,
            "source_platform": "youtube",
            "author": m["channel"],
            "published_at": m["published"],
            "confidence": "low",
            "_views": v,
        })

    candidates.sort(key=lambda f: f["_views"], reverse=True)
    sys.stderr.write(f"[fetch_youtube] кандидатов: {len(candidates)} (мин. {min_views} просмотров, окно {fresh}д)\n")

    if args.write and candidates:
        out_fp = radar_dir / "data" / "finds" / f"{today.isoformat()}.json"
        existing = json.loads(out_fp.read_text(encoding="utf-8")) if out_fp.exists() else []
        clean = [{k: v for k, v in f.items() if not k.startswith("_")} for f in candidates]
        out_fp.write_text(json.dumps(existing + clean, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        sys.stderr.write(f"[fetch_youtube] записано +{len(clean)} в {out_fp}\n")
    else:
        json.dump(candidates, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
