"""Suivi des révisions : profil, journal, répétition espacée (SM-2 simplifié), notes, rétroplanning.

Tout est stocké en Markdown versionné par git (edn_store) : profil.md · revisions.md · journal/AAAA-MM.md · notes/ · plans/.
Une seule utilisatrice. Stdlib uniquement.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

import edn_store as store

PROFILE_KEYS = {"nom", "exam_edn", "exam_ecos", "heures_par_semaine", "jours_off", "points_faibles", "style", "notes", "ville"}
DATE_KEYS = {"exam_edn", "exam_ecos"}
KINDS = {"dp", "qi", "tcs", "lca", "ecos", "fiche", "cours", "carte", "autre"}
LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) \| (\w+) \| ([^|]*) \| ([^|]*) \| q=(\d) \| ([^|]*) \| ?(.*)$")


def today() -> dt.date:
    return dt.date.fromisoformat(os.environ["EDN_TODAY"]) if os.environ.get("EDN_TODAY") else dt.date.today()


def _clean(x, n=200) -> str:
    return re.sub(r"[|\n\r]+", " / ", str(x or "")).strip()[:n]


# ------------------------------------------------------------------ profil

def get_profile() -> dict:
    return store.read_edn("profil.md", {})


def profile_file(values: dict):
    """Valide `values` et renvoie (texte de profil.md, profil fusionné) sans rien écrire."""
    bad = set(values) - PROFILE_KEYS
    if bad:
        raise ValueError(f"clés inconnues {sorted(bad)} ; autorisées : {sorted(PROFILE_KEYS)}")
    for k in DATE_KEYS & set(values):
        try:
            dt.date.fromisoformat(values[k])
        except (TypeError, ValueError) as e:
            raise ValueError(f"{k} : date AAAA-MM-JJ attendue") from e
    h = values.get("heures_par_semaine")
    if h is not None and not (isinstance(h, int) and not isinstance(h, bool) and 1 <= h <= 100):
        raise ValueError("heures_par_semaine : entier 1-100")
    p = {**get_profile(), **values}
    body = "\n".join(f"- **{k}** : {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(p.items()))
    return (f"# Profil\n\nValeurs fournies par l'étudiante ; une valeur absente est inconnue (jamais supposée).\n\n"
            f"```edn\n{json.dumps(p, ensure_ascii=False, indent=1, sort_keys=True)}\n```\n\n{body}\n"), p


def set_profile(values: dict) -> dict:
    text, p = profile_file(values)
    store.write("profil.md", text, "mise à jour du profil (" + ", ".join(sorted(values)) + ")")
    return p


# ------------------------------------------------------------------ journal + répétition espacée

def _journal_path(d: dt.date) -> str:
    return f"journal/{d:%Y-%m}.md"


def _read_journal(month_path: str) -> list[str]:
    t = store.read(month_path, "")
    return [l for l in t.splitlines() if l.startswith("- ")]


def all_cards() -> dict:
    return _cards()


def _cards() -> dict:
    return store.read_edn("revisions.md", {})


def _render_cards(cards: dict) -> str:
    rows = "\n".join(f"| {k} | {v.get('category') or ''} | {v['due']} | {v['interval']} j | {v['lapses']} |"
                     for k, v in sorted(cards.items(), key=lambda kv: kv[1]["due"]))
    return ("# Révisions espacées\n\nCalendrier calculé (SM-2 simplifié) : ne pas éditer à la main.\n\n"
            f"```edn\n{json.dumps(cards, ensure_ascii=False, indent=1, sort_keys=True)}\n```\n\n"
            f"| Élément | Spécialité | Prochaine révision | Intervalle | Échecs |\n|---|---|---|---|---|\n{rows}\n")


def attempt_files(item, quality, kind="autre", category=None, minutes=None, note=None, _cards_state=None, _journal_lines=None):
    """Calcule (sans écrire) les fichiers journal + révisions après un exercice. Renvoie (fichiers, résultat)."""
    if kind not in KINDS:
        raise ValueError(f"kind parmi {sorted(KINDS)}")
    t, item = today(), _clean(item)
    if not item:
        raise ValueError("item vide")
    jp = _journal_path(t)
    lines = list(_journal_lines) if _journal_lines is not None else _read_journal(jp)
    lines.append(f"- {t.isoformat()} | {kind} | {_clean(category, 60)} | {item} | q={quality} | {minutes if minutes is not None else ''} | {_clean(note, 600)}")
    cards = dict(_cards_state) if _cards_state is not None else _cards()
    c = cards.get(item, {"ease": 2.5, "interval": 0, "reps": 0, "lapses": 0, "category": None})
    ease, interval, reps, lapses = c["ease"], c["interval"], c["reps"], c["lapses"]
    if quality < 3:
        reps, interval, lapses = 0, 1, lapses + 1
    else:
        reps += 1
        interval = 1 if reps == 1 else 3 if reps == 2 else max(1, round(interval * ease))
    ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    due = (t + dt.timedelta(days=interval)).isoformat()
    cards[item] = {"ease": round(ease, 3), "interval": interval, "reps": reps, "lapses": lapses,
                   "due": due, "category": _clean(category, 60) or c.get("category")}
    files = {jp: f"# Journal {t:%Y-%m}\n\nFormat : date | type | spécialité | élément | q=qualité 0-5 | minutes | note\n\n" + "\n".join(lines) + "\n",
             "revisions.md": _render_cards(cards)}
    return files, {"item": item, "prochaine_revision": due, "intervalle_jours": interval, "facilite": round(ease, 2)}


def log_attempt(item, quality, kind="autre", category=None, minutes=None, note=None) -> dict:
    """quality 0-5 (0 trou noir · 3 juste mais difficile · 5 facile). Écrit le journal et planifie la prochaine révision."""
    files, res = attempt_files(item, quality, kind, category, minutes, note)
    store.write_many(files, f"{kind} {res['item']} q={quality}")
    return res


def due_reviews(limit=15, category=None) -> list:
    t = today()
    rows = [dict(item=k, category=v.get("category"), due=v["due"], interval=v["interval"], lapses=v["lapses"],
                 retard_jours=(t - dt.date.fromisoformat(v["due"])).days)
            for k, v in _cards().items() if v["due"] <= t.isoformat()
            and (not category or (v.get("category") or "").lower() == category.lower())]
    return sorted(rows, key=lambda r: (r["due"], -r["lapses"]))[: max(1, min(limit, 50))]


def attempts(days=14) -> list[dict]:
    t = today()
    since = t - dt.timedelta(days=days)
    months = sorted({_journal_path(since + dt.timedelta(days=i)) for i in range(0, days + 1, 7)} | {_journal_path(since), _journal_path(t)})
    out = []
    for mp in months:
        for l in _read_journal(mp):
            m = LINE.match(l)
            if m and m.group(1) >= since.isoformat():
                out.append(dict(at=m.group(1), kind=m.group(2), category=m.group(3).strip() or "?", item=m.group(4).strip(),
                                quality=int(m.group(5)), minutes=int(m.group(6)) if m.group(6).strip().isdigit() else 0))
    return out


def progress(days=14) -> dict:
    a = attempts(days)
    by_kind, by_cat = {}, {}
    for r in a:
        k = by_kind.setdefault(r["kind"], [0, 0, 0]); k[0] += 1; k[1] += r["quality"]; k[2] += r["minutes"]
        c = by_cat.setdefault(r["category"], [0, 0]); c[0] += 1; c[1] += r["quality"]
    cards = _cards()
    return {"fenetre_jours": days,
            "par_type": [{"kind": k, "n": v[0], "moy": round(v[1] / v[0], 2), "minutes": v[2]} for k, v in sorted(by_kind.items())],
            "plus_faibles": sorted(({"category": k, "n": v[0], "moy": round(v[1] / v[0], 2)} for k, v in by_cat.items() if v[0] >= 2 and v[1] / v[0] < 3.5),
                                   key=lambda r: r["moy"])[:6],
            "cartes": len(cards), "a_reviser_aujourd_hui": sum(1 for v in cards.values() if v["due"] <= today().isoformat())}


# ------------------------------------------------------------------ notes (traces durables, sources obligatoires)

def _slug(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80] or "note"


def save_note(title: str, content: str, sources: list) -> dict:
    """Enregistre une fiche/réponse. `sources` obligatoire : cours [Catégorie — Titre, p.N] et/ou URL + année + date de consultation."""
    srcs = [s.strip() for s in sources if isinstance(s, str) and s.strip()]
    if not srcs:
        raise ValueError("au moins une source est obligatoire (cours avec page, ou URL officielle avec année)")
    rel = f"notes/{_slug(title)}.md"
    existing = store.read(rel)
    body = f"# {title.strip()}\n\n{content.strip()}\n\n## Sources\n" + "\n".join(f"- {s}" for s in srcs) + "\n"
    r = store.write(rel, body, "mise à jour" if existing else "nouvelle note")
    return r | {"remplace_une_note": existing is not None}


# ------------------------------------------------------------------ rétroplanning

def plan_backwards(kb, exam_date=None, hours_per_week=None, save=False) -> dict:
    """Rétroplanning déterministe : phases proportionnelles au temps restant ; spécialités pondérées par le volume de cours
    et majorées par les points faibles mesurés. Un plan de départ à ajuster, pas un protocole publié."""
    p = get_profile()
    ex = exam_date or p.get("exam_edn")
    if not ex:
        raise ValueError("date de l'épreuve inconnue : la demander à l'étudiante (set_profile exam_edn) ; ne pas la supposer")
    exam = dt.date.fromisoformat(ex)
    hpw = hours_per_week or p.get("heures_par_semaine")
    if not hpw:
        raise ValueError("heures_par_semaine inconnu : le demander à l'étudiante (set_profile) ; ne pas le supposer")
    days = (exam - today()).days
    if days <= 0:
        raise ValueError("la date de l'épreuve est passée ou aujourd'hui")
    weeks = max(1, -(-days // 7))
    if weeks <= 2:
        phases = [("dernière ligne droite : annales, erreurs récurrentes, sommeil", weeks)]
    else:
        last = max(1, round(weeks * 0.12)); lca = max(1, round(weeks * 0.12)) if weeks >= 8 else 0
        train = max(1, round(weeks * 0.30)); core = weeks - last - lca - train
        phases = [(n, w) for n, w in [("consolidation des cours par spécialité (SdD rang A d'abord)", core),
                                       ("entraînement DP / QI / TCS chronométré", train),
                                       ("LCA : lecture d'articles + épreuves types", lca),
                                       ("dernière ligne droite : annales, erreurs récurrentes, sommeil", last)] if w > 0]
    weak = {r["category"]: r["moy"] for r in progress(30)["plus_faibles"]}
    skip = ("Masterclass", "Cours publics", "Entrainement", "LCA", "Divers", "Méthodologie ECOS", "Entrainements aux ECOS",
            "Coaching et Méthodologie")
    w8 = sorted(((r["category"], (r["pages"] or 1) * (1.5 if weak.get(r["category"], 5) < 3 else 1)) for r in kb
                 if r["category"] not in skip), key=lambda x: -x[1])
    schedule, wk, start = [], 0, today()
    for name, n in phases:
        for _ in range(n):
            focus = [w8[(wk * 2 + j) % len(w8)][0] for j in range(2)] if name.startswith("consolidation") else []
            schedule.append({"semaine": wk + 1, "debut": (start + dt.timedelta(days=7 * wk)).isoformat(), "phase": name,
                             "focus": focus, "heures": hpw})
            wk += 1
    res = {"epreuve": exam.isoformat(), "jours_restants": days, "semaines": weeks, "heures_par_semaine": hpw,
           "repartition_hebdo": "≈ 60 % cours/fiches, 30 % questions chronométrées, 10 % révisions dues (due_reviews)",
           "plan": schedule}
    if save:
        rows = "\n".join(f"| {s['semaine']} | {s['debut']} | {s['phase']} | {', '.join(s['focus']) or '—'} | {s['heures']} h |" for s in schedule)
        res["enregistre"] = store.write(f"plans/plan-{today().isoformat()}.md",
            f"# Rétroplanning au {today().isoformat()}\n\nÉpreuve : {exam.isoformat()} · {weeks} semaines · {hpw} h/semaine. Trame calculée, "
            f"à ajuster (non issue d'un protocole publié).\n\n| Sem. | Début | Phase | Focus | Heures |\n|---|---|---|---|---|\n{rows}\n",
            f"plan jusqu'au {exam.isoformat()}")
    return res
