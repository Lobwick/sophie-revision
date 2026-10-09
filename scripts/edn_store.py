"""Stockage du suivi : fichiers Markdown dans un dépôt git (même principe que l'API de fichiers d'ai-bike-coach).

Chaque écriture est VALIDÉE, ATOMIQUE, COMMITÉE (préfixe « [coach] ») et ANNULABLE. Rien n'est supprimé.
Liste blanche : profil.md · revisions.md · journal/AAAA-MM.md · notes/*.md · plans/*.md. Noms [A-Za-z0-9_.-]+.md, un niveau de
dossier, ni « .. », ni chemin absolu, ni lien symbolique, ≤ 200 Ko. Stdlib uniquement ; nécessite le binaire `git`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "[coach]"
MAX_BYTES = 200_000
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.md$")
ROOT_FILES = {"profil.md", "revisions.md", "cartes-perso.md", "erreurs.md", "quiz.md", "examens.md", "cartes-corrections.md"}
DIRS = {"journal", "notes", "plans"}
EDN_BLOCK = re.compile(r"```edn\n(.*?)\n```", re.S)
_lock = threading.RLock()


class StoreError(ValueError):
    pass


def data_dir() -> Path:
    return Path(os.environ.get("EDN_DATA_DIR") or ROOT / "suivi")


def _git(*args, check=True):
    env = dict(os.environ, GIT_AUTHOR_NAME="Coach internat", GIT_AUTHOR_EMAIL="coach@internat.local",
               GIT_COMMITTER_NAME="Coach internat", GIT_COMMITTER_EMAIL="coach@internat.local")
    try:
        r = subprocess.run(["git", "-C", str(data_dir()), *args], capture_output=True, text=True, env=env)
    except FileNotFoundError as e:
        raise StoreError("git est introuvable : le suivi versionné est impossible sans git") from e
    if check and r.returncode != 0:
        raise StoreError(f"git : {r.stderr.strip() or r.stdout.strip()}")
    return r


def ensure_repo():
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    if not (d / ".git").is_dir():
        _git("init", "-q")
        _git("config", "core.quotepath", "false")
    return d


def resolve(rel: str, for_read=False) -> Path:
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel or rel.startswith("/") or ".." in rel.split("/"):
        raise StoreError("chemin invalide")
    parts = rel.split("/")
    ok = (len(parts) == 1 and parts[0] in ROOT_FILES) or (len(parts) == 2 and parts[0] in DIRS and NAME.match(parts[1]))
    if not ok:
        raise StoreError(f"chemin non autorisé : {rel} (autorisés : profil.md, revisions.md, journal|notes|plans/<nom>.md)")
    p = data_dir() / rel
    for q in [p, *p.parents]:
        if q == data_dir():
            break
        if q.is_symlink():
            raise StoreError("lien symbolique refusé")
    return p


def validate(rel: str, content: str):
    if not content.lstrip().startswith("# "):
        raise StoreError("le fichier doit commencer par un titre « # … »")
    m = EDN_BLOCK.search(content)
    if rel in ROOT_FILES:
        if not m:
            raise StoreError("bloc ```edn (JSON) manquant")
        try:
            json.loads(m.group(1))
        except ValueError as e:
            raise StoreError(f"bloc edn : JSON invalide ({e})") from e
    if rel.startswith("notes/"):
        # « précise toujours la source » : une note sans section Sources non vide n'est pas écrite
        src = re.search(r"^## Sources\s*\n(.+)", content, re.M | re.S)
        if not src or not src.group(1).strip():
            raise StoreError("une note doit se terminer par une section « ## Sources » non vide (cours [Catégorie — Titre, p.N] et/ou URL + année)")


def read(rel: str, default=None) -> str | None:
    p = resolve(rel, for_read=True)
    return p.read_text("utf-8") if p.exists() else default


def read_edn(rel: str, default):
    t = read(rel)
    m = EDN_BLOCK.search(t) if t else None
    return json.loads(m.group(1)) if m else default


def list_files(directory: str = ""):
    d = ensure_repo()
    if directory and directory not in DIRS:
        raise StoreError(f"dossier parmi {sorted(DIRS)}")
    base = d / directory if directory else d
    names = [p.relative_to(d).as_posix() for p in sorted(base.rglob("*.md")) if not any(x.startswith(".") for x in p.parts)]
    return [{"path": n, "octets": (d / n).stat().st_size} for n in names]


def _write_atomic(rel: str, content: str):
    path = resolve(rel)
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_BYTES:
        raise StoreError(f"contenu invalide ou supérieur à {MAX_BYTES} octets")
    validate(rel, content)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".edn-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def write_many(files: dict, message: str) -> dict:
    """Écrit plusieurs fichiers (tous validés AVANT la première écriture) et les commite ensemble."""
    with _lock:
        ensure_repo()
        for rel, content in files.items():          # validation préalable : tout ou rien
            resolve(rel)
            validate(rel, content)
        for rel, content in files.items():
            _write_atomic(rel, content)
            _git("add", "--", rel)
        names = ", ".join(files)
        if _git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return {"ok": True, "paths": list(files), "commit": None, "note": "aucun changement"}
        _git("commit", "-q", "-m", f"{PREFIX} {names} : {message}"[:200])
        return {"ok": True, "paths": list(files), "commit": _git("rev-parse", "--short", "HEAD").stdout.strip()}


def write(rel: str, content: str, message: str) -> dict:
    r = write_many({rel: content}, message)
    return {"ok": True, "path": rel, "commit": r["commit"], **({"note": r["note"]} if "note" in r else {})}


def history(path: str | None = None, n: int = 15) -> dict:
    ensure_repo()
    args = ["log", f"-{min(max(int(n), 1), 50)}", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M"]
    if path:
        resolve(path)
        args += ["--", path]
    if _git("rev-parse", "--verify", "-q", "HEAD", check=False).returncode != 0:
        return {"commits": [], "note": "aucune écriture pour l'instant"}
    return {"commits": [dict(zip(("commit", "date", "message"), l.split("|", 2))) for l in _git(*args).stdout.splitlines() if l]}


def undo_last_change() -> dict:
    with _lock:
        ensure_repo()
        if _git("rev-parse", "--verify", "-q", "HEAD", check=False).returncode != 0:
            raise StoreError("rien à annuler")
        msg = _git("log", "-1", "--format=%s").stdout.strip()
        if not msg.startswith(PREFIX):
            raise StoreError("le dernier commit ne vient pas du coach : annulation refusée")
        _git("revert", "--no-edit", "HEAD")
        return {"ok": True, "annule": msg}


def version() -> str:
    """Identifiant de la dernière écriture du suivi (commit git) : le site le consulte pour se recharger tout seul après une modification."""
    d = data_dir()
    try:
        head = (d / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = d / ".git" / head[5:]
            if ref.exists():
                return ref.read_text().strip()[:12]
        elif head:
            return head[:12]
    except OSError:
        pass
    r = _git("rev-parse", "--short=12", "HEAD", check=False) if (d / ".git").is_dir() else None
    return r.stdout.strip() if r and r.returncode == 0 else "0"
