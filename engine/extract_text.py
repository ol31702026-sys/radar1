#!/usr/bin/env python3
"""
Извлекает СЫРОЙ текст первоисточника находки для последующего перевода скиллом `translate`.

- Статья (blog/docs/github/...): скачивает страницу и вытаскивает основной текст (грубо, без зависимостей).
- YouTube: пытается достать субтитры через yt-dlp (если установлен); иначе — описание видео
  через YouTube Data API (env YOUTUBE_API_KEY). Если ничего не доступно — сообщает честно.

Печатает в stdout JSON: {"id","source_url","platform","kind","lang_hint","text"}.
kind = article | youtube_subs | youtube_description | none

Запуск:
    python3 engine/extract_text.py <slug> <find_id>

Перевод НЕ делает (это работа скилла translate через Claude) — только собирает текст.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; RadarBot/0.1)"


def load_find(radar_dir: Path, fid: str) -> dict | None:
    for fp in (radar_dir / "data" / "finds").glob("*.json"):
        try:
            for f in json.loads(fp.read_text(encoding="utf-8")):
                if f.get("id") == fid:
                    return f
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def fetch_html(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(charset, "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as e:
        sys.stderr.write(f"[extract] fetch error: {e}\n")
        return None


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg|head).*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    # сохранить переносы у блочных тегов
    html = re.sub(r"(?i)</(p|div|h[1-6]|li|br|section|article)>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#39;|&rsquo;|&lsquo;", "'", text)
    text = re.sub(r"&quot;|&ldquo;|&rdquo;", '"', text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def video_id(url: str) -> str | None:
    m = re.search(r"(?:watch\?v=|shorts/|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else None


def youtube_subs(url: str) -> str | None:
    """Субтитры через yt-dlp (если установлен). Возвращает текст или None."""
    if not _have("yt-dlp"):
        return None
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        try:
            subprocess.run(
                ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
                 "--sub-langs", "en.*,ru.*,.*", "--sub-format", "vtt",
                 "-o", str(Path(td) / "%(id)s.%(ext)s"), url],
                check=False, capture_output=True, timeout=120,
            )
        except (subprocess.SubprocessError, OSError) as e:
            sys.stderr.write(f"[extract] yt-dlp error: {e}\n")
            return None
        vtts = list(Path(td).glob("*.vtt"))
        if not vtts:
            return None
        return _vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))


def _vtt_to_text(vtt: str) -> str:
    out = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.upper().startswith("WEBVTT") or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not out or out[-1] != line):
            out.append(line)
    return "\n".join(out)


def youtube_description(url: str) -> str | None:
    vid = video_id(url)
    key = os.environ.get("YOUTUBE_API_KEY")
    if not (vid and key):
        return None
    api = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={vid}&key={key}"
    try:
        with urllib.request.urlopen(api, timeout=20) as r:
            data = json.loads(r.read().decode())
        items = data.get("items", [])
        if not items:
            return None
        sn = items[0]["snippet"]
        return f"{sn.get('title','')}\n\n{sn.get('description','')}"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError) as e:
        sys.stderr.write(f"[extract] yt description error: {e}\n")
        return None


def _have(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: extract_text.py <slug> <find_id>\n")
        return 2
    slug, fid = sys.argv[1], sys.argv[2]
    radar_dir = ROOT / "radars" / slug
    f = load_find(radar_dir, fid)
    if not f:
        sys.stderr.write(f"find {fid} не найден в {slug}\n")
        return 1

    url = f["source_url"]
    platform = f.get("source_platform", "")
    result = {"id": fid, "source_url": url, "platform": platform, "kind": "none", "lang_hint": "", "text": ""}

    if platform == "youtube":
        subs = youtube_subs(url)
        if subs and len(subs) > 80:
            result.update(kind="youtube_subs", text=subs)
        else:
            desc = youtube_description(url)
            if desc:
                result.update(kind="youtube_description", text=desc)
            else:
                result["text"] = ("Субтитры недоступны (нет yt-dlp или у видео нет субтитров), "
                                  "и описание не получено. Установи yt-dlp (pip install yt-dlp) "
                                  "и/или задай YOUTUBE_API_KEY.")
    else:
        html = fetch_html(url)
        if html:
            text = html_to_text(html)
            result.update(kind="article", text=text[:20000])  # ограничить объём
        else:
            result["text"] = "Не удалось скачать страницу (возможно, блокирует ботов)."

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
