---
name: bilan-semaine
description: Commande /bilan — bilan hebdomadaire chiffré (volume, qualité par type et spécialité, retards) et plan de la semaine suivante. Agent planificateur.
---

# /bilan

1. `progress(days=7)`, puis `progress(days=30)` pour la tendance ; `due_reviews` pour le retard.
2. Présente en 6 lignes : heures réalisées vs prévues, exercices par type, moyenne par type, 2 forces, 2 fragilités, retard de révisions.
3. Décisions : quoi réduire/ajouter, quel thème re-travailler (cours + fiche), quel format s'entraîner davantage (DP, LCA, ECOS).
4. Propose le plan de la semaine suivante (skill `plan-revision`). Pas de culpabilisation ; mentionne ce qui va bien.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.
