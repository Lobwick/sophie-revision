"""Recherche dans la base de cours (SQLite FTS5, lecture seule). Stdlib uniquement."""
import os
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "knowledge" / "cours.db"
WORD = re.compile(r"[\wÀ-ÿ]{2,}", re.U)
# Les Masterclass et conférences sont des synthèses larges : on préfère le cours dédié à pertinence égale.
PENALTY = {"Masterclass": 1.5, "Cours publics": 1.0, "Entrainement": 0.5}


import threading

_local = threading.local()


def _conn():
    if not hasattr(_local, "c"):
        c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        _local.c = c
    return _local.c


class ThreadKB:
    """Une connexion SQLite (lecture seule) par thread : le serveur est multi-thread."""

    def execute(self, *a):
        return _conn().execute(*a)


def connect():
    return ThreadKB()


def _match(query: str, mode: str) -> str:
    toks = list(dict.fromkeys(t.lower() for t in WORD.findall(query)))[:12]
    if not toks:
        return ""
    return (" AND " if mode == "and" else " OR ").join(f'"{t}"' for t in toks)


def _snippet(text: str, query: str, width=360) -> str:
    low = text.lower()
    pos = min((p for p in (low.find(t.lower()) for t in WORD.findall(query)) if p >= 0), default=0)
    a = max(0, pos - width // 4)
    s = re.sub(r"\s+", " ", text[a:a + width]).strip()
    return ("…" if a else "") + s + ("…" if a + width < len(text) else "")


class Dense:
    """Recherche sémantique OPTIONNELLE, désactivée par défaut (EDN_EMB_TAG=<tag> pour l'activer) sur knowledge/emb/<tag>.npy.
    Dépendances optionnelles : numpy + fastembed. Aucun modèle testé n'a battu les mots-clés (voir AGENTS.md).
    Chargement paresseux ; si indisponible, `available` reste faux et la recherche retombe sur les mots-clés."""

    def __init__(self, tag=None):
        self.tag, self.ok, self.err, self._m, self._ids, self._model, self._prefix = tag, None, None, None, None, None, ""

    def _load(self):
        if self.ok is not None:
            return self.ok
        try:
            import json
            import numpy as np
            emb = ROOT / "knowledge" / "emb"
            tag = self.tag or os.environ.get("EDN_EMB_TAG")
            if not tag or not (emb / f"{tag}.npy").exists():
                raise FileNotFoundError("recherche sémantique non activée (EDN_EMB_TAG + knowledge/emb/<tag>.npy)")
            meta = json.loads((emb / f"{tag}.json").read_text())
            from fastembed import TextEmbedding
            self._m = np.load(emb / f"{tag}.npy").astype("float32")
            self._ids = np.load(emb / f"{tag}.ids.npy")
            self._model = TextEmbedding(meta["model"], threads=4)
            self._prefix = "query: " if "e5" in meta["model"].lower() else ""
            self.tag, self.ok = tag, True
        except Exception as e:  # noqa: BLE001
            self.ok, self.err = False, f"{type(e).__name__}: {e}"
        return self.ok

    @property
    def available(self):
        return self._load()

    def top(self, query, k=80):
        if not self._load():
            return []
        import numpy as np
        v = np.asarray(next(iter(self._model.embed([self._prefix + query]))), dtype="float32")
        v /= np.linalg.norm(v) + 1e-9
        sims = self._m @ v
        idx = np.argpartition(-sims, min(k, len(sims) - 1))[:k]
        idx = idx[np.argsort(-sims[idx])]
        return [(int(self._ids[i]), float(sims[i])) for i in idx]


def _fts_ranked(db, query, category, sdd, want=30):
    """Pages classées par pertinence. `category` : nom, ou liste de noms. Les pages contenant TOUS les mots passent d'abord ; si elles sont
    trop peu nombreuses, on complète avec les pages contenant AU MOINS UN mot (déjà classées par BM25 : les plus complètes en tête)."""
    cats = [category] if isinstance(category, str) else list(category or [])
    seen, ranked = set(), []
    for mode in ("and", "or"):
        m = _match(query, mode)
        if not m:
            return []
        sql = ("SELECT pages_fts.rowid AS rid, d.category AS category, bm25(pages_fts,1.0,4.0,1.0) AS score FROM pages_fts "
               "JOIN pages p ON p.rowid=pages_fts.rowid JOIN docs d ON d.id=p.doc_id WHERE pages_fts MATCH ?")
        args = [m]
        if cats:
            sql += " AND d.category COLLATE NOCASE IN (%s)" % ",".join("?" * len(cats)); args += cats
        if sdd:
            sql += " AND d.sdd=?"; args.append(sdd)
        rows = db.execute(sql + " ORDER BY score LIMIT 120", args).fetchall()
        for r in sorted(rows, key=lambda r: r["score"] + PENALTY.get(r["category"], 0)):
            if r["rid"] not in seen:
                seen.add(r["rid"]); ranked.append(r["rid"])
        if len(ranked) >= want:
            break
    return ranked


def search(db, query, category=None, sdd=None, limit=6, dense=None):
    """Mots-clés (FTS5/BM25) seuls, ou hybride mots-clés + sémantique (fusion par rangs réciproques) si `dense` est utilisable."""
    limit = max(1, min(limit, 15))
    kw = _fts_ranked(db, query, category, sdd)
    sem = []
    if dense is not None and dense.available:
        cand = dense.top(query, 120)
        if cand:
            ph = ",".join("?" * len(cand))
            meta = {r["rowid"]: r for r in db.execute(
                f"SELECT p.rowid AS rowid, d.category AS category, d.sdd AS sdd FROM pages p JOIN docs d ON d.id=p.doc_id WHERE p.rowid IN ({ph})",
                [c[0] for c in cand])}
            sem = [rid for rid, _ in cand if rid in meta
                   and (not category or meta[rid]["category"].lower() in [c.lower() for c in ([category] if isinstance(category, str) else category)]) and (not sdd or meta[rid]["sdd"] == sdd)]
            # les Masterclass/entraînements sont rétrogradés de quelques rangs, comme dans la recherche par mots-clés
            sem = [rid for _, rid in sorted((i + 6 * (meta[rid]["category"] in PENALTY), rid) for i, rid in enumerate(sem))]
    scores = {}
    for lst in (kw, sem):
        for rank, rid in enumerate(lst):
            scores[rid] = scores.get(rid, 0) + 1 / (60 + rank)
    fused = sorted(scores, key=lambda r: -scores[r])[:60]
    if not fused:
        return []
    ph = ",".join("?" * len(fused))
    rows = {r["rowid"]: r for r in db.execute(
        f"SELECT p.rowid AS rowid,d.slug,d.category,d.title,d.sdd,p.page,p.text FROM pages p JOIN docs d ON d.id=p.doc_id WHERE p.rowid IN ({ph})", fused)}
    out, per_doc = [], {}
    for rid in fused:
        r = rows[rid]
        if per_doc.get(r["slug"], 0) >= 2:
            continue
        per_doc[r["slug"]] = per_doc.get(r["slug"], 0) + 1
        out.append({"slug": r["slug"], "category": r["category"], "title": r["title"], "sdd": r["sdd"], "page": r["page"],
                    "extrait": _snippet(r["text"], query), "via": "mots-clés+sens" if rid in kw and rid in sem else
                    "sens" if rid in sem else "mots-clés"})
        if len(out) >= limit:
            break
    return out


def list_docs(db, category=None, query=None, limit=60):
    sql, args = "SELECT slug,category,title,sdd,n_pages,quality FROM docs WHERE 1=1", []
    if category:
        sql += " AND category=? COLLATE NOCASE"; args.append(category)
    if query:
        sql += " AND (title LIKE ? OR category LIKE ?)"; args += [f"%{query}%"] * 2
    sql += " ORDER BY category, COALESCE(sdd,9999), title LIMIT ?"
    return [dict(r) for r in db.execute(sql, args + [max(1, min(limit, 200))])]


def categories(db):
    return [dict(r) for r in db.execute(
        "SELECT category,COUNT(*) docs,SUM(n_pages) pages FROM docs GROUP BY 1 ORDER BY 2 DESC")]


def get_doc(db, slug=None, sdd=None, page_from=1, page_to=None, max_chars=12000):
    d = (db.execute("SELECT * FROM docs WHERE slug=?", (slug,)).fetchone() if slug else
         db.execute("SELECT * FROM docs WHERE sdd=? ORDER BY n_chars DESC LIMIT 1", (sdd,)).fetchone())
    if not d:
        return None
    rows = db.execute("SELECT page,text FROM pages WHERE doc_id=? AND page>=? AND page<=? ORDER BY page",
                      (d["id"], page_from, page_to or 10**6)).fetchall()
    out, used, last = [], 0, page_from - 1
    for r in rows:
        if used + len(r["text"]) > max_chars and out:
            break
        out.append(f"## p.{r['page']}\n{r['text']}")
        used += len(r["text"]); last = r["page"]
    return {"slug": d["slug"], "category": d["category"], "title": d["title"], "sdd": d["sdd"],
            "source": d["source"], "qualite": d["quality"], "pages_total": d["n_pages"],
            "pages_renvoyees": f"{page_from}-{last}", "suite": last < d["n_pages"] and last + 1 or None,
            "texte": "\n\n".join(out)}
