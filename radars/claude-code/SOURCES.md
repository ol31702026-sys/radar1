# Источники сбора — Claude Code Radar

Сбор идёт из двух мест: `prompts/queries.md` (WebSearch) и `sources.json` (прямые ленты).
Ниже — честный статус каждого канала (проверено через встроенный WebFetch, июнь 2026).

## Статус каналов

| Канал | Статус | Комментарий |
|-------|--------|-------------|
| **WebSearch** (блоги/доки) | ✅ работает | Хорошо по статьям/релизам. Плохо видит соцсети. |
| **YouTube RSS** | ✅ работает | Видео с конкретных каналов (по `channel_id`). 6 каналов подключено. |
| **YouTube Data API** | 🔑 готов, нужен ключ | Поиск по всему YouTube. `engine/fetch_youtube.py`, env `YOUTUBE_API_KEY`. Инструкция ниже. |
| **Прочие RSS/Atom** | ⚠️ зависит | Часть доменов отдаётся, часть блокирует WebFetch — проверять. |
| **Reddit** (json/rss, www/old) | ❌ заблокирован по IP | И WebFetch, и внешний скрипт получают 403 — блок по IP/сети (датацентр/WSL), не по User-Agent. Обход: см. ниже. |
| **X (Twitter)** | ❌ нет доступа | За логином. Нужен MCP/официальный API (платный). |

## Как добавить YouTube-канал

1. Найди `channel_id`: открой канал → исходник страницы → `"channelId":"UC..."`
   (или из URL вида `youtube.com/channel/UC...`). По `@handle` напрямую не получится — редирект на consent.
2. Добавь в `sources.json` запись `type: "youtube_rss"`, `enabled: true`, URL:
   `https://www.youtube.com/feeds/videos.xml?channel_id=UC...`

Сейчас включён: **Nick Saraev** (`UCbo-KbSjJDG6JWQ_MTZ_rNA`).

## Reddit: сборщик готов, но нужен обход IP-блока

Скрипт `engine/fetch_reddit.py` написан и проверен: читает `sources.json`, фильтрует по
свежести, дедуплицирует. Но Reddit отдаёт **403 по IP** (датацентр/WSL) — смена User-Agent
не помогает. Три способа включить его:

1. **Reddit OAuth (рекомендуется, бесплатно).** Зарегистрируй app:
   <https://www.reddit.com/prefs/apps> → тип «script» → получишь `client_id` и `secret`.
   Затем:
   ```bash
   export REDDIT_CLIENT_ID=...   REDDIT_CLIENT_SECRET=...
   python3 engine/fetch_reddit.py claude-code --write
   ```
   Скрипт сам пойдёт через `oauth.reddit.com` и обойдёт блок.
2. **Запуск с домашнего IP / через VPN** — где IP не в блоклисте Reddit, работает и без OAuth.
3. **MCP-сервер Reddit** — альтернатива скрипту, если предпочитаешь интеграцию через MCP.

## YouTube: поиск по ВСЕМУ YouTube (Data API)

RSS даёт видео только с подключённых каналов. Чтобы искать «все видео по Claude Code за
период по всему YouTube» — нужен **YouTube Data API v3** (бесплатно, ~100 поисков/день).

**Как получить ключ (один раз, ~10 минут):**
1. <https://console.cloud.google.com/> → создать проект (напр. `radar-youtube`).
2. **APIs & Services → Library** → найти «**YouTube Data API v3**» → **Enable**.
3. **APIs & Services → Credentials** → **Create Credentials → API key** → скопировать `AIza...`.
4. (Рекомендуется) Edit key → API restrictions → только «YouTube Data API v3».
5. Передать ключ через переменную окружения (НЕ коммитить в git):
   ```bash
   export YOUTUBE_API_KEY=AIza...твой_ключ
   ```

**Запуск:**
```bash
python3 engine/fetch_youtube.py claude-code           # печатает кандидатов
python3 engine/fetch_youtube.py claude-code --write    # сразу пишет в data/finds/<today>.json
```

Параметры поиска — в `radar.config.json → youtube_search` (запросы, `min_views` для отсева
шума, `max_per_query`). Скрипт ищет по окну `freshness_days`, подтягивает просмотры и
отбрасывает видео ниже порога. Квота: 1 поиск = 100 ед из 10 000/день.

## Полный текст / транскрипция («Весь текст» на сайте)

Кнопка «Весь текст» в drill-down показывает полный русский перевод первоисточника. Готовится
лениво скиллом `/translate <slug> <find_id>` → файл `data/fulltext/<id>.ru.md`.

- **Статьи** — `engine/extract_text.py` скачивает страницу и вытаскивает текст → перевод.
  Часть сайтов (напр. geeky-gadgets) блокируют фетч — тогда делаем краткий пересказ.
- **YouTube** — субтитры через **yt-dlp** (`pip install yt-dlp`). Нюанс: YouTube иногда отдаёт
  **429/«not a bot»** с датацентровых IP — субтитры могут не скачаться (как блок Reddit). С
  домашнего IP работает. Запасной путь — описание видео через Data API (env `YOUTUBE_API_KEY`).

## X (Twitter)

За логином, бесплатного пути нет. Нужен MCP-сервер X или официальный API (платный).
