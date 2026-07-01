#!/usr/bin/env python3
"""Сборка человекочитаемого дайджеста дня из находок (упрощённый авто-формат).

Читает radars/<slug>/data/finds/<DATE>.json и генерирует
radars/<slug>/data/digests/<DATE>.md.

У авто-находок поле details пустое, поэтому используется упрощённый формат
(без блоков Зачем/Как/Подвох — они появляются только при ручной расшифровке):

    # Claude Code Radar — дайджест за <DATE>

    _Собрано N находок._

    ---

    ## 1. <title>

    <summary>

    `<теги>` · Источник: [<platform>/<author>](<source_url>)

    ---

Использование:
    python3 engine/build_digest.py <slug> [YYYY-MM-DD]
    python3 engine/build_digest.py claude-code
    python3 engine/build_digest.py claude-code 2026-07-01
"""
import sys
import os
import json
import datetime

# Человекочитаемое имя радара по slug (для шапки). Фолбэк — из конфига/slug.
DEFAULT_TITLES = {
    "claude-code": "Claude Code Radar",
}


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def radar_title(radar_dir, slug):
    cfg_path = os.path.join(radar_dir, "radar.config.json")
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        t = cfg.get("title")
        if t:
            return t
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_TITLES.get(slug, slug)


def source_line(x):
    platform = x.get("source_platform", "other")
    author = (x.get("author") or "").strip()
    url = x.get("source_url", "")
    label = f"{platform}/{author}" if author else platform
    tags = x.get("tags") or []
    tags_str = " · ".join(tags) if tags else "tips"
    return f"`{tags_str}` · Источник: [{label}]({url})"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    slug = args[0]
    day = args[1] if len(args) > 1 else datetime.datetime.utcnow().strftime("%Y-%m-%d")

    root = repo_root()
    radar_dir = os.path.join(root, "radars", slug)
    finds_path = os.path.join(radar_dir, "data", "finds", f"{day}.json")
    digests_dir = os.path.join(radar_dir, "data", "digests")

    if not os.path.exists(finds_path):
        sys.exit(f"Нет файла находок за {day}: {finds_path}")

    items = json.load(open(finds_path, encoding="utf-8"))
    if not isinstance(items, list):
        sys.exit(f"Файл {finds_path} не массив находок")

    os.makedirs(digests_dir, exist_ok=True)
    title = radar_title(radar_dir, slug)

    lines = []
    lines.append(f"# {title} — дайджест за {day}")
    lines.append("")
    lines.append(f"_Собрано {len(items)} находок._")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, x in enumerate(items, 1):
        t = (x.get("title") or "").strip() or "(без заголовка)"
        summary = (x.get("summary") or "").strip()
        lines.append(f"## {i}. {t}")
        lines.append("")
        if summary:
            lines.append(summary)
            lines.append("")
        lines.append(source_line(x))
        lines.append("")
        lines.append("---")
        lines.append("")

    out_path = os.path.join(digests_dir, f"{day}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    print(f"Дайджест собран: {out_path} ({len(items)} блоков)")


if __name__ == "__main__":
    main()
