# Шаблон радара

Скопируй эту папку в `radars/<твой-slug>` и заполни:

1. **`radar.config.json`** — `slug`, `title`, `description`, `taxonomy` (словарь тегов темы).
2. **`prompts/queries.md`** — поисковые запросы под тему.
3. **`prompts/profile.md`** — оставь как есть; обучится сам по рейтингам.

`data/` уже содержит пустые `finds/`, `digests/`, `feedback/ratings.json` — трогать не нужно.

Затем: `/collect-finds <твой-slug>`.
