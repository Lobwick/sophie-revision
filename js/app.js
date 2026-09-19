// Utilitaires partagés : chargement des données, persistance via l'API serveur, SRS, navigation.
//
// Les données mutables (progression SRS, cartes personnelles, journal) ne sont PAS stockées dans
// le navigateur : elles vivent côté serveur (fichier JSON dans un volume Docker), via /api/*.
// initData() doit être appelée une fois par page, avant tout appel à getSrsState/getCustomCards/getJournal.

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

// ---------- Data loading (contenu statique de référence, versionné avec le site) ----------

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

// Gardes connues, synchronisées côté serveur depuis le calendrier iCloud partagé.
// { updated_at, gardes: [{debut_date, debut_time, fin_date, fin_time, jour_recuperation}], enabled, error }
export async function loadGardes() {
  try {
    const res = await fetch("/api/gardes");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error("Impossible de charger les gardes synchronisées :", e);
    return { updated_at: null, gardes: [], enabled: false, error: String(e) };
  }
}

// Gardes dont la période (ou le jour de récupération) touche la semaine [debut, fin] (ISO).
export function gardesInRange(gardes, debut, fin) {
  return gardes.filter((g) => g.debut_date <= fin && g.jour_recuperation >= debut);
}

// ---------- Données mutables : cache mémoire synchronisé avec le serveur ----------

let _cache = null; // { srs: {}, customCards: [], journal: [] }
let _cachePromise = null;

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).error || "";
    } catch {
      // ignore
    }
    throw new Error(`${url} → HTTP ${res.status}${detail ? " — " + detail : ""}`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// À appeler une fois par page, avant tout getSrsState()/getCustomCards()/getJournal().
export async function initData() {
  if (_cache) return _cache;
  if (!_cachePromise) {
    _cachePromise = fetchJSON("/api/data")
      .then((d) => {
        _cache = { srs: d.srs || {}, customCards: d.customCards || [], journal: d.journal || [] };
        return _cache;
      })
      .catch((e) => {
        console.error("Impossible de charger les données depuis le serveur :", e);
        toast("Serveur de données injoignable — vérifie que le conteneur tourne");
        _cache = { srs: {}, customCards: [], journal: [] };
        return _cache;
      });
  }
  return _cachePromise;
}

function cache() {
  if (!_cache) {
    console.warn("initData() n'a pas encore été appelée : cache vide utilisé par défaut");
    _cache = { srs: {}, customCards: [], journal: [] };
  }
  return _cache;
}

// ---------- SRS (répétition espacée, SM-2 simplifié) ----------

const INTERVALS = [0, 1, 3, 7, 16];

export function getSrsState() {
  return cache().srs;
}

export function isDue(cardId, state, refDateISO) {
  const s = state[cardId];
  if (!s) return true;
  return s.due <= refDateISO;
}

// quality: 0=again 1=hard 2=good 3=easy
// Met à jour `state` en mémoire immédiatement (l'UI reste réactive) et persiste sur le serveur
// en arrière-plan ; state est censé être le même objet que celui retourné par getSrsState().
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

  fetchJSON("/api/srs", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cardId, record: s }),
  }).catch((e) => {
    console.error("Échec de sauvegarde de la progression", e);
    toast("Progression non sauvegardée (serveur injoignable)");
  });

  return s;
}

// ---------- Cartes personnelles ----------

export function getCustomCards() {
  return cache().customCards;
}

export async function addCustomCard(card) {
  const created = await fetchJSON("/api/custom-cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(card),
  });
  cache().customCards.push(created);
  return created;
}

export async function deleteCustomCard(id) {
  await fetchJSON(`/api/custom-cards/${encodeURIComponent(id)}`, { method: "DELETE" });
  const c = cache();
  c.customCards = c.customCards.filter((x) => x.id !== id);
  delete c.srs[id];
}

// ---------- Journal d'erreurs ----------

export function getJournal() {
  return cache().journal;
}

export async function addJournalEntry(text, deck) {
  const entry = await fetchJSON("/api/journal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, deck: deck || null }),
  });
  cache().journal.unshift(entry);
  return entry;
}

export async function deleteJournalEntry(id) {
  await fetchJSON(`/api/journal/${encodeURIComponent(id)}`, { method: "DELETE" });
  const c = cache();
  c.journal = c.journal.filter((e) => e.id !== id);
}

// ---------- Sauvegarde manuelle (export/import), en plus de la persistance serveur ----------

export function exportBackup() {
  const c = cache();
  const payload = {
    exported_at: new Date().toISOString(),
    srs: c.srs,
    customCards: c.customCards,
    journal: c.journal,
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

export async function importBackup(obj) {
  const saved = await fetchJSON("/api/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj),
  });
  _cache = { srs: saved.srs || {}, customCards: saved.customCards || [], journal: saved.journal || [] };
}

// ---------- Countdown / exam info ----------

// Trouve la semaine de phase_partiel.semaines qui contient la date ISO donnée (ou null).
export function findCurrentWeek(planning, iso) {
  return planning.phase_partiel.semaines.find((s) => iso >= s.debut && iso <= s.fin) || null;
}

export function examCountdownLabel(planning) {
  const iso = todayISO();
  const partiel = planning.meta.cible_immediate;
  const diffPartiel = daysBetween(iso, partiel.date);
  if (diffPartiel > 0) return `J-${diffPartiel} avant le partiel`;
  if (diffPartiel === 0) return "Jour J — partiel aujourd'hui";

  const edn = planning.meta.cible_principale;
  const estDate = edn.date_estimee_ordre_de_grandeur;
  if (estDate) {
    const diffEdn = daysBetween(iso, estDate);
    if (diffEdn > 0) return `~J-${diffEdn} avant l'EDN (estimation)`;
  }
  return "EDN — dates à confirmer";
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
