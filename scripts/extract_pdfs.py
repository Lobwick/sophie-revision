#!/usr/bin/env python3
"""Extrait cours/*.pdf -> knowledge/md/*.md + knowledge/cours.db (SQLite FTS5).

Usage: .venv/bin/python scripts/extract_pdfs.py [--limit N]
Idempotent : reconstruit tout (rapide, ~30 000 pages). Les PDF ne sont jamais modifiés.
"""
import argparse, json, re, sqlite3, sys, unicodedata
from collections import Counter
from pathlib import Path

import fitz  # pymupdf

ROOT = Path(__file__).resolve().parent.parent
COURS, KB = ROOT / "cours", ROOT / "knowledge"
LOW_TEXT = 40  # caractères/page en dessous : page quasi visuelle


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:90]


def parse_name(stem: str):
    cat, _, title = stem.partition(" - ")
    if not title:
        cat, title = "Divers", stem
    m = re.match(r"(?:SDD|SdD)\s*(\d+)\s*-\s*(.*)", title, re.I)
    sdd = int(m.group(1)) if m else None
    return cat.strip(), (m.group(2) if m else title).strip(), sdd


def clean_pages(raw: list[str]) -> list[str]:
    # lignes répétées sur >40 % des pages = en-têtes/pieds de page
    n = max(len(raw), 1)
    cnt = Counter(l.strip() for t in raw for l in set(t.splitlines()) if l.strip())
    boiler = {l for l, c in cnt.items() if n >= 5 and c / n > 0.4}
    out = []
    for t in raw:
        lines = [l.strip() for l in t.splitlines()]
        lines = [l for l in lines if l and l not in boiler and l not in {"-", "•", "–"}]
        txt = "\n".join(lines)
        # recolle les tirets de césure et les retours à la ligne en milieu de phrase
        txt = re.sub(r"(\w)-\n(\w)", r"\1\2", txt)
        txt = re.sub(r"(?<=[a-zé,;])\n(?=[a-zé(])", " ", txt)
        out.append(txt.strip())
    return out


def load_ocr() -> dict:
    """knowledge/ocr_cache.jsonl (scripts/run_ocr.py) -> {(fichier, page): texte OCR}."""
    cache, path = {}, KB / "ocr_cache.jsonl"
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
                cache[(r["file"], r["page"])] = r["text"]
            except (ValueError, KeyError):
                pass
    return cache


def merge_ocr(text: str, ocr: str) -> str:
    """Ajoute à une page les lignes OCR absentes de son texte natif (le texte des images, schémas, tableaux)."""
    known = {re.sub(r"\W+", "", l.lower()) for l in text.splitlines()}
    new = [l.strip() for l in ocr.splitlines()
           if len(l.strip()) > 2 and re.sub(r"\W+", "", l.lower()) not in known and re.sub(r"\W+", "", l.lower()) not in text.lower().replace(" ", "")]
    if not new:
        return text
    return (text + "\n" if text else "") + "[Texte des images] " + " / ".join(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    files = sorted(COURS.glob("*.pdf"))[: a.limit]
    (KB / "md").mkdir(parents=True, exist_ok=True)
    for old in (KB / "md").glob("*.md"):
        old.unlink()
    db_path = KB / "cours.db"
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript("""
    CREATE TABLE docs(id INTEGER PRIMARY KEY, slug TEXT UNIQUE, category TEXT, title TEXT,
        sdd INTEGER, source TEXT, n_pages INTEGER, n_chars INTEGER, quality TEXT);
    CREATE TABLE pages(doc_id INTEGER, page INTEGER, text TEXT, PRIMARY KEY(doc_id, page));
    CREATE VIRTUAL TABLE pages_fts USING fts5(text, doc_title, category,
        content='', tokenize='unicode61 remove_diacritics 2');
    """)
    ocr = load_ocr()
    print(f"cache OCR : {len(ocr)} pages")
    report, seen = [], set()
    for i, f in enumerate(files, 1):
        cat, title, sdd = parse_name(f.stem)
        s = slug(f"{cat}-{('sdd%03d-' % sdd) if sdd else ''}{title}")
        while s in seen:
            s += "-b"
        seen.add(s)
        try:
            d = fitz.open(f)
            raw = [p.get_text() for p in d]
        except Exception as e:  # noqa: BLE001
            print(f"ERREUR {f.name}: {e}", file=sys.stderr)
            report.append({"file": f.name, "quality": "error"})
            continue
        pages = clean_pages(raw)
        pages = [merge_ocr(t, ocr[(f.name, n)]) if (f.name, n) in ocr else t for n, t in enumerate(pages, 1)]
        n_chars = sum(map(len, pages))
        poor = sum(1 for p in pages if len(p) < LOW_TEXT)
        quality = ("empty" if n_chars < 200 else
                   "low" if n_chars / max(len(pages), 1) < 150 or poor / max(len(pages), 1) > 0.5 else "ok")
        cur = db.execute("INSERT INTO docs(slug,category,title,sdd,source,n_pages,n_chars,quality) VALUES(?,?,?,?,?,?,?,?)",
                         (s, cat, title, sdd, f.name, len(pages), n_chars, quality))
        did = cur.lastrowid
        md = [f"# {title}", f"_Source : {f.name} · {cat}" + (f" · SdD {sdd}" if sdd else "") + f" · qualité : {quality}_", ""]
        for n, t in enumerate(pages, 1):
            if not t:
                continue
            db.execute("INSERT INTO pages VALUES(?,?,?)", (did, n, t))
            db.execute("INSERT INTO pages_fts(rowid,text,doc_title,category) VALUES(?,?,?,?)",
                       (db.execute("SELECT last_insert_rowid()").fetchone()[0], t, title, cat))
            md += [f"## p.{n}", t, ""]
        (KB / "md" / f"{s}.md").write_text("\n".join(md), encoding="utf-8")
        report.append({"slug": s, "category": cat, "title": title, "sdd": sdd,
                       "pages": len(pages), "chars": n_chars, "quality": quality, "file": f.name})
        if i % 100 == 0:
            print(f"{i}/{len(files)}", flush=True)
    db.commit()
    db.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
    db.commit(); db.close()
    (KB / "extraction_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    q = Counter(r["quality"] for r in report)
    print("terminé:", dict(q), "| pages:", sum(r.get("pages", 0) for r in report))


if __name__ == "__main__":
    main()
