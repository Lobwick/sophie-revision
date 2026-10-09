#!/usr/bin/env python3
"""Construit data/cartes-edn.json (deck final vérifié) : deck source + corrections + preuves de concordance avec les cours.

Statuts : `corrigee` / `completee` (modifiée après vérification ; l'ancienne version reste dans verification.avant),
`confirmee_cours` (relue ET page de cours concordante retrouvée), `relue` (relue, cohérente avec les référentiels, aucune page de cours
suffisamment concordante retrouvée automatiquement : à confronter avant de s'y fier pour un chiffre).
La concordance est automatique (part des mots significatifs de la réponse présents dans une page) : indice, pas preuve."""
import json, re, sys, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edn_kb  # noqa: E402
from verify_cards import DECK_CATS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STOP = set("dans avec pour sans plus entre comme chez cette leurs aussi sont être avoir selon ainsi lorsque alors toute toutes tous elle elles ils fait faire peut doit font très après avant depuis puis".split())
DATE = "2026-10-09"


def toks(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{6,}", t) if w not in STOP}


def main():
    kb = edn_kb.connect()
    src = json.load(open(ROOT / "data" / "cartes-edn.source.json"))
    corr = json.load(open(ROOT / "data" / "cartes-corrections.json"))["corrections"]
    stats, out = {}, []
    for c in src["cards"]:
        card = {k: v for k, v in c.items() if k != "srs"}
        ver = {"date": DATE}
        ans_toks = toks(c["answer"])
        # preuves automatiques
        best = []
        for cat in DECK_CATS.get(c["deck"], [None]):
            for h in edn_kb.search(kb, c["question"] + " " + " ".join(c.get("tags", [])), category=cat, limit=8):
                row = kb.execute("SELECT p.text FROM pages p JOIN docs d ON d.id=p.doc_id WHERE d.slug=? AND p.page=?", (h["slug"], h["page"])).fetchone()
                sc = len(ans_toks & toks(row["text"])) / max(len(ans_toks), 1) if row else 0
                best.append((sc, h))
        best.sort(key=lambda x: -x[0])
        fix = corr.get(c["id"])
        if fix:
            ver["statut"] = fix["statut"]
            if fix["statut"] in ("corrigee", "completee"):
                ver["avant"] = {"question": c["question"], "answer": c["answer"]}
                ver["motif"] = fix["motif"]
                card["answer"] = fix["answer"]
                card["question"] = fix.get("question", c["question"])
            if fix.get("remarque"):
                ver["remarque"] = fix["remarque"]
            srcs = []
            for title, page in fix.get("sources_cours", []):
                r = kb.execute("SELECT slug,category,title FROM docs WHERE title=? LIMIT 1", (title,)).fetchone()
                assert r, f"cours introuvable : {title}"
                srcs.append({"slug": r["slug"], "page": page, "titre": f"{r['category']} — {r['title']}"})
            ver["sources_cours"], ver["sources_web"] = srcs, fix.get("sources_web", [])
        else:
            good = [(s, h) for s, h in best if s >= 0.45][:2]
            ver["statut"] = "confirmee_cours" if good else "relue"
            ver["sources_cours"] = [{"slug": h["slug"], "page": h["page"], "titre": f"{h['category']} — {h['title']}", "concordance": round(s, 2)} for s, h in good]
            ver["sources_web"] = []
            if not good and best:  # indice seulement : page la plus proche, avec son score
                sc, h = best[0]
                ver["page_proche"] = {"slug": h["slug"], "page": h["page"], "titre": f"{h['category']} — {h['title']}", "concordance": round(sc, 2)}
        stats[ver["statut"]] = stats.get(ver["statut"], 0) + 1
        card["verification"] = ver
        out.append(card)
    meta = dict(src["meta"], version="2.0", verifie_le=DATE,
                avertissement="Deck relu et confronté aux cours le " + DATE + " : voir verification.statut de chaque carte. « relue » = cohérente avec les référentiels mais sans page de cours concordante retrouvée automatiquement : à recouper avant d'apprendre un chiffre. Les seules sources opposables restent LiSA et les référentiels de collège.")
    (ROOT / "data" / "cartes-edn.json").write_text(json.dumps({"meta": meta, "decks": src["decks"], "cards": out}, ensure_ascii=False, indent=1), "utf-8")
    lines = ["# Vérification du deck de cartes", "", f"Réalisée le {DATE} : lecture des {len(out)} cartes, confrontation aux cours (base FTS) et aux recommandations.", "",
             "| Statut | Cartes |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(stats.items())] + ["", "## Corrections", ""]
    for cid, f in corr.items():
        if f["statut"] in ("corrigee", "completee"):
            c0 = next(x for x in src["cards"] if x["id"] == cid)
            lines += [f"### {cid} — {f['statut']}", f"**Avant** : {c0['answer']}", "", f"**Après** : {f['answer']}", "", f"**Pourquoi** : {f['motif']}", ""]
    (ROOT / "knowledge" / "cards_verification_report.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(stats)


if __name__ == "__main__":
    main()
