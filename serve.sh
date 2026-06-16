#!/usr/bin/env bash
# Запуск сайта Radar локально. Поднимает статический сервер из КОРНЯ проекта,
# чтобы сайт (engine/site/) видел данные (manifest.json, radars/...).
set -e
cd "$(dirname "$0")"

# Выбрать рабочий Python (на Windows 'python3' бывает Store-заглушкой → берём 'python').
if command -v python3 >/dev/null 2>&1 && python3 -c '' >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python не найден" >&2; exit 1
fi

"$PY" engine/build_manifest.py
PORT="${1:-8765}"
echo ""
echo "  Открой:  http://127.0.0.1:${PORT}/engine/site/index.html"
echo ""
"$PY" -m http.server "$PORT" --bind 127.0.0.1
