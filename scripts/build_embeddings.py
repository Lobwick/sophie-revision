#!/usr/bin/env python3
"""Vectorise chaque page de knowledge/cours.db (fastembed, ONNX, local — aucun envoi externe).

Sortie : knowledge/emb/<tag>.npy (float16, vecteurs normalisés) + <tag>.ids.npy (rowid des pages) + <tag>.json (modèle, dim).
Usage : .venv/bin/python scripts/build_embeddings.py --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 --tag minilm
"""
import argparse, json, sqlite3, time
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

KB = Path(__file__).resolve().parent.parent / "knowledge"
PREFIX = {"e5": "passage: "}  # les modèles E5 exigent un préfixe « passage: » / « query: »


def passage_text(title, cat, text):
    return f"{cat} — {title}\n{text}"[:1800]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    db = sqlite3.connect(KB / "cours.db")
    rows = db.execute("SELECT p.rowid,d.title,d.category,p.text FROM pages p JOIN docs d ON d.id=p.doc_id "
                      "WHERE length(p.text)>=40 ORDER BY p.rowid").fetchall()[: a.limit]
    pre = next((v for k, v in PREFIX.items() if k in a.model.lower()), "")
    texts = [pre + passage_text(t, c, x) for _, t, c, x in rows]
    model = TextEmbedding(a.model, threads=8)
    t0, out = time.time(), []
    for i, v in enumerate(model.embed(texts, batch_size=32), 1):
        out.append(v)
        if i % 2000 == 0:
            print(f"{i}/{len(texts)}  {i / (time.time() - t0):.1f} p/s", flush=True)
    m = np.asarray(out, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-9
    (KB / "emb").mkdir(exist_ok=True)
    np.save(KB / "emb" / f"{a.tag}.npy", m.astype(np.float16))
    np.save(KB / "emb" / f"{a.tag}.ids.npy", np.asarray([r[0] for r in rows], dtype=np.int64))
    (KB / "emb" / f"{a.tag}.json").write_text(json.dumps({"model": a.model, "dim": int(m.shape[1]), "pages": len(rows)}))
    print("terminé", m.shape, round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
