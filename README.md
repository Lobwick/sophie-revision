# Sophie · Coach de révision EDN

Site de révision (planning, cartes en répétition espacée, journal d'erreurs), avec un petit serveur Node/Express qui sert les pages statiques et persiste les données dans un fichier JSON monté en volume Docker. Pensé pour tourner sur une Freebox via Docker Compose.

## Structure

- `index.html` — tableau de bord : compte à rebours, semaine en cours, cartes dues, avancement par spécialité
- `planning.html` — les 22 semaines jusqu'au partiel du 16/02/2027, tour EDN complet, jours d'épreuve, filet de la seconde session
- `cartes.html` — révision par répétition espacée (SM-2 simplifié), navigation dans le deck, ajout de cartes personnelles
- `journal.html` — journal d'erreurs + export/import de sauvegarde
- `data/planning-edn.json`, `data/cartes-edn.json` — données de référence, versionnées avec le site (contenu, pas progression)
- `css/style.css`, `js/app.js` — styles et logique partagée du front
- `server/` — serveur Express : sert les pages statiques **et** l'API `/api/*` qui lit/écrit le fichier de données
- `Dockerfile`, `docker-compose.yml` — build et déploiement du conteneur

## Où vivent les données

Deux catégories bien séparées :

1. **Contenu de référence** (`data/*.json`) : le planning et le deck de cartes générés au départ. Versionné avec le site, modifié en éditant les fichiers ou via git — pas de partie dynamique ici.
2. **Données personnelles de Sophie** (progression SRS, cartes ajoutées, journal d'erreurs) : stockées côté serveur dans un fichier JSON (`/app/db/store.json` dans le conteneur), **pas dans le navigateur**. Ça veut dire que la progression est la même sur tous les appareils qui pointent vers le même serveur, et qu'elle survit à la fermeture du navigateur.

Le fichier de données vit dans un **volume Docker nommé** (`sophie_data`), donc :
- `docker compose restart`, `docker compose down` + `up`, un reboot de la Freebox, ou la recréation du conteneur après un nouveau build → les données sont conservées.
- Seul `docker volume rm sophie-revision_sophie_data` (ou un `docker compose down -v`) efface réellement les données.

La page **Journal** garde en plus un bouton « Exporter une sauvegarde » / « Importer une sauvegarde » pour un backup manuel téléchargeable (utile avant une manipulation risquée, ou pour transférer les données ailleurs).

## Déploiement sur la Freebox (Docker Compose)

Copier tout ce dossier sur la Freebox (ou cloner le dépôt), puis :

```bash
docker compose up -d --build
```

Le site est alors servi sur le port `8811` (modifiable dans `docker-compose.yml`, section `ports`). Pour changer le port externe, éditer la ligne `"8811:8080"` (seul le premier nombre, le port hôte, doit changer).

Pour mettre à jour le site après une modification du code (planning, cartes, front, serveur) :

```bash
docker compose up -d --build
```

Les données de progression ne sont pas affectées par un rebuild : elles vivent dans le volume, pas dans l'image.

Pour consulter les logs :

```bash
docker compose logs -f
```

## Développement local sans Docker

Le serveur Node peut tourner directement sur la machine (utile pour itérer vite) :

```bash
cd server && npm install
PORT=8811 DB_PATH=../db/store.json node server.js
```

Puis ouvrir `http://localhost:8811`. Cette base locale (`db/store.json` à la racine) est distincte de celle du conteneur Docker — c'est un bac à sable de dev, à ne pas committer (déjà exclu du build via `.dockerignore`).

## Mettre à jour le contenu de référence

- Ajouter/modifier des cartes du deck de départ : éditer `data/cartes-edn.json` (respecter le schéma décrit dans `meta.schema`). Les cartes ajoutées par Sophie via le formulaire du site n'ont pas besoin de ça, elles sont déjà persistées côté serveur.
- Modifier le planning : éditer `data/planning-edn.json`.

## API

Tout est sous `/api/*`, consommé par `js/app.js` :

| Route | Méthode | Rôle |
|---|---|---|
| `/api/data` | GET | état complet (srs, cartes perso, journal) |
| `/api/srs` | PUT | met à jour l'état SRS d'une carte |
| `/api/custom-cards` | POST | ajoute une carte personnelle |
| `/api/custom-cards/:id` | DELETE | supprime une carte personnelle |
| `/api/journal` | POST | ajoute une entrée de journal |
| `/api/journal/:id` | DELETE | supprime une entrée de journal |
| `/api/export` | GET | export JSON téléchargeable |
| `/api/import` | POST | restaure un export JSON (remplace tout) |
| `/api/gardes` | GET | dernières gardes connues, synchronisées depuis le calendrier iCloud |
| `/api/gardes/refresh` | POST | force une resynchronisation immédiate du calendrier |

Pas d'authentification : c'est un usage personnel derrière la Freebox. Si le port est un jour exposé directement sur Internet (redirection de port publique), il vaut mieux le mettre derrière une authentification basique ou un VPN plutôt que de l'ouvrir tel quel.

## Synchronisation avec le calendrier (gardes)

Sophie a un calendrier iCloud partagé (« Sophie ❤️Félix ») qui contient, entre autres événements personnels, ses **gardes de 24h**. Le serveur ([server/calendar-sync.js](server/calendar-sync.js)) télécharge ce calendrier (format `.ics`, l'URL `webcal://` fonctionne directement en `https://`), filtre uniquement les événements dont le résumé contient « garde », et expose le résultat via `/api/gardes`. Le reste du calendrier (vie privée, événements de Félix) n'est jamais lu au-delà de ce filtre ni exposé par l'API.

- Resynchronisation automatique toutes les 6h, plus au démarrage du serveur.
- Configuré via la variable d'environnement `CALENDAR_ICS_URL` (voir `docker-compose.yml` et `.claude/launch.json`). Si elle est absente, la fonctionnalité se désactive proprement (`enabled: false`) sans casser le reste du site.
- Le front (`index.html`, `planning.html`) affiche les gardes connues : badge sur la semaine concernée, et jour de récupération (le lendemain) marqué comme « rythme allégé », en cohérence avec la règle du planning.
- Cette synchro ne couvre que les gardes. Les changements de date d'examen (partiel, EDN) ne sont **pas** détectés automatiquement — c'est le rôle du skill `update-planning` (voir ci-dessous) de vérifier ça à la main lors d'une mise à jour du planning.

## Skill : mise à jour du planning

Le skill [.claude/skills/update-planning/SKILL.md](.claude/skills/update-planning/SKILL.md) encadre toute future modification de `data/planning-edn.json`. Sa règle centrale : **ne jamais modifier le planning sans avoir d'abord revérifié le calendrier** (nouvelles gardes, dates d'examen changées), quelle que soit la raison de la demande de mise à jour. Il documente aussi comment resynchroniser manuellement si le serveur ne tourne pas, et comment garder le planning cohérent avec sa structure existante (22 semaines, priorité rang A, répartition 80/20, règle des gardes) après modification.

## Contexte

Sophie est en 5e année (DFASM2), année universitaire 2026-2027. Deux échéances :

- **Partiel du 16 février 2027** (date confirmée) : Ophtalmologie, ORL, Chirurgie maxillo-faciale, Médecine intensive et réanimation, Gériatrie/médecine adaptative et de réadaptation.
- **EDN, première session** : accès à l'internat, prévue en octobre 2027 (année universitaire 2027-2028). **Les dates officielles n'étaient pas publiées au moment de la génération de ce planning** (19/09/2026) — l'arrêté d'ouverture existe (23/03/2026) mais le calendrier précis des épreuves n'était pas accessible publiquement. Les comptes UFR pour cette campagne ouvrent le 21/09/2026 ; les dates exactes devraient être communiquées peu après. `data/planning-edn.json` utilise une estimation clairement signalée (`a_confirmer: true`) par analogie avec les campagnes précédentes — à corriger dans le fichier dès que les dates réelles sont connues (champ `meta.cible_principale`).

Le planning tient compte des gardes de 24h et des stages à temps plein (rythme visé : 10-15h/semaine, pas un sprint permanent) et répartit environ 80% du temps sur les matières du partiel et 20% en révision transversale EDN en continu jusqu'au 16/02.

## Avertissement sur le contenu

Les cartes et le planning ont été générés automatiquement à partir d'une recherche de sources publiques (LiSA/UNESS, référentiels de collèges, HAS) et de connaissances médicales générales. Ils doivent être recoupés avec LiSA et les référentiels de collège avant d'être appris — ce sont les seules sources opposables, en particulier pour les seuils chiffrés et les schémas thérapeutiques.
