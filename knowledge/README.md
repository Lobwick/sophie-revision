# knowledge/ — contenu des cours (non versionné)

Ce dossier contient, une fois construit, le **texte des cours** (base `cours.db`, cache OCR, index, fichiers Markdown). Ce contenu vient des PDF de
cours de l'étudiante : il n'est **pas** publié dans ce dépôt (droits d'auteur). Il se reconstruit localement à partir de `cours/` :

```bash
python3 -m venv .venv && .venv/bin/pip install pymupdf
swiftc -O scripts/ocr_pdf.swift -o scripts/bin/ocr_pdf        # macOS seulement (OCR Apple Vision)
.venv/bin/python scripts/run_ocr.py                            # OCR des pages pauvres en texte (~7 min)
.venv/bin/python scripts/extract_pdfs.py                       # knowledge/cours.db + md/
.venv/bin/python scripts/build_index.py                        # knowledge/INDEX.md
```
`deploy/Dockerfile` copie `knowledge/cours.db` : construis la base avant `docker compose up --build`.
`cards_verification_report.md` (versionné) détaille la vérification du deck de cartes.
