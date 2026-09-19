# Sophie · Coach de révision EDN

Site statique (HTML/CSS/JS vanilla, aucune dépendance, aucun build). Fait pour être servi tel quel par n'importe quel serveur de fichiers statiques — y compris le serveur de fichiers de la Freebox.

## Structure

- `index.html` — tableau de bord : compte à rebours, journée du jour, cartes dues, avancement par spécialité
- `planning.html` — sprint complet des 23 jours (19/09 → 11/10/2026), jours d'épreuve, filet de janvier
- `cartes.html` — révision par répétition espacée (SM-2 simplifié), navigation dans le deck, ajout de cartes personnelles
- `journal.html` — journal d'erreurs + export/import de sauvegarde
- `data/planning-edn.json`, `data/cartes-edn.json` — données sources (éditables directement)
- `css/style.css`, `js/app.js` — styles et logique partagée

## Hébergement sur la Freebox

Le site n'a besoin que d'être servi en HTTP (le `fetch()` des fichiers JSON échoue en ouverture directe `file://`). Il suffit de copier ce dossier entier dans le répertoire servi par le serveur de fichiers de la Freebox et de pointer dessus. Aucune étape de build, aucun serveur d'application, aucune base de données.

## Stockage des données

La progression des révisions (SRS), les cartes ajoutées par Sophie et le journal d'erreurs sont stockés **uniquement dans le navigateur** (`localStorage`), pas sur le serveur. Cela signifie :

- Chaque appareil/navigateur a sa propre progression.
- Vider les données du navigateur efface tout.
- La page **Journal** propose un bouton « Exporter une sauvegarde » (à faire régulièrement) et « Importer une sauvegarde » pour restaurer ou transférer les données vers un autre appareil.

## Mettre à jour le contenu

- Ajouter/modifier des cartes : éditer `data/cartes-edn.json` (respecter le schéma décrit dans `meta.schema`), ou utiliser le formulaire « Ajouter une carte » du site (ces cartes-là restent côté navigateur).
- Modifier le planning : éditer `data/planning-edn.json`.

## Avertissement sur le contenu

Les cartes et le planning ont été générés automatiquement à partir d'une recherche de sources publiques (LiSA/UNESS, référentiels de collèges, HAS). Ils doivent être recoupés avec LiSA et les référentiels de collège avant d'être appris — ce sont les seules sources opposables, en particulier pour les seuils chiffrés et les schémas thérapeutiques.
