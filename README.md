# Coach internat — révision EDN + ECOS

Serveur MCP + site (tableau de bord, explorateur de cours, lecteur de PDF à la bonne page, cartes en répétition espacée, quiz, examens) pour
préparer l'internat de médecine avec Claude ou ChatGPT. Dérivé de la structure de `ai-running-coach`, et fusion de l'ancien site `sophie-revision`.

- **Fonctionnement, outils, règles** : [AGENTS.md](AGENTS.md) · **Déploiement et tests locaux** : [deploy/README.md](deploy/README.md)
- **Agents** : `agents/` · **Skills** (`/quiz`, `/cartes`, `/coach-setup`, `/plan`, …) : `skills/` · **Deck de cartes vérifié** : `data/`
- **Le contenu des cours n'est pas dans ce dépôt** (droits d'auteur) : voir [knowledge/README.md](knowledge/README.md) pour reconstruire la base.
- Suivi de l'étudiante (profil, journal, quiz, examens…) : dossier `suivi/`, un dépôt git local **jamais versionné ici**.

```bash
EDN_MCP_TOKEN=<24+ caractères> EDN_SITE_PASSWORD=<mot de passe> EDN_PUBLIC_URL=http://127.0.0.1:8001 python3 scripts/edn_mcp.py   # puis http://127.0.0.1:8001/
.venv/bin/python tests/test_mcp.py   # 160 vérifications (nécessite cours/ et la base reconstruite)
```
