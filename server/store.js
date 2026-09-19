// Persistance simple sur fichier JSON, avec écriture atomique (write-then-rename)
// et une file d'attente pour sérialiser les écritures concurrentes.

const fs = require("fs");
const path = require("path");

const DB_PATH = process.env.DB_PATH || path.join(__dirname, "..", "db", "store.json");

const DEFAULT_STORE = { srs: {}, customCards: [], journal: [] };

function ensureDir() {
  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function normalize(raw) {
  return {
    srs: raw && typeof raw.srs === "object" && raw.srs !== null ? raw.srs : {},
    customCards: Array.isArray(raw?.customCards) ? raw.customCards : [],
    journal: Array.isArray(raw?.journal) ? raw.journal : [],
  };
}

function save(store) {
  ensureDir();
  const tmp = DB_PATH + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(store, null, 2));
  fs.renameSync(tmp, DB_PATH);
}

function load() {
  ensureDir();
  if (!fs.existsSync(DB_PATH)) {
    const fresh = normalize(DEFAULT_STORE);
    save(fresh);
    return fresh;
  }
  try {
    const raw = fs.readFileSync(DB_PATH, "utf-8");
    return normalize(JSON.parse(raw));
  } catch (e) {
    console.error("[store] fichier de données illisible, un fichier vide est utilisé :", e.message);
    return normalize(DEFAULT_STORE);
  }
}

let state = load();
let writeChain = Promise.resolve();

// Toute mutation passe par ici : lit l'état en mémoire, applique fn, sauvegarde sur disque,
// le tout en série pour éviter les écritures concurrentes qui s'écraseraient.
function mutate(fn) {
  writeChain = writeChain.then(() => {
    const result = fn(state);
    save(state);
    return result;
  });
  return writeChain;
}

function getState() {
  return state;
}

module.exports = { getState, mutate, DB_PATH };
