#!/usr/bin/env python3
"""Локальный watcher: причёсывает сырой дневной файл находок до daily_target.

Зачем: ночной сбор (облачный routine / расписание) кладёт сырой дамп в
data/finds/<сегодня>.json и не доводит до конца. Этот watcher ловит такой
файл и прогоняет детерминированную часть — postprocess_finds.py (дедуп +
обрезка до daily_target). НЕ переводит и НЕ коммитит: русификация и дайджест
требуют LLM, а коммит непереведённого опасен (попадёт на сайт). После работы
watcher печатает чёткий TODO — что осталось сделать человеку/агенту.

Ставится в OS-cron на ~00:20 локального времени (после того как сбор записал
файл). Идемпотентен: если файл уже причёсан (≤target и есть кириллица в
заголовках) — ничего не делает.

Использование:
    python3 engine/watch_finds.py <slug> [YYYY-MM-DD]
    python3 engine/watch_finds.py claude-code           # сегодня (локальная дата)
"""
import sys, os, json, re, subprocess, datetime

ENGINE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ENGINE)


def is_raw(path, target):
    """Файл считается сырым (нужна обработка), если находок больше target
    ИЛИ хоть один заголовок без кириллицы (не переведён)."""
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "файл нечитаем/не JSON"
    if not isinstance(data, list):
        return False, "не массив находок"
    if len(data) > target:
        return True, f"{len(data)} находок > target {target}"
    no_cyr = [i + 1 for i, x in enumerate(data)
              if not re.search("[а-яА-Я]", x.get("title", ""))]
    if no_cyr:
        return True, f"заголовки без кириллицы: позиции {no_cyr}"
    return False, f"уже причёсан ({len(data)} находок, заголовки русские)"


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    slug = args[0]
    day = args[1] if len(args) > 1 else datetime.date.today().strftime("%Y-%m-%d")

    radar = os.path.join(ROOT, "radars", slug)
    target_path = os.path.join(radar, "data", "finds", f"{day}.json")
    config = json.load(open(os.path.join(radar, "radar.config.json"), encoding="utf-8"))
    daily_target = config.get("daily_target", 15)

    print(f"[watch_finds] {slug} {day}")
    if not os.path.exists(target_path):
        print(f"  Файла за {day} нет — сбор ещё не отработал или дата пустая. Выходим.")
        return

    raw, why = is_raw(target_path, daily_target)
    if not raw:
        print(f"  Обработка не нужна: {why}")
        return

    print(f"  Файл сырой ({why}) — запускаю postprocess_finds.py")
    r = subprocess.run(
        [sys.executable, os.path.join(ENGINE, "postprocess_finds.py"), slug, day],
        capture_output=True, text=True,
    )
    print(r.stdout.rstrip())
    if r.returncode != 0:
        print(f"  ОШИБКА postprocess (код {r.returncode}):\n{r.stderr}")
        sys.exit(r.returncode)

    # Постпроцессор урезал, но НЕ перевёл. Явный TODO — намеренно без авто-коммита.
    print("  ----")
    print(f"  ГОТОВО (детерминированная часть). ОСТАЛОСЬ вручную/агентом:")
    print(f"    1. Русифицировать title+summary в {os.path.relpath(target_path, ROOT)}")
    print(f"    2. Собрать дайджест radars/{slug}/data/digests/{day}.md")
    print(f"    3. python3 engine/build_manifest.py")
    print(f"    4. git add radars/{slug}/data/ manifest.json && git commit && git push")
    print(f"  Сырой бэкап: radars/{slug}/data/_raw/{day}.json")


if __name__ == "__main__":
    main()
