---
name: fiche
description: Commande /fiche <sujet> — fiche de révision d'une page à partir des cours (cités) et vérifiée sur les sources officielles. Agent tuteur.
---

# /fiche <sujet>

1. `search_cours` (mots-clés précis, `category` si connue) puis `get_cours` du cours dédié ET de la SdD associée (`sdd`).
2. Vérifie les points qui bougent (skill `recherche-sources`). Divergence → encadré « ⚠ Divergence ».
3. Format fixe, une page maximum, **rang A en premier** :
   - **À savoir absolument** (rang A) : définition en une ligne, 5-8 points clés.
   - **Orientation / diagnostic** : signes de gravité d'abord, examens de 1ʳᵉ intention, critères diagnostiques.
   - **Traitement** : urgence, 1ʳᵉ ligne, surveillance, éducation. Doses seulement si présentes dans le cours ou la reco citée.
   - **Pièges d'EDN** : 3 maximum.
   - **Sources** : [Catégorie — Titre, p.N](lien) — un lien par page citée — et URLs officielles (année, date de consultation).
4. Termine par 2 questions de rappel actif sur la fiche, puis `log_attempt` (kind `fiche`).
5. Sauvegarde la fiche avec `save_note` (titre, contenu, `sources` = les mêmes citations, liens inclus) : elle est historisée (`history`) et annulable (`undo_last_change`).

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
