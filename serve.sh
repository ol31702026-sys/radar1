#!/usr/bin/env bash
# Запуск сайта Radar локально. Поднимает статический сервер из КОРНЯ проекта,
# чтобы сайт (engine/site/) видел данные (manifest.json, radars/...).
set -e
cd "$(dirname "$0")"
python3 engine/build_manifest.py
PORT="${1:-8765}"
echo ""
echo "  Открой:  http://127.0.0.1:${PORT}/engine/site/index.html"
echo ""
python3 -m http.server "$PORT" --bind 127.0.0.1
