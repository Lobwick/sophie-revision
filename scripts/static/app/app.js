// Tableau de bord coach internat. Aucun innerHTML : tout le texte passe par textContent (le contenu des cours et des notes n'est jamais interprété comme du HTML).
const $ = (s, r = document) => r.querySelector(s);
const MAIN = $("#main");

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || (v === false && !k.startsWith("aria-"))) continue;
    if (v === false) { el.setAttribute(k, "false"); continue; }
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, typeof v === "boolean" ? (k.startsWith("aria-") ? "true" : "") : v);
  }
  const add = (x) => { if (x == null || x === false) return; if (Array.isArray(x)) x.forEach(add); else el.append(x instanceof Node ? x : document.createTextNode(String(x))); };
  kids.forEach(add);
  return el;
}
const svgEl = (tag, attrs) => { const e = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v); return e; };
const safeHref = (u) => (/^\/pdf\/[a-z0-9-]+(\?page=\d+)?$/.test(u) || /^https:\/\//.test(u)) ? u : "#";
const pdfLink = (slug, page, text) => h("a", { href: safeHref(`/pdf/${slug}${page ? `?page=${page}` : ""}`), target: "_blank", rel: "noopener" }, text);

let VER = null;
async function syncVersion() { try { VER = (await (await fetch("/api/version", { credentials: "same-origin" })).json()).version; } catch (_) {} }

async function api(path, opts = {}) {
  const o = { headers: { "Accept": "application/json" }, credentials: "same-origin", ...opts };
  if (opts.body !== undefined) { o.method = opts.method || "POST"; o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opts.body); }
  if (o.method && o.method !== "GET") o.headers["X-Requested-With"] = "edn";
  const r = await fetch(path, o);
  if (r.status === 401) { location.href = "/login?next=/"; throw new Error("session expirée"); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `erreur ${r.status}`);
  if (o.method && o.method !== "GET") await syncVersion();   // nos propres écritures ne déclenchent pas de rechargement
  return j;
}
function toast(msg, err) { const t = h("div", { class: "toast" + (err ? " err" : ""), role: "status" }, msg); document.body.append(t); setTimeout(() => t.remove(), 3200); }
const fdate = (d) => new Date(d + "T12:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
const fdatel = (d) => new Date(d + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const plural = (n, s, p) => `${n} ${n > 1 ? (p || s + "s") : s}`;

function highlight(text, q) {
  const words = (q || "").split(/\s+/).filter((w) => w.length > 2).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return [text];
  const re = new RegExp(`(${words.join("|")})`, "gi");
  return text.split(re).map((part, i) => (i % 2 ? h("mark", {}, part) : part));
}

function bars(data, key, label, { w = 560, hgt = 90 } = {}) {
  const max = Math.max(1, ...data.map((d) => d[key]));
  const bw = w / data.length;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${hgt + 16}`, class: "chart", role: "img", "aria-label": label });
  data.forEach((d, i) => {
    const bh = d[key] ? Math.max(3, (d[key] / max) * hgt) : 2;
    const r = svgEl("rect", { x: i * bw + 1, y: hgt - bh, width: Math.max(1, bw - 2), height: bh, class: d[key] ? "b" : "b0", rx: 2 });
    const t = svgEl("title"); t.textContent = `${d.date ? fdate(d.date) : "J+" + d.jour} : ${d[key]}`; r.append(t); svg.append(r);
  });
  const first = svgEl("text", { x: 0, y: hgt + 12 }); first.textContent = data[0].date ? fdate(data[0].date) : "aujourd'hui";
  const last = svgEl("text", { x: w, y: hgt + 12, "text-anchor": "end" }); last.textContent = data.at(-1).date ? fdate(data.at(-1).date) : `J+${data.at(-1).jour}`;
  svg.append(first, last);
  return svg;
}

/* ------------------------------------------------------------------ navigation */
const SECTIONS = [["", "Aujourd'hui"], ["avancement", "Avancement"], ["cours", "Cours"], ["cartes", "Cartes"], ["examens", "Examens"], ["planning", "Planning"], ["erreurs", "Erreurs"]];
function renderNav(cur) {
  $("#nav").replaceChildren(...SECTIONS.map(([k, l]) => h("a", { href: `#/${k}`, "aria-current": k === cur ? "page" : null }, l)));
}
function parseHash() {
  const [p, qs] = location.hash.replace(/^#\/?/, "").split("?");
  return { view: p || "", params: Object.fromEntries(new URLSearchParams(qs || "")) };
}
const setHash = (view, params) => { const qs = new URLSearchParams(Object.entries(params || {}).filter(([, v]) => v)).toString(); location.hash = `#/${view}${qs ? "?" + qs : ""}`; };
let S = null; // résumé partagé

async function loadSummary() {
  S = await api("/api/summary");
  $("#countdowns").replaceChildren(...S.echeances.slice(0, 3).map((e) => h("span", { class: "cd" + (e.estime ? " est" : ""), title: (e.note || "") + " " + fdatel(e.date) }, e.court, " ", h("b", {}, e.jours >= 0 ? `J-${e.jours}` : `J+${-e.jours}`))));
}
const deckName = (k) => (S?.paquets.find((p) => p.cle === k) || {}).nom || k;

const NIVEAU = { fort: ["Point fort", "ok"], faible: ["Point faible", "bad"], moyen: ["Moyen", "warn"], a_confirmer: ["À confirmer", ""] };
const TEND = { hausse: " ↗", baisse: " ↘", stable: " →" };
function niveauBadge(n) { const [l, k] = NIVEAU[n] || ["", ""]; return h("span", { class: "badge " + k }, l); }
function quizBlock(Q, { full } = {}) {
  if (!Q.total_sessions) return h("p", { class: "muted" }, "Aucun quiz enregistré. Demande « /quiz cardiologie » à ton coach : le score est enregistré ici à la fin.");
  return [
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Spécialité"), h("th", {}, "Score"), h("th", {}, "Quiz"), h("th", {}, "Niveau"))),
      h("tbody", {}, Q.specialites.map((r) => h("tr", {}, h("td", {}, r.nom), h("td", {}, h("b", {}, `${r.pct} %`), (r.tendance && TEND[r.tendance]) || "", h("span", { class: "small faint" }, ` (${r.points}/${r.max})`)),
        h("td", {}, r.sessions), h("td", {}, niveauBadge(r.niveau)))))),
    h("p", { class: "small faint" }, Q.regle),
    full && Q.sujets_a_retravailler.length ? [h("h3", { style: "margin-top:14px" }, "Sujets à retravailler (< 60 %)"), h("ul", { class: "list" }, Q.sujets_a_retravailler.map((x) => h("li", { class: "small" }, h("b", {}, x.sujet), ` — ${x.pct} % sur ${plural(x.n, "quiz", "quiz")}`)))] : null,
    full && Q.recents.length ? [h("h3", { style: "margin-top:14px" }, "Derniers quiz"), h("table", {}, h("tbody", {}, Q.recents.map((s) => h("tr", {}, h("td", {}, fdate(s.date)), h("td", {}, s.sujet), h("td", {}, s.format), h("td", {}, `${s.points}/${s.max}`), h("td", {}, `${s.pct} %`), h("td", {}, s.minutes ? `${s.minutes} min` : "")))))] : null,
  ];
}

/* ------------------------------------------------------------------ Aujourd'hui */
async function viewToday() {
  const w = S.semaine, c = S.cartes, g = S.gardes;
  const next = (g.gardes || []).filter((x) => x.debut_date >= S.aujourd_hui).slice(0, 4);
  const main = [
    h("h1", {}, "Aujourd'hui"), h("p", { class: "sub" }, fdatel(S.aujourd_hui)),
    h("div", { class: "grid" },
      h("section", { class: "card accent" },
        h("h2", {}, w ? `Semaine ${w.s} sur 22 — ${w.matiere}` : "Hors des 22 semaines du partiel"),
        w ? [h("p", {}, w.sujet), h("p", { class: "small muted" }, `${fdate(w.debut)} → ${fdate(w.fin)} · bloc EDN transversal : `, h("b", {}, deckName(w.edn_transversal))), w.vacances && h("p", {}, h("span", { class: "badge warn" }, "Vacances")), w.note && h("p", { class: "small" }, w.note)]
          : h("p", { class: "muted" }, "Le planning du partiel court du 21/09/2026 au 15/02/2027. Voir l'onglet Planning pour la suite."),
        h("p", { class: "small faint" }, S.partiel_regle.regle_gardes)),
      h("section", { class: "card" }, h("h2", {}, "Cartes"),
        h("div", { class: "row between" }, h("div", {}, h("div", { class: "big" }, c.dues), h("div", { class: "muted small" }, plural(c.dues, "carte due", "cartes dues"))),
          h("div", {}, h("div", { class: "big" }, c.nouvelles), h("div", { class: "muted small" }, plural(c.nouvelles, "nouvelle"))),
          h("div", {}, h("div", { class: "big" }, c.mures), h("div", { class: "muted small" }, "mûres (≥ 21 j)"))),
        h("p", {}, h("a", { class: "btn", href: "#/cartes?mode=reviser" }, c.dues + c.nouvelles ? "Réviser maintenant" : "Parcourir les cartes"))),
      h("section", { class: "card" }, h("h2", {}, "Activité — 28 jours"), bars(S.activite, "n", "Exercices par jour"),
        h("p", { class: "small muted" }, `${S.progression.par_type.reduce((a, t) => a + t.n, 0)} exercices sur 14 jours · ${S.progression.par_type.reduce((a, t) => a + t.minutes, 0)} min notées`)),
      h("section", { class: "card" }, h("h2", {}, "Quiz — forts et faibles"),
        S.quiz.total_sessions ? [S.quiz.faibles.length ? h("p", {}, h("b", {}, "À travailler : "), S.quiz.faibles.slice(0, 3).map((r) => `${r.nom} (${r.pct} %)`).join(", ")) : h("p", { class: "muted small" }, "Aucun point faible confirmé."),
          S.quiz.forts.length ? h("p", {}, h("b", {}, "Solide : "), S.quiz.forts.slice(0, 3).map((r) => `${r.nom} (${r.pct} %)`).join(", ")) : null,
          h("p", { class: "small" }, h("a", { href: "#/avancement" }, "Voir le détail"))] : h("p", { class: "muted small" }, "Aucun quiz pour l'instant : lance « /quiz » avec ton coach.")),
      h("section", { class: "card" }, h("h2", {}, "Gardes à venir"),
        !g.enabled ? h("p", { class: "muted small" }, "Calendrier non relié (variable EDN_CALENDAR_ICS_URL).") :
          g.error ? h("p", { class: "small", style: "color:var(--bad)" }, g.error) :
          next.length ? h("ul", { class: "list" }, next.map((x) => h("li", {}, h("b", {}, fdate(x.debut_date)), " — lendemain allégé le ", fdate(x.jour_recuperation)))) : h("p", { class: "muted" }, "Aucune garde connue."))),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Avancement par spécialité"), paquetsTable(S.paquets)),
  ];
  MAIN.replaceChildren(...main);
}
function paquetsTable(ps) {
  return h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Paquet"), h("th", {}, "Progression"), h("th", {}, "Mûres / vues / total"), h("th", {}, "Dues"), h("th", {}, "Quiz"))),
    h("tbody", {}, ps.map((p) => h("tr", {}, h("td", {}, h("span", { class: "dot", style: `background:${p.couleur}` }), " ", p.nom),
      h("td", { style: "min-width:120px" }, h("div", { class: "bar", role: "img", "aria-label": `${p.mures} mûres, ${p.vues} vues sur ${p.total}` }, h("i", { class: "m", style: `width:${pct(p.mures, p.total)}%` }), h("i", { class: "v", style: `width:${pct(p.vues - p.mures, p.total)}%` }))),
      h("td", {}, `${p.mures} / ${p.vues} / ${p.total}`), h("td", {}, p.dues || "—"),
      h("td", {}, p.quiz ? [h("b", {}, `${p.quiz.pct} %`), " ", niveauBadge(p.quiz.niveau)] : h("span", { class: "faint" }, "—"))))));
}

/* ------------------------------------------------------------------ Avancement */
async function viewProgress(params) {
  const days = [14, 30, 90].includes(+params.days) ? +params.days : 30;
  const d = await api(`/api/progress?days=${days}`);
  const p = d.progression;
  MAIN.replaceChildren(
    h("div", { class: "row between" }, h("h1", {}, "Avancement"),
      h("div", { class: "chips" }, [14, 30, 90].map((n) => h("button", { class: "chip", "aria-pressed": n === days, onclick: () => setHash("avancement", { days: n }) }, `${n} jours`)))),
    h("div", { class: "grid" },
      h("section", { class: "card" }, h("h2", {}, "Exercices par jour"), bars(d.activite, "n", "Exercices par jour")),
      h("section", { class: "card" }, h("h2", {}, "Révisions à venir (15 jours)"), bars(d.a_venir, "n", "Cartes à réviser par jour"),
        h("p", { class: "small muted" }, `${p.cartes} éléments suivis · ${p.a_reviser_aujourd_hui} à réviser aujourd'hui`)),
      h("section", { class: "card" }, h("h2", {}, "Par type d'exercice"),
        p.par_type.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Type"), h("th", {}, "N"), h("th", {}, "Qualité moy. /5"), h("th", {}, "Min."))),
          h("tbody", {}, p.par_type.map((t) => h("tr", {}, h("td", {}, t.kind), h("td", {}, t.n), h("td", {}, t.moy), h("td", {}, t.minutes))))) : h("p", { class: "muted" }, "Aucun exercice enregistré sur la période.")),
      h("section", { class: "card" }, h("h2", {}, "Points faibles"),
        p.plus_faibles.length ? h("ul", { class: "list" }, p.plus_faibles.map((f) => h("li", {}, h("b", {}, f.category), ` — qualité moyenne ${f.moy}/5 sur ${f.n} exercices`))) : h("p", { class: "muted" }, "Aucune spécialité sous 3,5/5 de qualité moyenne (2 exercices minimum par spécialité).")),
    ),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Quiz — points forts et faibles"), quizBlock(d.quiz, { full: true })),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Cartes par paquet"), paquetsTable(d.paquets)),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Derniers exercices"),
      d.recents.length ? h("table", {}, h("tbody", {}, d.recents.map((r) => h("tr", {}, h("td", {}, fdate(r.at)), h("td", {}, r.kind), h("td", {}, r.item), h("td", {}, `q=${r.quality}`))))) : h("p", { class: "muted" }, "Rien pour l'instant.")),
    h("p", { class: "small muted" }, "Toutes les données sont des fichiers Markdown versionnés : ", h("a", { href: "/api/export", download: "suivi-revisions.json" }, "exporter une sauvegarde (JSON)"), ".")
  );
}

/* ------------------------------------------------------------------ Cours */
let FAC = null;
async function viewCours(params) {
  FAC = FAC || await api("/api/cours/facets");
  const q = params.q || "", theme = params.theme || "", cat = params.category || "";
  const go = (patch) => setHash("cours", { q, theme, category: cat, ...patch, offset: "" });
  const form = h("form", { class: "row", role: "search", onsubmit: (e) => { e.preventDefault(); go({ q: $("#q").value.trim() }); } },
    h("input", { id: "q", type: "search", value: q, placeholder: "Rechercher dans les 931 cours (ex. ponction lombaire, glaucome aigu)", class: "grow", "aria-label": "Rechercher dans les cours", style: "min-width:220px" }),
    h("button", { class: "btn" }, "Chercher"));
  const themeChips = h("div", { class: "chips", role: "group", "aria-label": "Thème" },
    h("button", { class: "chip", "aria-pressed": !theme && !cat, onclick: () => go({ theme: "", category: "" }) }, "Tout"),
    FAC.themes.map((t) => h("button", { class: "chip", "aria-pressed": theme === t.cle && !cat, onclick: () => go({ theme: t.cle, category: "" }) }, `${t.nom} · ${t.docs}`)));
  const catSel = h("select", { "aria-label": "Spécialité", onchange: (e) => go({ category: e.target.value, theme: "" }) },
    h("option", { value: "" }, "Toutes les spécialités"),
    FAC.specialites.map((s) => h("option", { value: s.category, ...(s.category === cat ? { selected: true } : {}) }, `${s.category} (${s.docs})`)));
  const out = h("div", {});
  MAIN.replaceChildren(h("h1", {}, "Explorer les cours"), h("p", { class: "sub" }, "Recherche plein texte dans les PDF, texte des images compris. Chaque résultat ouvre le PDF à la bonne page."),
    form, h("div", { class: "row", style: "margin:10px 0" }, themeChips, catSel), out);
  const qs = new URLSearchParams({ ...(theme && { theme }), ...(cat && { category: cat }) });
  if (q) {
    out.append(h("p", { class: "muted" }, "Recherche…"));
    const r = await api(`/api/cours/search?q=${encodeURIComponent(q)}&${qs}`);
    out.replaceChildren(h("p", { class: "muted small" }, `${plural(r.resultats.length, "résultat")} pour « ${q} »`),
      r.resultats.length ? h("ul", { class: "list" }, r.resultats.map((x) => h("li", { class: "hit" },
        h("h3", {}, pdfLink(x.slug, x.page, `${x.title} — p.${x.page}`)),
        h("div", { class: "row small muted" }, h("span", { class: "badge" }, x.category), x.sdd && h("span", { class: "badge" }, `SdD ${x.sdd}`), x.via && h("span", { class: "faint" }, x.via)),
        h("p", { class: "small" }, highlight(x.extrait, q))))) : h("p", { class: "empty" }, "Aucun résultat. Essaie un synonyme ou un terme médical plus précis (ex. « prééclampsie » plutôt que « tension élevée enceinte »)."));
  } else {
    const r = await api(`/api/cours/docs?${qs}`);
    out.replaceChildren(h("p", { class: "muted small" }, `${r.total} documents${r.total > r.docs.length ? ` (${r.docs.length} affichés — précise un thème ou une spécialité)` : ""}`),
      h("ul", { class: "list" }, r.docs.map((d) => h("li", { class: "hit" }, h("div", { class: "row between" },
        h("div", {}, h("h3", {}, pdfLink(d.slug, null, d.title)), h("div", { class: "small muted" }, d.category, d.sdd ? ` · SdD ${d.sdd}` : "", ` · ${d.n_pages} p.`)),
        d.quality !== "ok" ? h("span", { class: "badge warn", title: "Peu de texte exploitable : lire le PDF" }, "texte partiel") : null)))));
  }
}

/* ------------------------------------------------------------------ Cartes */
const STATUT = { corrigee: ["Corrigée après vérification", "warn"], completee: ["Complétée après vérification", "warn"], confirmee_cours: ["Confirmée par le cours", "ok"], relue: ["Relue — à recouper avec le cours", ""], perso: ["Ma carte", ""], modifiee: ["Modifiée par toi", "warn"] };
let SES = null;
function verifBlock(c) {
  const v = c.verification || {}, [label, kind] = STATUT[v.statut] || ["", ""];
  const srcs = [...(v.sources_cours || []).map((s) => pdfLink(s.slug, s.page, `${s.titre}, p.${s.page}`)), ...(v.sources_web || []).map((s) => h("a", { href: safeHref(s.url), target: "_blank", rel: "noopener" }, `${s.titre} (${s.annee})`))];
  const mdLink = (t) => { const m = /^\[(.+?)\]\((\S+?)\)$/.exec(t); return m ? h("a", { href: safeHref(m[2]), target: "_blank", rel: "noopener" }, m[1]) : t; };
  (v.sources || []).forEach((t) => srcs.push(mdLink(t)));
  const near = !srcs.length && v.page_proche ? [pdfLink(v.page_proche.slug, v.page_proche.page, `${v.page_proche.titre}, p.${v.page_proche.page}`), h("span", { class: "faint" }, ` (page la plus proche, concordance ${v.page_proche.concordance})`)] : null;
  return h("div", { class: "small", style: "margin-top:10px" }, label && h("span", { class: "badge " + kind }, label),
    v.motif && h("p", {}, h("b", {}, "Pourquoi : "), v.motif), v.remarque && h("p", { class: "muted" }, v.remarque),
    v.avant && h("details", {}, h("summary", {}, "Ancienne version"), h("p", { class: "muted" }, v.avant.answer)),
    (srcs.length || near) && h("p", {}, h("b", {}, "Dans le cours : "), srcs.flatMap((s, i) => (i ? [" · ", s] : [s])), near));
}
function cardMeta(c) {
  const deckC = (S.paquets.find((p) => p.cle === c.deck) || {});
  return h("div", { class: "row small muted" }, h("span", { class: "dot", style: `background:${deckC.couleur || "#999"}` }), deckC.nom || c.deck, h("span", { class: "badge" }, `Rang ${c.rang}`),
    h("span", { class: "badge" }, c.etat.etat === "nouvelle" ? "nouvelle" : c.etat.etat === "due" ? "à réviser" : c.etat.etat === "mature" ? "mûre" : "en cours"));
}
async function viewCards(params) {
  const mode = params.mode === "parcourir" ? "parcourir" : "reviser";
  const tabs = h("div", { class: "chips", style: "margin:6px 0 12px" }, h("button", { class: "chip", "aria-pressed": mode === "reviser", onclick: () => setHash("cartes", { mode: "reviser", deck: params.deck }) }, "Réviser"),
    h("button", { class: "chip", "aria-pressed": mode === "parcourir", onclick: () => setHash("cartes", { mode: "parcourir", deck: params.deck }) }, "Parcourir / ajouter"));
  const deckSel = h("select", { "aria-label": "Paquet", onchange: (e) => setHash("cartes", { ...params, deck: e.target.value }) }, h("option", { value: "" }, "Tous les paquets"),
    S.paquets.map((p) => h("option", { value: p.cle, ...(p.cle === params.deck ? { selected: true } : {}) }, `${p.nom} (${p.dues} dues)`)));
  const box = h("div", {});
  MAIN.replaceChildren(h("h1", {}, "Cartes"), h("div", { class: "row" }, tabs, deckSel), box);
  if (mode === "reviser") return session(box, params);
  return browse(box, params);
}
async function session(box, params) {
  const r = await api(`/api/cards?etat=a_reviser&limit=40${params.deck ? `&deck=${params.deck}` : ""}`);
  SES = { queue: r.cartes, i: 0, shown: false, done: 0, total: r.total };
  if (!SES.queue.length) { box.replaceChildren(h("div", { class: "card empty" }, h("h2", {}, "Rien à réviser 🎉"), h("p", {}, "Toutes les cartes sont à jour. Reviens demain, ou parcours le paquet."))); return; }
  drawCard(box);
}
function drawCard(box) {
  const c = SES.queue[SES.i];
  if (!c) { box.replaceChildren(h("div", { class: "card empty" }, h("h2", {}, `Session terminée — ${plural(SES.done, "carte revue", "cartes revues")}`), h("p", {}, SES.total > SES.queue.length ? `Il en reste ${SES.total - SES.queue.length} à réviser.` : "Tout est à jour."), h("a", { class: "btn", href: "#/" }, "Retour au tableau de bord"))); loadSummary(); return; }
  const rate = (q, cls, label, hint) => h("button", { class: `btn ${cls}`, onclick: async () => { try { await api("/api/cards/review", { body: { id: c.id, quality: q } }); SES.done++; SES.i++; SES.shown = false; drawCard(box); } catch (e) { toast(e.message, true); } } }, label, h("small", {}, hint));
  box.replaceChildren(h("section", { class: "card" }, h("div", { class: "row between" }, cardMeta(c), h("span", { class: "small muted" }, `${SES.i + 1} / ${SES.queue.length}`)),
    h("p", { class: "qa" }, c.question),
    SES.shown ? [h("p", { class: "qa ans" }, c.answer), verifBlock(c), h("div", { class: "rate" }, rate("encore", "r1", "Encore", "demain"), rate("difficile", "r2", "Difficile", "bientôt"), rate("bien", "r3", "Bien", "espacer"), rate("facile", "r4", "Facile", "beaucoup plus tard"))]
      : h("button", { class: "btn", id: "show", onclick: () => { SES.shown = true; drawCard(box); } }, "Afficher la réponse (espace)")));
  $("#show")?.focus();
}
async function browse(box, params) {
  const q = params.q || "", etat = params.etat || "";
  const f = h("form", { class: "row", onsubmit: (e) => { e.preventDefault(); setHash("cartes", { ...params, q: $("#cq").value.trim(), offset: "" }); } },
    h("input", { id: "cq", type: "search", value: q, placeholder: "Filtrer les cartes", class: "grow", "aria-label": "Filtrer" }),
    h("select", { "aria-label": "État", onchange: (e) => setHash("cartes", { ...params, etat: e.target.value }) }, [["", "Tous les états"], ["dues", "À réviser"], ["nouvelle", "Nouvelles"], ["en_cours", "En cours"], ["mature", "Mûres"]].map(([v, l]) => h("option", { value: v, ...(v === etat ? { selected: true } : {}) }, l))),
    h("button", { class: "btn alt" }, "Filtrer"));
  const r = await api(`/api/cards?limit=60&q=${encodeURIComponent(q)}&etat=${etat}${params.deck ? `&deck=${params.deck}` : ""}`);
  box.replaceChildren(f, h("p", { class: "muted small" }, `${plural(r.total, "carte")}${r.total > r.cartes.length ? ` (${r.cartes.length} affichées)` : ""}`),
    h("ul", { class: "list" }, r.cartes.map((c) => h("li", { class: "hit" }, cardMeta(c), h("h3", {}, c.question), h("details", {}, h("summary", {}, "Voir la réponse"), h("p", {}, c.answer), verifBlock(c)),
      c.perso && h("button", { class: "btn danger sm", onclick: async () => { if (!confirm("Supprimer cette carte ?")) return; try { await api(`/api/cards/custom/${c.id}`, { method: "DELETE" }); toast("Carte supprimée"); viewRoute(); } catch (e) { toast(e.message, true); } } }, "Supprimer")))),
    addCardForm());
}
function addCardForm() {
  const deck = h("select", { id: "nd", required: true, "aria-label": "Paquet" }, S.paquets.map((p) => h("option", { value: p.cle }, p.nom)));
  return h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Ajouter une carte"), h("p", { class: "small muted" }, "Une carte = un fait atomique, créé à partir d'une erreur ou d'un fait de rang A."),
    h("form", { class: "list", onsubmit: async (e) => { e.preventDefault(); try { await api("/api/cards/custom", { body: { deck: deck.value, question: $("#nq").value, answer: $("#na").value, tags: $("#nt").value.split(",").map((t) => t.trim()).filter(Boolean) } }); toast("Carte ajoutée"); viewRoute(); } catch (er) { toast(er.message, true); } } },
      h("label", {}, "Paquet", deck), h("label", {}, "Question", h("textarea", { id: "nq", required: true, maxlength: 600 })), h("label", {}, "Réponse", h("textarea", { id: "na", required: true, maxlength: 2000 })),
      h("label", {}, "Mots-clés (séparés par des virgules)", h("input", { id: "nt" })), h("div", {}, h("button", { class: "btn" }, "Ajouter"))));
}


/* ------------------------------------------------------------------ Examens (modifiables) */
let EDIT = null;
async function viewExams() {
  const d = await api("/api/exams");
  const upcoming = d.examens.filter((e) => !e.passe), past = d.examens.filter((e) => e.passe);
  const card = (e) => h("article", { class: "card" + (e.passe ? "" : " accent"), style: e.passe ? "opacity:.65" : "" },
    h("div", { class: "row between" }, h("div", {}, h("div", { class: "row" }, h("span", { class: "badge" }, e.type_nom), e.estime && h("span", { class: "badge warn" }, "date à confirmer")),
      h("h2", { style: "margin-top:6px" }, e.nom), h("div", {}, fdatel(e.date), e.heure ? ` à ${e.heure}` : "", e.lieu ? ` · ${e.lieu}` : "")),
      h("div", { class: "big", title: e.passe ? "passé" : "dans" }, e.passe ? "passé" : e.jours === 0 ? "J" : `J-${e.jours}`)),
    e.matieres_detail.length ? h("div", { class: "chips", style: "margin-top:10px" }, e.matieres_detail.map((m) => m.categories.length
      ? h("a", { class: "chip", href: `#/cours?category=${encodeURIComponent(m.categories[0])}`, title: "Explorer les cours : " + m.categories.join(", ") }, m.matiere)
      : h("span", { class: "chip", style: "cursor:default" }, m.matiere))) : h("p", { class: "small muted" }, "Matières non renseignées."),
    e.note && h("p", { class: "small" }, e.note),
    h("div", { class: "row", style: "margin-top:10px" }, h("button", { class: "btn alt sm", onclick: () => { EDIT = e; viewExams(); window.scrollTo(0, 0); } }, "Modifier"),
      h("button", { class: "btn danger sm", onclick: async () => { if (!confirm(`Supprimer « ${e.nom} » ?`)) return; try { await api(`/api/exams/${e.id}`, { method: "DELETE" }); toast("Examen supprimé"); await loadSummary(); viewExams(); } catch (er) { toast(er.message, true); } } }, "Supprimer")));
  const e0 = EDIT || {}, f = (k) => e0[k] || "";
  const type = h("select", { id: "xt", "aria-label": "Type", ...(EDIT && ["edn", "ecos"].includes(e0.type) ? { disabled: true } : {}) }, Object.entries(d.types).map(([k, l]) => h("option", { value: k, ...(k === (e0.type || "partiel") ? { selected: true } : {}) }, l)));
  const form = h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, EDIT ? `Modifier : ${e0.nom}` : "Ajouter un examen"),
    h("p", { class: "small muted" }, "Une date = un examen : indique les matières de CE jour. L'EDN et les ECOS sont synchronisés avec ton profil. ", d.note_planning),
    h("form", { class: "list", onsubmit: async (ev) => { ev.preventDefault(); try {
      const body = { type: type.value, nom: $("#xn").value, date: $("#xd").value, heure: $("#xh").value || null, matieres: $("#xm").value.split(/[\n,;]+/).map((x) => x.trim()).filter(Boolean), lieu: $("#xl").value, note: $("#xo").value, estime: $("#xe").checked };
      if (EDIT) body.id = EDIT.id;
      await api("/api/exams", { body }); toast(EDIT ? "Examen modifié" : "Examen ajouté"); EDIT = null; await loadSummary(); viewExams(); } catch (er) { toast(er.message, true); } } },
      h("label", {}, "Type", type), h("label", {}, "Nom", h("input", { id: "xn", required: true, maxlength: 100, value: f("nom"), placeholder: "ex. Partiel de cardiologie" })),
      h("div", { class: "row" }, h("label", {}, "Date", h("input", { id: "xd", type: "date", required: true, value: f("date") })), h("label", {}, "Heure (facultatif)", h("input", { id: "xh", type: "time", value: f("heure") })),
        h("label", { class: "row", style: "align-self:end" }, h("input", { id: "xe", type: "checkbox", ...(e0.estime ? { checked: true } : {}) }), "Date à confirmer")),
      h("label", {}, "Matières de ce jour (une par ligne ou séparées par des virgules)", h("textarea", { id: "xm" }, (e0.matieres || []).join("\n"))),
      h("label", {}, "Lieu (facultatif)", h("input", { id: "xl", maxlength: 100, value: f("lieu") })), h("label", {}, "Note (facultatif)", h("input", { id: "xo", maxlength: 300, value: f("note") })),
      h("div", { class: "row" }, h("button", { class: "btn" }, EDIT ? "Enregistrer" : "Ajouter"), EDIT && h("button", { class: "btn alt", type: "button", onclick: () => { EDIT = null; viewExams(); } }, "Annuler"))));
  MAIN.replaceChildren(...[h("h1", {}, "Examens"), h("p", { class: "sub" }, "Dates et matières de chaque examen de l'année. Tout est modifiable ici ou avec ton coach (« /coach-setup »)."),
    upcoming.length ? h("div", { class: "list" }, upcoming.map(card)) : h("p", { class: "empty" }, "Aucun examen à venir."),
    past.length ? h("div", {}, h("h2", { style: "margin-top:18px" }, "Passés"), h("div", { class: "list" }, past.map(card))) : null, form].filter(Boolean));
}

/* ------------------------------------------------------------------ Planning */
async function viewPlanning() {
  const p = await api("/api/planning");
  const m = p.meta;
  MAIN.replaceChildren(h("h1", {}, "Planning"), h("p", { class: "sub" }, m.niveau), h("p", { class: "small muted" }, m.principe_directeur),
    h("section", { class: "card" }, h("h2", {}, p.phase_partiel.libelle), h("p", { class: "small" }, p.phase_partiel.template_semaine.structure_type),
      h("p", { class: "small muted" }, h("b", {}, "Gardes : "), p.phase_partiel.template_semaine.regle_gardes), h("p", { class: "small muted" }, h("b", {}, "Stage : "), p.phase_partiel.template_semaine.regle_stage)),
    ...p.semaines.map((w) => h("div", { class: "week" + (w.courante ? " cur" : "") + (w.passee ? " past" : ""), ...(w.courante ? { id: "cur" } : {}) },
      h("div", { class: "row between" }, h("b", {}, `S${w.s} · ${fdate(w.debut)} → ${fdate(w.fin)} — ${w.matiere}`), h("div", { class: "row" }, w.courante && h("span", { class: "badge ok" }, "en cours"), w.vacances && h("span", { class: "badge warn" }, "vacances"), w.gardes.length > 0 && h("span", { class: "badge" }, plural(w.gardes.length, "garde")))),
      h("div", { class: "small" }, w.sujet), h("div", { class: "small muted" }, `Bloc EDN transversal : ${deckLabel(p, w.edn_transversal)}`), w.note && h("div", { class: "small" }, w.note))),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, p.phase_edn_tour.libelle), h("ul", { class: "list" }, p.phase_edn_tour.structure.map((b) => h("li", {}, h("b", {}, `${b.bloc} (${plural(b.duree_semaines, "semaine")})`), h("div", { class: "small" }, b.contenu)))), h("p", { class: "small muted" }, p.phase_edn_tour.note)),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Règles transversales"), h("ul", { class: "list" }, p.regles.map((r) => h("li", { class: "small" }, r)))),
    h("section", { class: "card", style: "margin-top:14px" }, h("h2", {}, "Examen et filet"), h("p", { class: "small" }, p.phase_edn_examen.libelle), h("p", { class: "small muted" }, p.phase_edn_rattrapage.libelle)));
  $("#cur")?.scrollIntoView({ block: "center" });
}
const deckLabel = (_p, k) => deckName(k);

/* ------------------------------------------------------------------ Erreurs */
async function viewErrors() {
  const d = await api("/api/errors");
  const deck = h("select", { id: "ed", "aria-label": "Paquet" }, h("option", { value: "" }, "Sans paquet"), d.paquets.map((p) => h("option", { value: p.cle }, p.nom)));
  MAIN.replaceChildren(h("h1", {}, "Journal d'erreurs"), h("p", { class: "sub" }, "Une erreur notée = une carte à créer. Rien n'est supprimé de l'historique git."),
    h("section", { class: "card" }, h("form", { class: "list", onsubmit: async (e) => { e.preventDefault(); try { await api("/api/errors", { body: { text: $("#et").value, deck: deck.value } }); toast("Erreur enregistrée"); viewErrors(); } catch (er) { toast(er.message, true); } } },
      h("label", {}, "Ce que je me suis trompé(e)", h("textarea", { id: "et", required: true, maxlength: 1500 })), h("label", {}, "Paquet", deck), h("div", {}, h("button", { class: "btn" }, "Enregistrer")))),
    d.erreurs.length ? h("ul", { class: "list" }, d.erreurs.map((e) => h("li", { class: "hit" }, h("div", { class: "row between" }, h("span", { class: "small muted" }, fdate(e.date), e.deck ? ` · ${deckName(e.deck)}` : ""),
      h("button", { class: "btn danger sm", onclick: async () => { try { await api(`/api/errors/${e.id}`, { method: "DELETE" }); viewErrors(); } catch (er) { toast(er.message, true); } } }, "Supprimer")), h("p", {}, e.text)))) : h("p", { class: "empty" }, "Aucune erreur notée pour l'instant."));
}

/* ------------------------------------------------------------------ routeur */
const VIEWS = { "": viewToday, avancement: viewProgress, cours: viewCours, cartes: viewCards, examens: viewExams, planning: viewPlanning, erreurs: viewErrors };
async function viewRoute() {
  const { view, params } = parseHash();
  renderNav(VIEWS[view] ? view : "");
  try {
    if (!S) await loadSummary();
    await (VIEWS[view] || viewToday)(params);
  } catch (e) { MAIN.replaceChildren(h("div", { class: "card empty" }, h("h2", {}, "Impossible de charger cette page"), h("p", {}, e.message))); }
  window.scrollTo(0, 0);
}

/* ------------------------------------------------------------------ rechargement automatique quand les données changent (coach, autre onglet) */
function busy() {
  if (SES && SES.queue && SES.i < SES.queue.length) return true;                       // session de cartes en cours
  const a = document.activeElement;
  return !!(a && a.matches && a.matches("input,textarea,select") && MAIN.contains(a) && (a.value || "").length > 0);   // saisie en cours
}
async function checkVersion() {
  if (document.visibilityState !== "visible") return;
  let v; try { v = (await (await fetch("/api/version", { credentials: "same-origin" })).json()).version; } catch (_) { return; }
  if (VER === null) { VER = v; return; }
  if (v === VER) return;
  if (busy()) {
    if (!$("#update")) document.body.append(h("div", { id: "update", class: "toast", role: "status" }, "Nouvelles données reçues. ", h("button", { class: "btn sm alt", onclick: () => { $("#update").remove(); reload(); } }, "Actualiser")));
    return;
  }
  VER = v; await reload(); toast("Données mises à jour");
}
async function reload() { $("#update")?.remove(); S = null; FAC = null; await syncVersion(); await viewRoute(); }
setInterval(checkVersion, 5000);
document.addEventListener("visibilitychange", checkVersion);
syncVersion();

addEventListener("hashchange", () => { if (parseHash().view !== "cartes") SES = null; viewRoute(); });
addEventListener("keydown", (e) => {
  if (!SES || e.target.matches("input,textarea,select")) return;
  if (!SES.shown && (e.key === " " || e.key === "Enter") && $("#show")) { e.preventDefault(); $("#show").click(); }
  else if (SES.shown && "1234".includes(e.key) && e.key) { document.querySelectorAll(".rate .btn")[+e.key - 1]?.click(); }
});
$("#theme").addEventListener("click", () => { const r = document.documentElement, dark = getComputedStyle(r).getPropertyValue("--bg").trim() === "#0f1713"; const next = dark ? "light" : "dark"; r.dataset.theme = next; try { localStorage.setItem("edn-theme", next); } catch (_) {} });
try { const t = localStorage.getItem("edn-theme"); if (t) document.documentElement.dataset.theme = t; } catch (_) {}
viewRoute();
