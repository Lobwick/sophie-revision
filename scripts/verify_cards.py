#!/usr/bin/env python3
"""Confronte chaque carte du deck aux cours (base FTS) : chiffres de la réponse retrouvés ou non, meilleures pages.

Sortie : knowledge/cards_verification.json + résumé. Ce script PRÉPARE la vérification (preuves), il ne tranche pas :
un chiffre absent des cours n'est pas faux, un chiffre présent n'est pas forcément dans le bon contexte → relecture humaine/web.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edn_kb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
from edn_dash import DECK_CATS  # noqa: E402
NUM = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(%|mm\s?hg|mmhg|mmol/l|g/l|g/dl|µmol/l|mg/dl|mg|g|µg|ml|l|h|heures?|minutes?|min|jours?|j|semaines?|sem|mois|ans?|cm|mm|kg|bpm|/min|j\b)?", re.I)


def norm(t):
    return re.sub(r"\s+", " ", t.lower().replace(",", ".").replace(" ", " ").replace("\xa0", " "))


def numbers(text):
    out = []
    for m in NUM.finditer(text):
        v, u = m.group(1).replace(",", "."), (m.group(2) or "").lower().replace(" ", "")
        if u or float(v) >= 10 or "." in v:  # ignore les chiffres isolés (1, 2, 3…) trop ambigus
            out.append((v, u))
    return list(dict.fromkeys(out))


def main():
    kb = edn_kb.connect()
    cards = json.load(open(ROOT / "data" / "cartes-edn.source.json"))["cards"]
    res = []
    for c in cards:
        q = f"{c['question']} {' '.join(c.get('tags', []))}"
        pages = []
        for cat in DECK_CATS.get(c["deck"], [None]):
            pages += edn_kb.search(kb, q, category=cat, limit=6)
        # texte complet des meilleures pages
        texts = []
        for h in pages[:10]:
            r = kb.execute("SELECT p.text FROM pages p JOIN docs d ON d.id=p.doc_id WHERE d.slug=? AND p.page=?", (h["slug"], h["page"])).fetchone()
            texts.append(norm(r["text"]) if r else "")
        blob = " ".join(texts)
        nums = numbers(c["answer"])
        found = [n for n in nums if re.search(rf"(?<![\d.]){re.escape(n[0])}\s*{re.escape(n[1])}" if n[1] else rf"(?<![\d.]){re.escape(n[0])}(?![\d])", blob)]
        res.append({"id": c["id"], "deck": c["deck"], "question": c["question"], "answer": c["answer"],
                    "nombres": [f"{v}{u}" for v, u in nums], "nombres_retrouves": [f"{v}{u}" for v, u in found],
                    "nombres_absents": [f"{v}{u}" for v, u in nums if (v, u) not in found],
                    "pages": [{"titre": h["title"], "cat": h["category"], "page": h["page"], "slug": h["slug"], "extrait": h["extrait"][:220]} for h in pages[:3]]})
    (ROOT / "knowledge" / "cards_verification.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    nn = [r for r in res if r["nombres"]]
    print(f"{len(res)} cartes ; {len(nn)} contiennent des chiffres ; "
          f"{sum(1 for r in nn if not r['nombres_absents'])} avec tous les chiffres retrouvés dans les cours ; "
          f"{sum(1 for r in nn if r['nombres_absents'])} avec au moins un chiffre absent ; {sum(1 for r in res if not r['pages'])} sans aucune page trouvée")


if __name__ == "__main__":
    main()
