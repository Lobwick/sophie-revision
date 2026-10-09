# Coach internat — EDN + ECOS (Lille)

Espace de travail pour accompagner les révisions de l'EDN et des ECOS à partir de **931 PDF de cours** (`cours/`, source intacte)
et de la recherche web (HAS, CNG, collèges…). Dérivé de la structure du projet `ai-running-coach` (agents/ + skills/ + MCP).

## Flux

```
cours/*.pdf ──run_ocr.py (Apple Vision)──► knowledge/ocr_cache.jsonl ─┐
cours/*.pdf ──extract_pdfs.py (texte natif + OCR)───────────────────┴► knowledge/cours.db (SQLite FTS5, 29 430 pages) + md/ + INDEX.md
                                        │
 Claude / ChatGPT ◄── MCP (scripts/edn_server → edn_mcp.py) ── agents/ + skills/ + recherche + suivi (suivi/ : Markdown + git)
```

Les pages avec images (schémas, tableaux, diapos) sont lues par OCR et leur texte est préfixé `[Texte des images]`.
**Recherche sémantique (embeddings) : testée, non retenue.** Sur 15 questions cliniques sans mot commun avec les cours
(`tests/eval_search.py`), mots-clés seuls 11/15, hybride MiniLM 10/15 ; mpnet abandonné (≈ 4 p/s, plusieurs heures). Le code reste
(`scripts/build_embeddings.py`, `edn_kb.Dense`, opt-in `EDN_EMB_TAG`) pour un meilleur modèle (ex. multilingual-e5-large, ≈ 2 h 30).
Le MCP renvoie des **extraits courts** à la demande (`search_cours` → `get_cours`) : peu de tokens, aucun téléversement de fichiers.

## Agents (`agents/`)
`planificateur` · `tuteur` · `examinateur` · 13 coachs de spécialité `coach-<spécialité>` (générés par `scripts/gen_coaches.py`).
`agents/_commun.md` (règles communes : sources, rappel actif, limites) est ajouté à chaque agent par le MCP.

## Skills (`skills/`)
`coach-setup` · `plan-revision` (/plan) · `revision-du-jour` (/today) · `fiche` · `quiz` · `dossier-progressif` (/dp) · `ecos` · `lca` ·
`bilan-semaine` (/bilan) · `recherche-sources` · `repondre-question` · `cartes` (/cartes : ajouter ou corriger des cartes depuis un texte ou un JSON).
`coach-setup` demande aussi la date de l'écrit final (EDN), de l'oral final (ECOS) et, pour CHAQUE examen de l'année, sa date et ses matières.

## Outils MCP
Instructions : `list_skills` `get_skill` `list_agents` `get_agent`. Cours : `list_categories` `list_cours` `search_cours` `get_cours`.
Cartes : `get_card` `find_cards` `save_cards` (ajout / correction, aperçu puis écriture, un commit). Examens : `list_exams` `save_exam` `delete_exam`. Quiz : `quiz_options` `save_quiz`. Suivi : `get_profile` `set_profile` `log_attempt` `due_reviews` `progress` `plan_backwards` `save_note` `list_files` `read_file`.
Historique : `history` `undo_last_change` (chaque écriture = un commit git `[coach]`, annulable, rien n'est supprimé).

## Tableau de bord (`/`) et lecteur de PDF
Même serveur, même URL, même mot de passe (`EDN_SITE_PASSWORD`). Reprend et fusionne l'ancien site `sophie-revision` et le suivi du coach :
- **Aujourd'hui** : compte à rebours (partiel 16/02/2027, EDN), semaine du planning, cartes dues, avancement par spécialité, gardes.
- **Avancement** : activité, révisions à venir, qualité par type d'exercice, points faibles, export JSON.
- **Cours** : recherche plein texte dans les 931 PDF avec filtres (thème partiel / situations de départ / entraînement, spécialité) et liste des documents ; chaque résultat ouvre le PDF à la bonne page.
- **Cartes** : révision en répétition espacée (clavier : espace, 1-4), parcours/filtres, ajout de cartes perso ; chaque carte montre son statut de vérification et ses sources.
- **Examens** : dates, heures et matières de chaque examen (partiels, EDN écrit, ECOS oral), modifiables sur le site ou par le coach ; les dates EDN/ECOS restent synchronisées avec le profil ; les matières mènent aux cours.
- **Rechargement automatique** : le site consulte `/api/version` toutes les 5 s ; quand le coach modifie quelque chose, la page se met à jour toute seule (si une saisie ou une session de cartes est en cours, un bouton « Actualiser » est proposé à la place). Chaque outil qui écrit ajoute à sa réponse la ligne `[site] Données modifiées … se recharge tout seul`.
- **Planning** (22 semaines + tour EDN + examen + filet) et **Erreurs** (journal).
Les cartes et le planning de référence sont dans `data/` ; la progression dans le suivi git (`revisions.md`, `cartes-perso.md`, `erreurs.md`).
Deck vérifié le 2026-10-09 : voir `knowledge/cards_verification_report.md`.

## Site de lecture des PDF
`/pdf/<slug>?page=N` ouvre le PDF d'origine à la bonne page (pdf.js embarqué, mot de passe `EDN_SITE_PASSWORD`, lien public
`EDN_PUBLIC_URL`). Chaque résultat de `search_cours` / `get_cours` / `list_cours` porte son `lien` ; les agents le recopient dans leurs
citations. Le site est servi par le même processus et la même URL que le MCP (`edn_site.py`).

## Règles non négociables
1. Tout contenu médical vient des cours (cités : [Catégorie — Titre, p.N]) ou d'une source officielle (URL, année). Jamais de dose/seuil inventé.
2. Divergence cours ↔ recommandation récente : toujours la signaler. Aucune supposition : donnée inconnue = demandée ; rien de fiable = « je n'ai pas trouvé ».
3. Dates et modalités des épreuves : vérifier sur CNG / UFR3S avant de les affirmer.
4. Outil de révision : aucun avis médical réel ; détresse de l'étudiante → arrêter les révisions et orienter (3114).
5. Chaque exercice est journalisé (`log_attempt`).

## Commandes
```
swiftc -O scripts/ocr_pdf.swift -o scripts/bin/ocr_pdf         # une fois (macOS ; Apple Vision, français)
.venv/bin/python scripts/run_ocr.py                              # OCR des pages pauvres en texte/riches en images (reprenable, ~7 min)
.venv/bin/python scripts/extract_pdfs.py && .venv/bin/python scripts/build_index.py   # reconstruire la base (fusionne l'OCR)
python3 scripts/gen_coaches.py                                                         # régénérer les coachs
.venv/bin/python tests/test_mcp.py                                                     # tests de bout en bout
EDN_MCP_TOKEN=<24+ car.> EDN_SITE_PASSWORD=<mot de passe> EDN_PUBLIC_URL=https://<domaine> python3 scripts/edn_mcp.py                                    # serveur local 127.0.0.1:8001
```
Le serveur n'exige que la bibliothèque standard ; `.venv` (PyMuPDF) ne sert qu'à l'extraction.

## Scripts du site et du deck
`edn_dash.py` (API du tableau de bord) · `edn_site.py` (routes, cookie, PDF) · `build_cards.py` + `verify_cards.py` (deck vérifié + preuves) ·
`import_sophie.py` (progression de l'ancien site → suivi, simulation par défaut, `--apply`) · `data/cartes-corrections.json` (corrections motivées).
Le calendrier des gardes se relie avec `EDN_CALENDAR_ICS_URL` (seuls les événements « garde » sont lus ; l'URL est un secret).
