#!/usr/bin/env python3
"""Génère agents/coach-<spécialité>.md depuis un gabarit + les thèmes à fort rendement EDN. Relancer après modification."""
import re
import unicodedata
from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / "agents"

# catégorie (nom exact dans la base) -> thèmes fréquents à l'EDN (point de départ : à confronter à l'INDEX et aux annales)
SPECS = {
    "Cardiologie": "douleur thoracique/SCA, insuffisance cardiaque, fibrillation atriale et anticoagulants, TVP/EP, HTA, valvulopathies (RAo, IAo, IM), endocardite, péricardite, ECG (tachycardies, BAV), arrêt cardiaque, AOMI, facteurs de risque CV",
    "Pneumologie": "dyspnée aiguë, asthme, BPCO, pneumonie, EP, pneumothorax, pleurésie, cancer bronchique, tuberculose, sarcoïdose, SAOS, insuffisance respiratoire (oxygénothérapie, VNI)",
    "Neurologie": "AVC (thrombolyse, thrombectomie, prévention), épilepsie, céphalées/HSA/migraine, SEP, Parkinson, déficit moteur aigu, compression médullaire, Guillain-Barré/myasthénie, démences, coma/confusion",
    "Endocrinologie": "diabète (type 1/2, complications, acidocétose), thyroïde (hyper/hypothyroïdie, nodule), hypercalcémie/hyperparathyroïdie, surrénales, hypophyse, obésité, dyslipidémies",
    "Pédiatrie": "fièvre du nourrisson, bronchiolite, déshydratation, convulsion fébrile, développement psychomoteur, vaccination, maltraitance, invagination, maladies éruptives, croissance, urgences néonatales",
    "Gynécologie": "suivi de grossesse, pré-éclampsie/HTA gravidique, diabète gestationnel, GEU, hémorragies du post-partum, contraception, IVG, dépistage/cancers (sein, col), saignements anormaux, infections génitales, ménopause",
    "Maladies infectieuses": "antibiothérapie, méningites, sepsis/choc septique, endocardite, IST/VIH, hépatites, tuberculose, infections urinaires, pneumonies, paludisme et fièvre au retour de voyage, vaccination",
    "Rhumatologie": "polyarthrite rhumatoïde, spondyloarthrite, arthrite septique, goutte/microcristallines, lombalgie et sciatique, ostéoporose, LED, vascularites, artérite à cellules géantes/PPR, corticothérapie",
    "Médecine interne": "LED et connectivites, vascularites, sarcoïdose, fièvre prolongée, syndrome inflammatoire, SAPL, amylose, cytopénies auto-immunes, maladies systémiques",
    "Dermatologie": "mélanome et carcinomes cutanés, dermatite atopique/eczéma, psoriasis, urticaire/angiœdème, toxidermies (DRESS, Lyell), dermohypodermite, bulleuses, infections cutanées, lésions élémentaires",
    "Ophtalmologie": "œil rouge, baisse d'acuité visuelle brutale (OACR, OVCR, décollement de rétine), glaucome aigu, rétinopathie diabétique, DMLA, strabisme/amblyopie, uvéites, traumatismes oculaires",
    "Chirurgie orthopédique": "fractures (col du fémur, poignet), arthroplasties, infections ostéo-articulaires, syndrome des loges, traumatologie de l'enfant, rachis, lésions ligamentaires, ostéoporose fracturaire",
    "Psychiatrie": "dépression et risque suicidaire, schizophrénie, trouble bipolaire, anxiété/TOC/PTSD, addictions, soins sans consentement, urgences psychiatriques, TCA, psychotropes et effets indésirables",
}

TEMPLATE = """---
name: {name}
description: "Coach {cat} EDN/ECOS — thèmes à fort rendement, cours de l'étudiante, questions et stations ciblées sur cette spécialité."
mode: subagent
---

Tu es le coach de la spécialité **{cat}** pour l'EDN et les ECOS. La catégorie de cours dans la base est `{cat}` (filtre
`category` de `search_cours` / `list_cours`) ; les SdD associées sont dans la catégorie « Situations de départ ».

## THÈMES À FORT RENDEMENT (point de départ, à confronter à l'INDEX et aux annales — ne pas les traiter comme exhaustifs)
{themes}

## MÉTHODE
1. `get_profile`, puis `list_cours(category="{cat}")` et `progress` : où en est-elle, quels thèmes sont faibles ?
2. Pour un thème : cours dédié (`search_cours` avec `category`), puis la **SdD** correspondante (`search_cours` sans filtre,
   `get_cours(sdd=N)`), puis le Masterclass/entraînement pour s'exercer. Vérifie sur les sources officielles (skill `recherche-sources`).
3. Enchaîne **cours → fiche (skill `fiche`) → quiz de 3 à 5 questions (skill `quiz`, enregistré à la fin par `save_quiz`)**. Termine par un DP complet quand un
   thème est acquis (agent `examinateur`).
4. Par thème, donne toujours : urgences/signes de gravité, examens de 1ʳᵉ intention, traitement de 1ʳᵉ ligne et surveillance,
   et les 2-3 pièges d'EDN les plus fréquents.
5. Pour un oral/ECOS dans cette spécialité : anamnèse ciblée, examen clinique à verbaliser, annonce/éducation, conduite à tenir.

## COORDINATION
Planning global → `planificateur`. Épreuves chronométrées multi-spécialités, LCA, ECOS → `examinateur`. Questions transversales → `tuteur`.
"""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).strip("-")


for cat, themes in SPECS.items():
    name = "coach-" + slug(cat)
    body = TEMPLATE.format(name=name, cat=cat, themes="\n".join(f"- {t.strip()}" for t in re.split(r",\s*(?![^()]*\))", themes)))
    (AGENTS / f"{name}.md").write_text(body, encoding="utf-8")
print(len(SPECS), "coachs générés")
