#!/usr/bin/env python3
"""Перевод title/summary находок дня на русский через бесплатный MyMemory API.

Только stdlib (urllib), без ключей. Для каждой находки в
radars/<slug>/data/finds/<DATE>.json переводит поля title и summary
на русский через https://api.mymemory.translated.net/get?q=...&langpair=en|ru
(берём responseData.translatedText).

Правила:
  * Если в поле уже есть кириллица — поле не трогаем (уже переведено).
  * Пауза 1 сек между запросами (rate limit MyMemory).
  * Ошибку перевода одного поля логируем и оставляем оригинал, не падаем.
  * Сохраняем обратно в тот же файл (ensure_ascii=False, indent=2).

Использование:
    python3 engine/translate_finds.py <slug> [YYYY-MM-DD]
    python3 engine/translate_finds.py claude-code
    python3 engine/translate_finds.py claude-code 2026-07-01
"""
import sys
import os
import json
import re
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error

UA = "radar-translate-finds/1.0 (+https://radar.local; stdlib-only)"
CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def has_cyrillic(s):
    return bool(CYRILLIC_RE.search(s or ""))


# Пост-обработка: MyMemory коверкает имена продуктов. Чиним ГОТОВЫЙ перевод
# словарём замен — это надёжнее плейсхолдеров (их MyMemory переставляет/ломает).
# Ключ — регекс (регистронезависимо), значение — правильное имя.
POST_FIXES = [
    (r"\bкод[аеуо]?\s+клод[аеуы]?\b", "Claude Code"),
    (r"\bкодекс[аеуо]?\s+клод[аеуы]?\b", "Claude Codex"),
    (r"\bклод[аеуы]?\b", "Claude"),
    (r"\bблизнец[ыао]в?\b", "Gemini"),
    (r"\bсоннет[аеуо]?\b", "Sonnet"),
    (r"\bкурсор[аеуо]?\b", "Cursor"),
    (r"\bкодекс[аеуо]?\b", "Codex"),
]


def apply_post_fixes(text):
    if not text:
        return text
    for pat, repl in POST_FIXES:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    return text


def mymemory_translate(text, retries=2):
    """Перевести короткий текст en->ru. Имена чиним пост-словарём. None при неудаче."""
    text = (text or "").strip()
    if not text:
        return None
    # MyMemory ограничивает длину q (~500 байт на бесплатном режиме).
    q = urllib.parse.quote(text[:480])
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|ru"
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            rd = data.get("responseData") or {}
            translated = rd.get("translatedText")
            status = data.get("responseStatus")
            if translated and (status in (200, "200") or status is None):
                # Отсеиваем служебные сообщения об ошибке лимита
                low = translated.lower()
                if "mymemory warning" in low or "query length limit" in low or "invalid" in low:
                    sys.stderr.write(f"[translate_finds] MyMemory отказал: {translated[:80]}\n")
                    return None
                return apply_post_fixes(translated)
            # status != 200 — залогируем и попробуем ещё
            sys.stderr.write(f"[translate_finds] responseStatus={status} для '{text[:40]}'\n")
        except urllib.error.HTTPError as e:
            sys.stderr.write(f"[translate_finds] HTTP {e.code} (попытка {attempt+1})\n")
            if e.code in (429, 500, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
            sys.stderr.write(f"[translate_finds] {type(e).__name__} (попытка {attempt+1})\n")
            time.sleep(2 * (attempt + 1))
    return None


def translate_field(value):
    """Вернуть (новое_значение, переведено?). Кириллица -> без изменений."""
    if not value or has_cyrillic(value):
        return value, False
    translated = mymemory_translate(value)
    time.sleep(1)  # rate limit MyMemory: пауза 1 сек между запросами
    if translated:
        return translated, True
    return value, False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    slug = args[0]
    day = args[1] if len(args) > 1 else datetime.datetime.utcnow().strftime("%Y-%m-%d")

    root = repo_root()
    target_path = os.path.join(root, "radars", slug, "data", "finds", f"{day}.json")
    if not os.path.exists(target_path):
        sys.exit(f"Нет файла находок за {day}: {target_path}")

    items = json.load(open(target_path, encoding="utf-8"))
    if not isinstance(items, list):
        sys.exit(f"Файл {target_path} не массив находок")

    print(f"Перевод {len(items)} находок за {day} (en->ru, MyMemory)…")
    translated_titles = translated_summaries = skipped = 0

    for i, x in enumerate(items, 1):
        title = x.get("title", "")
        summary = x.get("summary", "")

        new_title, t_done = translate_field(title)
        if t_done:
            x["title"] = new_title
            translated_titles += 1
        elif title and has_cyrillic(title):
            skipped += 1

        new_summary, s_done = translate_field(summary)
        if s_done:
            x["summary"] = new_summary
            translated_summaries += 1

        if t_done or s_done:
            print(f"  {i:2d}. переведено: {new_title[:60]}")

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(
        f"Готово: заголовков переведено {translated_titles}, "
        f"summary переведено {translated_summaries}, "
        f"уже на русском (пропущено) {skipped}. -> {target_path}"
    )


if __name__ == "__main__":
    main()
