# Déploiement et connexion à Claude / ChatGPT

claude.ai et ChatGPT ne se connectent qu'à un serveur MCP **distant en HTTPS**. Le serveur ne contient que la base de cours (21 Mo),
les agents/skills et un petit fichier de suivi.

## 1. Lancer le serveur
```
openssl rand -hex 24                         # → le jeton ; le mettre dans .env :  EDN_MCP_TOKEN=…
# .env aussi : EDN_SITE_PASSWORD=<mot de passe du site PDF>   EDN_PUBLIC_URL=https://<ton-domaine>
docker compose -f deploy/compose.yaml up -d --build
curl -s localhost:8001/health                # {"ok":true}
```
Sans Docker : `EDN_MCP_TOKEN=… python3 scripts/edn_mcp.py` (Python ≥ 3.9, stdlib seule).

## 2. Le rendre joignable en HTTPS (au choix)
- **Cloudflare Tunnel** (le plus simple, sans ouvrir de port) : `cloudflared tunnel --url http://localhost:8001` pour tester,
  puis un tunnel nommé avec un domaine pour un usage durable.
- **Reverse proxy** (Traefik/Caddy) devant `127.0.0.1:8001`, comme le projet vélo sur la Freebox.

## Tableau de bord
`https://<domaine>/` : avancement, planning, cours (recherche + filtres), cartes en répétition espacée, journal d'erreurs, gardes. Même mot de passe
que le lecteur de PDF. Les écritures (réviser une carte, ajouter une erreur…) exigent un en-tête propre à l'application (anti-CSRF) et sont
commitées dans le suivi git.
- **Gardes** : `EDN_CALENDAR_ICS_URL` (lien `webcal://` ou `https://` du calendrier partagé) dans `.env`. Seuls les événements dont le titre
  contient « garde » sont lus ; le reste du calendrier n'est jamais exposé. Sans cette variable, la fonction est simplement désactivée.
- **Reprendre la progression de l'ancien site `sophie-revision`** (sur la Freebox, le volume Docker `sophie_data`) :
  ```
  docker cp sophie-revision:/app/db/store.json ./store-sophie.json
  EDN_DATA_DIR=suivi python3 scripts/import_sophie.py store-sophie.json            # simulation : affiche ce qui serait importé
  EDN_DATA_DIR=suivi python3 scripts/import_sophie.py store-sophie.json --apply    # un seul commit git, rien n'est écrasé
  ```
  Les cartes sont reconnues par leur identifiant (inchangé) ; une carte inconnue ou invalide est signalée et ignorée.

## Site de lecture des PDF
Le même serveur, sur la même URL publique, sert un lecteur de PDF : `https://<domaine>/pdf/<cours>?page=N` ouvre le PDF d'origine
**à la bonne page** (pdf.js embarqué, sans CDN ; mobile compris : glisser pour changer de page, bouton « Texte indexé » pour voir ce que
la recherche a lu, utile quand l'OCR se trompe). Les agents joignent ce lien à chaque citation de cours.
- Accès par **mot de passe** (`EDN_SITE_PASSWORD`, cookie `HttpOnly` de 30 jours, 8 essais / 5 min) ; sans mot de passe défini, le site est désactivé.
- Les liens ne contiennent **ni jeton ni mot de passe** : ils peuvent être partagés avec elle sans risque, mais exigent la connexion.
- Les PDF ne sont pas dans l'image : `compose.yaml` monte `../cours` en lecture seule dans `/app/cours`.
- Derrière un proxy HTTPS, il doit envoyer `X-Forwarded-Proto: https` (Cloudflare Tunnel, Traefik et Caddy le font) pour que le cookie soit `Secure`.
- `EDN_PUBLIC_URL` doit être l'URL publique exacte, sans `/` final : sans elle, les liens sont relatifs et les agents citent sans lien.

## 3. Connecter les clients
L'URL à donner est `https://<domaine>/t/<JETON>/mcp` : le jeton est dans l'URL, car les formulaires de connecteurs n'ont pas toujours
de champ d'en-tête. **Traite cette URL comme un mot de passe** (ne la partage pas ; régénère le jeton si elle fuit).
- **Claude (web/mobile)** : Paramètres → Connecteurs → Ajouter un connecteur personnalisé → coller l'URL. Activer le connecteur dans la conversation.
- **ChatGPT** : Paramètres → Connecteurs (mode développeur, selon l'offre) → ajouter un serveur MCP distant → coller l'URL.
  Vérifie dans l'interface actuelle que ton abonnement permet les connecteurs MCP personnalisés.
- **Claude Code / Codex** : `claude mcp add --transport http coach-internat https://<domaine>/mcp --header "X-Api-Key: <JETON>"`.

## 4. Prompt de démarrage (à mettre dans les instructions d'un Projet Claude ou d'un GPT)
```
Tu es mon coach de révision EDN + ECOS (Lille). Utilise le connecteur « coach-internat » : au début de chaque conversation appelle
get_profile ; pour une demande, appelle list_skills puis get_skill (/plan, /today, /fiche, /quiz, /dp, /ecos, /lca, /bilan) et
get_agent (planificateur, tuteur, examinateur, coach-<spécialité>). Appuie tout contenu médical sur search_cours / get_cours (cite
[Catégorie — Titre, p.N]) et vérifie sur les sources officielles ; signale toute divergence. Enregistre chaque exercice avec log_attempt.
```

## Persistance du suivi (rien ne se perd au redémarrage)
Le suivi (profil, journal, révisions, notes, plans, cartes personnelles, erreurs) est un **dépôt git de fichiers Markdown** dans le
dossier `suivi/` **de ton disque**, monté dans le conteneur sur `/data` (`compose.yaml`). Il survit donc à `restart`, `up --build`,
`down -v`, à la suppression du conteneur et de l'image. Vérifié : écriture, destruction du conteneur, nouveau conteneur, données et historique intacts.
- **Garde-fou** : l'image impose `EDN_REQUIRE_PERSIST=1`. Si `/data` n'est pas un dossier monté (`docker run` sans `-v`), le serveur **refuse de
  démarrer** avec un message, au lieu de perdre tout en silence à la prochaine recréation. (Pas de `VOLUME` dans le Dockerfile : il créerait un
  volume anonyme et neutraliserait ce contrôle.)
- **Droits** : Linux (Freebox) → `EDN_UID=$(id -u)` et `EDN_GID=$(id -g)` dans `.env`. Docker Desktop (Mac/Windows) → `EDN_UID=0 EDN_GID=0`.
  Le dossier monté doit être sous un chemin partagé avec Docker Desktop (ex. `/Users/…`, pas `/tmp`).
- **Lire / sauvegarder sans Docker** : `git -C suivi log`, `cp -r suivi sauvegarde/`. Annuler le dernier changement : outil `undo_last_change`.
- La base de cours (`knowledge/cours.db`) se reconstruit à partir de `cours/` ; elle n'est pas dans le suivi.
