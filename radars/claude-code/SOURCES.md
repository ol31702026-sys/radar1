# Источники сбора — Claude Code Radar

Сбор идёт из двух мест: `prompts/queries.md` (WebSearch) и `sources.json` (прямые ленты).
Ниже — честный статус каждого канала (проверено через встроенный WebFetch, июнь 2026).

## Статус каналов

| Канал | Статус | Комментарий |
|-------|--------|-------------|
| **WebSearch** (блоги/доки) | ✅ работает | Хорошо по статьям/релизам. Плохо видит соцсети. |
| **YouTube RSS** | ✅ работает | Отдаёт видео с точными датами. Нужен `channel_id` (не `@handle`). |
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

## X (Twitter)

За логином, бесплатного пути нет. Нужен MCP-сервер X или официальный API (платный).
