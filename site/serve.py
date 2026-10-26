#!/usr/bin/env python3
"""Serves the built DecKoOS website from this PC. Static files only, nothing executes: resumable downloads (Range) for
the ISO, the right types, caching for the versioned CSS/JS, the 404 page, and security headers.

Listens on this PC only (127.0.0.1) unless told otherwise. For the public internet, put it behind a tunnel or reverse
proxy rather than opening a port on the router (see site/README.md); on a real server, use Caddy or nginx instead.

    python3 site/serve.py [--dir site/public] [--host 127.0.0.1] [--port 8080]
"""
import argparse
import email.utils
import mimetypes
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".svg": "image/svg+xml", ".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".woff2": "font/woff2",
         ".ttf": "font/ttf", ".iso": "application/x-iso9660-image", ".sha256": "text/plain; charset=utf-8",
         ".sig": "application/pgp-signature", ".gpg": "application/pgp-keys", ".txt": "text/plain; charset=utf-8",
         ".xml": "application/xml"}
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                               "script-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'",
}


class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")
    server_version = "DecKoOS"
    sys_version = ""

    def resolve(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if "\x00" in path:
            return None
        target = (self.root / path.lstrip("/")).resolve()
        # Inside the site only. The ISO in downloads/ may be a link to out/: allowed because the site made it.
        inside = target.is_relative_to(self.root) or (self.root / path.lstrip("/")).parent.resolve() == (self.root / "downloads").resolve()
        if not inside:
            return None
        if target.is_dir():
            target = target / "index.html"
        return target if target.is_file() else None

    def do_HEAD(self):
        self.send(head=True)

    def do_GET(self):
        self.send(head=False)

    def send(self, head):
        f = self.resolve()
        status = 200
        if f is None:
            f, status = self.root / "404.html", 404
            if not f.exists():
                self.send_error(404)
                return
        size = f.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        if rng and status == 200:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if not m or (not m.group(1) and not m.group(2)):
                return self.not_satisfiable(size)
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                return self.not_satisfiable(size)
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", TYPES.get(f.suffix, mimetypes.guess_type(f.name)[0] or "application/octet-stream"))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", email.utils.formatdate(f.stat().st_mtime, usegmt=True))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        query = urllib.parse.urlsplit(self.path).query
        # Pages revalidate (a rebuild shows at once); versioned CSS/JS, fonts and images are kept
        cache = "public, max-age=31536000, immutable" if query.startswith("v=") or f.parent.name in ("fonts", "img") \
            else "no-cache"
        self.send_header("Cache-Control", cache)
        if f.suffix == ".iso":
            self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
        for k, v in HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        if head:
            return
        with open(f, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the download was cancelled or paused: it resumes with a Range request

    def not_satisfiable(self, size):
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        # The path and status, not the visitor's address: nothing about who visits is kept.
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n".replace(self.address_string() + " ", ""))


def main(argv=None):
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Serve the built DecKoOS website.")
    ap.add_argument("--dir", default=os.environ.get("DECKOS_SITE_DIR", str(here / "public")))
    ap.add_argument("--host", default=os.environ.get("DECKOS_SITE_HOST", "127.0.0.1"),
                    help="127.0.0.1: this PC only (default); 0.0.0.0: the home network too")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DECKOS_SITE_PORT", "8080")))
    a = ap.parse_args(argv)
    root = Path(a.dir).resolve()
    if not (root / "index.html").exists():
        print(f"no site in {root}: run site/build.py first", file=sys.stderr)
        return 1
    Handler.root = root
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print(f"DecKoOS website: http://{'localhost' if a.host == '127.0.0.1' else a.host}:{a.port}/ (from {root})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
