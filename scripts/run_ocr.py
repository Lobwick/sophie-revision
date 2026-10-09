#!/usr/bin/env python3
"""OCR (Apple Vision) des pages de cours dont le texte natif est pauvre ou qui portent de grandes images.

Résultat cumulatif dans knowledge/ocr_cache.jsonl ({"file","page","text"}) ; relancer reprend où ça s'est arrêté.
Ensuite : extract_pdfs.py fusionne ce cache dans la base. Usage : .venv/bin/python scripts/run_ocr.py [--workers 5] [--all]
"""
import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
BIN, CACHE = ROOT / "scripts" / "bin" / "ocr_pdf", ROOT / "knowledge" / "ocr_cache.jsonl"
CHUNK = 40


def candidates(pdf: Path, every=False):
    d = fitz.open(pdf)
    out = []
    for i, p in enumerate(d, 1):
        if every:
            out.append(i); continue
        pa = p.rect.width * p.rect.height
        area = sum(max(0, (b[2] - b[0]) * (b[3] - b[1])) for b in (x["bbox"] for x in p.get_image_info()))
        if len(p.get_text().strip()) < 300 or area / pa > 0.15:
            out.append(i)
    return out


def ocr_chunk(pdf: Path, pages):
    r = subprocess.run([str(BIN), str(pdf), ",".join(map(str, pages))], capture_output=True, text=True, timeout=900)
    return [json.loads(l) | {"file": pdf.name} for l in r.stdout.splitlines() if l.startswith("{")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--all", action="store_true", help="toutes les pages, pas seulement les candidates")
    a = ap.parse_args()
    done = set()
    if CACHE.exists():
        for l in CACHE.read_text("utf-8").splitlines():
            try:
                r = json.loads(l); done.add((r["file"], r["page"]))
            except ValueError:
                pass
    jobs = []
    for pdf in sorted((ROOT / "cours").glob("*.pdf")):
        todo = [p for p in candidates(pdf, a.all) if (pdf.name, p) not in done]
        jobs += [(pdf, todo[i:i + CHUNK]) for i in range(0, len(todo), CHUNK)]
    total = sum(len(p) for _, p in jobs)
    print(f"{total} pages à traiter ({len(done)} déjà en cache)", flush=True)
    n, t0 = 0, time.time()
    with CACHE.open("a", encoding="utf-8") as out, ThreadPoolExecutor(a.workers) as ex:
        for f in as_completed([ex.submit(ocr_chunk, *j) for j in jobs]):
            try:
                recs = f.result()
            except Exception as e:  # noqa: BLE001
                print("erreur chunk:", e, file=sys.stderr); continue
            for r in recs:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush(); n += len(recs)
            if n % 500 < CHUNK:
                print(f"{n}/{total}  {n / (time.time() - t0):.1f} p/s", flush=True)
    print("terminé", n, "pages en", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
