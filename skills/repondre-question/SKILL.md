---
name: repondre-question
description: Procédure pour toute question médicale — chercher dans les cours, sinon sur internet (sources officielles), citer la source à chaque fois, ne jamais supposer ni répondre de mémoire.
---

# Répondre à une question

1. **Reformule** la question en 2 jeux de mots-clés médicaux (terme courant + terme du cours/synonyme).
2. **Cours** : `search_cours` (avec puis sans `category` ; `sdd` si c'est une situation de départ). Lis le meilleur résultat avec
   `get_cours` (page±1). Note : titre, page, qualité du cours (`qualite` : `low`/`empty` = incomplet).
3. **Décide** :
   - trouvé, clair → réponds ; vérifie sur une source officielle tout point qui évolue (voir `recherche-sources`) ;
   - partiel → donne ce que dit le cours, puis complète sur le web en séparant les deux ;
   - absent → web officiel, et écris « absent des cours de l'étudiante » ;
   - rien de fiable → « je n'ai pas trouvé ». Pas de réponse de mémoire, pas de « en général ».
4. **Format de la réponse** (sections omises si vides) :
   - **Réponse** (courte, directe)
   - **Ce que disent les cours** — [Catégorie — Titre, p.N](lien)
   - **Ce que dit la source officielle** — URL, année, consultée le AAAA-MM-JJ
   - **Non vérifié / à confirmer** — ce que tu n'as pas pu sourcer
5. **Garder une trace** : si la réponse mérite d'être revue, `save_note` (titre, contenu, `sources` obligatoires) ; si c'était un exercice,
   `log_attempt`. Rien n'est écrit sans source.
6. Ne devine jamais une donnée sur l'étudiante : si elle manque (date d'épreuve, heures…), demande-la.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
