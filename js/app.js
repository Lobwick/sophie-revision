// Utilitaires partagés : chargement des données, stockage local, SRS, navigation.

const LS_KEYS = {
  srs: "sophie_srs_state_v1",
  customCards: "sophie_custom_cards_v1",
  journal: "sophie_journal_v1",
};

export function todayISO() {
  const d = new Date();
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d - tz).toISOString().slice(0, 10);
}

export function daysBetween(isoA, isoB) {
  const a = new Date(isoA + "T00:00:00");
  const b = new Date(isoB + "T00:00:00");
  return Math.round((b - a) / 86400000);
}

export function formatDateFR(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
}

export function formatDateShort(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}

// ---------- Data loading ----------

let _planningCache = null;
let _cartesCache = null;

export async function loadPlanning() {
  if (_planningCache) return _planningCache;
  const res = await fetch("data/planning-edn.json");
  _planningCache = await res.json();
  return _planningCache;
}

export async function loadCartesBase() {
  if (_cartesCache) return _cartesCache;
  const res = await fetch("data/cartes-edn.json");
  _cartesCache = await res.json();
  return _cartesCache;
}

export async function loadAllCards() {
  const base = await loadCartesBase();
  const custom = getCustomCards();
  return { decks: base.decks, cards: [...base.cards, ...custom], meta: base.meta };
}

// ---------- LocalStorage: SRS state ----------

function safeParse(raw, fallback) {
  try {
    const v = JSON.parse(raw);
    return v ?? fallback;
  } catch {
    return fallback;
  }
}

export function getSrsState() {
  return safeParse(localStorage.getItem(LS_KEYS.srs), {});
}

export function saveSrsState(state) {
  try {
    localStorage.setItem(LS_KEYS.srs, JSON.stringify(state));
  } catch (e) {
    console.error("Impossible d'enregistrer la progression", e);
  }
}

const INTERVALS = [0, 1, 3, 7, 16];

export function isDue(cardId, state, refDateISO) {
  const s = state[cardId];
  if (!s) return true;
  return s.due <= refDateISO;
}

// quality: 0=again 1=hard 2=good 3=easy
export function reviewCard(cardId, quality, state, refDateISO) {
  const prev = state[cardId] || { ease: 2.5, intervalIdx: -1, interval: 0, reps: 0, lapses: 0 };
  const s = { ...prev };
  s.reps += 1;
  if (quality === 0) {
    s.lapses += 1;
    s.intervalIdx = 0;
    s.interval = INTERVALS[0];
    s.ease = Math.max(1.3, s.ease - 0.2);
  } else {
    s.intervalIdx += 1;
    if (s.intervalIdx < INTERVALS.length) {
      s.interval = INTERVALS[s.intervalIdx];
    } else {
      s.interval = Math.max(1, Math.round(s.interval * s.ease));
    }
    if (quality === 1) s.ease = Math.max(1.3, s.ease - 0.15);
    if (quality === 3) s.ease = s.ease + 0.15;
  }
  const dueDate = new Date(refDateISO + "T00:00:00");
  dueDate.setDate(dueDate.getDate() + s.interval);
  const tz = dueDate.getTimezoneOffset() * 60000;
  s.due = new Date(dueDate - tz).toISOString().slice(0, 10);
  s.last = refDateISO;
  state[cardId] = s;
  saveSrsState(state);
  return s;
}

// ---------- LocalStorage: custom cards ----------

export function getCustomCards() {
  return safeParse(localStorage.getItem(LS_KEYS.customCards), []);
}

export function addCustomCard(card) {
  const cards = getCustomCards();
  const id = "custom-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const full = { id, srs: null, item: "", tags: [], ...card };
  cards.push(full);
  localStorage.setItem(LS_KEYS.customCards, JSON.stringify(cards));
  return full;
}

export function deleteCustomCard(id) {
  const cards = getCustomCards().filter((c) => c.id !== id);
  localStorage.setItem(LS_KEYS.customCards, JSON.stringify(cards));
}

// ---------- LocalStorage: journal d'erreurs ----------

export function getJournal() {
  return safeParse(localStorage.getItem(LS_KEYS.journal), []);
}

export function addJournalEntry(text, deck) {
  const entries = getJournal();
  const entry = { id: Date.now().toString(36), date: todayISO(), text, deck: deck || null };
  entries.unshift(entry);
  localStorage.setItem(LS_KEYS.journal, JSON.stringify(entries));
  return entry;
}

export function deleteJournalEntry(id) {
  const entries = getJournal().filter((e) => e.id !== id);
  localStorage.setItem(LS_KEYS.journal, JSON.stringify(entries));
}

// ---------- Backup export / import ----------

export function exportBackup() {
  const payload = {
    exported_at: new Date().toISOString(),
    srs: getSrsState(),
    customCards: getCustomCards(),
    journal: getJournal(),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sophie-revision-sauvegarde-${todayISO()}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function importBackup(obj) {
  if (obj.srs) localStorage.setItem(LS_KEYS.srs, JSON.stringify(obj.srs));
  if (obj.customCards) localStorage.setItem(LS_KEYS.customCards, JSON.stringify(obj.customCards));
  if (obj.journal) localStorage.setItem(LS_KEYS.journal, JSON.stringify(obj.journal));
}

// ---------- Countdown / exam info ----------

export function examCountdownLabel(planning) {
  const iso = todayISO();
  const firstExam = planning.meta.cible_principale.dates[0];
  const diff = daysBetween(iso, firstExam);
  if (diff > 0) return `J-${diff} avant l'EDN`;
  if (diff === 0) return "Jour J — 1re épreuve aujourd'hui";
  const lastExam = planning.meta.cible_principale.dates[planning.meta.cible_principale.dates.length - 1];
  if (iso <= lastExam) return "Épreuves EDN en cours";
  return "Épreuves EDN terminées";
}

// ---------- Toast ----------

export function toast(msg) {
  let el = document.getElementById("app-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "app-toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2200);
}

// ---------- Nav injection ----------

export function renderTopbar(activePage, planning) {
  const el = document.getElementById("topbar");
  if (!el) return;
  const pages = [
    { href: "index.html", label: "Accueil" },
    { href: "planning.html", label: "Planning" },
    { href: "cartes.html", label: "Cartes" },
    { href: "journal.html", label: "Journal" },
  ];
  const links = pages
    .map(
      (p) =>
        `<a href="${p.href}" class="${p.href === activePage ? "active" : ""}">${p.label}</a>`
    )
    .join("");
  const chip = planning
    ? `<span class="countdown-chip">${examCountdownLabel(planning)}</span>`
    : "";
  el.innerHTML = `<span class="brand">🩺 Sophie · EDN</span><nav>${links}</nav>${chip}`;
}
