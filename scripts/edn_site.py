"""Site de lecture des cours : /pdf/<slug>?page=N ouvre le PDF d'origine à la bonne page (pdf.js embarqué, aucun CDN).

Routes (toutes derrière un mot de passe → cookie signé) :
  /login                    formulaire (EDN_SITE_PASSWORD obligatoire : sans lui le site est désactivé)
  /pdf/<slug>?page=N        visionneuse (pages précédente/suivante, aller à, zoom, texte indexé de la page)
  /file/<slug>.pdf          le PDF (requêtes Range gérées) ; seuls les fichiers connus de la base sont servis
  /api/page/<slug>/<n>      texte indexé de la page (OCR compris) — pour vérifier une lecture douteuse
  /static/pdfjs/…           pdf.js (Apache-2.0)
Stdlib uniquement. Liens produits par `page_link()` : jamais de jeton ni de mot de passe dans une URL.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import time
import urllib.parse
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
COOKIE = "edn_session"
_fail: dict[str, deque] = defaultdict(deque)


def cours_dir() -> Path:
    return Path(os.environ.get("EDN_COURS_DIR") or ROOT / "cours")


def public_url() -> str:
    return (os.environ.get("EDN_PUBLIC_URL") or "").rstrip("/")


def page_link(slug: str, page: int | None = None) -> str:
    """URL à donner à l'étudiante. Sans EDN_PUBLIC_URL : chemin relatif (jamais un domaine inventé)."""
    q = f"?page={int(page)}" if page else ""
    return f"{public_url()}/pdf/{slug}{q}"


def enabled() -> bool:
    return bool(os.environ.get("EDN_SITE_PASSWORD"))


def _sig() -> str:
    pw = os.environ.get("EDN_SITE_PASSWORD", "")
    return hmac.new(pw.encode(), b"edn-session-v1", hashlib.sha256).hexdigest()


def _authed(h) -> bool:
    for part in (h.headers.get("Cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE and hmac.compare_digest(v, _sig()):
            return True
    return False


def _doc(kb, slug: str):
    if not SLUG.match(slug):
        return None
    return kb.execute("SELECT slug,category,title,sdd,source,n_pages FROM docs WHERE slug=?", (slug,)).fetchone()


def _send(h, code, body: bytes = b"", ctype="text/html; charset=utf-8", extra: dict | None = None):
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(body)))
    if "Cache-Control" not in (extra or {}):
        h.send_header("Cache-Control", "no-store" if ctype.startswith(("text/html", "application/json")) else "private, max-age=3600")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Referrer-Policy", "no-referrer")
    h.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                  "worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
    for k, v in (extra or {}).items():
        h.send_header(k, v)
    h.end_headers()
    if body:
        h.wfile.write(body)


def _redirect(h, to, extra=None):
    _send(h, 302, b"", extra={"Location": to, **(extra or {})})


def _safe_next(n: str) -> str:
    return n if (n == "/" or n.startswith(("/pdf/", "/#/"))) and "//" not in n.replace("/#/", "/") and "\\" not in n else "/"


LOGIN = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cours — connexion</title><style>body{font:16px system-ui;margin:0;display:grid;place-items:center;min-height:100vh;background:#f4f6f8;color:#14202b}
form{background:#fff;padding:28px;border-radius:12px;box-shadow:0 2px 12px #0002;width:min(320px,90vw)}input,button{width:100%%;box-sizing:border-box;padding:12px;margin-top:12px;font-size:16px;border-radius:8px;border:1px solid #9aa7b4}
button{background:#0b5cad;color:#fff;border:0}.e{color:#b00020;margin-top:10px}@media(prefers-color-scheme:dark){body{background:#10161c;color:#e8eef4}form{background:#18212a}input{background:#10161c;color:#e8eef4}}</style>
<form method="post" action="/login"><h1 style="font-size:20px;margin:0">Cours de révision</h1>
<input type="hidden" name="next" value="%(next)s"><input type="password" name="password" placeholder="Mot de passe" autofocus autocomplete="current-password">
<button>Entrer</button>%(err)s</form></html>"""

VIEWER = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s — p.%(page)s</title>
<style>
:root{--bg:#eef1f4;--fg:#14202b;--bar:#fff;--bd:#c9d2db;--ac:#0b5cad}
@media(prefers-color-scheme:dark){:root{--bg:#0d1217;--fg:#e8eef4;--bar:#18212a;--bd:#2b3945;--ac:#6db3ff}}
html,body{margin:0;height:100%%;background:var(--bg);color:var(--fg);font:15px system-ui}
header{position:sticky;top:0;z-index:5;background:var(--bar);border-bottom:1px solid var(--bd);padding:8px 12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
header h1{font-size:14px;margin:0;flex:1 1 100%%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
header small{opacity:.7}button,input{font:inherit;padding:8px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--bar);color:var(--fg);min-height:40px}
input{width:64px;text-align:center}button:hover{border-color:var(--ac)}main{display:grid;place-items:start center;padding:12px}
canvas{max-width:100%%;height:auto;background:#fff;box-shadow:0 1px 8px #0003}#txt{display:none;max-width:900px;margin:12px;padding:12px;background:var(--bar);border:1px solid var(--bd);border-radius:8px;white-space:pre-wrap}
#msg{padding:24px}
</style>
<body data-slug="%(slug)s" data-total="%(total)s" data-page="%(page)s">
<header><h1>%(category)s — %(title)s <small>· %(total)s p.</small></h1>
<button id="prev" aria-label="Page précédente">◀</button><input id="num" type="number" min="1" max="%(total)s" value="%(page)s" aria-label="Numéro de page">
<span>/ %(total)s</span><button id="next" aria-label="Page suivante">▶</button><button id="zo">−</button><button id="zi">+</button>
<button id="tg">Texte indexé</button><a href="/file/%(slug)s.pdf" style="color:var(--ac)">PDF</a></header>
<main><div id="msg">Chargement…</div><canvas id="c" hidden></canvas></main><pre id="txt"></pre>
<script src="/static/pdfjs/pdf.min.js"></script>
<script src="/static/viewer.js"></script></html>"""


def _send_pdf(h, path: Path):
    size = path.stat().st_size
    start, end, code = 0, size - 1, 200
    m = re.match(r"^bytes=(\d*)-(\d*)$", h.headers.get("Range") or "")
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else end
        else:
            start = max(0, size - int(m.group(2)))
        end = min(end, size - 1)
        if start > end or start >= size:
            return _send(h, 416, b"", extra={"Content-Range": f"bytes */{size}"})
        code = 206
    h.send_response(code)
    h.send_header("Content-Type", "application/pdf")
    h.send_header("Accept-Ranges", "bytes")
    h.send_header("Content-Length", str(end - start + 1))
    h.send_header("Cache-Control", "private, max-age=3600")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Disposition", "inline")
    if code == 206:
        h.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    h.end_headers()
    with path.open("rb") as f:
        f.seek(start)
        left = end - start + 1
        while left > 0:
            chunk = f.read(min(262144, left))
            if not chunk:
                break
            h.wfile.write(chunk); left -= len(chunk)


def _api(h, method, path, q, kb) -> bool:
    import edn_dash
    query = {k: v[0] for k, v in q.items()}
    body = {}
    if method in ("POST", "PUT", "DELETE"):
        # Protection CSRF : en-tête que seul notre JS peut poser (un formulaire d'un autre site ne le peut pas) + Origin cohérent.
        origin = h.headers.get("Origin")
        if h.headers.get("X-Requested-With") != "edn" or (origin and urllib.parse.urlsplit(origin).netloc != h.headers.get("Host")):
            _send(h, 403, b'{"error":"requete refusee"}', "application/json")
            return True
        n = int(h.headers.get("Content-Length") or 0)
        if n > 64_000:
            _send(h, 413, b'{"error":"trop volumineux"}', "application/json")
            return True
        if n:
            try:
                body = json.loads(h.rfile.read(n))
            except ValueError:
                _send(h, 400, b'{"error":"JSON invalide"}', "application/json")
                return True
    try:
        res = edn_dash.route(method, path, query, body if isinstance(body, dict) else {}, kb)
    except Exception:  # noqa: BLE001 — jamais de trace vers le client
        import logging
        logging.getLogger("edn-site").exception("api %s", path)
        _send(h, 500, b'{"error":"erreur interne"}', "application/json")
        return True
    if res is None:
        _send(h, 404, b'{"error":"introuvable"}', "application/json")
    else:
        _send(h, res[0], json.dumps(res[1], ensure_ascii=False).encode(), "application/json")
    return True


def try_handle(h, method: str, kb) -> bool:
    """Traite la requête si c'est une route du site ; renvoie False sinon (le MCP s'en charge)."""
    u = urllib.parse.urlsplit(h.path)
    path, q = u.path, urllib.parse.parse_qs(u.query)
    if not (path in ("/", "/login", "/logout") or path.startswith(("/pdf/", "/file/", "/api/", "/static/", "/app/"))):
        return False
    if not enabled():
        _send(h, 404, b"site desactive (EDN_SITE_PASSWORD non defini)", "text/plain; charset=utf-8")
        return True
    if path == "/login":
        if method == "POST":
            n = min(int(h.headers.get("Content-Length") or 0), 4096)
            form = urllib.parse.parse_qs(h.rfile.read(n).decode("utf-8", "ignore"))
            ip, now = h.client_address[0], time.time()
            dq = _fail[ip]
            while dq and now - dq[0] > 300:
                dq.popleft()
            if len(dq) >= 8:
                _send(h, 429, (LOGIN % {"next": "/", "err": '<p class="e">Trop d\'essais, réessaie dans 5 minutes.</p>'}).encode())
                return True
            if hmac.compare_digest((form.get("password") or [""])[0].encode(), os.environ["EDN_SITE_PASSWORD"].encode()):
                secure = "; Secure" if h.headers.get("X-Forwarded-Proto") == "https" else ""
                _redirect(h, _safe_next((form.get("next") or ["/"])[0]),
                          {"Set-Cookie": f"{COOKIE}={_sig()}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000{secure}"})
                return True
            dq.append(now)
            _send(h, 401, (LOGIN % {"next": html.escape(_safe_next((form.get("next") or ["/"])[0])),
                                    "err": '<p class="e">Mot de passe incorrect.</p>'}).encode())
            return True
        _send(h, 200, (LOGIN % {"next": html.escape(_safe_next((q.get("next") or ["/"])[0])), "err": ""}).encode())
        return True
    if path == "/logout":
        _redirect(h, "/login", {"Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0"})
        return True
    if not _authed(h):
        if path == "/" or path.startswith("/pdf/"):
            _redirect(h, "/login?next=" + urllib.parse.quote(h.path, safe="/?=&"))
        else:
            _send(h, 401, b"non autorise", "text/plain; charset=utf-8")
        return True
    if path == "/" or path.startswith("/app/"):
        name = "index.html" if path == "/" else path[len("/app/"):]
        types = {"index.html": "text/html; charset=utf-8", "app.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                 "favicon.svg": "image/svg+xml"}
        f = STATIC / "app" / name
        if method == "GET" and name in types and f.is_file():
            _send(h, 200, f.read_bytes(), types[name], {"Cache-Control": "no-cache"})   # toujours revalidé : une mise à jour est visible aussitôt
        else:
            _send(h, 404, b"introuvable", "text/plain; charset=utf-8")
        return True
    if path.startswith("/api/") and not path.startswith("/api/page/"):
        return _api(h, method, path, q, kb)
    if method != "GET":
        _send(h, 405, b"GET uniquement", "text/plain; charset=utf-8")
        return True
    if path.startswith("/static/pdfjs/"):
        name = path.rsplit("/", 1)[1]
        f = STATIC / "pdfjs" / name
        if name in ("pdf.min.js", "pdf.worker.min.js") and f.is_file():
            _send(h, 200, f.read_bytes(), "text/javascript; charset=utf-8")
        else:
            _send(h, 404, b"introuvable", "text/plain; charset=utf-8")
        return True
    if path == "/static/viewer.js":
        _send(h, 200, (STATIC / "viewer.js").read_bytes(), "text/javascript; charset=utf-8", {"Cache-Control": "no-cache"})
        return True
    m = re.match(r"^/(pdf|file)/([a-z0-9-]+?)(?:\.pdf)?$", path) or re.match(r"^/(api)/page/([a-z0-9-]+)/(\d+)$", path)
    if not m:
        _send(h, 404, b"introuvable", "text/plain; charset=utf-8")
        return True
    d = _doc(kb, m.group(2))
    if not d:
        _send(h, 404, b"cours inconnu", "text/plain; charset=utf-8")
        return True
    if m.group(1) == "api":
        row = kb.execute("SELECT p.text FROM pages p JOIN docs d ON d.id=p.doc_id WHERE d.slug=? AND p.page=?", (d["slug"], int(m.group(3)))).fetchone()
        _send(h, 200, json.dumps({"text": row["text"] if row else ""}, ensure_ascii=False).encode(), "application/json")
        return True
    if m.group(1) == "file":
        f = cours_dir() / d["source"]
        if f.resolve().parent != cours_dir().resolve() or not f.is_file():
            _send(h, 404, b"fichier PDF absent du serveur (voir EDN_COURS_DIR)", "text/plain; charset=utf-8")
        else:
            _send_pdf(h, f)
        return True
    try:
        page = max(1, min(int((q.get("page") or ["1"])[0]), d["n_pages"]))
    except ValueError:
        page = 1
    _send(h, 200, (VIEWER % {"title": html.escape(d["title"]), "category": html.escape(d["category"]), "total": d["n_pages"],
                             "page": page, "slug": d["slug"]}).encode())
    return True
