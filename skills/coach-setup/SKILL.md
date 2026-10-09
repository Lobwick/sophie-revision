---
name: coach-setup
description: Première configuration et mises à jour — profil (heures, points faibles, style) et dates des examens : écrit final (EDN), oral final (ECOS), et chaque examen de l'année avec ses matières par date. Alimente l'onglet Examens du site ; rejouable pour modifier.
---

# /coach-setup

1. **Lire l'existant** : `get_profile` et `list_exams`. Ne repose pas ce qui est déjà renseigné ; propose seulement de le **modifier** (« ton partiel est noté au 16/02, ça n'a pas changé ? »).
2. **Pose en un seul message** (réponses courtes acceptées ; « je ne sais pas » est une réponse valable) :
   - **Écrit final (EDN)** : date exacte, ou « pas encore publiée » (prévu en octobre 2027 ; le CNG publie les dates plus tard).
   - **Oral final (ECOS)** : date ou période.
   - **Examens de l'année** (5ᵉ année) : « liste-les tous ; pour **chaque date** : nom, date (et heure si tu l'as), **matières de ce jour**, lieu si utile ».
     Elle peut coller un tableau, un mail de la scolarité ou une liste : tu l'analyses toi-même. Une date = un examen.
   - Heures de révision réelles par semaine, jours off, gardes et stages à venir.
   - Spécialités où elle se sent faible / forte ; ressources déjà utilisées (annales, ECOS déjà passés ?).
   - Style : direct / encourageant / très structuré ; messages courts ou détaillés ; prénom.
3. **Ne devine rien** : date inconnue → ne l'invente pas. Pour l'EDN/ECOS inconnus : `save_exam(type="edn", date=<estimation annoncée>, estime=true)` seulement si elle donne
   une estimation ; sinon laisse vide et dis-le.
4. **Enregistre** :
   - `set_profile` : `nom`, `heures_par_semaine`, `jours_off`, `points_faibles`, `style`, `notes`, `ville`, et `exam_edn` / `exam_ecos` **seulement si la date est confirmée**
     (cela met aussi à jour la fiche d'examen correspondante).
   - `save_exam` **une fois par examen** : `type` (`partiel`, `autre`, `edn`, `ecos`), `nom`, `date` (AAAA-MM-JJ), `heure` (HH:MM), `matieres` (liste), `lieu`, `note`,
     `estime=true` si la date n'est pas confirmée. Modifier un examen existant : repasse son `id` (`list_exams`) ; le supprimer : `delete_exam`.
5. **Récapitule** dans un tableau (date · nom · matières · confirmé/à confirmer) et demande « c'est bon ? ». Corrige avec `save_exam(id=…)`.
6. **Termine** : « ✔ Enregistré — l'onglet **Examens** du site se met à jour tout seul. » (seulement si la réponse des outils contient la ligne `[site] … se recharge tout seul`).
   Rappelle que **le planning de révision n'est pas recalculé automatiquement** quand une date change : propose `/plan` pour le refaire. Enchaîne avec `plan-revision` si elle le souhaite.
Ne redemande pas le setup dans la même session.
