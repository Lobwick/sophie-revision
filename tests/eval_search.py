"""Banc d'essai : questions cliniques SANS mot commun avec le titre du cours attendu. Mesure le taux de réussite top-5 par méthode.
Usage : .venv/bin/python tests/eval_search.py [tag ...]   (tags = fichiers knowledge/emb/<tag>.npy)"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import edn_kb  # noqa: E402

# (question, regex sur « catégorie titre » attendue dans le top 5)
CASES = [
    ("patient confus avec fièvre et raideur de nuque", r"m[ée]ning|confus|ponction lombaire"),
    ("œil rouge très douloureux avec halos colorés autour des lumières et vomissements", r"glaucome|[œo]il rouge"),
    ("nourrisson qui pleure par crises avec vomissements et selles sanglantes", r"invagination|douleur abdominale|vomissement|rectorragie|h[ée]morragie digestive|gastro"),
    ("femme enceinte avec tension élevée, maux de tête et protéinurie", r"pr[ée].?[ée]clampsie|hta pendant la grossesse"),
    ("perte de vision soudaine indolore d'un seul œil", r"alt[ée]ration aigu[ëe] de la vision|anomalie de la vision|r[ée]tin|occlusion"),
    ("jambe gonflée et douloureuse après un long voyage en avion", r"thrombose|phl[ée]bite|embolie|mollet|jambe"),
    ("soif intense, polyurie, haleine acétonique et respiration ample chez un jeune diabétique", r"c[ée]to|diab[èe]te de type 1|insulinoth[ée]rapie"),
    ("crise convulsive qui dure plus de cinq minutes", r"[ée]pilep|convulsion|[ée]tat de mal"),
    ("enfant avec fièvre prolongée, éruption, conjonctivite et lèvres rouges fissurées", r"kawasaki|[ée]ruption|fi[èe]vre.*enfant|vascularite"),
    ("fatigue, prise de poids, frilosité et constipation chez une femme de 40 ans", r"hypothyro|thyro[iï]d"),
    ("douleur thoracique irradiant dans le bras avec sueurs", r"coronar|infarctus|sca|douleur thoracique|angor"),
    ("homme âgé qui tombe et ne peut plus se relever, jambe raccourcie en rotation externe", r"f[ée]mur|chute|fracture|hanche"),
    ("quelle antibiothérapie pour une jeune femme avec brûlures mictionnelles et fièvre", r"urinaire|pyélo|cystite"),
    ("patiente de 25 ans avec douleur pelvienne brutale et retard de règles", r"algies pelviennes|douleur pelvienne|grossesse extra|geu|retard de r[èe]gles"),
    ("idées suicidaires chez un adolescent après une rupture", r"suicid|crise suicidaire|d[ée]pression|adolescent"),
]


def run(name, fn, kb):
    ok = 0
    for q, rx in CASES:
        hits = fn(q)
        good = any(re.search(rx, f"{h['category']} {h['title']}", re.I) for h in hits)
        ok += good
        if "-v" in sys.argv and not good:
            print(f"   ✗ {q[:60]}  → {[h['title'][:30] for h in hits[:3]]}")
    print(f"{name:<22} {ok}/{len(CASES)}")


kb = edn_kb.connect()
run("mots-clés seuls", lambda q: edn_kb.search(kb, q, limit=5), kb)
for tag in [a for a in sys.argv[1:] if not a.startswith("-")]:
    d = edn_kb.Dense(tag)
    if not d.available:
        print(tag, "indisponible :", d.err); continue
    run(f"hybride {tag}", lambda q: edn_kb.search(kb, q, limit=5, dense=d), kb)
