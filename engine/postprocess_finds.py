#!/usr/bin/env python3
"""Постобработка дневного файла находок: дедуп + обрезка до daily_target.

Детерминированная часть конвейера сбора, вынесенная из промпта облачного
routine — чтобы не зависеть от того, доведёт ли LLM работу до конца. Если
ночной прогон выдал «сырой дамп» (десятки находок, дубли), один вызов
причёсывает его до нужного объёма.

Что делает:
  1. Дедуп кандидатов против ВСЕХ прошлых data/finds/*.json (по id и по
     нормализованному source_url) и внутри самого файла.
  2. Отбор ровно daily_target: сортировка по свежести (published_at) и весам
     тегов из profile.md, баланс по площадкам (round-robin), затем топ-N.
  3. Перезапись файла дня (с бэкапом .raw рядом) и отчёт в stdout.

Что НЕ делает: перевод title/summary на русский и сборку дайджеста — это
по-прежнему за LLM (творческая часть). Скрипт только режет и дедуплицирует.

Использование:
    python3 engine/postprocess_finds.py <slug> [YYYY-MM-DD]
    python3 engine/postprocess_finds.py claude-code            # сегодня (UTC)
    python3 engine/postprocess_finds.py claude-code 2026-06-29
    python3 engine/postprocess_finds.py claude-code --dry-run  # только показать
"""
import sys, os, json, glob, re, collections, datetime

CONF_RANK = {"high": 2, "med": 1, "medium": 1, "low": 0}


def norm_url(u):
    """Грубая нормализация URL для дедупа: схема/хост/путь без хвостового слеша,
    без query и якоря, в нижнем регистре."""
    u = (u or "").strip().lower()
    u = re.split(r"[?#]", u, maxsplit=1)[0]
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def load_tag_weights(profile_path):
    """Прочитать веса тегов из таблицы profile.md (| тег | вес |). Нет файла
    или строки — вес по умолчанию 1.0."""
    weights = {}
    if not os.path.exists(profile_path):
        return weights
    with open(profile_path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\|\s*([a-z0-9-]+)\s*\|\s*([\d.]+)\s*\|", line.strip())
            if m:
                weights[m.group(1)] = float(m.group(2))
    return weights


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print(__doc__)
        sys.exit(1)

    slug = args[0]
    day = args[1] if len(args) > 1 else datetime.datetime.utcnow().strftime("%Y-%m-%d")
    dry = "--dry-run" in flags

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    radar = os.path.join(root, "radars", slug)
    finds_dir = os.path.join(radar, "data", "finds")
    target_path = os.path.join(finds_dir, f"{day}.json")
    config_path = os.path.join(radar, "radar.config.json")
    profile_path = os.path.join(radar, "prompts", "profile.md")

    if not os.path.exists(target_path):
        sys.exit(f"Нет файла находок за {day}: {target_path}")
    config = json.load(open(config_path, encoding="utf-8"))
    daily_target = config.get("daily_target", 15)
    weights = load_tag_weights(profile_path)

    # id/url всех прошлых дней
    seen_ids, seen_urls = set(), set()
    for f in sorted(glob.glob(os.path.join(finds_dir, "*.json"))):
        if os.path.basename(f) == f"{day}.json":
            continue
        try:
            for x in json.load(open(f, encoding="utf-8")):
                seen_ids.add(x.get("id"))
                seen_urls.add(norm_url(x.get("source_url")))
        except (json.JSONDecodeError, TypeError):
            continue

    items = json.load(open(target_path, encoding="utf-8"))
    if not isinstance(items, list):
        sys.exit(f"Файл {target_path} не массив находок")
    print(f"Исходно за {day}: {len(items)} (цель {daily_target})")

    # Дедуп против прошлого + внутри файла
    out, lids, lurls = [], set(), set()
    dup_past = dup_self = 0
    for x in items:
        xid, url = x.get("id"), norm_url(x.get("source_url"))
        if not url:
            continue  # без ссылки находка не публикуется (правило проекта)
        if xid in seen_ids or url in seen_urls:
            dup_past += 1; continue
        if xid in lids or url in lurls:
            dup_self += 1; continue
        lids.add(xid); lurls.add(url); out.append(x)
    print(f"Дубли прошлых дней: {dup_past}, дубли внутри файла: {dup_self}, уникальных: {len(out)}")

    def score(x):
        tag_w = max((weights.get(t, 1.0) for t in x.get("tags", [])), default=1.0)
        return (x.get("published_at", ""), tag_w, CONF_RANK.get(x.get("confidence"), 0))

    out.sort(key=score, reverse=True)

    # Баланс по площадкам: round-robin, внутри площадки порядок уже по score
    by_plat = collections.OrderedDict()
    for x in out:
        by_plat.setdefault(x.get("source_platform", "other"), []).append(x)
    selected = []
    while len(selected) < daily_target and any(by_plat.values()):
        for plat in list(by_plat.keys()):
            if by_plat[plat]:
                selected.append(by_plat[plat].pop(0))
                if len(selected) >= daily_target:
                    break
    selected.sort(key=score, reverse=True)

    plats = dict(collections.Counter(x.get("source_platform") for x in selected))
    print(f"Отобрано: {len(selected)}; площадки: {plats}")
    if len(out) < daily_target:
        print(f"  (свежего меньше цели — взято всё, что есть: {len(selected)})")

    if dry:
        print("\n--dry-run: файл не изменён. Заголовки отобранного:")
        for i, x in enumerate(selected, 1):
            print(f"  {i:2d}. [{x.get('source_platform')}] {x.get('title','')[:70]}")
        return

    # Бэкап сырого файла в data/_raw/ — НЕ в finds/, чтобы build_manifest
    # (он делает finds/glob("*.json")) не посчитал дамп как отдельный день.
    raw_dir = os.path.join(radar, "data", "_raw")
    os.makedirs(raw_dir, exist_ok=True)
    raw_backup = os.path.join(raw_dir, f"{day}.json")
    if not os.path.exists(raw_backup):
        with open(raw_backup, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"Бэкап исходных {len(items)} находок: {raw_backup}")

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)
    print(f"Записано {len(selected)} в {target_path}")
    print("Перевод title/summary и дайджест — отдельно (LLM).")


if __name__ == "__main__":
    main()
