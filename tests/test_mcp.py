"""Test de bout en bout du serveur MCP (HTTP réel, port éphémère, données de suivi temporaires)."""
import json, os, re, sys, tempfile, threading, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["EDN_DATA_DIR"] = tempfile.mkdtemp()
os.environ["EDN_TODAY"] = "2026-10-09"
import edn_mcp  # noqa: E402

TOKEN = "t" * 24
srv = edn_mcp.Server(("127.0.0.1", 0), edn_mcp.make_handler(edn_mcp.Registry(), TOKEN))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}"
_id = [0]


def rpc(method, params=None, path="/mcp", headers=None):
    _id[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _id[0], "method": method, "params": params or {}}).encode()
    h = {"Content-Type": "application/json", "X-Api-Key": TOKEN, **(headers or {})}
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + path, body, h))
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def call(name, args=None):
    s, r = rpc("tools/call", {"name": name, "arguments": args or {}})
    assert s == 200, s
    if "error" in r:
        return r["error"]
    res = r["result"]
    return res["content"][0]["text"], res.get("isError", False)


def check(label, cond):
    print(("OK  " if cond else "FAIL"), label)
    if not cond:
        sys.exit(1)


check("sans jeton -> 401", rpc("ping", headers={"X-Api-Key": "mauvais"})[0] == 401)
check("jeton Bearer", rpc("ping", headers={"X-Api-Key": "", "Authorization": f"Bearer {TOKEN}"})[0] == 200)
check("jeton dans l'URL", rpc("ping", path=f"/t/{TOKEN}/mcp", headers={"X-Api-Key": ""})[0] == 200)
s, r = rpc("initialize", {"protocolVersion": "2025-06-18"})
check("initialize", r["result"]["serverInfo"]["name"] == "coach-internat")
names = {t["name"] for t in rpc("tools/list")[1]["result"]["tools"]}
check("outils exposés", {"search_cours", "get_cours", "log_attempt", "plan_backwards", "get_skill"} <= names)
txt, err = call("search_cours", {"query": "insuffisance aortique indication chirurgicale", "category": "Cardiologie", "limit": 3})
env = json.loads(txt)
hits = env["resultats"]
check("source citée dans la réponse", "cours de l'étudiante" in env["source"])
check("search_cours renvoie le cours dédié", hits and hits[0]["title"].lower().startswith("insuffisance aortique"))
check("extraits courts", all(len(h["extrait"]) < 420 for h in hits))
doc = json.loads(call("get_cours", {"slug": hits[0]["slug"], "page_from": 19, "page_to": 20})[0])
check("get_cours pages", "## p.19" in doc["texte"])
check("get_cours sdd", json.loads(call("get_cours", {"sdd": 51, "max_chars": 2000})[0])["sdd"] == 51)
check("skills listés", len(json.loads(call("list_skills")[0])) >= 9)
check("agents listés (sans _commun)", all(not a["name"].startswith("_") for a in json.loads(call("list_agents")[0])))
ag = call("get_agent", {"name": "coach-cardiologie"})[0]
check("agent + règles communes", "RÈGLES COMMUNES" in ag and "THÈMES" in ag)
check("nom invalide refusé", "invalide" in str(call("get_skill", {"name": "../x"})))
check("argument inconnu refusé", "inconnu" in str(call("search_cours", {"query": "a", "x": 1})))
check("profil", json.loads(call("set_profile", {"values": {"exam_edn": "2027-10-11", "heures_par_semaine": 30}})[0])["exam_edn"] == "2027-10-11")
check("date invalide refusée", call("set_profile", {"values": {"exam_edn": "demain"}})[1] is True)
check("clé de profil inconnue refusée", isinstance(call("set_profile", {"values": {"x": 1}}), dict))
check("profil.md écrit", "exam_edn" in call("read_file", {"path": "profil.md"})[0])
check("log_attempt SM-2", json.loads(call("log_attempt", {"item": "SDD 51", "quality": 4, "kind": "dp", "category": "Endocrinologie", "note": "a|b"})[0])["intervalle_jours"] == 1)
check("journal écrit", "SDD 51" in call("read_file", {"path": "journal/2026-10.md"})[0])
check("due_reviews demain", call("due_reviews")[0] == "[]")
check("progress", json.loads(call("progress")[0])["cartes"] == 1)
plan = json.loads(call("plan_backwards", {"save": True})[0])
check("plan_backwards + enregistré", plan["semaines"] > 50 and plan["plan"][0]["focus"] and plan["enregistre"]["commit"])
check("plan sans date -> erreur claire", call("plan_backwards", {"exam_date": "2026-10-01"})[1] is True)
# --- historique git
h = json.loads(call("history")[0])["commits"]
check("historique : un commit par écriture (profil, journal+révisions, plan)", len(h) == 3 and all(c["message"].startswith("[coach]") for c in h))
check("historique d'un fichier", len(json.loads(call("history", {"path": "profil.md"})[0])["commits"]) == 1)
# --- notes : source obligatoire
check("note sans source refusée", call("save_note", {"title": "IAo", "content": "x", "sources": []})[1] is True)
n = json.loads(call("save_note", {"title": "IAo — indications", "content": "Chirurgie si symptomatique.", "sources": ["[Cardiologie — Insuffisance aortique, p.19]"]})[0])
check("note enregistrée + commit", n["commit"] and n["path"].startswith("notes/"))
check("note contient Sources", "## Sources" in call("read_file", {"path": n["path"]})[0])
# --- annulation
before = len(json.loads(call("history")[0])["commits"])
check("undo_last_change", "annule" in call("undo_last_change")[0])
check("undo ajoute un revert (rien de supprimé)", len(json.loads(call("history")[0])["commits"]) == before + 1)
check("note annulée absente", call("read_file", {"path": n["path"]})[1] is True)
# --- sécurité des chemins
for bad in ("../etc/passwd", "/etc/passwd", "notes/../profil.md", "config/x.md", "notes/a/b.md", "notes/x.txt"):
    check(f"chemin refusé {bad}", call("read_file", {"path": bad})[1] is True)
# --- aucun résultat -> consigne explicite
e = json.loads(call("search_cours", {"query": "zzqxwv"})[0])
check("aucun résultat -> consigne internet + ne pas combler", e["resultats"] == [] and "internet" in e["consigne"] and "mémoire" in e["consigne"])
print("tous les tests passent")

# ================= site de lecture des PDF =================
import http.client, urllib.parse  # noqa: E402

os.environ["EDN_SITE_PASSWORD"] = "motdepasse-test"
os.environ["EDN_PUBLIC_URL"] = "https://coach.example.test"
host, port = "127.0.0.1", srv.server_address[1]


def http_get(path, headers=None, method="GET", body=None):
    c = http.client.HTTPConnection(host, port, timeout=20)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    data = r.read()
    return r.status, dict(r.getheaders()), data


hits = json.loads(call("search_cours", {"query": "insuffisance aortique indication chirurgicale", "category": "Cardiologie", "limit": 2})[0])["resultats"]
slug, page = hits[0]["slug"], hits[0]["page"]
check("lien dans les résultats de recherche", hits[0]["lien"] == f"https://coach.example.test/pdf/{slug}?page={page}")
check("lien dans get_cours", json.loads(call("get_cours", {"slug": slug, "page_from": 19, "page_to": 19})[0])["lien"].endswith(f"/pdf/{slug}?page=19"))
check("lien dans list_cours", all("/pdf/" in d["lien"] for d in json.loads(call("list_cours", {"category": "Cardiologie", "limit": 3})[0])))
st, hd, _ = http_get(f"/pdf/{slug}?page={page}")
check("sans connexion -> redirection /login?next=", st == 302 and hd["Location"].startswith("/login?next=%2Fpdf%2F" if False else "/login?next=/pdf/"))
check("PDF brut sans connexion -> 401", http_get(f"/file/{slug}.pdf")[0] == 401)
check("API texte sans connexion -> 401", http_get(f"/api/page/{slug}/1")[0] == 401)
check("mauvais mot de passe -> 401", http_get("/login", {"Content-Type": "application/x-www-form-urlencoded"}, "POST", "password=non&next=/")[0] == 401)
st, hd, _ = http_get("/login", {"Content-Type": "application/x-www-form-urlencoded"}, "POST",
                     urllib.parse.urlencode({"password": "motdepasse-test", "next": f"/pdf/{slug}?page={page}"}))
cookie = hd["Set-Cookie"].split(";")[0]
check("connexion -> redirection vers la page demandée", st == 302 and hd["Location"] == f"/pdf/{slug}?page={page}" and "HttpOnly" in hd["Set-Cookie"])
st, hd, _ = http_get("/login", {"Content-Type": "application/x-www-form-urlencoded"}, "POST", "password=motdepasse-test&next=//evil.example")
check("open redirect refusé", hd["Location"] == "/")
H = {"Cookie": cookie}
st, hd, body = http_get(f"/pdf/{slug}?page=19", H)
check("visionneuse ouvre la bonne page", st == 200 and b'value="19"' in body and b'data-page="19"' in body and "no-store" in hd["Cache-Control"])
check("aucun script en ligne (la CSP les bloque)", re.search(rb"<script(?![^>]*\ssrc=)", body) is None)
check("viewer.js servi", b"pdfjsLib" in http_get("/static/viewer.js", H)[2])
m = re.search(rb'data-page="(\d+)"', http_get(f"/pdf/{slug}?page=99999", H)[2])
check("page hors bornes ramenée dans le PDF", m is not None and 1 <= int(m.group(1)) <= 200)
st, hd, body = http_get(f"/file/{slug}.pdf", {**H, "Range": "bytes=0-99"})
check("PDF : Range -> 206, 100 octets, %PDF", st == 206 and len(body) == 100 and body.startswith(b"%PDF") and hd["Content-Range"].startswith("bytes 0-99/"))
check("PDF : Range invalide -> 416", http_get(f"/file/{slug}.pdf", {**H, "Range": "bytes=999999999999-"})[0] == 416)
st, _, body = http_get(f"/api/page/{slug}/19", H)
check("texte indexé de la page", st == 200 and "indication" in json.loads(body)["text"].lower())
for bad in ("../../etc/passwd", "inconnu-xyz", "%2e%2e%2fsecret"):
    check(f"slug refusé {bad}", http_get(f"/pdf/{bad}", H)[0] == 404 and http_get(f"/file/{bad}.pdf", H)[0] == 404)
check("pdf.js servi localement", http_get("/static/pdfjs/pdf.min.js", H)[0] == 200)
check("autre fichier statique refusé", http_get("/static/pdfjs/../../edn_mcp.py", H)[0] == 404)
check("CSP sans CDN externe", "cdn" not in http_get(f"/pdf/{slug}", H)[1]["Content-Security-Policy"])
check("MCP toujours protégé par son jeton", rpc("ping", headers={"X-Api-Key": "x"})[0] == 401 and rpc("ping")[0] == 200)
pw = os.environ.pop("EDN_SITE_PASSWORD")
check("site désactivé sans mot de passe", http_get("/login")[0] == 404)
os.environ["EDN_SITE_PASSWORD"] = pw
print("tests du site : OK")

# ================= tableau de bord =================
import edn_dash  # noqa: E402

JSONH = {"Content-Type": "application/json", "X-Requested-With": "edn"}
st, hd, _ = http_get("/login", {"Content-Type": "application/x-www-form-urlencoded"}, "POST", "password=motdepasse-test&next=/")
H = {"Cookie": hd["Set-Cookie"].split(";")[0]}


def api_(method, path, body=None, headers=None):
    st, hd, data = http_get(path, {**H, **(headers if headers is not None else JSONH)}, method, json.dumps(body) if body is not None else None)
    try:
        return st, json.loads(data)
    except ValueError:
        return st, data


check("/ sans connexion -> /login", http_get("/")[0] == 302 and http_get("/")[1]["Location"].startswith("/login"))
check("/api/summary sans connexion -> 401", http_get("/api/summary")[0] == 401)
st, hd, body = http_get("/", H)
check("page d'accueil + assets revalidés", st == 200 and b"/app/app.js" in body and http_get("/app/app.js", H)[1]["Cache-Control"] == "no-cache")
check("aucun script en ligne sur /", re.search(rb"<script(?![^>]*\ssrc=)", body) is None)
check("fichier hors liste refusé", http_get("/app/../edn_mcp.py", H)[0] == 404 and http_get("/app/secret.txt", H)[0] == 404)

st, s = api_("GET", "/api/summary")
check("résumé : échéances, semaine, paquets", st == 200 and s["echeances"][0]["jours"] == 130 and s["semaine"]["s"] == 3 and len(s["paquets"]) == 20)
edn_ = [e for e in s["echeances"] if e["type"] == "edn"][0]
check("date EDN du profil : fiche d'examen synchronisée, non estimée", edn_["date"] == "2027-10-11" and edn_["estime"] is False)
check("write sans en-tête CSRF refusé", api_("POST", "/api/cards/review", {"id": "cardio-001", "quality": "bien"}, {"Content-Type": "application/json"})[0] == 403)
check("write avec mauvais Origin refusé", api_("POST", "/api/errors", {"text": "x"}, {**JSONH, "Origin": "https://evil.example"})[0] == 403)

# deck : intégrité
st, d = api_("GET", "/api/cards?limit=200")
cards = d["cartes"]
check("151 cartes, identifiants uniques", d["total"] == 151 and len({c["id"] for c in cards}) == 151)
check("toutes les cartes ont un statut de vérification", all(c["verification"]["statut"] for c in cards))
byid = {c["id"]: c for c in cards}
check("cardio-002 corrigée : 10 minutes (ESC 2023), plus 30", "10 minutes" in byid["cardio-002"]["answer"] and "30 minutes" not in byid["cardio-002"]["answer"]
      and byid["cardio-002"]["verification"]["statut"] == "corrigee" and byid["cardio-002"]["verification"]["avant"]["answer"].count("30 minutes") == 1)
check("corrections sourcées", all(byid[i]["verification"]["sources_cours"] or byid[i]["verification"]["sources_web"]
                                  for i in ("cardio-001", "cardio-002", "pediatrie-002", "nephro-001", "reanimation-007", "geriatrie_mpr-007")))
check("albuminémie plus critère diagnostique (HAS 2021)", "n'est pas un critère diagnostique" in byid["geriatrie_mpr-007"]["answer"])
check("bloc de branche gauche plus équivalent", "n'est plus considéré comme un équivalent" in byid["cardio-001"]["answer"])

# révision : SM-2 + un seul commit + état
n0 = len(json.loads(call("history", {"n": 50})[0])["commits"])
st, r = api_("POST", "/api/cards/review", {"id": "cardio-001", "quality": "bien"})
check("révision d'une carte", st == 200 and r["intervalle_jours"] == 1 and r["item"] == "carte:cardio-001")
check("une révision = UN commit", len(json.loads(call("history", {"n": 50})[0])["commits"]) == n0 + 1)
check("carte revue : plus à réviser aujourd'hui", "cardio-001" not in [c["id"] for c in api_("GET", "/api/cards?etat=a_reviser&limit=200")[1]["cartes"]])
check("révision invalide refusée", api_("POST", "/api/cards/review", {"id": "cardio-001", "quality": "n'importe quoi"})[0] == 400 and api_("POST", "/api/cards/review", {"id": "nope", "quality": 3})[0] == 404)
check("filtre par paquet", all(c["deck"] == "ophtalmo" for c in api_("GET", "/api/cards?deck=ophtalmo")[1]["cartes"]))
check("progression des paquets", [p for p in api_("GET", "/api/summary")[1]["paquets"] if p["cle"] == "cardio"][0]["vues"] == 1)

# cartes perso + erreurs
st, c = api_("POST", "/api/cards/custom", {"deck": "cardio", "question": "Ma question ?", "answer": "Ma réponse", "tags": ["a"]})
check("carte perso ajoutée", st == 201 and c["id"].startswith("custom-") and api_("GET", "/api/cards?q=Ma%20question")[1]["total"] == 1)
check("carte perso : paquet inconnu refusé", api_("POST", "/api/cards/custom", {"deck": "zz", "question": "q", "answer": "a"})[0] == 400)
check("carte perso supprimée (historique conservé)", api_("DELETE", f"/api/cards/custom/{c['id']}")[0] == 200 and api_("GET", "/api/cards?q=Ma%20question")[1]["total"] == 0)
st, e = api_("POST", "/api/errors", {"text": "Confondu IAo et RAo", "deck": "cardio"})
check("erreur ajoutée puis listée", st == 201 and api_("GET", "/api/errors")[1]["erreurs"][0]["id"] == e["id"])
check("erreur supprimée", api_("DELETE", f"/api/errors/{e['id']}")[0] == 200 and api_("GET", "/api/errors")[1]["erreurs"] == [])
check("texte du journal : XSS stocké tel quel mais jamais interprété (échappement côté client)", api_("POST", "/api/errors", {"text": "<img src=x onerror=alert(1)>"})[0] == 201)

# explorateur
st, f = api_("GET", "/api/cours/facets")
check("facettes : 3 thèmes, partiel = 66 documents", st == 200 and len(f["themes"]) == 3 and f["themes"][0]["docs"] == 66)
st, r = api_("GET", "/api/cours/search?q=glaucome%20aigu&theme=partiel")
check("recherche filtrée par thème (partiel) : bonnes catégories", st == 200 and r["resultats"] and all(x["category"] in edn_dash.PARTIEL for x in r["resultats"]))
check("résultats avec lien vers la page", all(x["lien"].startswith("/pdf/") and "?page=" in x["lien"] for x in r["resultats"]))
check("recherche sans terme refusée", api_("GET", "/api/cours/search?q=")[0] == 400)
st, r = api_("GET", "/api/cours/docs?category=Cardiologie")
check("liste des documents d'une spécialité", r["total"] == 25 and all(d["lien"].startswith("/pdf/") for d in r["docs"]))
st, r = api_("GET", "/api/planning")
check("planning : 22 semaines, une courante", st == 200 and len(r["semaines"]) == 22 and sum(w["courante"] for w in r["semaines"]) == 1)
st, r = api_("GET", "/api/progress?days=30")
check("avancement", st == 200 and len(r["activite"]) == 30 and len(r["a_venir"]) == 15)
check("export complet", "revisions" in api_("GET", "/api/export")[1] and "carte:cardio-001" in api_("GET", "/api/export")[1]["revisions"])

gc = json.loads(call("get_card", {"id": "carte:cardio-002"})[0])
check("MCP get_card : statut et sources", gc["verification"]["statut"] == "corrigee" and gc["verification"]["sources_web"][0]["url"].startswith("https://"))
check("MCP get_card : carte inconnue -> erreur", call("get_card", {"id": "nope"})[1] is True)

# gardes : le reste du calendrier n'est jamais exposé
ICS = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Garde urgences\r\nDTSTART:20261020T080000\r\nDTEND:20261021T080000\r\nEND:VEVENT\r\n" \
      "BEGIN:VEVENT\r\nSUMMARY:Rendez-vous dentiste privé\r\nDTSTART:20261022T090000\r\nDTEND:20261022T100000\r\nEND:VEVENT\r\n" \
      "BEGIN:VEVENT\r\nSUMMARY:GARDE\r\n  nuit\r\nDTSTART;VALUE=DATE:20261101\r\nDTEND;VALUE=DATE:20261102\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
g = edn_dash.gardes_from_ics(ICS)
check("gardes : seules les gardes sont gardées", [x["debut_date"] for x in g] == ["2026-10-20", "2026-11-01"] and "dentiste" not in json.dumps(g))
check("gardes : lendemain de récupération", g[0]["jour_recuperation"] == "2026-10-21" and g[1]["jour_recuperation"] == "2026-11-02")
check("gardes non configurées -> désactivées sans erreur", api_("GET", "/api/gardes")[1]["enabled"] is False)
print("tests du tableau de bord : OK")

# ================= quiz : lancé par le skill /quiz, enregistré UNE fois à la fin =================
opts = json.loads(call("quiz_options")[0])
check("quiz_options : 20 spécialités", len(opts["specialites"]) == 20 and opts["specialites"][0]["cle"] == "cardio")
check("quiz_options(spécialité) : catégories de cours", json.loads(call("quiz_options", {"specialite": "geriatrie_mpr"})[0])["categories"] == ["Gériatrie", "MPR"])
check("spécialité hors liste refusée", isinstance(call("save_quiz", {"specialite": "cardiologie", "sujet": "x", "questions": [{"enonce": "q", "points": 1}]}), dict))
n_c = len(json.loads(call("history", {"n": 50})[0])["commits"])
Q = [{"enonce": "Délai de fibrinolyse", "points": 0, "max": 1, "piege": "10 min, pas 30", "source": "[Cardiologie — SCA, p.23]"},
     {"enonce": "Seuil V2-V3 homme ≥ 40 ans", "points": 1, "max": 1}, {"enonce": "CHA2DS2-VASc", "points": 1, "max": 1},
     {"enonce": "Triade du RAo", "points": 1, "max": 1}, {"enonce": "DAPT après IDM", "points": 0.5, "max": 1, "piege": "12 mois"}]
r = json.loads(call("save_quiz", {"specialite": "cardio", "sujet": "SCA ST+", "format": "qi", "sdd": 12, "minutes": 9, "questions": Q})[0])
check("save_quiz : score 3,5/5 = 70 %, niveau fort (5 questions)", r["score"] == "3.5/5" and r["pct"] == 70 and r["niveau_session"] == "fort")
check("save_quiz : UN seul commit pour quiz + journal + révisions + erreurs", r["erreurs_ajoutees"] == 2 and len(json.loads(call("history", {"n": 50})[0])["commits"]) == n_c + 1)
check("save_quiz : bilan renvoyé", r["bilan"]["specialites"][0]["cle"] == "cardio" and r["bilan"]["forts"][0]["pct"] == 70)
check("quiz.md écrit (lisible)", "SCA ST+" in call("read_file", {"path": "quiz.md"})[0])
check("erreurs du quiz dans le journal d'erreurs", any("Délai de fibrinolyse" in e["text"] and e["deck"] == "cardio" for e in api_("GET", "/api/errors")[1]["erreurs"]))
check("révision de l'item planifiée", any(d["item"] == "quiz:SCA ST+" for d in json.loads(call("due_reviews", {"limit": 50})[0])) or "quiz:SCA ST+" in call("read_file", {"path": "revisions.md"})[0])
st, qz = api_("GET", "/api/quiz")
check("API quiz : spécialité, niveau, dernier quiz", st == 200 and qz["specialites"][0]["nom"] == "Cardiologie" and qz["recents"][0]["sujet"] == "SCA ST+" and "questions" not in qz["recents"][0])
# 2e quiz faible sur une autre spécialité + moins de 5 questions => « à confirmer »
call("save_quiz", {"specialite": "orl", "sujet": "Angine", "questions": [{"enonce": "a", "points": 0}, {"enonce": "b", "points": 1}]})
call("save_quiz", {"specialite": "neuro", "sujet": "AVC", "questions": [{"enonce": str(i), "points": 0} for i in range(6)]})
qz = api_("GET", "/api/quiz")[1]
check("moins de 5 questions = « à confirmer », jamais « faible »", [x for x in qz["specialites"] if x["cle"] == "orl"][0]["niveau"] == "a_confirmer")
check("0/6 = point faible, listé en premier", qz["faibles"][0]["cle"] == "neuro" and qz["sujets_a_retravailler"][0]["sujet"] == "AVC")
paq = {p["cle"]: p for p in api_("GET", "/api/summary")[1]["paquets"]}
check("avancement par spécialité : colonne quiz", paq["cardio"]["quiz"]["pct"] == 70 and paq["neuro"]["quiz"]["niveau"] == "faible" and paq["pediatrie"]["quiz"] is None)
for bad, why in (({"specialite": "cardio", "sujet": "x", "questions": [{"enonce": "q", "points": 2, "max": 1}]}, "points > max"),
                 ({"specialite": "cardio", "sujet": "x", "questions": []}, "aucune question"),
                 ({"specialite": "cardio", "sujet": "x", "format": "zz", "questions": [{"enonce": "q", "points": 1}]}, "format inconnu")):
    res = call("save_quiz", bad)
    check(f"save_quiz refuse : {why}", (isinstance(res, dict)) or res[1] is True)
check("rien d'écrit par un quiz invalide", api_("GET", "/api/quiz")[1]["total_sessions"] == 3)
print("tests du quiz : OK")

def rejected(res):
    return isinstance(res, dict) or res[1] is True      # erreur RPC (schéma) ou isError (règle métier)


# ================= examens : onglet modifiable, synchronisé avec le profil =================
st, ex = api_("GET", "/api/exams")
types = {e["type"]: e for e in ex["examens"]}
check("examens : partiel avec ses 5 matières + EDN", st == 200 and len(types["partiel"]["matieres"]) == 5 and types["edn"]["date"] == "2027-10-11")
check("matières reliées aux catégories de cours", {d["matiere"]: d["categories"] for d in types["partiel"]["matieres_detail"]}["Ophtalmologie"] == ["Ophtalmologie"]
      and "Anesthésie-réanimation" in str(types["partiel"]["matieres_detail"]) and "MPR" in str(types["partiel"]["matieres_detail"]))
n_c = len(json.loads(call("history", {"n": 50})[0])["commits"])
r = json.loads(call("save_exam", {"type": "autre", "nom": "Partiel de cardiologie", "date": "2026-12-14", "heure": "14:00", "matieres": ["Cardiologie", "Pneumologie"], "lieu": "Amphi A"})[0])
check("save_exam : nouvel examen, UN commit", r["cree"] and r["examen"]["id"].startswith("exam-") and len(json.loads(call("history", {"n": 50})[0])["commits"]) == n_c + 1)
eid = r["examen"]["id"]
check("save_exam : modification (champs absents conservés)", json.loads(call("save_exam", {"id": eid, "date": "2026-12-15"})[0])["examen"]["matieres"] == ["Cardiologie", "Pneumologie"])
check("l'API le liste, trié par date", [e["id"] for e in api_("GET", "/api/exams")[1]["examens"]].index(eid) < [e["id"] for e in api_("GET", "/api/exams")[1]["examens"]].index("exam-edn"))
check("compteur de l'en-tête : prochains examens", any(e["cle"] == eid and e["jours"] == 67 for e in api_("GET", "/api/summary")[1]["echeances"]))
check("examen modifiable depuis l'interface (API)", api_("POST", "/api/exams", {"id": eid, "matieres": ["Cardiologie"], "note": "Salle 3"})[1]["examen"]["note"] == "Salle 3")
check("date invalide refusée", rejected(call("save_exam", {"type": "autre", "nom": "x", "date": "demain"})))
check("heure invalide refusée", api_("POST", "/api/exams", {"id": eid, "heure": "25:99"})[0] == 400)
check("id inconnu refusé", api_("POST", "/api/exams", {"id": "exam-zzz", "nom": "x"})[0] == 400)
# EDN / ECOS : une fiche par type, synchronisée avec le profil dans les deux sens
json.loads(call("save_exam", {"type": "ecos", "date": "2028-04-10", "heure": "08:30"})[0])
check("ECOS -> profil.md (exam_ecos)", json.loads(call("get_profile")[0])["exam_ecos"] == "2028-04-10")
call("set_profile", {"values": {"exam_edn": "2027-10-12"}})
check("set_profile exam_edn -> fiche d'examen EDN", [e for e in api_("GET", "/api/exams")[1]["examens"] if e["type"] == "edn"][0]["date"] == "2027-10-12")
r2 = json.loads(call("save_exam", {"type": "edn", "date": "2027-10-13"})[0])
check("EDN : même fiche mise à jour (pas de doublon) + profil", not r2["cree"] and len([e for e in api_("GET", "/api/exams")[1]["examens"] if e["type"] == "edn"]) == 1 and json.loads(call("get_profile")[0])["exam_edn"] == "2027-10-13")
check("estime=true : date à confirmer, profil intact", json.loads(call("save_exam", {"type": "edn", "date": "2027-10-20", "estime": True})[0])["examen"]["estime"] is True and json.loads(call("get_profile")[0])["exam_edn"] == "2027-10-13")
check("suppression d'un examen", api_("DELETE", f"/api/exams/{eid}")[0] == 200 and eid not in [e["id"] for e in api_("GET", "/api/exams")[1]["examens"]])
check("suppression annulable (undo_last_change)", "annule" in call("undo_last_change")[0] and eid in [e["id"] for e in api_("GET", "/api/exams")[1]["examens"]])
check("examens.md lisible", "Partiel de cardiologie" in call("read_file", {"path": "examens.md"})[0])
print("tests des examens : OK")

# ================= cartes : ajouter / corriger depuis du texte ou du JSON =================
n_c = len(json.loads(call("history", {"n": 50})[0])["commits"])
ap = json.loads(call("save_cards", {"apercu": True, "cartes": [{"deck": "cardio", "question": "Valeur seuil de la PAM dans le choc septique ?", "answer": "65 mmHg"}]})[0])
check("aperçu : rien n'est écrit", ap["apercu"] and ap["ajoutees"] == 1 and len(json.loads(call("history", {"n": 50})[0])["commits"]) == n_c)
r = json.loads(call("save_cards", {"cartes": [{"deck": "cardio", "question": "Valeur seuil de la PAM dans le choc septique ?", "answer": "65 mmHg", "tags": ["choc"], "sources": ["[Anesthésie-réanimation — Les états de choc, p.3](/pdf/anesthesie-reanimation-les-etats-de-choc?page=3)"]},
                                          {"deck": "neuro", "question": "Fenêtre de thrombolyse ?", "answer": "4 h 30"}]})[0])
check("import : 2 nouvelles cartes, UN commit", r["ajoutees"] == 2 and r["commit"] and len(json.loads(call("history", {"n": 50})[0])["commits"]) == n_c + 1)
newid = r["detail"][0]["id"]
check("cartes importées visibles sur le site", api_("GET", "/api/cards?q=choc%20septique")[1]["total"] >= 1 and api_("GET", "/api/cards?deck=neuro&q=thrombolyse")[1]["total"] >= 1)
check("doublon refusé", rejected(call("save_cards", {"cartes": [{"deck": "cardio", "question": "valeur seuil de la PAM dans le choc septique", "answer": "x"}]})))
check("paquet inconnu refusé", rejected(call("save_cards", {"cartes": [{"deck": "zz", "question": "q ?", "answer": "a"}]})))
check("carte perso modifiée en place", json.loads(call("save_cards", {"cartes": [{"id": newid, "answer": "PAM ≥ 65 mmHg sous noradrénaline"}]})[0])["modifiees"] == 1
      and [c for c in api_("GET", "/api/cards?q=choc%20septique")[1]["cartes"] if c["id"] == newid][0]["answer"].startswith("PAM ≥ 65"))
check("corriger une carte du deck SANS motif : refusé", rejected(call("save_cards", {"cartes": [{"id": "cardio-005", "answer": "Un AOD."}]})))
r = json.loads(call("save_cards", {"cartes": [{"id": "cardio-005", "answer": "Un anticoagulant oral direct (AOD) ; AVK si valve mécanique ou rétrécissement mitral modéré à sévère.", "motif": "Réponse plus précise", "sources": ["[Cardiologie — Fibrillation Atriale, p.13]"]}]})[0])
check("correction du deck : persistante, sourcée", r["corrigees"] == 1 and r["detail"][0]["sourcee"])
c5 = [c for c in api_("GET", "/api/cards?deck=cardio&limit=200")[1]["cartes"] if c["id"] == "cardio-005"][0]
check("carte corrigée : nouvelle réponse, ancienne conservée, statut « modifiée »", c5["answer"].startswith("Un anticoagulant oral direct (AOD)") and c5["verification"]["statut"] == "modifiee"
      and c5["verification"]["avant"]["answer"].startswith("Un anticoagulant oral direct. Les antivitamines") and c5["verification"]["motif"] == "Réponse plus précise")
check("le deck d'origine n'est jamais modifié (data/)", "AVK si valve mécanique" not in open("data/cartes-edn.json").read() and "Réponse plus précise" not in open("data/cartes-edn.json").read())
nb = api_("GET", "/api/cards?limit=1")[1]["total"]
call("save_cards", {"cartes": [{"deck": "cardio", "question": "Carte valide du lot ?", "answer": "oui"}, {"id": "inconnu-1", "answer": "x"}]})
check("lot avec une carte invalide : rien n'est écrit", api_("GET", "/api/cards?limit=1")[1]["total"] == nb)
print("tests des cartes : OK")

# ================= rechargement automatique du site =================
v0 = api_("GET", "/api/version")[1]["version"]
txt = urllib.request.urlopen(urllib.request.Request(BASE + "/mcp", json.dumps({"jsonrpc": "2.0", "id": 99, "method": "tools/call", "params": {"name": "save_note",
      "arguments": {"title": "Test rechargement", "content": "x", "sources": ["[Cours — Test, p.1]"]}}}).encode(), {"Content-Type": "application/json", "X-Api-Key": TOKEN}))
body = json.loads(txt.read())["result"]["content"]
v1 = api_("GET", "/api/version")[1]["version"]
check("toute écriture change la version des données", v0 != v1 and len(v1) >= 7)
check("la réponse de l'outil annonce le rechargement du site", len(body) == 2 and "se recharge tout seul" in body[1]["text"] and v1 in body[1]["text"])
check("une lecture ne change rien", api_("GET", "/api/version")[1]["version"] == v1 and (call("list_exams"), api_("GET", "/api/version")[1]["version"] == v1)[1])
check("/api/version protégé par la connexion", http_get("/api/version")[0] == 401)
print("tests du rechargement : OK")

# ================= audit : tout ce qui modifie des données fait recharger le site =================
import glob  # noqa: E402
WRITE = {"set_profile", "log_attempt", "plan_backwards", "save_note", "undo_last_change", "save_quiz", "save_exam", "delete_exam", "save_cards"}
tools_ = {t["name"]: t for t in rpc("tools/list")[1]["result"]["tools"]}
check("outils d'écriture déclarés (un nouvel outil doit être ajouté ici sciemment)", {n for n, t in tools_.items() if not t["annotations"]["readOnlyHint"]} == WRITE)
check("plan_backwards sans save : pas d'annonce de rechargement", len(json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/mcp", json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
      "params": {"name": "plan_backwards", "arguments": {}}}).encode(), {"Content-Type": "application/json", "X-Api-Key": TOKEN})).read())["result"]["content"]) == 1)
skills_ = {os.path.basename(os.path.dirname(f)): open(f).read() for f in glob.glob(str(ROOT / "skills" / "*" / "SKILL.md"))}
writers = {n for n, t in skills_.items() if any(w in t for w in ("save_", "log_attempt", "set_profile", "delete_exam", "plan_backwards", "undo_last_change"))}
missing = sorted(n for n in writers if not ("se met à jour tout seul" in skills_[n] or "se recharge tout seul" in skills_[n]))
check(f"chaque skill qui écrit annonce le rechargement du site ({len(writers)} skills : {', '.join(sorted(writers))})", not missing and {"cartes", "coach-setup", "quiz", "fiche"} <= writers)
check("les skills en lecture seule ne promettent pas de rechargement", all("recharge" not in skills_[n] for n in ("recherche-sources", "bilan-semaine")))
for n in ("cartes", "coach-setup"):
    check(f"skill {n} : exige la ligne [site] avant d'annoncer l'enregistrement", "[site]" in skills_[n])
check("coach-setup : écrit final, oral final, examens par date avec matières", all(k in skills_["coach-setup"] for k in ("EDN", "ECOS", "matières", "save_exam", "list_exams", "pour **chaque date**")))
print("audit des skills : OK")
