---
name: plan-revision
description: Commande /plan — rétroplanning jusqu'à l'EDN et aux ECOS, plan de la semaine, ajustement selon les résultats. Agent planificateur.
---

# /plan

Adopte l'agent `planificateur` (`get_agent`).
1. `get_profile` ; profil incomplet → skill `coach-setup`.
2. `plan_backwards` (trame) + `progress` (30 jours) : ajuste le focus aux spécialités les plus faibles.
3. Présente : (a) vue d'ensemble par phase, (b) **la semaine en cours** jour par jour (durée, thème, type d'exercice), un jour off.
4. Termine par UNE question : « Ça tient avec ta semaine réelle ? » et corrige si non. Ne promets rien que `heures_par_semaine` ne permet pas.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
