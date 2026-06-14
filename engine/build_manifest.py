#!/usr/bin/env python3
"""
Строит manifest.json — индекс для статического сайта (который не умеет листать папки).
Перечисляет радары и дни с находками. Сайт читает manifest, затем нужные data/*.json.

Общий для всех радаров (часть engine/). Запуск:
    python3 engine/build_manifest.py            # все радары
    python3 engine/build_manifest.py claude-code  # только один

Кладёт manifest.json в КОРЕНЬ проекта (рядом окажется engine/site/), чтобы статический
сервер, поднятый из корня, отдавал и сайт, и данные, и манифест по относительным путям.
"""
import json
import sys
from pathlib import Path


def build_radar(radar_dir: Path) -> dict:
    cfg = json.loads((radar_dir / "radar.config.json").read_text(encoding="utf-8"))
    finds_dir = radar_dir / "data" / "finds"
    days = []
    for fp in sorted(finds_dir.glob("*.json")):
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        days.append({"date": fp.stem, "count": len(arr)})
    days.sort(key=lambda d: d["date"], reverse=True)
    return {
        "slug": cfg["slug"],
        "title": cfg.get("title", cfg["slug"]),
        "description": cfg.get("description", ""),
        "language": cfg.get("language", "ru"),
        "taxonomy": cfg.get("taxonomy", []),
        "platforms": cfg.get("platforms", []),
        "days": days,
        "total_finds": sum(d["count"] for d in days),
    }


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    radars_dir = root / "radars"
    only = sys.argv[1] if len(sys.argv) > 1 else None

    radars = []
    for rd in sorted(radars_dir.iterdir()):
        if not rd.is_dir() or not (rd / "radar.config.json").exists():
            continue
        if only and rd.name != only:
            continue
        radars.append(build_radar(rd))

    manifest = {"radars": radars}
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(f"manifest.json: {len(radars)} радаров, "
          f"{sum(r['total_finds'] for r in radars)} находок всего")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
