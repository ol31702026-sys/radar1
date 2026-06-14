#!/usr/bin/env python3
"""
Собирает страницу «На обдумывание» (THINKING.md) для радара из data/feedback/saved.json,
подтягивая заголовки/ссылки/теги из data/finds/*.json.

Общий для всех радаров (часть engine/). Запуск:
    python3 engine/build_thinking.py <slug>

Группировка по темам (первый тег находки), внутри — по статусу. Показывает личную заметку.
Не требует внешних зависимостей.
"""
import json
import sys
from pathlib import Path

STATUS_ORDER = ["new", "thinking", "done", "archived"]
STATUS_LABEL = {
    "new": "🆕 Новое",
    "thinking": "🤔 В работе",
    "done": "✅ Решено",
    "archived": "🗄 Архив",
}


def load_finds(radar_dir: Path) -> dict:
    finds = {}
    finds_dir = radar_dir / "data" / "finds"
    for fp in sorted(finds_dir.glob("*.json")):
        try:
            for f in json.loads(fp.read_text(encoding="utf-8")):
                finds[f["id"]] = f
        except (json.JSONDecodeError, KeyError):
            continue
    return finds


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: build_thinking.py <slug>", file=sys.stderr)
        return 2
    slug = sys.argv[1]
    root = Path(__file__).resolve().parent.parent
    radar_dir = root / "radars" / slug
    if not radar_dir.is_dir():
        print(f"radar not found: {radar_dir}", file=sys.stderr)
        return 1

    cfg = json.loads((radar_dir / "radar.config.json").read_text(encoding="utf-8"))
    saved = json.loads((radar_dir / "data" / "feedback" / "saved.json").read_text(encoding="utf-8"))
    items = saved.get("items", [])
    finds = load_finds(radar_dir)

    out = [f"# {cfg.get('title', slug)} — На обдумывание", ""]
    if not items:
        out += ["_Пока ничего не отложено. Нажми «⚑ Отложить» на карточке находки._", ""]
        (radar_dir / "THINKING.md").write_text("\n".join(out), encoding="utf-8", newline="\n")
        print("0 отложенных — страница пуста")
        return 0

    active = [i for i in items if i.get("status") != "archived"]
    out += [f"_Отложено: {len(items)} (активных: {len(active)})._", ""]

    # группировка по теме = первый тег находки
    by_theme: dict[str, list] = {}
    for it in items:
        f = finds.get(it.get("find_id"))
        theme = (f.get("tags") or ["(без темы)"])[0] if f else "(находка не найдена)"
        by_theme.setdefault(theme, []).append((it, f))

    for theme in sorted(by_theme):
        out += [f"## Тема: {theme}", ""]
        group = by_theme[theme]
        group.sort(key=lambda pair: STATUS_ORDER.index(pair[0].get("status", "new"))
                   if pair[0].get("status", "new") in STATUS_ORDER else 99)
        for it, f in group:
            status = it.get("status", "new")
            title = f.get("title", it.get("find_id", "?")) if f else f"(находка {it.get('find_id')} не найдена)"
            out.append(f"### {STATUS_LABEL.get(status, status)} — {title}")
            if f:
                tags = " · ".join(f.get("tags", []))
                src = f.get("source_url", "")
                author = f.get("author") or f.get("source_platform", "источник")
                out.append(f"_{tags}_ · Источник: [{author}]({src}) · отложено {it.get('saved_at','?')}")
            note = (it.get("note") or "").strip()
            if note:
                out += ["", f"> {note.replace(chr(10), chr(10)+'> ')}"]
            out.append("")
        out.append("")

    (radar_dir / "THINKING.md").write_text("\n".join(out).rstrip() + "\n", encoding="utf-8", newline="\n")
    print(f"THINKING.md обновлён: {len(items)} отложенных в {len(by_theme)} темах")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
