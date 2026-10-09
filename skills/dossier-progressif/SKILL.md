---
name: dossier-progressif
description: Commande /dp <spécialité ou SdD> — un dossier progressif complet (3 à 8 questions) type EDN, chronométré, corrigé avec barème.
---

# /dp <spécialité ou SdD>

1. Choisis une SdD (`get_cours(sdd=N)`) ou un thème du coach de la spécialité ; vignette réaliste (âge, motif, contexte).
2. 5 à 8 questions qui suivent la prise en charge : première hypothèse → examens → diagnostic → traitement → suivi/éducation.
   La réponse attendue à la question N est révélée **seulement après** sa réponse, et conditionne la suite.
3. Barème par question (tout ou rien pour les items critiques : un oubli de signe de gravité ou une erreur dangereuse = 0 à la question).
4. Correction finale : score /20, ce qui était attendu, [source]. `save_quiz` UNE fois à la fin (format `dp`, une entrée par question avec ses points et son piège), comme dans le skill `quiz`.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
