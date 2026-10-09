"""API du tableau de bord (JSON) : avancement, planning, cartes en répétition espacée, explorateur de cours, journal d'erreurs, gardes.

Fonction pure `route(method, path, query, body, kb)` -> (code, payload) ou None si la route n'est pas la sienne ; l'envoi HTTP, le cookie et
la protection CSRF sont dans edn_site. Toutes les données personnelles vivent dans le dépôt git du suivi (edn_store) ; le contenu de
référence (deck vérifié, planning) dans data/. Stdlib uniquement.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import secrets
import threading
import time
import urllib.request
from pathlib import Path

import edn_exams
import edn_kb
import edn_store as store
import edn_study as study

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MATURE_DAYS = 21
QUALITY = {"encore": 1, "difficile": 3, "bien": 4, "facile": 5}

# Thèmes de l'explorateur : étiquette -> catégories de la base de cours
PARTIEL = ["Ophtalmologie", "ORL", "Chirurgie maxillo-faciale", "Anesthésie-réanimation", "Gériatrie", "MPR"]
THEMES = [
    ("partiel", "Partiel du 16/02", PARTIEL),
    ("sdd", "Situations de départ", ["Situations de départ"]),
    ("entrainement", "Entraînement, annales, LCA", ["Entrainement", "Entrainements aux ECOS", "Masterclass", "Cours publics", "LCA", "Méthodologie ECOS", "Coaching et Méthodologie"]),
]
SPECIALITES_HORS = {c for _, _, cs in THEMES for c in cs}


DECK_CATS = {"cardio": ["Cardiologie"], "pneumo": ["Pneumologie"], "infectio": ["Maladies infectieuses"], "neuro": ["Neurologie"],
             "nephro": ["Néphrologie"], "endoc": ["Endocrinologie"], "hge": ["HGE"], "hemato": ["Hématologie"], "cancero": ["Oncologie"],
             "gyneco": ["Gynécologie"], "pediatrie": ["Pédiatrie"], "psy": ["Psychiatrie"], "urgences": ["Anesthésie-réanimation", "Situations de départ"],
             "transversal": ["Santé publique", "LCA", "Cours publics"], "dermato_rhumato": ["Dermatologie", "Rhumatologie"],
             "ophtalmo": ["Ophtalmologie"], "orl": ["ORL"], "cmf": ["Chirurgie maxillo-faciale"], "reanimation": ["Anesthésie-réanimation"],
             "geriatrie_mpr": ["Gériatrie", "MPR"]}


class ApiError(ValueError):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code, self.msg = code, msg


# ------------------------------------------------------------------ contenu de référence (mis en cache par date de modification)

_cache: dict = {}


def _json(name):
    p = DATA / name
    m = p.stat().st_mtime
    if _cache.get(name, (0,))[0] != m:
        _cache[name] = (m, json.loads(p.read_text("utf-8")))
    return _cache[name][1]


def deck():
    return _json("cartes-edn.json")


def planning():
    return _json("planning-edn.json")


def _edn_list(rel):
    return store.read_edn(rel, [])


def custom_cards():
    return _edn_list("cartes-perso.md")


def errors():
    return _edn_list("erreurs.md")


def _save_list(rel, title, items, message):
    store.write(rel, f"# {title}\n\n```edn\n{json.dumps(items, ensure_ascii=False, indent=1)}\n```\n", message)


def _gid(prefix):
    return f"{prefix}-{int(time.time()):x}{secrets.token_hex(3)}"


def deck_meta():
    return {d["cle"]: d for d in deck()["decks"]}


def corrections_perso():
    return store.read_edn("cartes-corrections.md", {})


def all_cards():
    ov, out = corrections_perso(), []
    for c in deck()["cards"]:
        c = dict(c)
        o = ov.get(c["id"])
        if o:
            avant = {"question": c["question"], "answer": c["answer"]}
            for k in ("question", "answer", "tags", "rang"):
                if k in o:
                    c[k] = o[k]
            c["verification"] = {"statut": "modifiee", "motif": o.get("motif"), "avant": avant, "sources": o.get("sources", []), "sources_cours": [], "sources_web": [],
                                 "remarque": f"Modifiée le {o.get('date')} (version d'origine : {c['verification']['statut']})."}
        out.append(c)
    for c in custom_cards():
        out.append(dict(c, verification={"statut": "perso"}))
    return out


# ------------------------------------------------------------------ cartes + répétition espacée

def _state(rev, cid):
    r = rev.get(f"carte:{cid}")
    t = study.today().isoformat()
    if not r:
        return {"etat": "nouvelle"}
    s = "due" if r["due"] <= t else ("mature" if r["interval"] >= MATURE_DAYS else "en_cours")
    return {"etat": s, "due": r["due"], "intervalle": r["interval"], "echecs": r["lapses"], "repetitions": r["reps"]}


def cards_view(query):
    rev = study.all_cards()
    dk, st, rang = query.get("deck"), query.get("etat"), query.get("rang")
    needle = (query.get("q") or "").lower().strip()
    items = []
    for c in all_cards():
        s = _state(rev, c["id"])
        if dk and c["deck"] != dk: continue
        if rang and c["rang"] != rang: continue
        if st:
            ok = (st == "a_reviser" and s["etat"] in ("due", "nouvelle")) or s["etat"] == st or (st == "dues" and s["etat"] == "due")
            if not ok: continue
        if needle and needle not in (c["question"] + " " + c["answer"] + " " + " ".join(c.get("tags", []))).lower(): continue
        v = c.get("verification") or {}
        items.append({"id": c["id"], "deck": c["deck"], "rang": c["rang"], "question": c["question"], "answer": c["answer"], "tags": c.get("tags", []),
                      "perso": c["id"].startswith("custom-"), "etat": s, "verification": {
                          "statut": v.get("statut"), "motif": v.get("motif"), "remarque": v.get("remarque"),
                          "sources_cours": v.get("sources_cours", []), "sources_web": v.get("sources_web", []), "sources": v.get("sources", []), "page_proche": v.get("page_proche"),
                          "avant": v.get("avant")}})
    # dues d'abord (les plus en retard), puis nouvelles, puis le reste
    order = {"due": 0, "nouvelle": 1, "en_cours": 2, "mature": 3}
    items.sort(key=lambda x: (order[x["etat"]["etat"]], x["etat"].get("due", ""), x["id"]))
    off, lim = int(query.get("offset", 0) or 0), min(int(query.get("limit", 40) or 40), 200)
    return {"total": len(items), "offset": off, "cartes": items[off:off + lim]}


def review(body):
    cid, q = str(body.get("id", "")), body.get("quality")
    card = next((c for c in all_cards() if c["id"] == cid), None)
    if not card:
        raise ApiError(404, "carte inconnue")
    if q in QUALITY:
        q = QUALITY[q]
    if not isinstance(q, int) or isinstance(q, bool) or not 0 <= q <= 5:
        raise ApiError(400, "quality : encore | difficile | bien | facile (ou 0-5)")
    d = deck_meta().get(card["deck"], {})
    r = study.log_attempt(f"carte:{cid}", q, "carte", d.get("nom") or card["deck"], None, card["question"][:80])
    return {"ok": True, **r}


def _normq(t):
    import unicodedata
    return re.sub(r"\W+", " ", unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()).strip()


def save_cards(body):
    """Ajoute de nouvelles cartes ou corrige des cartes existantes. Tout est validé AVANT la moindre écriture ; un seul commit.
    `apercu: true` renvoie ce qui changerait sans rien écrire."""
    items = body.get("cartes")
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ApiError(400, "cartes : 1 à 100")
    decks = deck_meta()
    ref = {c["id"]: c for c in deck()["cards"]}
    ov = dict(corrections_perso())
    customs = [dict(c) for c in custom_cards()]
    cidx = {c["id"]: c for c in customs}
    known = {_normq(c["question"]): c["id"] for c in all_cards()}
    report, today = [], study.today().isoformat()
    for n, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise ApiError(400, f"carte {n} invalide")
        def txt(k, mx):
            v = it.get(k)
            if v is None: return None
            v = str(v).strip()
            if not v or len(v) > mx: raise ApiError(400, f"carte {n} : {k} vide ou trop long (≤ {mx})")
            return v
        q, a_, motif = txt("question", 600), txt("answer", 2000), txt("motif", 400)
        tags = [str(t).strip()[:40] for t in (it.get("tags") or []) if str(t).strip()][:8] if "tags" in it else None
        rang = it.get("rang")
        if rang not in (None, "A", "B"): raise ApiError(400, f"carte {n} : rang A ou B")
        srcs = [str(x).strip()[:300] for x in (it.get("sources") or []) if str(x).strip()][:10]
        cid = it.get("id")
        if cid:
            if cid in cidx:                                              # carte perso : modification directe (l'historique git garde l'ancienne version)
                c, before = cidx[cid], dict(cidx[cid])
                for k, v in (("question", q), ("answer", a_), ("tags", tags), ("rang", rang)):
                    if v is not None: c[k] = v
                if it.get("deck"):
                    if it["deck"] not in decks: raise ApiError(400, f"carte {n} : paquet inconnu {it['deck']}")
                    c["deck"] = it["deck"]
                report.append({"action": "modifiee" if c != before else "inchangee", "id": cid, "avant": {"question": before["question"], "answer": before["answer"]}, "apres": {"question": c["question"], "answer": c["answer"]}})
            elif cid in ref:                                             # carte du deck de référence : correction persistante, motif obligatoire
                if not motif: raise ApiError(400, f"carte {n} ({cid}) : `motif` obligatoire pour corriger une carte du deck")
                if q is None and a_ is None and tags is None and rang is None: raise ApiError(400, f"carte {n} ({cid}) : rien à corriger")
                o = dict(ov.get(cid, {}))
                for k, v in (("question", q), ("answer", a_), ("tags", tags), ("rang", rang)):
                    if v is not None: o[k] = v
                o.update(motif=motif, sources=srcs or o.get("sources", []), date=today)
                ov[cid] = o
                cur = next(c for c in all_cards() if c["id"] == cid)
                report.append({"action": "corrigee", "id": cid, "avant": {"question": cur["question"], "answer": cur["answer"]}, "apres": {"question": o.get("question", ref[cid]["question"]), "answer": o.get("answer", ref[cid]["answer"])}, "sourcee": bool(o["sources"])})
            else:
                raise ApiError(400, f"carte {n} : id inconnu {cid}")
        else:                                                            # nouvelle carte
            if it.get("deck") not in decks: raise ApiError(400, f"carte {n} : `deck` parmi {sorted(decks)}")
            if not q or not a_: raise ApiError(400, f"carte {n} : question et answer requis")
            if _normq(q) in known: raise ApiError(400, f"carte {n} : doublon de {known[_normq(q)]} (même question) — corrige-la avec son id")
            card = {"id": _gid("custom"), "deck": it["deck"], "rang": rang or "A", "item": str(it.get("item") or "")[:40], "question": q, "answer": a_, "tags": tags or []}
            if srcs: card["sources"] = srcs
            customs.append(card); cidx[card["id"]] = card; known[_normq(q)] = card["id"]
            report.append({"action": "ajoutee", "id": card["id"], "deck": card["deck"], "question": q})
    res = {"apercu": bool(body.get("apercu")), "ajoutees": sum(r["action"] == "ajoutee" for r in report), "modifiees": sum(r["action"] == "modifiee" for r in report),
           "corrigees": sum(r["action"] == "corrigee" for r in report), "detail": report}
    if body.get("apercu"):
        return res
    files = {}
    if res["ajoutees"] or res["modifiees"]:
        files["cartes-perso.md"] = f"# Cartes personnelles\n\n```edn\n{json.dumps(customs, ensure_ascii=False, indent=1)}\n```\n"
    if res["corrigees"]:
        files["cartes-corrections.md"] = f"# Corrections de cartes\n\nSurcharges du deck de référence (l'original reste dans data/ et dans verification.avant).\n\n```edn\n{json.dumps(ov, ensure_ascii=False, indent=1)}\n```\n"
    if not files:
        return dict(res, commit=None, note="aucun changement")
    r = store.write_many(files, f"cartes : +{res['ajoutees']} ~{res['modifiees']} corrigées {res['corrigees']}")
    return dict(res, commit=r["commit"])


def add_custom(body):
    deckk, question, answer = body.get("deck"), str(body.get("question", "")).strip(), str(body.get("answer", "")).strip()
    if deckk not in deck_meta(): raise ApiError(400, "paquet inconnu")
    if not question or not answer: raise ApiError(400, "question et réponse requises")
    if len(question) > 600 or len(answer) > 2000: raise ApiError(400, "texte trop long")
    tags = [str(t)[:40] for t in (body.get("tags") or []) if str(t).strip()][:8]
    card = {"id": _gid("custom"), "deck": deckk, "rang": "B" if body.get("rang") == "B" else "A", "item": "", "question": question, "answer": answer, "tags": tags}
    _save_list("cartes-perso.md", "Cartes personnelles", custom_cards() + [card], f"ajout carte {card['id']}")
    return card


def delete_custom(cid):
    cs = custom_cards()
    if not any(c["id"] == cid for c in cs): raise ApiError(404, "carte personnelle inconnue")
    _save_list("cartes-perso.md", "Cartes personnelles", [c for c in cs if c["id"] != cid], f"suppression carte {cid}")
    return {"ok": True}


# ------------------------------------------------------------------ journal d'erreurs

def add_error(body):
    text = str(body.get("text", "")).strip()
    if not text or len(text) > 1500: raise ApiError(400, "texte requis (≤ 1500 caractères)")
    dk = body.get("deck") if body.get("deck") in deck_meta() else None
    e = {"id": _gid("err"), "date": study.today().isoformat(), "text": text, "deck": dk}
    _save_list("erreurs.md", "Journal d'erreurs", [e] + errors(), f"erreur {e['id']}")
    return e


def delete_error(eid):
    es = errors()
    if not any(e["id"] == eid for e in es): raise ApiError(404, "entrée inconnue")
    _save_list("erreurs.md", "Journal d'erreurs", [e for e in es if e["id"] != eid], f"suppression erreur {eid}")
    return {"ok": True}


# ------------------------------------------------------------------ gardes (calendrier .ics)

_gardes = {"enabled": False, "updated_at": None, "gardes": [], "error": None}
_g_lock = threading.Lock()


def _ics_events(text):
    text = re.sub(r"\n[ \t]", "", text.replace("\r\n", "\n"))
    out = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        body = block.split("END:VEVENT")[0]
        summ = start = end = None
        for line in body.split("\n"):
            key, _, val = line.strip().partition(":")
            base = key.split(";")[0]
            m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", val.strip())
            if base == "SUMMARY": summ = val.strip()
            elif base in ("DTSTART", "DTEND") and m:
                d = {"date": f"{m[1]}-{m[2]}-{m[3]}", "time": f"{m[4]}:{m[5]}" if m[4] else None}
                start, end = (d, end) if base == "DTSTART" else (start, d)
        if summ and start and end:
            out.append((summ, start, end))
    return out


def gardes_from_ics(text):
    """Ne garde que les événements dont le titre contient « garde » (le reste du calendrier n'est jamais exposé)."""
    g = [{"debut_date": s["date"], "debut_time": s["time"], "fin_date": e["date"], "fin_time": e["time"], "jour_recuperation": e["date"]}
         for summ, s, e in _ics_events(text) if "garde" in summ.lower()]
    return sorted(g, key=lambda x: x["debut_date"])


def refresh_gardes():
    url = os.environ.get("EDN_CALENDAR_ICS_URL", "")
    if not url:
        return
    try:
        req = urllib.request.Request(re.sub(r"^webcal://", "https://", url, flags=re.I), headers={"User-Agent": "coach-internat"})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read(5_000_000).decode("utf-8", "replace")
        with _g_lock:
            _gardes.update(enabled=True, updated_at=dt.datetime.now().isoformat(timespec="seconds"), gardes=gardes_from_ics(text), error=None)
    except Exception as e:  # noqa: BLE001 — jamais l'URL (secrète) dans le message
        with _g_lock:
            _gardes.update(enabled=True, error=f"calendrier injoignable ({type(e).__name__})")


def start_gardes_sync():
    if not os.environ.get("EDN_CALENDAR_ICS_URL"):
        return

    def loop():
        while True:
            refresh_gardes()
            time.sleep(6 * 3600)
    threading.Thread(target=loop, daemon=True).start()


def gardes():
    with _g_lock:
        return dict(_gardes, gardes=list(_gardes["gardes"]))


# ------------------------------------------------------------------ planning et résumé

def _targets():
    """Prochains examens (à venir seulement), les plus proches d'abord : alimente les compteurs de l'en-tête."""
    t, out = study.today(), []
    for e in edn_exams.load(planning()):
        d = (dt.date.fromisoformat(e["date"]) - t).days
        if d >= 0:
            out.append({"cle": e["id"], "type": e["type"], "court": {"partiel": "Partiel", "edn": "EDN", "ecos": "ECOS"}.get(e["type"], e["nom"] if len(e["nom"]) <= 20 else e["nom"][:19].rstrip() + "…"),
                        "nom": e["nom"], "date": e["date"], "estime": e["estime"], "note": e["note"], "jours": d})
    return sorted(out, key=lambda x: x["jours"])[:4]


def exams_view(kb):
    cats = [r["category"] for r in edn_kb.categories(kb)]
    t, items = study.today(), []
    for e in edn_exams.load(planning()):
        d = (dt.date.fromisoformat(e["date"]) - t).days
        items.append(dict(e, jours=d, passe=d < 0, matieres_detail=[{"matiere": m, "categories": edn_exams.categories_for(m, cats)} for m in e["matieres"]],
                          type_nom=edn_exams.TYPES[e["type"]]))
    return {"examens": items, "types": edn_exams.TYPES, "persistant": store.read("examens.md") is not None,
            "note_planning": "Le planning de révision n'est pas recalculé automatiquement quand une date change."}


def _week_of(date):
    for w in planning()["phase_partiel"]["semaines"]:
        if w["debut"] <= date <= w["fin"]:
            return w
    return None


def planning_view():
    pl, g, t = planning(), gardes(), study.today().isoformat()
    weeks = []
    for w in pl["phase_partiel"]["semaines"]:
        gs = [x for x in g["gardes"] if w["debut"] <= x["debut_date"] <= w["fin"] or w["debut"] <= x["jour_recuperation"] <= w["fin"]]
        weeks.append(dict(w, gardes=gs, courante=w["debut"] <= t <= w["fin"], passee=w["fin"] < t))
    return {"aujourd_hui": t, "meta": pl["meta"], "semaines": weeks, "phase_partiel": {k: v for k, v in pl["phase_partiel"].items() if k != "semaines"},
            "phase_edn_tour": pl["phase_edn_tour"], "journee_sprint": pl["template_journee_sprint"], "phase_edn_examen": pl["phase_edn_examen"],
            "phase_edn_rattrapage": pl["phase_edn_rattrapage"], "regles": pl["regles_transversales"], "gardes": g}


def deck_progress():
    rev, meta = study.all_cards(), deck_meta()
    rows = {k: {"cle": k, "nom": v["nom"], "couleur": v["couleur"], "total": 0, "vues": 0, "mures": 0, "dues": 0} for k, v in meta.items()}
    t = study.today().isoformat()
    for c in all_cards():
        r = rows.get(c["deck"])
        if not r: continue
        r["total"] += 1
        s = rev.get(f"carte:{c['id']}")
        if s:
            r["vues"] += 1
            r["mures"] += s["interval"] >= MATURE_DAYS
            r["dues"] += s["due"] <= t
    qz = {r["cle"]: r for r in quiz_stats()["specialites"]}
    for k, r in rows.items():
        q = qz.get(k)
        r["quiz"] = {"pct": q["pct"], "niveau": q["niveau"], "sessions": q["sessions"]} if q else None
    return list(rows.values())


def summary():
    t = study.today()
    w = _week_of(t.isoformat())
    nxt = None
    if w:
        nxt = next((x for x in planning()["phase_partiel"]["semaines"] if x["s"] == w["s"] + 1), None)
    dp = deck_progress()
    prog = study.progress(14)
    return {"aujourd_hui": t.isoformat(), "profil": study.get_profile(), "echeances": _targets(), "semaine": w, "semaine_suivante": nxt,
            "cartes": {"total": sum(d["total"] for d in dp), "vues": sum(d["vues"] for d in dp), "mures": sum(d["mures"] for d in dp),
                       "dues": sum(d["dues"] for d in dp), "nouvelles": sum(d["total"] - d["vues"] for d in dp)},
            "paquets": dp, "progression": prog, "activite": activity(28), "gardes": gardes(),
            "partiel_regle": planning()["phase_partiel"]["template_semaine"], "quiz": quiz_stats()}


def activity(days):
    a = study.attempts(days)
    by = {}
    for r in a:
        d = by.setdefault(r["at"], {"date": r["at"], "n": 0, "minutes": 0})
        d["n"] += 1; d["minutes"] += r["minutes"]
    t = study.today()
    return [by.get((t - dt.timedelta(days=i)).isoformat(), {"date": (t - dt.timedelta(days=i)).isoformat(), "n": 0, "minutes": 0}) for i in range(days - 1, -1, -1)]


def progress_view(days):
    a = study.attempts(days)
    rev = study.all_cards()
    t = study.today()
    echeances = {}
    for k, v in rev.items():
        d = (dt.date.fromisoformat(v["due"]) - t).days
        echeances[max(d, 0)] = echeances.get(max(d, 0), 0) + 1
    return {"fenetre_jours": days, "progression": study.progress(days), "activite": activity(min(days, 90)), "paquets": deck_progress(),
            "a_venir": [{"jour": d, "n": echeances.get(d, 0)} for d in range(0, 15)],
            "recents": sorted(a, key=lambda r: r["at"], reverse=True)[:30], "plus_faibles": study.progress(days)["plus_faibles"], "quiz": quiz_stats()}


# ------------------------------------------------------------------ explorateur de cours

def facets(kb):
    cats = {r["category"]: r for r in edn_kb.categories(kb)}
    themes = []
    for key, label, cs in THEMES:
        themes.append({"cle": key, "nom": label, "categories": [c for c in cs if c in cats],
                       "docs": sum(cats[c]["docs"] for c in cs if c in cats), "pages": sum(cats[c]["pages"] or 0 for c in cs if c in cats)})
    spec = [{"category": c, "docs": r["docs"], "pages": r["pages"] or 0} for c, r in cats.items() if c not in SPECIALITES_HORS]
    return {"themes": themes, "specialites": sorted(spec, key=lambda x: x["category"]),
            "autres": [{"category": c, "docs": cats[c]["docs"], "pages": cats[c]["pages"] or 0} for c in SPECIALITES_HORS if c in cats]}


def _cats_for(query):
    theme = query.get("theme")
    cats = next((cs for k, _, cs in THEMES if k == theme), None)
    if query.get("category"):
        return [query["category"]]
    return cats


def search_cours(kb, query):
    q = (query.get("q") or "").strip()
    if not q:
        raise ApiError(400, "q requis")
    cats = _cats_for(query)
    limit = min(int(query.get("limit", 20) or 20), 15)
    sdd = int(query["sdd"]) if (query.get("sdd") or "").isdigit() else None
    hits = edn_kb.search(kb, q, category=cats, sdd=sdd, limit=15)
    off = int(query.get("offset", 0) or 0)
    return {"q": q, "total": len(hits), "resultats": [dict(h, lien=f"/pdf/{h['slug']}?page={h['page']}") for h in hits[off:off + 15]]}


def list_cours(kb, query):
    cats = _cats_for(query)
    out = []
    for c in (cats or [None]):
        out += edn_kb.list_docs(kb, c, query.get("q") or None, 200)
    if query.get("qualite"):
        out = [d for d in out if d["quality"] == query["qualite"]]
    off = int(query.get("offset", 0) or 0)
    return {"total": len(out), "docs": [dict(d, lien=f"/pdf/{d['slug']}") for d in out[off:off + 60]]}



# ------------------------------------------------------------------ quiz : enregistré À LA FIN, en un seul commit

QUIZ_FORMATS = {"qi": "qi", "dp": "dp", "kfp": "dp", "tcs": "tcs", "autre": "autre"}
FORT, FAIBLE, MIN_QUESTIONS = 70, 50, 5


def quiz_sessions():
    return store.read_edn("quiz.md", [])


def quiz_options(specialite=None, q=None):
    meta = deck_meta()
    if not specialite:
        st = {x["cle"]: x for x in quiz_stats()["specialites"]}
        return {"specialites": [{"cle": k, "nom": v["nom"], "quiz": st.get(k)} for k, v in meta.items()]}
    if specialite not in meta:
        raise ApiError(400, "spécialité inconnue (voir quiz_options sans paramètre)")
    return {"specialite": meta[specialite]["nom"], "cle": specialite, "categories": DECK_CATS.get(specialite, [])}


def save_quiz(body, kb=None):
    spec = body.get("specialite")
    if spec not in deck_meta():
        raise ApiError(400, f"specialite parmi {sorted(deck_meta())}")
    sujet = str(body.get("sujet", "")).strip()
    fmt = body.get("format", "qi")
    if not sujet or len(sujet) > 150: raise ApiError(400, "sujet requis (≤ 150 caractères)")
    if fmt not in QUIZ_FORMATS: raise ApiError(400, f"format parmi {sorted(QUIZ_FORMATS)}")
    qs = body.get("questions")
    if not isinstance(qs, list) or not 1 <= len(qs) <= 40: raise ApiError(400, "questions : 1 à 40")
    clean, pts, mx = [], 0.0, 0.0
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict): raise ApiError(400, f"question {i} invalide")
        p, m = q.get("points"), q.get("max", 1)
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (p, m)) or m <= 0 or not 0 <= p <= m:
            raise ApiError(400, f"question {i} : points entre 0 et max (> 0)")
        clean.append({"enonce": str(q.get("enonce", ""))[:300], "points": p, "max": m, "piege": str(q.get("piege", ""))[:400] or None, "source": str(q.get("source", ""))[:300] or None})
        pts += p; mx += m
    pct = round(100 * pts / mx)
    minutes = body.get("minutes") if isinstance(body.get("minutes"), int) and 0 <= body["minutes"] <= 600 else None
    nom = deck_meta()[spec]["nom"]
    sess = {"id": _gid("quiz"), "date": study.today().isoformat(), "specialite": spec, "sujet": sujet, "format": fmt,
            "sdd": body.get("sdd") if isinstance(body.get("sdd"), int) else None, "minutes": minutes,
            "points": round(pts, 2), "max": round(mx, 2), "pct": pct, "questions": clean}
    sessions = [sess] + quiz_sessions()
    for old in sessions[100:]:                       # borne la taille du fichier : le détail des anciens quiz est résumé
        old.pop("questions", None)
    quality = max(0, min(5, round(5 * pct / 100)))
    files, res = study.attempt_files(f"quiz:{sujet}", quality, QUIZ_FORMATS[fmt], nom, minutes, f"{_fmt(pts)}/{_fmt(mx)}")
    errs = errors()
    added = 0
    for q in clean:
        if q["points"] < q["max"]:
            errs.insert(0, {"id": _gid("err"), "date": sess["date"], "deck": spec, "text": f"[Quiz {sujet}] {q['enonce']}" + (f" — {q['piege']}" if q["piege"] else "")[:900]})
            added += 1
    files["quiz.md"] = f"# Quiz\n\n```edn\n{json.dumps(sessions, ensure_ascii=False, indent=1)}\n```\n"
    if added:
        files["erreurs.md"] = f"# Journal d'erreurs\n\n```edn\n{json.dumps(errs, ensure_ascii=False, indent=1)}\n```\n"
    r = store.write_many(files, f"quiz {sujet} {_fmt(pts)}/{_fmt(mx)}")
    return {"ok": True, "id": sess["id"], "score": f"{_fmt(pts)}/{_fmt(mx)}", "pct": pct, "niveau_session": _niveau(pct, mx),
            "erreurs_ajoutees": added, "prochaine_revision": res["prochaine_revision"], "commit": r["commit"], "bilan": quiz_stats()}


def _fmt(x):
    x = round(float(x), 2)
    return str(int(x)) if x == int(x) else str(x)


def _niveau(pct, nb):
    if nb < MIN_QUESTIONS: return "a_confirmer"
    return "fort" if pct >= FORT else "faible" if pct < FAIBLE else "moyen"


def quiz_stats():
    ss = quiz_sessions()
    meta = deck_meta()
    by = {}
    for s in reversed(ss):                            # du plus ancien au plus récent
        b = by.setdefault(s["specialite"], {"sessions": 0, "points": 0.0, "max": 0.0, "historique": []})
        b["sessions"] += 1; b["points"] += s["points"]; b["max"] += s["max"]; b["historique"].append(s["pct"])
    rows = []
    for k, b in by.items():
        pct = round(100 * b["points"] / b["max"])
        h = b["historique"]
        tend = None
        if len(h) >= 4:
            tend = "hausse" if sum(h[-2:]) / 2 - sum(h[:-2]) / len(h[:-2]) >= 5 else "baisse" if sum(h[-2:]) / 2 - sum(h[:-2]) / len(h[:-2]) <= -5 else "stable"
        rows.append({"cle": k, "nom": meta.get(k, {}).get("nom", k), "sessions": b["sessions"], "points": round(b["points"], 2), "max": round(b["max"], 2), "pct": pct,
                     "dernier": h[-1], "tendance": tend, "niveau": _niveau(pct, b["max"])})
    rows.sort(key=lambda r: r["pct"])
    sujets = {}
    for s in ss:
        x = sujets.setdefault((s["specialite"], s["sujet"]), {"specialite": s["specialite"], "sujet": s["sujet"], "points": 0.0, "max": 0.0, "n": 0, "date": s["date"]})
        x["points"] += s["points"]; x["max"] += s["max"]; x["n"] += 1
    a_retravailler = sorted(({**x, "pct": round(100 * x["points"] / x["max"])} for x in sujets.values()), key=lambda x: x["pct"])
    a_retravailler = [x for x in a_retravailler if x["pct"] < 60][:8]
    recents = [{k: v for k, v in s.items() if k != "questions"} for s in ss[:15]]
    return {"specialites": rows, "faibles": [r for r in rows if r["niveau"] == "faible"], "forts": [r for r in reversed(rows) if r["niveau"] == "fort"],
            "a_confirmer": [r for r in rows if r["niveau"] == "a_confirmer"], "sujets_a_retravailler": a_retravailler, "recents": recents,
            "total_sessions": len(ss), "regle": f"fort ≥ {FORT} %, faible < {FAIBLE} %, seulement à partir de {MIN_QUESTIONS} questions ; sinon « à confirmer »"}


# ------------------------------------------------------------------ export

def export_all():
    out = {"exporte_le": dt.datetime.now().isoformat(timespec="seconds")}
    for rel, key in (("profil.md", "profil"), ("revisions.md", "revisions"), ("cartes-perso.md", "cartes_perso"), ("erreurs.md", "erreurs")):
        out[key] = store.read_edn(rel, {} if key in ("profil", "revisions") else [])
    out["journal"] = {f["path"]: store.read(f["path"]) for f in store.list_files("journal")}
    out["notes"] = {f["path"]: store.read(f["path"]) for f in store.list_files("notes")}
    return out


# ------------------------------------------------------------------ routeur

def route(method, path, query, body, kb):
    """Renvoie (code, payload) ; None si la route n'appartient pas au tableau de bord."""
    try:
        if method == "GET":
            if path == "/api/summary": return 200, summary()
            if path == "/api/planning": return 200, planning_view()
            if path == "/api/cards": return 200, cards_view(query)
            if path == "/api/decks": return 200, {"paquets": deck_progress(), "meta": deck()["meta"]}
            if path == "/api/errors": return 200, {"erreurs": errors(), "paquets": [{"cle": k, "nom": v["nom"]} for k, v in deck_meta().items()]}
            if path == "/api/progress": return 200, progress_view(min(max(int(query.get("days", 30) or 30), 7), 180))
            if path == "/api/cours/facets": return 200, facets(kb)
            if path == "/api/cours/search": return 200, search_cours(kb, query)
            if path == "/api/cours/docs": return 200, list_cours(kb, query)
            if path == "/api/quiz": return 200, quiz_stats()
            if path == "/api/exams": return 200, exams_view(kb)
            if path == "/api/version": return 200, {"version": store.version()}
            if path == "/api/gardes": return 200, gardes()
            if path == "/api/export": return 200, export_all()
            if path == "/api/history": return 200, store.history(query.get("path"), int(query.get("n", 20) or 20))
        elif method == "POST":
            if path == "/api/cards/review": return 200, review(body)
            if path == "/api/cards/custom": return 201, add_custom(body)
            if path == "/api/errors": return 201, add_error(body)
            if path == "/api/exams": return 200, edn_exams.save(planning(), body)
            if path == "/api/cards/import": return 200, save_cards(body)
            if path == "/api/gardes/refresh":
                refresh_gardes(); return 200, gardes()
        elif method == "DELETE":
            m = re.match(r"^/api/cards/custom/([\w-]+)$", path)
            if m: return 200, delete_custom(m.group(1))
            m = re.match(r"^/api/exams/([\w-]+)$", path)
            if m: return 200, edn_exams.delete(planning(), m.group(1))
            m = re.match(r"^/api/errors/([\w-]+)$", path)
            if m: return 200, delete_error(m.group(1))
    except ApiError as e:
        return e.code, {"error": e.msg}
    except (store.StoreError, edn_exams.ExamError, ValueError) as e:
        return 400, {"error": str(e)}
    return None
