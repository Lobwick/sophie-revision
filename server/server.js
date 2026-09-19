const express = require("express");
const path = require("path");
const crypto = require("crypto");
const store = require("./store");
const { fetchGardes, CALENDAR_URL } = require("./calendar-sync");

const app = express();
app.use(express.json());

const SITE_ROOT = path.join(__dirname, "..");
app.use(express.static(SITE_ROOT, { extensions: ["html"] }));

function genId(prefix) {
  return `${prefix}-${Date.now().toString(36)}${crypto.randomBytes(3).toString("hex")}`;
}

// --- Synchronisation calendrier (gardes) ---
// Rafraîchie périodiquement en tâche de fond ; l'API sert toujours la dernière version connue,
// jamais un appel réseau bloquant côté client.
let gardesCache = { updated_at: null, gardes: [], enabled: !!CALENDAR_URL, error: null };

async function refreshGardes() {
  try {
    gardesCache = await fetchGardes();
  } catch (e) {
    console.error("[calendrier] échec de synchronisation :", e.message);
    gardesCache = { ...gardesCache, error: e.message };
  }
}

refreshGardes();
const GARDES_SYNC_INTERVAL_MS = 6 * 60 * 60 * 1000; // 6h
setInterval(refreshGardes, GARDES_SYNC_INTERVAL_MS);

app.get("/api/gardes", (req, res) => {
  res.json(gardesCache);
});

app.post("/api/gardes/refresh", async (req, res) => {
  await refreshGardes();
  res.json(gardesCache);
});

app.get("/api/health", (req, res) => {
  res.json({ ok: true, db: store.DB_PATH });
});

app.get("/api/data", (req, res) => {
  res.json(store.getState());
});

app.put("/api/srs", async (req, res) => {
  const { cardId, record } = req.body || {};
  if (!cardId || !record || typeof record !== "object") {
    return res.status(400).json({ error: "cardId et record sont requis" });
  }
  await store.mutate((s) => {
    s.srs[cardId] = record;
  });
  res.json({ ok: true });
});

app.post("/api/custom-cards", async (req, res) => {
  const { deck, rang, question, answer, tags } = req.body || {};
  if (!deck || !rang || !question || !answer) {
    return res.status(400).json({ error: "deck, rang, question et answer sont requis" });
  }
  const card = {
    id: genId("custom"),
    deck: String(deck),
    rang: String(rang),
    question: String(question),
    answer: String(answer),
    item: "",
    tags: Array.isArray(tags) ? tags.map(String) : [],
    srs: null,
  };
  await store.mutate((s) => {
    s.customCards.push(card);
  });
  res.status(201).json(card);
});

app.delete("/api/custom-cards/:id", async (req, res) => {
  await store.mutate((s) => {
    s.customCards = s.customCards.filter((c) => c.id !== req.params.id);
    delete s.srs[req.params.id];
  });
  res.json({ ok: true });
});

app.post("/api/journal", async (req, res) => {
  const { text, deck } = req.body || {};
  if (!text || !String(text).trim()) {
    return res.status(400).json({ error: "text est requis" });
  }
  const entry = {
    id: genId("j"),
    date: new Date().toISOString().slice(0, 10),
    text: String(text).trim(),
    deck: deck || null,
  };
  await store.mutate((s) => {
    s.journal.unshift(entry);
  });
  res.status(201).json(entry);
});

app.delete("/api/journal/:id", async (req, res) => {
  await store.mutate((s) => {
    s.journal = s.journal.filter((e) => e.id !== req.params.id);
  });
  res.json({ ok: true });
});

app.get("/api/export", (req, res) => {
  const s = store.getState();
  const filename = `sophie-revision-sauvegarde-${new Date().toISOString().slice(0, 10)}.json`;
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  res.json({ exported_at: new Date().toISOString(), ...s });
});

app.post("/api/import", async (req, res) => {
  const { srs, customCards, journal } = req.body || {};
  const next = {
    srs: srs && typeof srs === "object" ? srs : {},
    customCards: Array.isArray(customCards) ? customCards : [],
    journal: Array.isArray(journal) ? journal : [],
  };
  await store.mutate((s) => {
    s.srs = next.srs;
    s.customCards = next.customCards;
    s.journal = next.journal;
  });
  res.json(store.getState());
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Sophie révision — serveur prêt sur le port ${PORT} (données : ${store.DB_PATH})`);
});
