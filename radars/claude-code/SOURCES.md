# Источники сбора — Claude Code Radar

Сбор идёт из двух мест: `prompts/queries.md` (WebSearch) и `sources.json` (прямые ленты).
Ниже — честный статус каждого канала (проверено через встроенный WebFetch, июнь 2026).

## Статус каналов

| Канал | Статус | Комментарий |
|-------|--------|-------------|
| **WebSearch** (блоги/доки) | ✅ работает | Хорошо по статьям/релизам. Плохо видит соцсети. |
| **YouTube RSS** | ✅ работает | Видео с конкретных каналов (по `channel_id`). 6 каналов подключено. |
| **YouTube Data API** | ✅ работает + в автосборе | Ключ в `.secrets.ps1` (gitignored). `engine/fetch_youtube.py` вызывается ночной обёрткой `daily_collect.ps1` перед collect-finds. Окно свежести `[today−fresh; today]` (обе границы). |
| **Hacker News** (Algolia) | ✅ работает + в автосборе | Без ключа. `engine/fetch_sources.py` (`hn_algolia`). Истории/Show HN по «claude code», даты+баллы. Главная замена Reddit. |
| **Lobsters** | ✅ работает + в автосборе | Без ключа. `fetch_sources.py` (`lobsters`). Сбор по тегам `ai`/`programming` + фильтр `match` (search.json заблокирован 400). |
| **Dev.to** (Forem) | ✅ работает + в автосборе | Без ключа. `fetch_sources.py` (`devto`). Статьи по тегам `claude`/`mcp`/`aiagents`, фильтр `match`. |
| **GitHub** (Search API) | ✅ работает + в автосборе | Без ключа (лимит 10/мин на search — хватает). `fetch_sources.py` (`github_repos`). Свежие/обновлённые репо-инструменты, свежесть по `pushed_at`. |
| **Прочие RSS/Atom** | ⚠️ зависит | Часть доменов отдаётся, часть блокирует WebFetch — проверять. |
| **Reddit** (json/rss, API) | ❌ закрыт самим Reddit | В 2026 Reddit закрыл self-serve создание API-ключей (Responsible Builder Policy + ручное одобрение) И блокирует публичный JSON по IP (403 даже с Windows-хоста). Без-API обходы (redlib-инстансы, `site:reddit.com`) проверены и **не работают**. `fetch_reddit.py` готов на случай одобренного OAuth-ключа. Заменён связкой HN+Lobsters+Dev.to. |
| **X (Twitter)** | ❌ нет доступа | За логином. Нужен MCP/официальный API (платный). |

## Как добавить YouTube-канал

1. Найди `channel_id`: открой канал → исходник страницы → `"channelId":"UC..."`
   (или из URL вида `youtube.com/channel/UC...`). По `@handle` напрямую не получится — редирект на consent.
2. Добавь в `sources.json` запись `type: "youtube_rss"`, `enabled: true`, URL:
   `https://www.youtube.com/feeds/videos.xml?channel_id=UC...`

Сейчас включён: **Nick Saraev** (`UCbo-KbSjJDG6JWQ_MTZ_rNA`).

## Reddit: сборщик готов, но нужен обход IP-блока

Скрипт `engine/fetch_reddit.py` написан и проверен: читает `sources.json`, фильтрует по
свежести, дедуплицирует. Но Reddit отдаёт **403 по IP** (подтверждено и с Windows-хоста, не
только WSL) — смена User-Agent не помогает. Рекомендуемый путь — **Reddit OAuth** (бесплатно).

### Шаги (один раз, ~3 минуты)

1. Открой <https://www.reddit.com/prefs/apps> (залогинься своим reddit-аккаунтом).
2. Внизу **«create another app...»** (или «are you a developer? create an app»).
3. Заполни: **name** = `radar` (любое); тип — **`script`** (важно: именно script);
   **redirect uri** = `http://localhost:8080` (формальность, не используется). **Create app**.
4. После создания возьми два значения:
   - **client_id** — короткая строка ПОД названием приложения (под надписью «personal use script»).
   - **secret** — поле `secret`.
5. Впиши их в `radars/claude-code/.secrets.ps1` (файл в `.gitignore`, не коммитится) —
   раскомментируй и подставь:

   ```powershell
   $env:REDDIT_CLIENT_ID = "client_id_сюда"
   $env:REDDIT_CLIENT_SECRET = "secret_сюда"
   ```

После этого ночная обёртка `daily_collect.ps1` сама загрузит ключи и запустит сбор Reddit
(через `oauth.reddit.com`, в обход IP-блока). Ручная проверка:

```powershell
. .\radars\claude-code\.secrets.ps1
python engine/fetch_reddit.py claude-code --today 2026-06-20
```

Альтернативы, если OAuth не подходит: запуск с домашнего IP / VPN (где IP не в блоклисте,
работает и без OAuth), либо MCP-сервер Reddit.

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
