---
name: quiz
description: Commande /quiz [spécialité] [item] [qi|dp|kfp|tcs] [n] — lance un quiz sur une spécialité ou un item, pose les questions une à une, corrige, affiche le score final, puis enregistre le résultat sur le site (score, erreurs, prochaine révision, points forts/faibles). Agent examinateur.
---

# /quiz [spécialité] [item] [format] [n]

Défaut : 5 QI. Adopte l'agent `examinateur`. **Rien n'est enregistré pendant le quiz : un seul `save_quiz` à la fin.**

## 1. Choisir la spécialité
- Spécialité donnée (« /quiz cardio ») → retrouve sa **clé** avec `quiz_options` (sans paramètre : les 20 spécialités, avec les résultats déjà obtenus).
- Rien de précis → appelle `quiz_options`, propose la liste (avec le score de chacune) et demande laquelle. Suggère d'abord une spécialité
  **faible** (`progress`, `quiz_options`) ou des `due_reviews`.

## 2. Choisir l'item
- Appelle `quiz_options(specialite)` puis `list_cours(category=…)` (cours de la spécialité) et, pour une situation de départ,
  `search_cours(query, category="Situations de départ")`. Propose **6 à 8 items** (titre du cours ou SdD ; numéro de SdD si connu), plus
  « Tout / mélange » et « autre sujet ». Mets en tête les items déjà **faibles** (`sujets_a_retravailler` dans le bilan de `save_quiz`/site).
- Item donné d'emblée → vérifie qu'il existe (`search_cours`), sinon dis-le et propose les plus proches. Ne devine jamais un numéro d'item.
- Confirme en une ligne : « Quiz · Cardiologie · Insuffisance aortique · 5 QI — on y va ? »

## 3. Poser les questions
1. `search_cours` puis `get_cours` : **lis** le cours avant de poser. Chaque question est ancrée dans une page précise. Varie : diagnostic,
   examen, traitement, surveillance, urgence.
2. **Une question à la fois.** QI : énoncé court + choix ou réponse courte ; DP : vignette puis questions qui se dévoilent ; TCS : hypothèse +
   donnée nouvelle + échelle −2…+2. Chronomètre si demandé.
3. Après sa réponse : verdict, **points** (QI : 1 ou 0 ; DP/TCS : barème indiqué, crédit partiel possible), justification courte, l'erreur-type,
   source **[Catégorie — Titre, p.N](lien)**. Puis la question suivante. Tiens le compte (énoncé abrégé, points, max, piège, source).

## 4. Résultat final (à l'écran, avant d'enregistrer)
Affiche : **score x/y et %**, un tableau question par question (✔/✘, points), les 2-3 pièges à retenir, les sources cliquables.

## 5. Enregistrer — `save_quiz` UNE fois
Appelle `save_quiz(specialite=<clé>, sujet=<item>, format, sdd?, minutes?, questions=[{enonce, points, max, piege, source}])`.
Il enregistre sur le site : le score, les questions ratées dans le **journal d'erreurs**, la **prochaine révision** de l'item, et met à jour
**points forts / faibles** et l'avancement par spécialité. Puis dis en 2-3 lignes :
- le score de la session et son niveau, le niveau de la spécialité (`bilan` renvoyé : fort ≥ 70 %, faible < 50 %, « à confirmer » sous 5 questions) ;
- ce qui est à retravailler (`sujets_a_retravailler`) et la suite proposée (fiche, nouveau quiz ciblé, cartes) ;
- que le détail est dans l'onglet **Avancement** du site.

## Règles
- **Jamais de score inventé** : `points` = exactement ce que la correction a décidé. Quiz interrompu → demande si tu enregistres les questions déjà
  corrigées (alors seulement celles-là) ou rien.
- Ne rappelle pas `log_attempt` pour ces questions (double comptage). Si `save_quiz` échoue, dis-le avec le message d'erreur ; ne réessaie
  qu'une fois, après correction.
- Cours lacunaire ou question hors cours : dis-le, appuie-toi sur la source officielle citée (skill `recherche-sources`), jamais de mémoire.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
