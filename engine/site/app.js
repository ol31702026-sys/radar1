/* Radar static site — читает manifest.json + data/*.json, без сборки.
   Рейтинги и закладки хранятся в localStorage (по slug радара) и экспортируются в JSON,
   совместимый с data/feedback/ratings.json и saved.json. Серверный вариант — позже (Этап 2/4). */

const STATUS_LABEL = { new: "🆕 Новое", thinking: "🤔 В работе", done: "✅ Решено", archived: "🗄 Архив" };
const STATUS_ORDER = ["new", "thinking", "done", "archived"];

const state = {
  slug: null,
  radar: null,        // запись из manifest
  finds: [],          // находки выбранного дня
  day: null,
  activeTags: new Set(),
  platform: "",
  query: "",
  ratings: {},        // find_id -> 1..5 | -1
  saved: {},          // find_id -> {status, note, saved_at, note_updated_at}
};

/* ---------- persistence (localStorage) ---------- */
const lsKey = (kind) => `radar:${state.slug}:${kind}`;
function loadLocal() {
  try { state.ratings = JSON.parse(localStorage.getItem(lsKey("ratings"))) || {}; } catch { state.ratings = {}; }
  try { state.saved = JSON.parse(localStorage.getItem(lsKey("saved"))) || {}; } catch { state.saved = {}; }
}
function saveRatings() { localStorage.setItem(lsKey("ratings"), JSON.stringify(state.ratings)); }
function saveSaved() { localStorage.setItem(lsKey("saved"), JSON.stringify(state.saved)); }

/* ---------- data loading ---------- */
// Корень данных (manifest.json, radars/...) относительно index.html.
// Берётся из <meta name="data-root">; локально "../../", на деплое — "".
const DATA_ROOT = (document.querySelector('meta[name="data-root"]')?.content ?? "").trim();
const dataPath = (p) => DATA_ROOT + p;

async function getJSON(path) {
  const res = await fetch(dataPath(path), { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

// какой радар показать при загрузке: из localStorage, иначе первый в манифесте
const LAST_RADAR_KEY = "radar:_last_slug";

async function init() {
  let manifest;
  try {
    manifest = await getJSON("manifest.json");
  } catch (e) {
    document.getElementById("cards").innerHTML =
      `<div class="empty">Не нашёл <code>manifest.json</code>. Запусти <code>python3 engine/build_manifest.py</code> и открой сайт через локальный сервер из корня проекта.</div>`;
    return;
  }
  state.manifest = manifest;

  // селектор тем (показываем всегда; при одном радаре он просто не мешает)
  const radarSel = document.getElementById("radar-select");
  radarSel.innerHTML = manifest.radars
    .map((r) => `<option value="${r.slug}">${r.title}</option>`)
    .join("");
  radarSel.style.display = manifest.radars.length > 1 ? "" : "none";
  radarSel.addEventListener("change", () => selectRadar(radarSel.value));

  bindEvents();

  // восстановить последний выбранный радар, если он ещё есть в манифесте
  const remembered = localStorage.getItem(LAST_RADAR_KEY);
  const start = manifest.radars.find((r) => r.slug === remembered) || manifest.radars[0];
  radarSel.value = start.slug;
  await selectRadar(start.slug);
}

// Полностью переинициализирует UI под выбранный радар (вызывается при старте и смене темы).
async function selectRadar(slug) {
  const radar = state.manifest.radars.find((r) => r.slug === slug);
  if (!radar) return;
  state.radar = radar;
  state.slug = slug;
  localStorage.setItem(LAST_RADAR_KEY, slug);

  // рейтинги/закладки хранятся per-slug — перечитываем под новый радар
  loadLocal();
  // сбрасываем фильтры выбора, чтобы теги/платформы прошлой темы не зависали
  state.activeTags = new Set();
  state.platform = "";
  state.query = "";

  document.getElementById("radar-title").textContent = radar.title;
  document.getElementById("radar-desc").textContent = radar.description || "";
  const searchEl = document.getElementById("search");
  if (searchEl) searchEl.value = "";

  // дни
  const daySel = document.getElementById("day-select");
  daySel.innerHTML = (radar.days || [])
    .map((d) => `<option value="${d.date}">${d.date} · ${d.count} находок</option>`)
    .join("");
  // платформы заполняются динамически из реальных находок дня (см. updatePlatformOptions)
  // теги
  document.getElementById("tagbar").innerHTML = (radar.taxonomy || [])
    .map((t) => `<button class="tagchip" data-tag="${t}">${t}</button>`)
    .join("");

  await loadDay(radar.days[0]?.date);
  await loadAllFindsCache();   // нужно ДО доски: отложить можно находку любого дня
  renderThinkBoard();
  updateThinkCount();
}

/* Загружает находки ВСЕХ дней в кэш по id — чтобы доска «На обдумывание»
   находила отложенную находку из любого дня (заголовок + ссылка на оригинал). */
async function loadAllFindsCache() {
  const cache = {};
  await Promise.all((state.radar.days || []).map(async (d) => {
    try {
      const finds = await getJSON(`radars/${state.slug}/data/finds/${d.date}.json`);
      for (const f of finds) cache[f.id] = f;
    } catch { /* день мог не загрузиться — пропускаем */ }
  }));
  state._allFindsCache = cache;
}

async function loadDay(date) {
  if (!date) return;
  state.day = date;
  state.finds = await getJSON(`radars/${state.slug}/data/finds/${date}.json`);
  updatePlatformOptions();
  renderFeed();
}

// красивые подписи платформ
const PLATFORM_LABEL = {
  youtube: "▶ YouTube", reddit: "Reddit", x: "X", hn: "Hacker News",
  blog: "Блоги", github: "GitHub", docs: "Документация", other: "Прочее",
};
// список платформ строится из РЕАЛЬНЫХ находок дня (а не из статичного конфига)
function updatePlatformOptions() {
  const present = [...new Set(state.finds.map((f) => f.source_platform))].sort();
  const sel = document.getElementById("platform-select");
  const cur = state.platform;
  sel.innerHTML = `<option value="">Все платформы</option>` +
    present.map((p) => `<option value="${p}">${PLATFORM_LABEL[p] || p}</option>`).join("");
  // сохранить выбор, если он ещё доступен; иначе сбросить на «все»
  if (cur && present.includes(cur)) sel.value = cur;
  else { state.platform = ""; sel.value = ""; }
}

/* ---------- feed ---------- */
function filteredFinds() {
  const q = state.query.trim().toLowerCase();
  return state.finds.filter((f) => {
    if (state.platform && f.source_platform !== state.platform) return false;
    if (state.activeTags.size && !f.tags.some((t) => state.activeTags.has(t))) return false;
    if (q && !(`${f.title} ${f.summary} ${f.details || ""}`.toLowerCase().includes(q))) return false;
    return true;
  });
}

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// дата новости: показываем published_at; если нет — помечаем как дату находки
function dateLabel(f) {
  if (f.published_at) return `🗓 ${esc(f.published_at)}`;
  return `🗓 ${esc(f.date_found)} <span class="muted">(найдено)</span>`;
}

function starHtml(id) {
  const cur = state.ratings[id] || 0;
  let s = `<span class="stars" data-id="${id}">`;
  for (let i = 1; i <= 5; i++) s += `<span class="star ${cur >= i ? "on" : ""}" data-v="${i}">★</span>`;
  s += `</span>`;
  return s;
}

// Вытащить блок «Зачем» из details (markdown: «**Зачем.** ... » до следующего «**»)
function whyFromDetails(details) {
  if (!details) return "";
  const m = details.match(/\*\*Зачем\.\*\*\s*([\s\S]*?)(?:\n\s*\*\*|$)/);
  return m ? m[1].trim() : "";
}

function cardHtml(f) {
  const isSaved = !!state.saved[f.id];
  const why = whyFromDetails(f.details);
  return `<article class="card" data-id="${f.id}">
    <h3 data-open="${f.id}">${esc(f.title)}</h3>
    <p class="anons">${esc(f.summary)}</p>
    ${why ? `<p class="why"><strong>Зачем.</strong> ${esc(why)}</p>` : ""}
    <div class="meta">
      <span class="date" title="дата публикации">${dateLabel(f)}</span>
      ${f.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
      <span class="platform">${esc(f.source_platform)}${f.author ? " · " + esc(f.author) : ""}</span>
      <span class="src"><a href="${esc(f.source_url)}" target="_blank" rel="noopener">↗ оригинал</a></span>
    </div>
    <div class="card-actions">
      ${starHtml(f.id)}
      <button class="btn-save ${isSaved ? "on" : ""}" data-save="${f.id}">${isSaved ? "⚑ Отложено" : "⚑ Отложить"}</button>
      <span class="more"><button class="btn-more" data-open="${f.id}">подробнее →</button></span>
    </div>
  </article>`;
}

function renderFeed() {
  const list = filteredFinds();
  document.getElementById("feed-summary").textContent =
    `День ${state.day}: показано ${list.length} из ${state.finds.length}`;
  document.getElementById("cards").innerHTML =
    list.length ? list.map(cardHtml).join("") : `<div class="empty">Ничего не найдено по фильтрам.</div>`;
}

/* ---------- drill-down modal ---------- */
function openModal(id) {
  const f = state.finds.find((x) => x.id === id);
  if (!f) return;
  const isVideo = f.source_platform === "youtube";
  document.getElementById("modal-body").innerHTML = `
    <h2>${esc(f.title)}</h2>
    <p class="muted">${dateLabel(f)} · ${f.tags.map((t) => `#${esc(t)}`).join(" ")} · ${esc(f.source_platform)}${f.author ? " · " + esc(f.author) : ""}</p>
    <p><strong>Аннотация (рус).</strong> ${esc(f.summary)}</p>
    <div class="rasshifrovka">${esc(f.details || "(расшифровка не заполнена)")}</div>
    <div class="fulltext-bar">
      <button id="fulltext-btn" class="btn-fulltext" data-ft="${f.id}">📄 ${isVideo ? "Весь текст (транскрипция, рус)" : "Весь текст (перевод, рус)"}</button>
      <a class="orig-link" href="${esc(f.source_url)}" target="_blank" rel="noopener">↗ Первоисточник</a>
    </div>
    <div id="fulltext-body" class="fulltext-body hidden"></div>
    <div class="card-actions">${starHtml(f.id)}
      <button class="btn-save ${state.saved[f.id] ? "on" : ""}" data-save="${f.id}">${state.saved[f.id] ? "⚑ Отложено" : "⚑ Отложить"}</button>
    </div>`;
  document.getElementById("modal").classList.remove("hidden");
}

// «Весь текст»: подгрузить заранее подготовленный перевод data/fulltext/<id>.ru.md
async function loadFulltext(id) {
  const box = document.getElementById("fulltext-body");
  if (!box) return;
  box.classList.remove("hidden");
  // повторный клик — свернуть
  if (box.dataset.loaded === id) { box.classList.toggle("collapsed"); return; }
  box.innerHTML = `<p class="muted">Загружаю полный текст…</p>`;
  try {
    const res = await fetch(dataPath(`radars/${state.slug}/data/fulltext/${id}.ru.md`), { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    const md = await res.text();
    box.innerHTML = `<div class="ft-content">${mdToHtml(md)}</div>`;
    box.dataset.loaded = id;
  } catch {
    box.innerHTML = `<p class="muted">Полный текст ещё не подготовлен. Запусти перевод:</p>
      <pre class="ft-cmd">/translate ${state.slug} ${id}</pre>
      <p class="muted">(скилл скачает статью или субтитры видео, переведёт на русский и сохранит — после этого «Весь текст» покажет перевод).</p>`;
  }
}

// очень лёгкий markdown→html (заголовки, абзацы, **жирный**, списки) — без зависимостей
function mdToHtml(md) {
  const lines = md.split("\n");
  let html = "", inList = false;
  for (let raw of lines) {
    const l = raw.trimEnd();
    if (/^#{1,6}\s/.test(l)) {
      if (inList) { html += "</ul>"; inList = false; }
      const lvl = l.match(/^#+/)[0].length;
      html += `<h${lvl}>${esc(l.replace(/^#+\s/, ""))}</h${lvl}>`;
    } else if (/^[-*]\s/.test(l)) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${inline(esc(l.replace(/^[-*]\s/, "")))}</li>`;
    } else if (l === "") {
      if (inList) { html += "</ul>"; inList = false; }
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p>${inline(esc(l))}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
  function inline(s) { return s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>"); }
}

function closeModal() { document.getElementById("modal").classList.add("hidden"); }

/* ---------- ratings & saved actions ---------- */
function setRating(id, v) {
  state.ratings[id] = state.ratings[id] === v ? 0 : v; // повторный клик по той же звезде = снять
  if (state.ratings[id] === 0) delete state.ratings[id];
  saveRatings();
}
function toggleSave(id) {
  if (state.saved[id]) { delete state.saved[id]; }
  else { state.saved[id] = { status: "new", note: "", saved_at: today(), note_updated_at: null }; }
  saveSaved();
  renderThinkBoard();
  updateThinkCount();
}
function today() { return new Date().toISOString().slice(0, 10); }

/* ---------- think board ---------- */
function findById(id) {
  return state.finds.find((x) => x.id === id) || state._allFindsCache?.[id] || null;
}
function updateThinkCount() {
  const n = Object.keys(state.saved).filter((id) => state.saved[id].status !== "archived").length;
  document.getElementById("think-count").textContent = n;
}
function renderThinkBoard() {
  const ids = Object.keys(state.saved);
  const board = document.getElementById("think-board");
  document.getElementById("think-summary").textContent =
    `Отложено: ${ids.length}` + (ids.length ? ` (активных: ${ids.filter((i) => state.saved[i].status !== "archived").length})` : "");
  if (!ids.length) { board.innerHTML = `<div class="empty">Пока ничего не отложено. На карточке находки нажми «⚑ Отложить».</div>`; return; }

  // группировка по теме = первый тег находки (находку ищем среди текущего дня; иначе показываем по id)
  const byTheme = {};
  for (const id of ids) {
    const f = findById(id);
    const theme = f ? (f.tags[0] || "(без темы)") : "(другой день)";
    (byTheme[theme] ||= []).push({ id, f });
  }
  board.innerHTML = Object.keys(byTheme).sort().map((theme) => {
    const items = byTheme[theme].sort((a, b) =>
      STATUS_ORDER.indexOf(state.saved[a.id].status) - STATUS_ORDER.indexOf(state.saved[b.id].status));
    return `<section class="think-theme"><h2>Тема: ${esc(theme)}</h2>${items.map(thinkItemHtml).join("")}</section>`;
  }).join("");
}
function thinkItemHtml({ id, f }) {
  const s = state.saved[id];
  const title = f ? f.title : `(находка ${id} — открой её день в Ленте)`;
  const src = f ? `<a href="${esc(f.source_url)}" target="_blank" rel="noopener">↗ оригинал</a>` : "";
  return `<div class="think-item" data-id="${id}">
    <h4>${STATUS_LABEL[s.status]} — ${esc(title)}</h4>
    <div class="status-row">
      <label>Статус:
        <select data-status="${id}">
          ${STATUS_ORDER.map((st) => `<option value="${st}" ${st === s.status ? "selected" : ""}>${STATUS_LABEL[st]}</option>`).join("")}
        </select>
      </label>
      ${src} · <span class="muted">отложено ${s.saved_at}</span>
      <button class="btn-save on" data-save="${id}" title="Убрать из обдумывания">убрать</button>
    </div>
    <textarea data-note="${id}" placeholder="Личная заметка/мысль…">${esc(s.note || "")}</textarea>
    <span class="note-saved hidden" data-note-saved="${id}">сохранено ✓</span>
  </div>`;
}

/* ---------- export ---------- */
function exportData() {
  const ratings = { _format: "Map find.id -> rating (1..5 | -1).", ratings: state.ratings, updated_at: today() };
  const items = Object.entries(state.saved).map(([find_id, v]) => ({ find_id, ...v }));
  const saved = { _format: "Закладки 'На обдумывание'.", items, updated_at: today() };
  download(`${state.slug}.ratings.json`, ratings);
  download(`${state.slug}.saved.json`, saved);
}
function download(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------- events ---------- */
function bindEvents() {
  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => switchView(t.dataset.view)));

  document.getElementById("day-select").addEventListener("change", (e) => loadDay(e.target.value));
  document.getElementById("platform-select").addEventListener("change", (e) => { state.platform = e.target.value; renderFeed(); });
  document.getElementById("search").addEventListener("input", (e) => { state.query = e.target.value; renderFeed(); });
  document.getElementById("reset-filters").addEventListener("click", () => {
    state.activeTags.clear(); state.platform = ""; state.query = "";
    document.getElementById("platform-select").value = "";
    document.getElementById("search").value = "";
    document.querySelectorAll(".tagchip.on").forEach((c) => c.classList.remove("on"));
    renderFeed();
  });
  document.getElementById("tagbar").addEventListener("click", (e) => {
    const chip = e.target.closest(".tagchip"); if (!chip) return;
    const tag = chip.dataset.tag;
    if (state.activeTags.has(tag)) { state.activeTags.delete(tag); chip.classList.remove("on"); }
    else { state.activeTags.add(tag); chip.classList.add("on"); }
    renderFeed();
  });

  // делегирование: клики по карточкам/модалке (звёзды, отложить, открыть)
  document.body.addEventListener("click", (e) => {
    const star = e.target.closest(".star");
    if (star) { const wrap = star.closest(".stars"); setRating(wrap.dataset.id, +star.dataset.v); refreshStars(wrap.dataset.id); return; }
    const save = e.target.closest("[data-save]");
    if (save) { toggleSave(save.dataset.save); refreshSaveButtons(save.dataset.save); return; }
    const ft = e.target.closest("[data-ft]");
    if (ft) { loadFulltext(ft.dataset.ft); return; }
    const open = e.target.closest("[data-open]");
    if (open) { openModal(open.dataset.open); return; }
  });
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

  // think board: статус + заметка
  document.getElementById("think-board").addEventListener("change", (e) => {
    const st = e.target.closest("[data-status]");
    if (st) { state.saved[st.dataset.status].status = st.value; saveSaved(); renderThinkBoard(); updateThinkCount(); }
  });
  document.getElementById("think-board").addEventListener("input", (e) => {
    const ta = e.target.closest("[data-note]");
    if (ta) {
      const id = ta.dataset.note;
      state.saved[id].note = ta.value;
      state.saved[id].note_updated_at = today();
      saveSaved();
      const tag = document.querySelector(`[data-note-saved="${id}"]`);
      if (tag) { tag.classList.remove("hidden"); clearTimeout(tag._t); tag._t = setTimeout(() => tag.classList.add("hidden"), 1200); }
    }
  });

  document.getElementById("export-btn").addEventListener("click", exportData);
}

function refreshStars(id) {
  document.querySelectorAll(`.stars[data-id="${id}"]`).forEach((wrap) => {
    const cur = state.ratings[id] || 0;
    wrap.querySelectorAll(".star").forEach((s) => s.classList.toggle("on", +s.dataset.v <= cur));
  });
}
function refreshSaveButtons(id) {
  const on = !!state.saved[id];
  document.querySelectorAll(`[data-save="${id}"]`).forEach((b) => {
    if (b.closest(".think-item")) return; // в доске кнопка «убрать» — её перерисует renderThinkBoard
    b.classList.toggle("on", on);
    b.textContent = on ? "⚑ Отложено" : "⚑ Отложить";
  });
}

function switchView(view) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  document.getElementById("view-feed").classList.toggle("hidden", view !== "feed");
  document.getElementById("view-think").classList.toggle("hidden", view !== "think");
  if (view === "think") renderThinkBoard();
}

init();
