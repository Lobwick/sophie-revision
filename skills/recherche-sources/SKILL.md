---
name: recherche-sources
description: Procédure de vérification web d'un point médical (HAS, collèges, CNG, ANSM, sociétés savantes) et de signalement des divergences avec les cours.
---

# Recherche de sources

À utiliser pour tout traitement, seuil, dépistage, vaccination, classification, ou date/modalité d'épreuve.
1. Cherche d'abord dans les cours (`search_cours`) ; note la formulation du cours.
2. Recherche web ciblée, par ordre : **HAS** (has-sante.fr), **collèges nationaux** / référentiels de 2ᵉ cycle, **CNG** (cng.sante.fr,
   modalités EDN/ECOS), **ANSM / Vidal** (médicaments), **sociétés savantes** (ESC, SPILF, SFD, etc.). Prends l'année la plus récente.
3. Compare : identique / précisé / **divergent**. Divergence → montre les deux avec année et URL, dis lequel viser à l'EDN
   (reco officielle la plus récente par défaut), invite à vérifier avec ses enseignants si le cours est plus récent.
4. Pas de web disponible ou rien de fiable : « non vérifié sur une source officielle » — jamais de valeur reconstituée de mémoire.
5. Jamais de blog ni de forum comme source d'un fait médical.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.
