#!/usr/bin/env python3
"""Importe la progression de l'ancien site sophie-revision (store.json ou export /api/export) dans le suivi du coach.

  srs[carte]   -> revisions.md      (élément « carte:<id> », mêmes échéances, facilité, échecs)
  customCards  -> cartes-perso.md   (identifiants conservés)
  journal      -> erreurs.md        (journal d'erreurs, identifiants et dates conservés)

Simulation par défaut ; --apply écrit en UN commit git. N'écrase JAMAIS : ce qui existe déjà est conservé et compté.
Récupérer le fichier sur la Freebox :  docker cp sophie-revision:/app/db/store.json ./store-sophie.json
Usage : EDN_DATA_DIR=suivi python3 scripts/import_sophie.py store-sophie.json [--apply]
"""
import datetime as dt, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edn_dash, edn_store, edn_study  # noqa: E402

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def plan(raw):
    decks = edn_dash.deck_meta()
    known = {c["id"]: c for c in edn_dash.deck()["cards"]}
    custom_ids = {c["id"] for c in edn_dash.custom_cards()}
    rev, rep = dict(edn_study.all_cards()), {"srs": 0, "srs_deja": 0, "srs_inconnues": [], "perso": 0, "perso_deja": 0, "perso_invalides": [], "erreurs": 0, "erreurs_deja": 0}
    srs = raw.get("srs") or {}
    new_custom = [c for c in raw.get("customCards") or []]
    for cid, r in srs.items():
        item = f"carte:{cid}"
        if cid not in known and cid not in {c.get("id") for c in new_custom} and cid not in custom_ids:
            rep["srs_inconnues"].append(cid); continue
        if item in rev:
            rep["srs_deja"] += 1; continue
        if not (isinstance(r, dict) and ISO.match(str(r.get("due", ""))) and isinstance(r.get("interval"), (int, float))):
            rep["srs_inconnues"].append(cid); continue
        deck = (known.get(cid) or next((c for c in new_custom if c.get("id") == cid), {})).get("deck")
        rev[item] = {"ease": round(float(r.get("ease", 2.5)), 3), "interval": int(r["interval"]), "reps": int(r.get("reps", 0)), "lapses": int(r.get("lapses", 0)),
                     "due": r["due"], "category": (decks.get(deck) or {}).get("nom")}
        rep["srs"] += 1
    customs = list(edn_dash.custom_cards())
    for c in new_custom:
        if c.get("id") in custom_ids:
            rep["perso_deja"] += 1
        elif c.get("deck") in decks and str(c.get("question", "")).strip() and str(c.get("answer", "")).strip():
            customs.append({k: c.get(k) for k in ("id", "deck", "rang", "item", "question", "answer", "tags")} | {"tags": [str(t) for t in c.get("tags") or []]})
            rep["perso"] += 1
        else:
            rep["perso_invalides"].append(c.get("id"))
    errs = list(edn_dash.errors())
    have = {e["id"] for e in errs}
    for e in raw.get("journal") or []:
        if e.get("id") in have:
            rep["erreurs_deja"] += 1
        elif str(e.get("text", "")).strip():
            errs.append({"id": e["id"], "date": e.get("date") or dt.date.today().isoformat(), "text": str(e["text"]).strip()[:1500], "deck": e.get("deck") if e.get("deck") in decks else None})
            rep["erreurs"] += 1
    errs.sort(key=lambda e: e["date"], reverse=True)
    return rev, customs, errs, rep


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    raw = json.load(open(args[0], encoding="utf-8"))
    rev, customs, errs, rep = plan(raw)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if "--apply" not in sys.argv:
        print("Simulation : rien n'a été écrit. Relancer avec --apply."); return
    if not (rep["srs"] or rep["perso"] or rep["erreurs"]):
        print("Rien de nouveau à importer."); return
    r = edn_store.write_many({"revisions.md": edn_study._render_cards(rev),
                              "cartes-perso.md": f"# Cartes personnelles\n\n```edn\n{json.dumps(customs, ensure_ascii=False, indent=1)}\n```\n",
                              "erreurs.md": f"# Journal d'erreurs\n\n```edn\n{json.dumps(errs, ensure_ascii=False, indent=1)}\n```\n"},
                             f"import sophie-revision ({rep['srs']} révisions, {rep['perso']} cartes, {rep['erreurs']} erreurs)")
    print("Import écrit, commit", r["commit"])


if __name__ == "__main__":
    main()
