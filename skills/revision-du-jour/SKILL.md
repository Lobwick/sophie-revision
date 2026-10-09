---
name: revision-du-jour
description: Commande /today — programme du jour court : révisions espacées dues, un thème neuf, un exercice chronométré.
---

# /today

1. `get_profile`, `due_reviews` (limite 10), `progress` (7 jours).
2. Propose un programme tenant dans le temps du jour (demande la durée dispo si inconnue, sinon 3 h) :
   - **Rappel** : les cartes dues, une par une (question → réponse → `log_attempt`).
   - **Nouveau** : un thème de la semaine du plan (cours + `fiche`).
   - **Exercice** : 5 QI ou 1 DP (skill `quiz`), chronométré.
3. Ouvre par UNE ligne : « Aujourd'hui : 8 révisions, SdD 51 Obésité, 1 DP d'endocrino (≈ 3 h) ».
4. Fin de séance : demande comment ça s'est passé, `log_attempt` de ce qui n'a pas été journalisé.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
