"""Examens (partiels de l'année, EDN écrit, ECOS oral, autres) : dates, matières, tout modifiable. Stocké dans le suivi git (examens.md).

Tant que `examens.md` n'existe pas, la liste vient du planning de référence (partiel du 16/02/2027 + EDN estimé) ; la première modification
la rend persistante. Les dates de l'EDN et des ECOS restent synchronisées avec le profil (exam_edn / exam_ecos), qu'utilise le rétroplanning.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets
import time
import unicodedata

import edn_store as store
import edn_study as study

TYPES = {"partiel": "Partiel", "edn": "EDN (écrit)", "ecos": "ECOS (oral)", "autre": "Autre examen"}
UNIQUE = {"edn", "ecos"}                     # une seule date par type : elle vit aussi dans le profil
HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ALIAS = {"reanimation": "Anesthésie-réanimation", "geriatrie": "Gériatrie", "readaptation": "MPR", "maxillo": "Chirurgie maxillo-faciale"}


class ExamError(ValueError):
    pass


def _norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()


def _gid() -> str:
    return f"exam-{int(time.time()):x}{secrets.token_hex(2)}"


def seeds(planning: dict) -> list[dict]:
    """Examens par défaut, tirés du planning de référence. L'EDN n'est une date confirmée que si le profil la contient."""
    prof, m = study.get_profile(), planning["meta"]
    out = [{"id": "exam-partiel", "type": "partiel", "nom": "Partiel — " + ", ".join(m["cible_immediate"]["matieres"][:2]) + "…", "date": m["cible_immediate"]["date"],
            "heure": None, "matieres": m["cible_immediate"]["matieres"], "lieu": None, "note": None, "estime": False}]
    out.append({"id": "exam-edn", "type": "edn", "nom": "EDN — épreuves écrites", "date": prof.get("exam_edn") or m["cible_principale"]["date_estimee_ordre_de_grandeur"],
                "heure": None, "matieres": [], "lieu": None, "note": None if prof.get("exam_edn") else "Date estimée : le CNG ne l'a pas encore publiée.", "estime": not prof.get("exam_edn")})
    if prof.get("exam_ecos"):
        out.append({"id": "exam-ecos", "type": "ecos", "nom": "ECOS — épreuve orale", "date": prof["exam_ecos"], "heure": None, "matieres": [], "lieu": None, "note": None, "estime": False})
    return out


def load(planning: dict) -> list[dict]:
    items = store.read_edn("examens.md", None)
    return sorted(items if items is not None else seeds(planning), key=lambda e: (e["date"], e["id"]))


def _render(items: list[dict]) -> str:
    rows = "\n".join(f"| {e['date']} | {e.get('heure') or ''} | {TYPES[e['type']]} | {e['nom']} | {', '.join(e['matieres'])} |" for e in sorted(items, key=lambda e: e["date"]))
    return ("# Examens\n\nModifiables depuis le site (onglet Examens) ou avec les outils save_exam / delete_exam.\n\n"
            f"```edn\n{json.dumps(items, ensure_ascii=False, indent=1)}\n```\n\n| Date | Heure | Type | Nom | Matières |\n|---|---|---|---|---|\n{rows}\n")


def clean(body: dict, existing: dict | None = None) -> dict:
    """Valide une fiche d'examen ; `existing` = fiche à modifier (les champs absents sont conservés)."""
    e = dict(existing or {"matieres": [], "heure": None, "lieu": None, "note": None, "estime": False})
    t = body.get("type", e.get("type"))
    if t not in TYPES:
        raise ExamError(f"type parmi {sorted(TYPES)}")
    e["type"] = t
    if "nom" in body or "nom" not in e:
        nom = str(body.get("nom") or TYPES[t]).strip()
        if not nom or len(nom) > 100:
            raise ExamError("nom requis (≤ 100 caractères)")
        e["nom"] = nom
    if "date" in body or "date" not in e:
        try:
            dt.date.fromisoformat(str(body.get("date")))
        except ValueError as err:
            raise ExamError("date : AAAA-MM-JJ attendue") from err
        e["date"] = str(body["date"])
    if "heure" in body:
        h = body["heure"]
        if h not in (None, "") and not HEURE.match(str(h)):
            raise ExamError("heure : HH:MM (24 h)")
        e["heure"] = h or None
    if "matieres" in body:
        ms = body["matieres"]
        if not isinstance(ms, list) or len(ms) > 20 or not all(isinstance(x, str) and 0 < len(x.strip()) <= 100 for x in ms):
            raise ExamError("matieres : liste de 20 textes maximum (≤ 100 caractères chacun)")
        e["matieres"] = list(dict.fromkeys(x.strip() for x in ms))
    for k, n in (("lieu", 100), ("note", 300)):
        if k in body:
            v = str(body[k] or "").strip()
            if len(v) > n:
                raise ExamError(f"{k} : {n} caractères maximum")
            e[k] = v or None
    if "estime" in body:
        e["estime"] = bool(body["estime"])
    return e


def save(planning: dict, body: dict) -> dict:
    """Crée ou modifie un examen (par `id`, ou — pour edn/ecos — par type). Un seul commit : examens.md (+ profil.md pour edn/ecos)."""
    items = load(planning)
    eid = body.get("id")
    cur = next((x for x in items if x["id"] == eid), None) if eid else None
    if eid and not cur:
        raise ExamError(f"examen inconnu : {eid}")
    t = body.get("type", cur["type"] if cur else None)
    if not cur and t in UNIQUE:                                   # edn / ecos : on met à jour l'entrée existante du même type
        cur = next((x for x in items if x["type"] == t), None)
    if cur and t in UNIQUE and cur["type"] != t:
        raise ExamError("le type d'un examen EDN / ECOS ne se change pas : supprime-le et recrée-le")
    new = clean(body, cur)
    new["id"] = cur["id"] if cur else (f"exam-{t}" if t in UNIQUE else _gid())
    if t in UNIQUE and body.get("estime") is None and cur and cur["date"] != new["date"]:
        new["estime"] = False                                    # une date saisie explicitement n'est plus une estimation
    items = [x for x in items if x["id"] != new["id"]] + [new]
    files = {"examens.md": _render(sorted(items, key=lambda e: e["date"]))}
    if t in UNIQUE and not new["estime"]:
        files["profil.md"] = study.profile_file({"exam_edn" if t == "edn" else "exam_ecos": new["date"]})[0]
    r = store.write_many(files, f"examen {new['nom']} ({new['date']})")
    return {"ok": True, "examen": new, "commit": r["commit"], "cree": cur is None}


def delete(planning: dict, eid: str) -> dict:
    items = load(planning)
    gone = next((x for x in items if x["id"] == eid), None)
    if not gone:
        raise ExamError(f"examen inconnu : {eid}")
    r = store.write_many({"examens.md": _render([x for x in items if x["id"] != eid])}, f"suppression examen {gone['nom']}")
    return {"ok": True, "supprime": gone["nom"], "commit": r["commit"]}


def sync_from_profile(planning: dict, values: dict) -> None:
    """set_profile(exam_edn / exam_ecos) met aussi à jour la fiche d'examen correspondante (sans doubler le profil)."""
    for key, t, nom in (("exam_edn", "edn", "EDN — épreuves écrites"), ("exam_ecos", "ecos", "ECOS — épreuve orale")):
        if key in values:
            items = load(planning)
            cur = next((x for x in items if x["type"] == t), None)
            if not cur or cur["date"] != values[key] or cur["estime"]:
                save(planning, {"type": t, "nom": cur["nom"] if cur else nom, "date": values[key], "estime": False})


def categories_for(matiere: str, cats: list[str]) -> list[str]:
    """Catégories de cours qui correspondent à une matière d'examen (pour proposer le lien vers les cours)."""
    n, out = _norm(matiere), []
    for c in cats:
        if _norm(c) in n or n in _norm(c):
            out.append(c)
    for k, c in ALIAS.items():
        if k in n and c in cats and c not in out:
            out.append(c)
    return out
