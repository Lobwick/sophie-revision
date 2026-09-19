---
name: update-planning
description: Met à jour le planning de révision EDN de Sophie (data/planning-edn.json), en vérifiant toujours d'abord le calendrier iCloud partagé (gardes, dates d'examen) pour d'éventuelles modifications avant d'appliquer le changement demandé. À utiliser pour toute demande de mise à jour, ajustement, recalcul ou adaptation du planning — quelle qu'en soit la raison (garde ajoutée/annulée/déplacée, décalage d'une matière, changement de rythme, nouvelle date d'examen, imprévu, semaine à revoir, etc.).
---

# Mettre à jour le planning de révision de Sophie

Ce skill régit toute modification du planning (`data/planning-edn.json`, et par ricochet `data/cartes-edn.json` si le contenu change). Il s'applique dès que l'utilisateur demande de « mettre à jour », « ajuster », « recalculer », « adapter » ou « revoir » le planning — peu importe la raison invoquée dans sa demande. La règle non négociable : **on ne modifie jamais le planning sans avoir d'abord vérifié le calendrier**, même si la demande de l'utilisateur ne mentionne pas le calendrier explicitement.

## Contexte à connaître

- Le planning vit dans [data/planning-edn.json](../../data/planning-edn.json), documenté dans [README.md](../../README.md).
- Sophie a un calendrier iCloud partagé (« Sophie ❤️Félix ») qui contient entre autres ses **gardes de 24h** (résumé `Garde` ou variante contenant ce mot) et potentiellement des changements de dates d'examen ou d'événements pertinents. Le reste du calendrier est personnel (repas, soirées, voyages, événements de Félix) — ne jamais le faire remonter dans le planning ou dans une réponse à l'utilisateur au-delà de ce qui est pertinent pour les révisions.
- L'URL du calendrier (format `webcal://…`) est configurée côté serveur via la variable d'environnement `CALENDAR_ICS_URL` (voir `docker-compose.yml` et `.claude/launch.json`). Le serveur (`server/calendar-sync.js`) la resynchronise automatiquement toutes les 6h et expose le résultat sur `GET /api/gardes`.

## Étape 1 — Toujours vérifier le calendrier en premier

Deux façons de le faire, selon que le serveur du site tourne déjà ou non :

**A. Si le serveur tourne (preview_start / docker) :**
```bash
curl -s -X POST http://localhost:8811/api/gardes/refresh
```
Force une resynchronisation immédiate et retourne l'état à jour (`gardes`, `updated_at`, `enabled`, `error`).

**B. Sinon, resynchronise directement depuis le calendrier :**
```bash
curl -sL "https://p136-caldav.icloud.com/published/2/MTM2NTIwODY1MzEzNjUyMPUB1g3WgpeTnHDv0Ugq6hjg2s94zj4IdsyNv65-Uan1a-cE7a77K1OKH5LeFrcyEdkTLr_JViskZESfZVUwEKY" -o /tmp/sophie-calendar.ics
```
(`webcal://` = `https://`, c'est le même flux que `CALENDAR_ICS_URL`.) Parse-le ensuite (VEVENT : `SUMMARY`, `DTSTART`, `DTEND`, en dépliant les lignes RFC5545) — la logique de référence est dans [server/calendar-sync.js](../../server/calendar-sync.js), reproductible en Python/awk si besoin d'aller vite. Supprime le fichier temporaire une fois l'analyse terminée (ne pas laisser traîner une copie du calendrier personnel).

**Ce qu'il faut y chercher :**
1. **Gardes** (`SUMMARY` contenant « garde », insensible à la casse) : la synchro automatique du serveur ne fait que ça. Compare la liste obtenue à ce qui est déjà reflété dans le planning (les semaines qui portent une note/un badge de garde, cf. `phase_partiel.semaines`) — de nouvelles gardes, des gardes annulées, ou des gardes déplacées doivent être répercutées dans la mise à jour du planning que tu vas produire (rythme allégé le jour de récupération = date de fin de l'événement).
2. **Dates d'examen** : le serveur ne parse *pas* automatiquement ça. Parcours manuellement les résumés d'événements à la recherche de mots comme « partiel », « EDN », « examen », « ECOS », « épreuve ». Si une date diffère de `meta.cible_immediate.date` ou de l'estimation `meta.cible_principale`, signale-le explicitement à l'utilisateur avant de trancher — ne remplace jamais une date confirmée par une estimation, et inversement ne garde jamais une estimation périmée si une date réelle apparaît.
3. Tout autre événement dont le résumé indique sans ambiguïté un empêchement de réviser sur une période donnée (ex. un voyage explicitement lié aux études) — reste conservateur, ne réinterprète pas des événements personnels ambigus comme des contraintes de révision.

## Étape 2 — Rendre compte des écarts trouvés

Avant d'écrire quoi que ce soit, dis à l'utilisateur ce que la vérification du calendrier a changé (ou confirme qu'il n'y a rien de neuf). Exemple : « Le calendrier montre 2 nouvelles gardes depuis la dernière génération du planning (12/11, 03/12) et aucun changement de date d'examen. » Ne saute pas cette étape même si la demande de mise à jour semble n'avoir rien à voir avec le calendrier.

## Étape 3 — Appliquer la modification demandée

Une fois le calendrier vérifié, applique le changement que l'utilisateur a demandé (décalage de matière, ajustement de rythme, réorganisation d'une semaine, nouvelle contrainte, etc.), **en conservant la structure et les règles déjà établies** :

- `phase_partiel.semaines` : 22 semaines (ou le nombre ajusté), une matière dominante par semaine, `edn_transversal` en rotation, `vacances`/`note` quand pertinent.
- Priorité rang A partout — c'est ce qui conditionne le seuil ECOS.
- Répartition ≈80% matière du partiel / ≈20% EDN transversal tant qu'on est avant le 16/02 (ou la nouvelle échéance si elle a changé).
- Règle des gardes : jour de récupération = pas de séance structurée, cartes dues en mode léger seulement.
- Toute date EDN qui reste estimée doit rester marquée `a_confirmer: true` avec un `statut_dates` à jour — ne jamais faire disparaître cet avertissement tant que la date n'est pas officiellement confirmée.
- Si le changement affecte le contenu des cartes (nouvelle matière, spécialité retirée), mets à jour `data/cartes-edn.json` en conséquence (nouveau deck si besoin, cartes rang A, même format que l'existant, `srs: null`).

## Étape 4 — Valider avant de rendre la main

1. Valide le JSON :
   ```bash
   python3 -c "import json; json.load(open('data/planning-edn.json')); json.load(open('data/cartes-edn.json')); print('ok')"
   ```
2. Si possible, relance le site en local (`preview_start` avec la config `sophie-revision` de `.claude/launch.json`) et vérifie au moins `index.html` et `planning.html` dans le navigateur (pas d'erreur console, la semaine en cours et les badges de garde s'affichent correctement).
3. Résume à l'utilisateur : ce que le calendrier a révélé, ce qui a été changé dans le planning, et ce qui reste à confirmer (dates EDN notamment).
