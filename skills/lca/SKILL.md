---
name: lca
description: Commande /lca — entraînement lecture critique d'articles (lecture, grille méthodologique, questions types EDN), à partir des cours LCA et annales fournis.
---

# /lca [article]

1. Matériel : cours « LCA » et « Cours publics — Annales LCA » de la base (`list_cours(category="LCA")`). Les PDF d'annales
   peuvent être vides (images) : demande-lui de coller le texte de l'article si besoin.
2. Procédure : (a) type d'étude et question PICO ; (b) validité interne (biais, randomisation, aveugle, perdus de vue, analyse en ITT,
   critère de jugement) ; (c) résultats (effet, IC95 %, p, significativité vs pertinence clinique) ; (d) validité externe et conclusions
   abusives ; (e) partie physiopathologique/clinique.
3. Pose les questions **une à une** (style EDN), corrige avec la grille, cite le cours [LCA — Titre, p.N](lien).
4. Chiffres : calcule-les devant elle (RR, RRR, RAR, NNT) plutôt que de les affirmer.
5. `log_attempt` (kind `lca`).

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
