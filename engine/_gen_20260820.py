# -*- coding: utf-8 -*-
"""Генератор находок claude-code за 2026-08-20."""
import json, re, glob, os, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = "2026-08-20"
RADAR = os.path.join(ROOT, "radars", "claude-code")

def norm(u):
    u = (u or "").strip().lower()
    u = re.sub(r"[#?].*$", "", u)
    u = re.sub(r"/+$", "", u)
    return u

def fid(u, suffix=""):
    key = (norm(u) + suffix).encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:16]

CHANGELOG = "https://code.claude.com/docs/en/changelog"
OCTAVIUS = "https://octavius.ai/business-automation/ai-automation-case-studies-small-business/"

FINDS = [

# ===== ЧАСТЬ A: НОВОСТИ CLAUDE CODE (позиции 1-4) =====

dict(
    id=fid(CHANGELOG, " v2.1.235"),
    date_found=TODAY,
    title="Claude Code 2.1.235: спелл-чекер в промпте и оптимизация cloud-сессий",
    summary=(
        "Версия 2.1.235 (18 августа) добавляет проверку орфографии в поле ввода промпта "
        "и снижает нагрузку на память и CPU при длинных cloud-сессиях — /ultrareview и "
        "/autofix-pr теперь работают эффективнее."
    ),
    details=(
        "**Что нового.** Версия 2.1.235 от 18 августа 2026. Добавлена настройка `spellcheck` "
        "— подчёркивает опечатки в поле ввода промпта через aspell, hunspell или ispell. "
        "Оптимизированы использование памяти и CPU для cloud-сессий (/ultrareview, /autofix-pr). "
        "Исправлено 15+ багов: сброс кэша промпта при переподключении language server, "
        "сдвинутые подсветки в многострочных промптах, Shift+Tab в диалоге разрешений "
        "закрывал поле вместо одобрения, HTML-entity в slash commands во время ответа агента, "
        "агент анонсировал недоступных агентов, поломанные диалоги при редактировании ячеек ноутбука.\n\n"
        "**Зачем вам.** Если вы регулярно запускаете длинные cloud-сессии, они теперь едят "
        "меньше ресурсов. Спелл-чекер полезен при диктовке промптов или работе не в родном "
        "языке — опечатка в названии метода меняет поведение агента. Исправление Shift+Tab "
        "в диалоге разрешений ускорит работу тем, кто держит руки на клавиатуре.\n\n"
        "**Как попробовать.** Обновите: `npm install -g @anthropic-ai/claude-code` или "
        "через IDE-расширение. Спелл-чекер включается в /config — флаг spellcheck. "
        "Требует установленного aspell или hunspell в системе."
    ),
    tags=["новости-claude", "релиз", "возможности"],
    source_url=CHANGELOG,
    source_platform="docs",
    published_at="2026-08-18",
    confidence="high",
),

dict(
    id=fid(CHANGELOG, " v2.1.233"),
    date_found=TODAY,
    title="Claude Code 2.1.233: GitLab worktree, cgroup для Bash и TTL-кэш WebFetch",
    summary=(
        "Версия 2.1.233 (14 августа) добавляет GitLab MR URL во флаге --worktree, "
        "ограничение памяти для Bash-скриптов через Linux cgroup и настраиваемый TTL кэша WebFetch. "
        "Закрыта уязвимость обхода sandbox на Windows (NT-namespace путь \\\\?\\\\)."
    ),
    details=(
        "**Что нового.** Версия 2.1.233 от 14 августа 2026. Добавлено: (1) GitLab MR URL "
        "в флаге --worktree и в `claude agents` — worktree теперь запускается из GitLab "
        "merge request, не только GitHub PR; (2) opt-in memory cgroup для Bash на Linux "
        "через env var `CLAUDE_CODE_TOOL_MEMORY_LIMIT` — ограничивает память для скриптов "
        "в Bash tool; (3) env var `CLAUDE_CODE_WEBFETCH_CACHE_TTL_MS` (дефолт 15 мин) — "
        "регулирует TTL кэша WebFetch; (4) настройка forward_user_identity в apps gateway "
        "для per-user spend attribution. Исправлены: cloud-сессии терялись при рестарте "
        "окружения, MCP v2 бесконечно переподключался к медленным серверам, Windows "
        "NT-namespace путь обходил sandbox — это уязвимость безопасности.\n\n"
        "**Зачем вам.** Для команд на GitLab — поддержка worktree из MR ускоряет "
        "параллельный code review. Memory cgroup критичен, если агент запускает тяжёлые "
        "Bash-скрипты (сборки, трансформации данных) — можно ограничить их аппетит. "
        "WebFetch TTL полезен для сессий, которые часто фетчат одни и те же API, или "
        "когда нужны всегда свежие данные (TTL=0).\n\n"
        "**Как попробовать.** Обновите Claude Code. Memory cgroup: "
        "`export CLAUDE_CODE_TOOL_MEMORY_LIMIT=512m` в shell или .env. "
        "WebFetch TTL: `export CLAUDE_CODE_WEBFETCH_CACHE_TTL_MS=300000` (5 минут) "
        "или 0 для отключения кэша."
    ),
    tags=["новости-claude", "релиз"],
    source_url=CHANGELOG,
    source_platform="docs",
    published_at="2026-08-14",
    confidence="high",
),

dict(
    id=fid(CHANGELOG, " v2.1.229"),
    date_found=TODAY,
    title="Claude Code 2.1.229: хуки для self-hosted runners и SSE keepalive при долгом думании",
    summary=(
        "Версия 2.1.229 (12 августа) добавляет серверные хуки Claude Code для self-hosted runners "
        "и SSE keepalive pings во время длинного thinking — стриминг больше не обрывается "
        "при долгих рассуждениях агента."
    ),
    details=(
        "**Что нового.** Версия 2.1.229 от 12 августа 2026. Добавлено: (1) серверные хуки "
        "Claude Code для self-hosted runner сессий — организации задают политики хуков на "
        "уровне сервера, а не только в CLAUDE.md; (2) SSE keepalive pings в ответах gateway "
        "во время длинного thinking — соединение не разрывается при долгом рассуждении; "
        "(3) plugin marketplace с источниками типа `command` для динамического разрешения "
        "плагинов; (4) ListAgents теперь помечает отключённые Remote Control сессии как offline. "
        "Исправлены: длинные ответы частично пропадали при стриминге, RangeError на узких "
        "терминалах, Windows extended-length path вызывали крэши, Auto mode ломался у "
        "пользователей с отключённым attribution header, критические проблемы Remote Control.\n\n"
        "**Зачем вам.** Self-hosted runner хуки — для команд с собственной инфраструктурой, "
        "которые хотят централизованно управлять политиками (автоодобрение, блокировки). "
        "SSE keepalive устраняет обрывы при задачах, где агент долго думает — актуально "
        "для /ultrareview, сложных рефакторингов и агентов с reasoning. Маркетплейс плагинов "
        "с command-источниками упрощает дистрибуцию корпоративных плагинов.\n\n"
        "**Как попробовать.** Обновите Claude Code. Серверные хуки — конфигурация на уровне "
        "self-hosted runner (см. docs). SSE keepalive работает автоматически. Plugin marketplace "
        "command-источники — в /config плагинов."
    ),
    tags=["новости-claude", "релиз", "возможности"],
    source_url=CHANGELOG,
    source_platform="docs",
    published_at="2026-08-12",
    confidence="high",
),

dict(
    id=fid(CHANGELOG, " v2.1.225"),
    date_found=TODAY,
    title="Claude Code 2.1.225: лимит расходов в gateway и workspace trust при агентском запуске",
    summary=(
        "Версия 2.1.225 (8 августа) добавляет отображение лимита расходов для корпоративного "
        "gateway (cap, время сброса, сообщение оператора) и запрос доверия workspace при "
        "открытии claude agents в недоверенных директориях."
    ),
    details=(
        "**Что нового.** Версия 2.1.225 от 8 августа 2026. Добавлено: (1) gateway spend-limit "
        "support — при достижении лимита Claude Code показывает cap, время до сброса и сообщение "
        "оператора вместо непонятной ошибки; (2) workspace trust prompt в `claude agents` для "
        "недоверенных директорий — агент не запускается молча в untrusted контексте. "
        "Исправлены: временные 401-ошибки при замене long-lived OAuth-токенов, MCP OAuth на "
        "macOS падал с пачкой 401, cross-session сообщения зависали без expiry в headless "
        "сессиях, история разговора ломалась при Remote Control resume после compaction, "
        "фото из Claude-приложения теперь показываются напрямую в Remote Control.\n\n"
        "**Зачем вам.** Для команд с корпоративным gateway — наконец понятно, когда и почему "
        "кончился бюджет и когда сбросится. Workspace trust prompt снижает риск случайного "
        "запуска агента в недоверенном репозитории. Исправление MCP OAuth на macOS важно "
        "для пользователей MCP-серверов с OAuth-аутентификацией.\n\n"
        "**Как попробовать.** Обновите Claude Code. Spend-limit отображается автоматически, "
        "если оператор его настроил. Workspace trust управляется в /config."
    ),
    tags=["новости-claude", "релиз"],
    source_url=CHANGELOG,
    source_platform="docs",
    published_at="2026-08-08",
    confidence="high",
),

# ===== ЧАСТЬ B: КЕЙСЫ АВТОМАТИЗАЦИИ (позиции 5-9) =====

dict(
    id=fid(OCTAVIUS, " james finance broker"),
    date_found=TODAY,
    title="Финансовый брокер: AI-рассылка по спящей базе вернула $49 000 без рекламных расходов",
    summary=(
        "Небольшой брокер по долговым продуктам запустил AI-кампанию по 319 забытым контактам "
        "через SMS и email — вернул $49 000 дохода без единого доллара на рекламу."
    ),
    details=(
        "**Бизнес.** Финансовый брокер (долговые и консолидационные продукты), малая практика.\n\n"
        "**Процесс.** Реактивация спящей клиентской базы: 319 контактов без активности, "
        "которых вручную никто не прорабатывал из-за отсутствия ресурсов.\n\n"
        "**Было.** 319 «мёртвых» контактов в CRM — ноль дохода с них. Ручной outreach "
        "не вёлся.\n\n"
        "**Сделали.** Запустили AI-агента для персонализированных SMS и email по всем "
        "319 контактам. Агент формулировал сообщения и управлял цепочкой касаний.\n\n"
        "**Стало.** $49 000 восстановленного дохода. Рекламные расходы: $0.\n\n"
        "**Инструменты.** AI-платформа Octavius (голосовой и текстовый AI-агент "
        "для реактивации и продаж).\n\n"
        "**Как повторить.** 1) Выгрузить контакты без активности 6+ месяцев из CRM. "
        "2) Сегментировать по последнему интересу. 3) Подключить AI-агента с шаблонами "
        "под каждый сегмент. 4) Запустить SMS+email цепочку. 5) Ответивших передать "
        "менеджеру для закрытия.\n\n"
        "**Подвох.** Без проверки базы на закон о рекламных рассылках кампания может "
        "нарушить закон — SMS-отписки обязательны. Конверсия сильно зависит от свежести "
        "базы: контакты старше 3-5 лет дадут меньше отдачи. Детали стоимости платформы "
        "и длина цепочки не раскрыты."
    ),
    tags=["заявки-клиенты", "финансы-учёт", "ai", "бот"],
    source_url=OCTAVIUS,
    source_platform="blog",
    author="Octavius",
    published_at="2026-08-12",
    confidence="med",
),

dict(
    id=fid(OCTAVIUS, " justin touyz marketing agency voice ai"),
    date_found=TODAY,
    title="Маркетинговое агентство: AI-голосовой агент — выручка +27% за первый месяц",
    summary=(
        "Небольшое маркетинговое агентство подключило AI voice agent для ответа на входящие "
        "звонки в нерабочее время — выручка выросла на 27% уже в первый месяц работы."
    ),
    details=(
        "**Бизнес.** Маркетинговое агентство (Justin Touyz), небольшое.\n\n"
        "**Процесс.** Входящие звонки от потенциальных клиентов в нерабочее время уходили "
        "без ответа, лиды терялись.\n\n"
        "**Было.** Звонки вне рабочих часов оставались без ответа. Лиды, не "
        "дозвонившиеся днём, уходили к конкурентам.\n\n"
        "**Сделали.** Подключили AI voice agent для ответа на все входящие 24/7 — "
        "с квалификацией и фиксацией контактов.\n\n"
        "**Стало.** Выручка: +27% за первый месяц внедрения.\n\n"
        "**Инструменты.** AI voice agent Octavius.\n\n"
        "**Как повторить.** 1) Определить часы, когда пропускаете звонки. 2) Подключить "
        "голосовой AI к входящей линии. 3) Написать скрипт квалификации: бюджет, задача, срок. "
        "4) Настроить передачу лида в CRM. 5) Перезванивать по горячим лидам в рабочий день.\n\n"
        "**Подвох.** Цифра +27% за 1 месяц не исключает сезонный эффект. Если агентство не "
        "было готово к росту входящих, часть лидов могла потеряться на follow-up. Стоимость "
        "платформы и ROI за более длинный период не раскрыты."
    ),
    tags=["заявки-клиенты", "маркетинг-контент", "бот", "ai"],
    source_url=OCTAVIUS,
    source_platform="blog",
    author="Octavius",
    published_at="2026-08-12",
    confidence="med",
),

dict(
    id=fid(OCTAVIUS, " donna loeffler business coach receptionist"),
    date_found=TODAY,
    title="Бизнес-коуч: AI-рецепционист — продажи x2 за первый месяц",
    summary=(
        "Практик-коуч по бизнесу внедрила AI-рецепционист для квалификации входящих лидов "
        "и записи на консультации — продажи выросли вдвое за первый месяц работы."
    ),
    details=(
        "**Бизнес.** Бизнес-коуч (Donna Loeffler), индивидуальная практика.\n\n"
        "**Процесс.** Квалификация входящих лидов и запись на платные консультации — "
        "занимало личное время коуча, часть звонков оставалась без ответа.\n\n"
        "**Было.** Лиды квалифицировались вручную коучем лично. Часть потенциальных клиентов "
        "не дозванивалась или теряла интерес в ожидании ответа.\n\n"
        "**Сделали.** Подключили AI-рецепционист для автоматической квалификации и записи "
        "новых клиентов на консультации.\n\n"
        "**Стало.** Продажи: x2 за первый месяц внедрения.\n\n"
        "**Инструменты.** AI-рецепционист Octavius (голосовой AI-агент).\n\n"
        "**Как повторить.** 1) Прописать квалификационный скрипт: нужный клиент, бюджет, "
        "запрос. 2) Настроить AI на запись в календарь (Calendly или аналог). 3) AI "
        "фильтрует нецелевых лидов до контакта с коучем. 4) Горячие лиды получают "
        "автоматическое приглашение на встречу.\n\n"
        "**Подвох.** Начальный уровень продаж не раскрыт: удвоить 2 клиента в месяц "
        "и удвоить 20 — разные масштабы. Без базовых цифр сложно оценить применимость "
        "к другому бизнесу. Детали стоимости и настройки не указаны."
    ),
    tags=["заявки-клиенты", "розница-услуги", "бот", "ai"],
    source_url=OCTAVIUS,
    source_platform="blog",
    author="Octavius",
    published_at="2026-08-12",
    confidence="med",
),

]

# Build dedup set
existing_ids = set()
for fn in glob.glob(os.path.join(RADAR, "data/finds/*.json")):
    try:
        with open(fn, encoding="utf-8") as f:
            data = json.load(f)
        for fi in data:
            existing_ids.add(fi.get("id", ""))
    except Exception:
        pass

# Dedup check
new_ids = set()
deduped = []
skipped = []
for fi in FINDS:
    fid_val = fi["id"]
    if fid_val in existing_ids:
        skipped.append("ID-DUP: " + fid_val + " | " + fi["title"][:50])
    elif fid_val in new_ids:
        skipped.append("SELF-DUP: " + fid_val + " | " + fi["title"][:50])
    else:
        new_ids.add(fid_val)
        deduped.append(fi)

print("Total planned: " + str(len(FINDS)) + ", After dedup: " + str(len(deduped)) + ", Skipped: " + str(len(skipped)))
for s in skipped:
    print("  SKIP: " + s)

# Write finds JSON
finds_path = os.path.join(RADAR, "data/finds", TODAY + ".json")
with open(finds_path, "w", encoding="utf-8") as f:
    json.dump(deduped, f, ensure_ascii=False, indent=2)
print("Written: " + finds_path)

# Build digest
lines = []
lines.append("# Радар: автоматизация в малом бизнесе — дайджест за " + TODAY)
lines.append("")
lines.append("_Собрано " + str(len(deduped)) + " находок: 4 новости Claude Code + " + str(len(deduped) - 4) + " кейса автоматизации МСБ._")
lines.append("_6-я позиция в кейсах не заполнена: в окне свежести (90 дней, с 22 мая 2026) не нашлось достаточно новых кейсов с полным набором данных (бизнес + процесс + было/стало + инструменты), которые ещё не были собраны в предыдущих выпусках._")
lines.append("")
lines.append("---")
lines.append("")

for i, fi in enumerate(deduped, 1):
    lines.append("## " + str(i) + ". " + fi["title"])
    lines.append("")
    lines.append(fi.get("details", ""))
    lines.append("")
    tags_str = " `" + "` `".join(fi["tags"]) + "`"
    src = fi.get("author", fi.get("source_platform", ""))
    lines.append(tags_str + " · Источник: [" + src + "](" + fi["source_url"] + ")")
    lines.append("")
    lines.append("---")
    lines.append("")

digest_path = os.path.join(RADAR, "data/digests", TODAY + ".md")
with open(digest_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Written: " + digest_path)

print("GEN-OK finds=" + str(len(deduped)))
