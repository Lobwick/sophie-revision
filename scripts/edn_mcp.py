#!/usr/bin/env python3
"""Serveur MCP « coach internat » — bibliothèque standard uniquement. MCP Streamable HTTP sans état, réponses JSON.

Trois couches : INSTRUCTIONS (agents + skills du dépôt), COURS (recherche plein texte dans la base extraite des PDF,
renvoie des extraits courts pour économiser les tokens), SUIVI (profil, tentatives, répétition espacée, rétroplanning).

Sécurité : jeton obligatoire (refus de démarrer sans), comparé à temps constant, accepté en en-tête `X-Api-Key`,
`Authorization: Bearer` ou préfixe d'URL `/t/<jeton>/mcp` (pour les clients sans champ d'en-tête) ; corps ≤ 200 Ko ;
entrées validées ; aucun accès fichier hors de agents/ et skills/ ; jamais de trace d'erreur renvoyée.
"""
import hmac
import http.server
import json
import logging
import os
import re
import socketserver
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edn_dash  # noqa: E402
import edn_exams  # noqa: E402
import edn_kb  # noqa: E402
import edn_site  # noqa: E402
import edn_store  # noqa: E402
import edn_study  # noqa: E402

log = logging.getLogger("edn-mcp")
ROOT = edn_kb.ROOT
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_BODY = 200_000
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,50}$")
SERVER_INFO = {"name": "coach-internat", "version": "1.0.0"}
INSTRUCTIONS = (
    "Coach de révision EDN + ECOS (internat de médecine). Commence par `list_skills` / `get_skill` pour la procédure demandée "
    "(`/fiche`, `/quiz`, `/ecos`, `/lca`, `/revision-du-jour`…) et `get_agent` pour adopter le rôle (planificateur, tuteur, "
    "examinateur, coach de spécialité). Appuie TOUT contenu médical sur `search_cours` / `get_cours` (cours de l'étudiante, "
    "cités avec titre et page) puis, si tu as la recherche web, vérifie sur les sources officielles (HAS, collèges, CEC) et "
    "signale toute divergence. Enregistre chaque exercice avec `log_attempt`. Outil de révision : aucun avis clinique réel.")


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def _str(desc, **kw):
    return {"type": "string", "description": desc, **kw}


def _int(desc, **kw):
    return {"type": "integer", "description": desc, **kw}


def obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


def validate(v, s, path="arguments"):
    t = s.get("type")
    py = {"string": str, "object": dict, "array": list, "boolean": bool}
    if t == "integer":
        ok = isinstance(v, int) and not isinstance(v, bool)
    elif t in py:
        ok = isinstance(v, py[t]) and (t == "boolean" or not isinstance(v, bool))
    else:
        ok = True
    if not ok:
        raise RpcError(-32602, f"{path} : type {t} attendu")
    if "enum" in s and v not in s["enum"]:
        raise RpcError(-32602, f"{path} : valeur parmi {s['enum']}")
    if t == "string" and len(v) > s.get("maxLength", 4000):
        raise RpcError(-32602, f"{path} : trop long")
    if t == "integer":
        if "minimum" in s and v < s["minimum"] or "maximum" in s and v > s["maximum"]:
            raise RpcError(-32602, f"{path} : hors bornes")
    if t == "object":
        for k in s.get("required", []):
            if k not in v:
                raise RpcError(-32602, f"{path}.{k} requis")
        for k, x in v.items():
            if k not in s["properties"]:
                raise RpcError(-32602, f"{path}.{k} inconnu")
            validate(x, s["properties"][k], f"{path}.{k}")


# ---------------------------------------------------------------- instructions (agents, skills)

def _frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[m.end():] if m else text


def _files(kind):
    d = ROOT / kind
    if kind == "agents":
        return {p.stem: p for p in sorted(d.glob("*.md")) if not p.stem.startswith("_")}
    return {p.parent.name: p for p in sorted(d.glob("*/SKILL.md"))}


def list_instr(kind):
    return [{"name": n, "description": _frontmatter(p.read_text("utf-8"))[0].get("description", "")} for n, p in _files(kind).items()]


def get_instr(kind, name):
    if not NAME.match(name):
        raise RpcError(-32602, "nom invalide")
    p = _files(kind).get(name)
    if not p:
        raise RpcError(-32602, f"{kind[:-1]} inconnu : {name} (voir list_{kind})")
    body = _frontmatter(p.read_text("utf-8"))[1].strip()
    common = ROOT / "agents" / "_commun.md"
    return body + "\n\n" + common.read_text("utf-8").strip() if kind == "agents" and common.exists() else body


# ---------------------------------------------------------------- outils

class Registry:
    def __init__(self):
        self.kb = edn_kb.connect()
        self.dense = edn_kb.Dense() if os.environ.get("EDN_EMB_TAG") else None  # sémantique : opt-in
        self.tools = {}
        self._register()

    def tool(self, name, desc, schema, fn, read_only=True):
        self.tools[name] = {"def": {"name": name, "description": desc, "inputSchema": schema,
                                    "annotations": {"readOnlyHint": read_only, "openWorldHint": False}}, "fn": fn}

    def _register(self):
        kb, T = self.kb, self.tool
        T("list_skills", "Liste les skills (commandes) disponibles.", obj({}), lambda a: list_instr("skills"))
        T("get_skill", "Texte d'un skill : la procédure à suivre.", obj({"name": _str("nom du skill")}, ["name"]),
          lambda a: get_instr("skills", a["name"]))
        T("list_agents", "Liste les agents (rôles) : planificateur, tuteur, examinateur, coachs de spécialité.", obj({}),
          lambda a: list_instr("agents"))
        T("get_agent", "Instructions d'un agent à adopter.", obj({"name": _str("nom de l'agent")}, ["name"]),
          lambda a: get_instr("agents", a["name"]))
        T("list_categories", "Spécialités/catégories de cours avec nombre de documents et de pages.", obj({}),
          lambda a: edn_kb.categories(kb))
        T("list_cours", "Liste les documents de cours (filtre par catégorie ou mot du titre) avec le lien du PDF.",
          obj({"category": _str("ex. Cardiologie, Situations de départ"), "query": _str("mot du titre"),
               "limit": _int("max 200", minimum=1, maximum=200)}),
          lambda a: [d | {"lien": edn_site.page_link(d["slug"])} for d in edn_kb.list_docs(kb, a.get("category"), a.get("query"), a.get("limit", 60))])
        T("search_cours", "Recherche plein texte dans les cours de l'étudiante (PDF + texte des images par OCR). Renvoie des extraits courts "
          "(slug + page) ; lis ensuite avec get_cours AVANT d'affirmer. Si `resultats` est vide ou insuffisant : chercher sur internet "
          "(sources officielles) et le dire ; ne jamais combler de mémoire. Essaie 2 formulations (termes médicaux, synonymes).",
          obj({"query": _str("mots-clés", maxLength=300), "category": _str("limiter à une catégorie"),
               "sdd": _int("limiter à une situation de départ", minimum=1, maximum=400),
               "limit": _int("1-15, défaut 6", minimum=1, maximum=15)}, ["query"]),
          self._search)
        T("get_cours", "Lit un cours (slug) ou une situation de départ (sdd) page par page. `suite` donne la page suivante.",
          obj({"slug": _str("slug issu de search/list"), "sdd": _int("numéro de SdD", minimum=1, maximum=400),
               "page_from": _int("défaut 1", minimum=1), "page_to": _int("dernière page", minimum=1),
               "max_chars": _int("défaut 12000", minimum=1000, maximum=40000)}),
          self._get_cours)
        keys = sorted(edn_dash.deck_meta())
        T("find_cards", "Retrouve des cartes par mots du recto/verso/mots-clés (pour corriger une carte : récupère son `id`, puis save_cards). Max 10 résultats.",
          obj({"query": _str("mots recherchés", maxLength=200), "deck": _str("clé de paquet (facultatif)", enum=keys), "limit": _int("1-10", minimum=1, maximum=10)}, ["query"]),
          lambda a: [{"id": c["id"], "paquet": c["deck"], "rang": c["rang"], "question": c["question"], "reponse": c["answer"], "statut": c["verification"].get("statut")}
                     for c in edn_dash.cards_view({"q": a["query"], "deck": a.get("deck"), "limit": a.get("limit", 10)})["cartes"]])
        T("get_card", "Une carte du deck (question, réponse, statut de vérification et sources). Les révisions dues renvoient des éléments « carte:<id> » : "
          "passe l'<id> ici. Statuts : corrigee / completee (corrigée après vérification), confirmee_cours, relue (à recouper avec le cours), perso.",
          obj({"id": _str("ex. cardio-002", maxLength=60)}, ["id"]), self._get_card)
        T("quiz_options", "Menu du quiz. Sans paramètre : les 20 spécialités (clé, nom, résultats déjà obtenus). Avec `specialite` (clé) : ses catégories de cours, "
          "pour proposer des items (list_cours / search_cours) et choisir le sujet.",
          obj({"specialite": _str("clé de spécialité", enum=keys)}), lambda a: edn_dash.quiz_options(a.get("specialite")))
        T("save_quiz", "À appeler UNE FOIS, à la FIN du quiz : enregistre le score, les erreurs (journal d'erreurs) et la prochaine révision, et renvoie le bilan "
          "(forts / faibles par spécialité). `points` entre 0 et `max` par question ; `piege` = l'erreur à retenir ; `source` = [Catégorie — Titre, p.N].",
          obj({"specialite": _str("clé de spécialité (voir quiz_options)", enum=keys), "sujet": _str("item ou sujet, ex. « SDD 51 Obésité »", maxLength=150),
               "format": _str("format des questions", enum=["qi", "dp", "kfp", "tcs", "autre"]), "sdd": _int("numéro de SdD (facultatif)", minimum=1, maximum=400),
               "minutes": _int("durée totale (facultatif)", minimum=0, maximum=600),
               "questions": {"type": "array", "maxItems": 40, "items": {"type": "object", "properties": {
                   "enonce": _str("énoncé abrégé", maxLength=300), "points": {"type": "number"}, "max": {"type": "number"},
                   "piege": _str("erreur à retenir", maxLength=400), "source": _str("source", maxLength=300)}, "required": ["enonce", "points"], "additionalProperties": False}}},
              ["specialite", "sujet", "questions"]),
          lambda a: edn_dash.save_quiz(a), read_only=False)
        T("list_exams", "Examens enregistrés (partiel, EDN écrit, ECOS oral, autres) : date, heure, matières, lieu, J-n. Sans fichier, liste par défaut du planning.",
          obj({}), lambda a: edn_dash.exams_view(kb))
        T("save_exam", "Crée ou modifie un examen (visible dans l'onglet Examens du site). Modifier : passer `id` (voir list_exams). `type` edn / ecos : une seule fiche, "
          "synchronisée avec le profil (exam_edn / exam_ecos). Les champs absents sont conservés. `matieres` = liste des matières de CE jour. Ne jamais deviner une date.",
          obj({"id": _str("id d'un examen existant", maxLength=60), "type": _str("type", enum=sorted(edn_exams.TYPES)), "nom": _str("ex. « Partiel 5e année — bloc 2 »", maxLength=100),
               "date": _str("AAAA-MM-JJ"), "heure": _str("HH:MM (facultatif)", maxLength=5), "matieres": {"type": "array", "items": {"type": "string", "maxLength": 100}, "maxItems": 20},
               "lieu": _str("facultatif", maxLength=100), "note": _str("facultatif", maxLength=300), "estime": {"type": "boolean", "description": "true = date à confirmer"}}),
          lambda a: edn_exams.save(edn_dash.planning(), a), read_only=False)
        T("delete_exam", "Supprime un examen (l'historique git garde la trace ; undo_last_change annule).", obj({"id": _str("id de l'examen", maxLength=60)}, ["id"]),
          lambda a: edn_exams.delete(edn_dash.planning(), a["id"]), read_only=False)
        T("save_cards", "Ajoute de NOUVELLES cartes ou CORRIGE des cartes existantes (texte ou JSON déjà converti en liste). Sans `id` : nouvelle carte (deck, question, answer obligatoires ; "
          "doublon refusé). Avec `id` d'une carte du deck : correction persistante, `motif` OBLIGATOIRE (+ `sources` conseillées). Avec `id` d'une carte perso : modification directe. "
          "Appelle d'abord avec apercu=true, montre le résultat, puis confirme avant d'écrire.",
          obj({"apercu": {"type": "boolean", "description": "true = ne rien écrire, montrer le résultat"},
               "cartes": {"type": "array", "maxItems": 100, "items": {"type": "object", "additionalProperties": False, "properties": {
                   "id": _str("carte existante à corriger", maxLength=60), "deck": _str("clé du paquet", enum=keys), "rang": _str("A ou B", enum=["A", "B"]),
                   "question": _str("recto", maxLength=600), "answer": _str("verso", maxLength=2000), "item": _str("n° d'item (facultatif)", maxLength=40),
                   "tags": {"type": "array", "items": {"type": "string", "maxLength": 40}, "maxItems": 8}, "motif": _str("pourquoi cette correction", maxLength=400),
                   "sources": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 10}}}}}, ["cartes"]),
          lambda a: edn_dash.save_cards(a), read_only=False)
        T("get_profile", "Profil de l'étudiante : dates des épreuves, heures/semaine, points faibles, style. Une clé absente = inconnue.", obj({}),
          lambda a: edn_study.get_profile())
        T("set_profile", "Met à jour le profil (clés : %s). Dates AAAA-MM-JJ. Écrit profil.md et commite." % ", ".join(sorted(edn_study.PROFILE_KEYS)),
          obj({"values": {"type": "object", "description": "clés→valeurs", "properties": {k: {} for k in edn_study.PROFILE_KEYS},
                          "additionalProperties": False}}, ["values"]),
          self._set_profile, read_only=False)
        T("log_attempt", "Enregistre un exercice/une révision (journal/AAAA-MM.md, commité) et planifie la prochaine (répétition espacée). "
          "quality 0 = trou noir · 2 = raté · 3 = juste mais difficile · 4 = bien · 5 = facile.",
          obj({"item": _str("ex. 'SDD 51 Obésité' ou 'Cardio: IAo — indications chirurgicales'", maxLength=200),
               "quality": _int("0-5", minimum=0, maximum=5), "kind": _str("type d'exercice", enum=sorted(edn_study.KINDS)),
               "category": _str("spécialité"), "minutes": _int("durée", minimum=0, maximum=600), "note": _str("erreur/piège à retenir", maxLength=600)},
              ["item", "quality"]),
          lambda a: edn_study.log_attempt(a["item"], a["quality"], a.get("kind", "autre"), a.get("category"), a.get("minutes"), a.get("note")),
          read_only=False)
        T("due_reviews", "Éléments à réviser aujourd'hui (en retard d'abord).",
          obj({"limit": _int("défaut 15", minimum=1, maximum=50), "category": _str("filtre")}),
          lambda a: edn_study.due_reviews(a.get("limit", 15), a.get("category")))
        T("progress", "Bilan des N derniers jours : volume et moyenne par type, spécialités les plus faibles, cartes dues.",
          obj({"days": _int("défaut 14", minimum=1, maximum=180)}), lambda a: edn_study.progress(a.get("days", 14)))
        T("plan_backwards", "Rétroplanning jusqu'à l'épreuve (profil exam_edn + heures_par_semaine, ou paramètres). Refuse de supposer une "
          "date ou un volume horaire inconnus. save=true l'écrit dans plans/ (commité).",
          obj({"exam_date": _str("AAAA-MM-JJ"), "hours_per_week": _int("heures", minimum=1, maximum=100), "save": {"type": "boolean"}}),
          lambda a: edn_study.plan_backwards(edn_kb.categories(kb), a.get("exam_date"), a.get("hours_per_week"), a.get("save", False)),
          read_only=False)
        T("save_note", "Enregistre une fiche ou une réponse sous notes/ (commité, historisé). `sources` OBLIGATOIRE : cours "
          "« [Catégorie — Titre, p.N] » et/ou URL officielle + année + date de consultation.",
          obj({"title": _str("titre", maxLength=120), "content": _str("Markdown, sans section Sources", maxLength=60000),
               "sources": {"type": "array", "items": {"type": "string"}, "maxItems": 40}}, ["title", "content", "sources"]),
          lambda a: edn_study.save_note(a["title"], a["content"], a["sources"]), read_only=False)
        T("list_files", "Liste les fichiers de suivi (journal, notes, plans, profil, revisions).",
          obj({"directory": _str("journal | notes | plans (vide = tout)", enum=["", "journal", "notes", "plans"])}),
          lambda a: edn_store.list_files(a.get("directory", "")))
        T("read_file", "Lit un fichier de suivi (profil.md, revisions.md, journal/…, notes/…, plans/…).",
          obj({"path": _str("chemin relatif", maxLength=140)}, ["path"]), self._read_file)
        T("history", "Historique git des modifications du suivi (tout, ou un fichier). Chaque écriture est un commit « [coach] ».",
          obj({"path": _str("fichier (facultatif)", maxLength=140), "n": _int("1-50, défaut 15", minimum=1, maximum=50)}),
          lambda a: edn_store.history(a.get("path"), a.get("n", 15)))
        T("undo_last_change", "Annule le dernier changement du suivi s'il a été fait par ce coach (git revert ; rien n'est supprimé).",
          obj({}), lambda a: edn_store.undo_last_change(), read_only=False)

    def _set_profile(self, a):
        p = edn_study.set_profile(a["values"])
        edn_exams.sync_from_profile(edn_dash.planning(), a["values"])      # exam_edn / exam_ecos => fiche d'examen correspondante
        return p

    def _get_card(self, a):
        cid = a["id"].removeprefix("carte:")
        c = next((x for x in edn_dash.all_cards() if x["id"] == cid), None)
        if not c:
            raise ValueError(f"carte inconnue : {cid}")
        v = c.get("verification", {})
        return {"id": c["id"], "paquet": edn_dash.deck_meta().get(c["deck"], {}).get("nom"), "rang": c["rang"], "question": c["question"], "reponse": c["answer"],
                "verification": {k: v.get(k) for k in ("statut", "motif", "remarque", "sources_cours", "sources_web", "page_proche") if v.get(k)}}

    def _read_file(self, a):
        t = edn_store.read(a["path"])
        if t is None:
            raise ValueError(f"fichier absent : {a['path']} (voir list_files)")
        return t

    def _search(self, a):
        hits = edn_kb.search(self.kb, a["query"], a.get("category"), a.get("sdd"), a.get("limit", 6), self.dense)
        for h in hits:
            h["lien"] = edn_site.page_link(h["slug"], h["page"])
        r = {"source": "cours de l'étudiante (base locale) — citer [Catégorie — Titre, p.N](lien)", "resultats": hits}
        if hits and not edn_site.public_url():
            r["avertissement_liens"] = "EDN_PUBLIC_URL non défini : les liens sont relatifs ; ne jamais inventer de domaine."
        if not hits:
            r["consigne"] = ("AUCUN résultat dans les cours. Reformule une fois (synonyme, terme médical) ; sinon cherche sur internet "
                             "(HAS, collèges, CNG, ANSM, sociétés savantes), cite l'URL et l'année, et précise « absent des cours ». "
                             "Si rien de fiable : dis que tu n'as pas trouvé. Ne réponds pas de mémoire.")
        return r

    def _get_cours(self, a):
        if not (a.get("slug") or a.get("sdd")):
            raise RpcError(-32602, "slug ou sdd requis")
        r = edn_kb.get_doc(self.kb, a.get("slug"), a.get("sdd"), a.get("page_from", 1), a.get("page_to"), a.get("max_chars", 12000))
        if not r:
            raise RpcError(-32602, "cours introuvable (voir search_cours / list_cours)")
        first = int(str(r["pages_renvoyees"]).split("-")[0])
        r["lien"] = edn_site.page_link(r["slug"], first)
        r["lien_page"] = "ajouter ?page=N pour une autre page : " + edn_site.page_link(r["slug"], None) + "?page=N"
        return r

    def call(self, name, args):
        t = self.tools.get(name)
        if not t:
            raise RpcError(-32602, f"outil inconnu : {name}")
        validate(args, t["def"]["inputSchema"])
        v_avant = edn_store.version()
        try:
            res = t["fn"](args)
        except RpcError:
            raise
        except ValueError as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        except Exception:  # noqa: BLE001
            log.exception("outil %s", name)
            return {"content": [{"type": "text", "text": "erreur interne"}], "isError": True}
        text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, separators=(",", ":"))
        content = [{"type": "text", "text": text}]
        v_apres = edn_store.version()
        if v_apres != v_avant:           # annoncé seulement si une écriture a RÉELLEMENT eu lieu
            content.append({"type": "text", "text": f"[site] Données modifiées (version {v_apres}) : le site ouvert se recharge tout seul sous 5 secondes."})
        return {"content": content}


def handle(reg, msg):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        raise RpcError(-32600, "requête invalide")
    m, p = msg.get("method"), msg.get("params") or {}
    if m == "initialize":
        v = p.get("protocolVersion")
        return {"protocolVersion": v if v in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {}, "prompts": {}}, "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
    if m == "ping":
        return {}
    if m == "tools/list":
        return {"tools": [t["def"] for t in reg.tools.values()]}
    if m == "tools/call":
        return reg.call(p.get("name", ""), p.get("arguments") or {})
    if m == "prompts/list":
        return {"prompts": [{"name": s["name"], "description": s["description"]} for s in list_instr("skills")]}
    if m == "prompts/get":
        return {"messages": [{"role": "user", "content": {"type": "text", "text": get_instr("skills", p.get("name", ""))}}]}
    raise RpcError(-32601, f"méthode inconnue : {m}")


def make_handler(reg, token):
    if not token or len(token) < 16:
        raise SystemExit("EDN_MCP_TOKEN obligatoire (≥ 16 caractères) : le serveur refuse de démarrer sans jeton.")

    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body=b"", ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _auth(self):
            path, given = self.path.split("?")[0], ""
            m = re.match(r"^/t/([^/]+)(/.*)$", path)
            if m:
                given, path = m.group(1), m.group(2)
            else:
                given = self.headers.get("X-Api-Key") or re.sub(r"^Bearer\s+", "", self.headers.get("Authorization", ""))
            return path, hmac.compare_digest(given.encode(), token.encode())

        def do_GET(self):
            if edn_site.try_handle(self, "GET", reg.kb):
                return
            path, ok = self._auth()
            if path == "/health":
                return self._send(200, b'{"ok":true}')
            self._send(405 if ok else 401, b'{"error":"POST uniquement"}' if ok else b'{"error":"non autorise"}')

        def do_DELETE(self):
            if not edn_site.try_handle(self, "DELETE", reg.kb):
                self._send(404, b'{"error":"introuvable"}')

        def do_POST(self):
            if edn_site.try_handle(self, "POST", reg.kb):
                return
            path, ok = self._auth()
            if not ok:
                return self._send(401, b'{"error":"non autorise"}')
            if path.rstrip("/") not in ("/mcp", ""):
                return self._send(404, b'{"error":"introuvable"}')
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, b'{"error":"trop volumineux"}')
            try:
                msg = json.loads(self.rfile.read(n))
            except ValueError:
                return self._send(400, json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalide"}}).encode())
            batch = msg if isinstance(msg, list) else [msg]
            out = []
            for one in batch:
                rid = one.get("id") if isinstance(one, dict) else None
                is_note = isinstance(one, dict) and "id" not in one
                try:
                    res = handle(reg, one)
                    if not is_note:
                        out.append({"jsonrpc": "2.0", "id": rid, "result": res})
                except RpcError as e:
                    if not is_note:
                        out.append({"jsonrpc": "2.0", "id": rid, "error": {"code": e.code, "message": e.message}})
                except Exception:  # noqa: BLE001
                    log.exception("rpc")
                    out.append({"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": "erreur interne"}})
            if not out:
                return self._send(202)
            self._send(200, json.dumps(out if isinstance(msg, list) else out[0], ensure_ascii=False).encode())

    return H


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def check_persistence():
    """En conteneur (EDN_REQUIRE_PERSIST=1), refuse de démarrer si le dossier de suivi n'est pas un volume monté : sinon tout
    le suivi serait perdu à la prochaine recréation du conteneur, sans aucun message."""
    d = edn_store.data_dir()
    if os.environ.get("EDN_REQUIRE_PERSIST") == "1" and not os.path.ismount(d):
        raise SystemExit(f"{d} n'est pas un volume monté : le suivi serait perdu à la recréation du conteneur. "
                         f"Monte un dossier de l'hôte (-v ./suivi:{d}) ou désactive explicitement avec EDN_REQUIRE_PERSIST=0.")
    edn_store.ensure_repo()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    check_persistence()
    import edn_dash
    edn_dash.start_gardes_sync()
    host, port = os.environ.get("EDN_HOST", "127.0.0.1"), int(os.environ.get("EDN_PORT", 8001))
    srv = Server((host, port), make_handler(Registry(), os.environ.get("EDN_MCP_TOKEN", "")))
    print(f"MCP : http://{host}:{port}/mcp  (jeton requis)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
