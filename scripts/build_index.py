#!/usr/bin/env python3
"""knowledge/cours.db -> knowledge/INDEX.md (carte des cours : spécialités, SdD, fichiers à qualité faible)."""
import sqlite3
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "knowledge"
db = sqlite3.connect(KB / "cours.db")
o = ["# Index des cours", "", "## Spécialités (hors SdD)", "", "| Catégorie | Docs | Pages |", "|---|---|---|"]
for c, n, p in db.execute("select category,count(*),sum(n_pages) from docs where sdd is null and category!='Situations de départ' group by 1 order by 2 desc"):
    o.append(f"| {c} | {n} | {p} |")
o += ["", "## Situations de départ (SdD)", "", "| N° | Titre | Pages | Qualité |", "|---|---|---|---|"]
for s, t, p, q in db.execute("select sdd,title,n_pages,quality from docs where category='Situations de départ' order by coalesce(sdd,9999),title"):
    o.append(f"| {s or '—'} | {t} | {p} | {q} |")
o += ["", "## À traiter (OCR ou lecture manuelle)", ""]
for c, t, q in db.execute("select category,title,quality from docs where quality!='ok' order by quality,category,title"):
    o.append(f"- [{q}] {c} — {t}")
(KB / "INDEX.md").write_text("\n".join(o) + "\n", encoding="utf-8")
print("INDEX.md:", len(o), "lignes")
