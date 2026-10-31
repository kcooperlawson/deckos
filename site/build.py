#!/usr/bin/env python3
"""The DecKoOS website, generated from the repo: the README's features and limitations, the release notes What's New
shows, the docs, SECURITY.md and the newest ISO. One source of truth: change the docs, rebuild, and the site follows.

Plain Python (Pillow and fontTools are used when present, for WebP screenshots and a slim Inter). The output is a
folder of static files: serve it from this PC with serve.py, or copy it to any web server (see README.md).

    python3 site/build.py [--out DIR] [--iso FILE] [--url https://example.org]
"""
import argparse
import datetime
import hashlib
import html
import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SHARE = ROOT / "pkg/deckos-settings/rootfs/usr/share/deckos"
REPO = "kcooperlawson/deckos"
GITHUB = f"https://github.com/{REPO}"
PIN = ROOT / "out/site-iso"  # the ISO the site offers, when one was picked (DecKoOS Builder's Website card)
# Inter, where Arch and DecKoOS install it; without it the site uses the system's fonts
FONT_SOURCES = [Path("/usr/share/fonts/inter/InterVariable.ttf"), Path("/usr/share/fonts/TTF/InterVariable.ttf")]
FINGERPRINT = "F67E15FABF95D2DA72BE5D3F6322881773088C41"
NAME = "DecKoOS"

# The docs the site publishes, by group. Others (the reference machine, handoffs) stay in the repo only.
DOCS = [
    ("Get started", ["install", "guide", "undo"]),
    ("DecKoOS apps", ["files", "terminal", "editor", "disks", "bench", "work", "assistant-models"]),
    ("How it works", ["self-healing", "gaming-session"]),
    ("Contributing", ["development"]),
]
DOC_NAMES = {d for _, names in DOCS for d in names}
# Each doc's name in the navigation and its card on the docs page
DOC_META = {
    "install": ("Installing DecKoOS", "What you need, getting the ISO, and installing beside Windows or on its own drive."),
    "guide": ("Using DecKoOS", "The desktop, Gaming Mode, DecKoOS Hub, updates, AI and the apps, one by one."),
    "undo": ("Undo an update", "Put the system back to how it was before an update, from DecKoOS Hub or the boot menu."),
    "files": ("DecKoOS Files", "The file manager: views, tabs, split view, previews, drives and how it stays fast."),
    "terminal": ("DecKoOS Terminal", "The terminal: project-named tabs, splits, the mode chip and snapshot Undo."),
    "editor": ("DecKoOS Editor", "The text editor: syntax colours, find and replace, and safe saving of system files."),
    "disks": ("DecKoOS Disks", "Your drives and partitions, their health, and making sure they mount after a restart."),
    "bench": ("DecKoOS Bench", "Benchmarks with confidence ranges, history and comparisons, and what each test measures."),
    "work": ("DecKoOS Assistant's workspace", "A local workspace for code, documents and images, on the models on your PC."),
    "assistant-models": ("Choosing an AI model", "Which local models were measured with Deck, and how they did."),
    "self-healing": ("How fixes stay safe", "How DecKoOS's fixes work, and the rules no AI can get around."),
    "gaming-session": ("Inside Gaming Mode", "How the Steam Gaming Mode session starts, runs and hands back to the desktop."),
    "development": ("Developing DecKoOS", "Build, test and change DecKoOS: the checks, the apps' demo modes and releases."),
}

# README's "Why DecKoOS" rows: the icon each one gets
FEATURE_ICONS = {"Workload modes": "gauge", "Game Doctor": "gaming", "DecKoOS Assistant": "ai", "DecKoOS Bench": "flask",
                 "Updates you can undo": "undo", "A safe installer": "shield", "Move in from Windows": "folder",
                 "Fixes for real hardware": "display", "Its own desktop apps": "grid", "Vibes": "music",
                 "Kid mode": "user", "Every setting in one place": "search", "Make it yours": "appearance",
                 "Vibe mode": "play", "Made for you": "star", "React to music": "music"}

# Left off the home page's grid (a fix for one card family, not a headline; it keeps the grid even)
HOME_SKIP = {"Fixes for real hardware"}

SHOTS = [  # docs/screenshots: tab label, caption
    ("desktop", "Desktop", "Your pinned apps, live performance graphs and DecKoOS Menu, on KDE Plasma 6."),
    ("hub", "DecKoOS Hub", "Every setting, your games, updates and Undo, in one place."),
    ("assistant", "Deck", "A private assistant on your own graphics card. It shows every change before making it."),
    ("files", "Files", "A fast file manager with thumbnails, tabs, split view and previews."),
    ("terminal", "Terminal", "Tabs named after your project and branch, and a chip for the current mode."),
    ("menu", "Menu", "Search finds apps and DecKoOS itself: type \"drives\" or \"fix game\"."),
    ("quicksettings", "Quick Settings", "Wi-Fi, sound, power and the current mode, one click from the taskbar."),
    ("sysmon", "System Monitor", "Processes grouped by app, with Radeon and NVIDIA graphics figures."),
    ("bench", "Bench", "Benchmarks with confidence ranges, history and A/B comparisons."),
    ("welcome", "Welcome", "A first-login tour: your look, display, apps, gaming and privacy choices."),
]


# ---------------------------------------------------------------- markdown

def slug(text):
    """GitHub's heading anchors, so links written for GitHub land in the same place here."""
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


class Markdown:
    """The markdown the DecKoOS docs use: headings, paragraphs, nested lists, tables, code, quotes and links.
    Everything is escaped: the docs can't put raw HTML on the site."""

    def __init__(self, link=lambda url: url):
        self.link = link
        self.headings = []  # (level, id, text) for the page's table of contents

    def inline(self, text):
        codes = []

        def keep(m):
            codes.append(f"<code>{html.escape(m.group(1) or m.group(2))}</code>")
            return f"\x00{len(codes) - 1}\x00"

        text = re.sub(r"``\s?(.+?)\s?``|`([^`]+)`", keep, text)
        text = html.escape(text, quote=False)
        text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<img src="{html.escape(self.link(m.group(2)))}" alt="{m.group(1)}" loading="lazy">', text)
        text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: self._a(m.group(1), m.group(2)), text)
        text = re.sub(r"&lt;(https?://[^\s&]+)&gt;", lambda m: self._a(m.group(1), m.group(1)), text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
        text = re.sub(r"(?<!\w)_(?!\s)([^_]+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text)
        text = text.replace("  \n", "<br>")
        return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)

    def _a(self, label, url):
        url = self.link(html.unescape(url))
        ext = url.startswith("http") and not url.startswith("/")
        rel = ' rel="noopener"' if ext else ""
        return f'<a href="{html.escape(url)}"{rel}>{label}</a>'

    def render(self, text):
        return self.blocks(text.replace("\r\n", "\n").split("\n"))

    def blocks(self, lines):
        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            s = line.strip()
            if not s:
                i += 1
                continue
            if s.startswith("```"):
                lang = s[3:].strip()
                body = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    body.append(lines[i])
                    i += 1
                i += 1
                indent = min((len(b) - len(b.lstrip()) for b in body if b.strip()), default=0)
                code = html.escape("\n".join(b[indent:] for b in body))
                cls = f' class="language-{html.escape(lang)}"' if lang else ""
                out.append(f"<pre><code{cls}>{code}</code></pre>")
                continue
            m = re.match(r"(#{1,6})\s+(.*?)\s*#*$", s)
            if m:
                level, title = len(m.group(1)), m.group(2)
                hid = slug(title)
                self.headings.append((level, hid, title))
                inner = self.inline(title)
                anchor = f'<a class="anchor" href="#{hid}" aria-hidden="true">#</a>' if level in (2, 3) else ""
                out.append(f'<h{level} id="{hid}">{inner}{anchor}</h{level}>')
                i += 1
                continue
            if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
                out.append("<hr>")
                i += 1
                continue
            if s.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", lines[i + 1].strip()):
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    rows.append(lines[i].strip())
                    i += 1
                cells = [self._cells(r) for r in rows]
                head, body = cells[0], cells[2:]
                th = "" if not any(c.strip() for c in head) else \
                    "<thead><tr>" + "".join(f"<th>{self.inline(c)}</th>" for c in head) + "</tr></thead>"
                tb = "".join("<tr>" + "".join(f"<td>{self.inline(c)}</td>" for c in r) + "</tr>" for r in body)
                out.append(f'<div class="table"><table>{th}<tbody>{tb}</tbody></table></div>')
                continue
            if s.startswith(">"):
                quote = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                    i += 1
                out.append(f"<blockquote>{self.blocks(quote)}</blockquote>")
                continue
            if re.match(r"\s*([-*+]|\d+[.)])\s+", line):
                i = self._list(lines, i, out)
                continue
            para = []
            while i < len(lines) and lines[i].strip() and not self._starts_block(lines, i):
                para.append(lines[i].strip() + ("  " if lines[i].endswith("  ") else ""))
                i += 1
            out.append(f"<p>{self.inline(chr(10).join(para))}</p>")
        return "\n".join(out)

    @staticmethod
    def _cells(row):
        row = row.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [c.strip() for c in re.split(r"(?<!\\)\|", row)]

    @staticmethod
    def _starts_block(lines, i):
        s = lines[i].strip()
        return bool(s.startswith(("```", "#", ">", "|")) or re.match(r"([-*+]|\d+[.)])\s+", s) or re.fullmatch(r"-{3,}", s))

    def _list(self, lines, i, out):
        first = re.match(r"(\s*)([-*+]|\d+[.)])\s+", lines[i])
        base = len(first.group(1))
        ordered = first.group(2)[0].isdigit()
        items = []
        while i < len(lines):
            line = lines[i]
            m = re.match(r"(\s*)([-*+]|\d+[.)])\s+(.*)", line)
            if m and len(m.group(1)) == base and (m.group(2)[0].isdigit()) == ordered:
                items.append([m.group(3)])
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent > base and items:
                items[-1].append(line[base + 2:] if len(line) > base + 2 else line.strip())
                i += 1
                continue
            if not line.strip() and i + 1 < len(lines):
                nxt = lines[i + 1]
                nm = re.match(r"(\s*)([-*+]|\d+[.)])\s+", nxt)
                if (nm and len(nm.group(1)) >= base) or (nxt.strip() and len(nxt) - len(nxt.lstrip()) > base and items):
                    items[-1].append("")
                    i += 1
                    continue
            break
        tag = "ol" if ordered else "ul"
        html_items = []
        for item in items:
            head, rest = item[0], item[1:]
            sub = [ln for ln in rest]
            nested_at = next((k for k, ln in enumerate(sub) if re.match(r"\s*([-*+]|\d+[.)])\s+", ln)), None)
            text_lines = [head] + (sub[:nested_at] if nested_at is not None else sub)
            body = self.inline("\n".join(t.strip() for t in text_lines if t.strip()))
            if nested_at is not None:
                body += self.blocks(sub[nested_at:])
            html_items.append(f"<li>{body}</li>")
        out.append(f"<{tag}>{''.join(html_items)}</{tag}>")
        return i


def md_section(text, title, level="##"):
    """The part of a markdown file under '## title' (or another `level`), up to the next heading of that level."""
    m = re.search(rf"^{level}\s+{re.escape(title)}\s*$(.*?)(?=^#{{2,{len(level)}}}\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------- pieces

def icon(name, cls="icon"):
    f = SHARE / "icons" / f"{name}.svg"
    if not f.exists():
        return ""
    svg = f.read_text().replace('stroke="#000"', 'stroke="currentColor"').replace('fill="#000"', 'fill="currentColor"')
    return svg.replace("<svg ", f'<svg class="{cls}" aria-hidden="true" focusable="false" ', 1)


def version_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def fmt_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "bytes" else f"{n} bytes"
        n /= 1000


class Site:
    def __init__(self, out, iso=None, url=""):
        self.out = out
        self.url = url.rstrip("/")
        self.version = (ROOT / "VERSION").read_text().strip()
        self.readme = (ROOT / "README.md").read_text()
        self.releases = sorted((tomllib.loads(f.read_text()) | {"_dir": f.with_suffix("")}
                                for f in (SHARE / "releases").glob("*.toml")), key=lambda r: version_key(r["version"]), reverse=True)
        self.iso = self.find_iso(iso)
        self.pages = []
        self.css = "/style.css"
        self.font_url = None  # set by font(): what pages preload, if anything
        self.js = "/site.js"
        self.doc_titles = {n: DOC_META[n][0] for n in DOC_NAMES}

    # -- assets

    def find_iso(self, given):
        if given is False:  # --no-iso, and the tests
            return None
        if given:
            p = Path(given)
            return p if p.is_file() else sys.exit(f"no ISO at {p}")
        # The one DecKoOS Builder published (it may be older than the newest in out/), while it's still there
        pin = PIN.read_text().strip() if PIN.exists() else ""
        if pin and Path(pin).is_file():
            return Path(pin)
        # Release builds only (deckos-X.Y.Z-x86_64.iso), newest version first: not dated test builds
        isos = sorted((p for p in (ROOT / "out").glob("deckos-*-x86_64.iso") if re.fullmatch(r"deckos-\d{1,2}\.\d+\.\d+-x86_64\.iso", p.name)),
                      key=lambda p: version_key(p.name))
        return isos[-1] if isos else None

    def assets(self):
        for d in ("img", "fonts", "downloads"):
            (self.out / d).mkdir(parents=True, exist_ok=True)
        for f in ("style.css", "site.js"):
            data = (SITE / f).read_bytes()
            (self.out / f).write_bytes(data)
            ver = hashlib.sha256(data).hexdigest()[:10]
            if f.endswith(".css"):
                self.css = f"/style.css?v={ver}"
            else:
                self.js = f"/site.js?v={ver}"
        for f in ("logo.svg", "wordmark.svg"):
            shutil.copy(SHARE / "branding" / f, self.out / "img" / f)
        shutil.copy(SHARE / "branding/logo.svg", self.out / "favicon.svg")
        self.font()
        # Stamped after font(), which may rewrite the stylesheet
        self.css = f"/style.css?v={hashlib.sha256((self.out / 'style.css').read_bytes()).hexdigest()[:10]}"
        for name, _, _ in SHOTS:
            self.image(ROOT / "docs/screenshots" / f"{name}.png", f"shot-{name}")
        for r in self.releases:
            for h in r.get("highlights", []):
                if h.get("image"):
                    src = SHARE / "releases" / h["image"]
                    if src.exists():
                        h["_img"] = self.image(src, "release-" + src.stem)
        (self.out / "media").mkdir(exist_ok=True)  # the Vibe mode demo the home page plays
        for f in ("vibe-demo.mp4", "vibe-demo-poster.jpg"):
            if (ROOT / "docs/media" / f).exists():
                shutil.copy(ROOT / "docs/media" / f, self.out / "media" / f)
        keyring = ROOT / "pkg/deckos-settings/rootfs/usr/share/pacman/keyrings/deckos.gpg"
        if keyring.exists():
            shutil.copy(keyring, self.out / "downloads/deckos.gpg")

    def image(self, src, name):
        """A screenshot as WebP (when Pillow is here): a display size and the full size for the lightbox."""
        try:
            from PIL import Image
        except ImportError:
            dst = self.out / "img" / f"{name}{src.suffix}"
            shutil.copy(src, dst)
            return {"src": f"/img/{dst.name}", "full": f"/img/{dst.name}", "w": 0, "h": 0}
        img = Image.open(src)
        img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
        full = self.out / "img" / f"{name}.webp"
        img.save(full, "WEBP", quality=88, method=6)
        w, h = img.size
        if w > 1400:
            small = img.resize((1400, round(h * 1400 / w)), Image.LANCZOS)
            small.save(self.out / "img" / f"{name}-1400.webp", "WEBP", quality=86, method=6)
            return {"src": f"/img/{name}-1400.webp", "full": f"/img/{name}.webp", "w": 1400, "h": round(h * 1400 / w)}
        return {"src": f"/img/{name}.webp", "full": f"/img/{name}.webp", "w": w, "h": h}

    def font(self):
        """Inter (SIL Open Font License) from this PC, subset to Latin as WOFF2: no font requests to anyone else."""
        src = next((p for p in FONT_SOURCES if p.exists()), None)
        dst = self.out / "fonts/inter.woff2"
        css = self.out / "style.css"
        if not src:
            # No Inter here: no @font-face pointing at a missing file; the font stack falls back to the system's
            text = css.read_text()
            css.write_text(re.sub(r"@font-face\s*\{[^}]*\}\s*", "", text, count=1))
            return
        try:
            from fontTools import subset
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt", "cv11", "ss01", "tnum"]
            font = subset.load_font(str(src), opts)
            sub = subset.Subsetter(opts)
            sub.populate(unicodes=list(range(0x20, 0x7F)) + list(range(0xA0, 0x180)) + [0x2013, 0x2014, 0x2018, 0x2019,
                         0x201C, 0x201D, 0x2022, 0x2026, 0x2192, 0x2190, 0x2191, 0x2193, 0x00D7, 0x2212, 0x2122, 0x20AC])
            sub.subset(font)
            subset.save_font(font, str(dst), opts)
            self.font_url = ("/fonts/inter.woff2", "font/woff2")
        except Exception:
            shutil.copy(src, self.out / "fonts/inter.ttf")
            css.write_text(css.read_text().replace('url("/fonts/inter.woff2") format("woff2")',
                                                   'url("/fonts/inter.ttf") format("truetype")'))
            self.font_url = ("/fonts/inter.ttf", "font/ttf")
        (self.out / "fonts/LICENSE-Inter.txt").write_text(
            "Inter by Rasmus Andersson, licensed under the SIL Open Font License 1.1: https://openfontlicense.org\n")

    def iso_files(self):
        """Links the ISO into downloads/ (no 4 GB copy) with its SHA256 file, and a signature if there is one."""
        if not self.iso:
            return None
        iso = self.iso
        st = iso.stat()
        cache = iso.with_name(iso.name + ".sha256")
        digest = None
        if cache.exists() and cache.stat().st_mtime >= st.st_mtime:
            digest = cache.read_text().split()[0]
        if not digest or not re.fullmatch(r"[0-9a-f]{64}", digest):
            print(f"  checksum of {iso.name} (once per ISO)…")
            h = hashlib.sha256()
            with open(iso, "rb") as f:
                for block in iter(lambda: f.read(8 << 20), b""):
                    h.update(block)
            digest = h.hexdigest()
            cache.write_text(f"{digest}  {iso.name}\n")
        dl = self.out / "downloads"
        target = dl / iso.name
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            os.link(iso, target)
        except OSError:
            target.symlink_to(iso.resolve())
        (dl / f"{iso.name}.sha256").write_text(f"{digest}  {iso.name}\n")
        sig = iso.with_name(iso.name + ".sig")
        if sig.exists():
            shutil.copy(sig, dl / sig.name)
        version = re.search(r"deckos-([\d.]+)-", iso.name)
        return {"name": iso.name, "size": st.st_size, "sha256": digest, "sig": sig.exists(),
                "version": version.group(1) if version else "", "date": datetime.date.fromtimestamp(st.st_mtime)}

    # -- layout

    def page(self, path, title, body, description, current=""):
        nav = [("Features", "/#features"), ("What's new", "/releases.html"), ("Docs", "/docs/"), ("Source", "/source.html")]
        links = "".join(f'<a href="{h}"{" aria-current=page" if current == h else ""}>{t}</a>' for t, h in nav)
        full_title = f"{title} · {NAME}" if title != NAME else f"{NAME}: the desktop that plays along"
        canonical = f'<link rel="canonical" href="{self.url}/{path.replace("index.html", "")}">' if self.url else ""
        og_image = f'<meta property="og:image" content="{self.url}/img/shot-desktop-1400.webp">' if self.url else ""
        year = datetime.date.today().year
        doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(description)}">
<meta name="theme-color" content="#0b0d11">
<meta property="og:title" content="{html.escape(full_title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="website">
{og_image}
{canonical}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{f'<link rel="preload" href="{self.font_url[0]}" as="font" type="{self.font_url[1]}" crossorigin>' if self.font_url else ""}
<link rel="stylesheet" href="{self.css}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/"><img src="/img/logo.svg" alt="" width="30" height="30">{NAME}</a>
    <button class="menu-toggle" type="button" aria-label="Menu" aria-expanded="false">{icon("menu")}</button>
    <nav class="nav" aria-label="Main">{links}<a class="btn btn-primary btn-sm" href="/download.html">{icon("download")}Download</a></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <div class="foot-grid">
      <div class="foot-brand">
        <a class="brand" href="/"><img src="/img/logo.svg" alt="" width="30" height="30">{NAME}</a>
        <p>A desktop Linux distribution for people who play games and build things on the same PC.</p>
      </div>
      <div><h4>Get DecKoOS</h4><a href="/download.html">Download</a><a href="/docs/install.html">Install guide</a><a href="/download.html#requirements">Requirements</a><a href="/releases.html">What's new</a></div>
      <div><h4>Learn</h4><a href="/docs/guide.html">Using DecKoOS</a><a href="/docs/undo.html">Undo an update</a><a href="/docs/">All docs</a><a href="/download.html#limitations">Known limitations</a></div>
      <div><h4>Project</h4><a href="{GITHUB}" rel="noopener">GitHub</a><a href="{GITHUB}/issues" rel="noopener">Report a bug</a><a href="/security.html">Security</a><a href="/source.html">Source and licences</a></div>
    </div>
    <div class="legal">
      © {year} the DecKoOS contributors. DecKoOS's own code and artwork are MIT licensed; everything else keeps its
      own licence (<a href="/source.html">source and licences</a>). DecKoOS is an independent project, built on Arch Linux
      and CachyOS and not affiliated with or endorsed by them, KDE or Valve. Arch Linux, CachyOS, KDE, Plasma and Steam
      are trademarks of their respective owners.
    </div>
  </div>
</footer>
<script src="{self.js}" defer></script>
</body>
</html>
"""
        dst = self.out / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(doc)
        self.pages.append(path)

    def release_card(self, r, h_tag="h3"):
        hl = []
        for h in r.get("highlights", []):
            img = h.get("_img")
            dims = f' width="{img["w"]}" height="{img["h"]}"' if img and img["w"] else ""
            pic = (f'<img src="{img["src"]}" data-zoom="{img["full"]}" alt="{html.escape(h["title"])}" loading="lazy"{dims}>'
                   if img else "")
            hl.append(f'<div class="highlight">{pic}<h4>{icon(h.get("icon", "star"))}{html.escape(h["title"])}</h4>'
                      f'<p>{html.escape(" ".join(h["text"].split()))}</p></div>')
        fixes = "".join(f"<li>{icon('check')}<span>{html.escape(f)}</span></li>" for f in r.get("fixes", []))
        return f"""<article class="release-card" id="v{r['version']}">
  <div class="release-top"><{h_tag}>{html.escape(r['name'])}</{h_tag}><span class="version-tag">DecKoOS {r['version']}</span></div>
  <p class="tagline">{html.escape(r.get('tagline', ''))}</p>
  <div class="highlights">{''.join(hl)}</div>
  {f'<ul class="fixes">{fixes}</ul>' if fixes else ''}
</article>"""

    # -- pages

    def home(self, iso):
        intro = "DecKoOS is a Linux desktop for gaming PCs that moves with you. Put music on and the dock, the menu and " \
                "every DecKoOS app pulse on the beat while Vibe mode spreads the song across your monitors. Start a " \
                "game and the desktop takes on its colours and steps out of the way."
        # README's "What makes it different": the four things to know first
        different = "".join(
            f'<div class="feature"><div class="tile">{icon(ic)}</div><h3>{html.escape(t)}</h3><p>{Markdown(self.doc_link).inline(d)}</p></div>'
            for (t, d), ic in zip(re.findall(r"^- \*\*(.+?)\.\*\* (.+?)(?=\n- \*\*|\n\n)",
                                             md_section(self.readme, "What makes it different", "###") + "\n\n",
                                             re.M | re.S),
                                  ("music", "star", "appearance", "gaming")))
        rows = [(t, d) for t, d in re.findall(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$", md_section(self.readme, "Why DecKoOS"), re.M)
                if t not in HOME_SKIP]
        md = Markdown(self.doc_link)
        features = "".join(
            f'<div class="feature"><div class="tile">{icon(FEATURE_ICONS.get(t, "star"))}</div><h3>{html.escape(t)}</h3>'
            f'<p>{md.inline(d.rstrip("."))}.</p></div>' for t, d in rows)
        tabs = "".join(f'<button class="tab" role="tab" type="button" aria-selected="{str(i == 0).lower()}">{html.escape(label)}</button>'
                       for i, (_, label, _) in enumerate(SHOTS))
        shots = []
        for i, (name, label, cap) in enumerate(SHOTS):
            src = f"/img/shot-{name}"
            img = self._img_info(name)
            shots.append(f'<div class="shot{" active" if i == 0 else ""}" role="tabpanel"><figure>'
                         f'<img src="{img["src"]}" data-zoom="{img["full"]}" alt="{html.escape(label)}: {html.escape(cap)}" loading="lazy"'
                         f'{img["dims"]}><figcaption>{html.escape(cap)}</figcaption></figure></div>')
        latest = self.releases[0]
        hero_img = self._img_info("desktop")
        dl_meta = f"DecKoOS {self.version} · Free and open source · No account needed"
        body = f"""
<section class="hero">
  <div class="wrap">
    <a class="eyebrow" href="/releases.html"><span class="pill">New in {latest['version'].rsplit('.', 1)[0]}</span>{html.escape(latest['name'])} {icon('arrow-right')}</a>
    <h1>The desktop that <span class="gradient-text">plays along</span></h1>
    <p class="lede">{intro}</p>
    <div class="hero-actions">
      <a class="btn btn-primary btn-lg" href="/download.html">{icon('download')}Download DecKoOS</a>
      <a class="btn btn-lg" href="/docs/install.html">Read the install guide</a>
    </div>
    <p class="hero-meta">{dl_meta}</p>
    <div class="hero-shot"><video src="/media/vibe-demo.mp4" poster="/media/vibe-demo-poster.jpg" autoplay muted loop playsinline
      aria-label="Vibe mode on two monitors: live lyrics on one, the song's light on the other, through three of its looks"></video>
      <p class="hero-caption">Vibe mode on two monitors (a made-up demo song). Live lyrics on one screen, the music's light on the other.</p></div>
    <div class="stats">
      <div class="stat"><b>Plays along</b><span>The whole desktop on the beat</span></div>
      <div class="stat"><b>Learns you, locally</b><span>Nothing collected, nothing sent</span></div>
      <div class="stat"><b>Arch + CachyOS</b><span>KDE Plasma 6 and Steam Gaming Mode</span></div>
      <div class="stat"><b>Undo for updates</b><span>A snapshot before each one</span></div>
    </div>
  </div>
</section>

<section id="different">
  <div class="wrap">
    <div class="section-head">
      <span class="kicker">What makes it different</span>
      <h2>Not a theme on someone else's desktop</h2>
      <p>Every piece, from the boot menu to the apps, is built around one look and one idea: the PC moves with you.</p>
    </div>
    <div class="features four">{different}</div>
  </div>
</section>

<section id="features" class="band">
  <div class="wrap">
    <div class="section-head">
      <span class="kicker">Why DecKoOS</span>
      <h2>The whole PC, working as one system</h2>
      <p>Most gaming distributions tune the kernel and ship Steam. DecKoOS treats games, development and AI as one
      system, and ships its own tools to keep it healthy.</p>
    </div>
    <div class="features">{features}</div>
  </div>
</section>

<section id="tour">
  <div class="wrap" data-tabs>
    <div class="section-head">
      <span class="kicker">A look around</span>
      <h2>Its own apps, one consistent design</h2>
      <p>Files, Terminal, Editor, Hub, Store, Menu, Quick Settings, System Monitor and more, built for this system.</p>
    </div>
    <div class="tabs" role="tablist" aria-label="Screenshots">{tabs}</div>
    {''.join(shots)}
  </div>
</section>

<section class="band">
  <div class="wrap">
    <div class="section-head">
      <span class="kicker">Latest release</span>
      <h2>What's new in DecKoOS {latest['version'].rsplit('.', 1)[0]}</h2>
    </div>
    {self.release_card(latest)}
    <p style="text-align:center;margin-top:28px"><a href="/releases.html">Every release {icon('arrow-right')}</a></p>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="section-head">
      <span class="kicker">Built to be trusted</span>
      <h2>Safe to try, easy to take back</h2>
    </div>
    <div class="trust">
      <div class="trust-item">{icon('snapshot')}<div><h3>Every update can be undone</h3><p>A btrfs snapshot is taken before every update. Undo it from DecKoOS Hub, or start an older snapshot straight from the boot menu.</p></div></div>
      <div class="trust-item">{icon('shield')}<div><h3>An installer that leaves Windows alone</h3><p>It installs beside Windows, refuses BitLocker and in-use partitions, and installs itself in a virtual machine before every release.</p></div></div>
      <div class="trust-item">{icon('lock')}<div><h3>Signed packages</h3><p>Every DecKoOS update is signed, and your PC checks the signature before installing. <a href="/security.html">How it works</a>.</p></div></div>
      <div class="trust-item">{icon('ai')}<div><h3>Your AI stays on your PC</h3><p>The assistant runs on your own graphics card. Web search is off until you turn it on, and nothing is sent anywhere by itself.</p></div></div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="cta">
      <h2>Try DecKoOS on your PC</h2>
      <p>Download the ISO, write it to a USB stick, and install it next to Windows or on its own drive.</p>
      <div class="hero-actions" style="margin-top:0">
        <a class="btn btn-primary btn-lg" href="/download.html">{icon('download')}Download</a>
        <a class="btn btn-lg" href="/download.html#limitations">Known limitations</a>
      </div>
    </div>
  </div>
</section>
"""
        self.page("index.html", NAME, body, intro)

    def _img_info(self, name):
        for f, w in ((self.out / "img" / f"shot-{name}-1400.webp", 1400), (self.out / "img" / f"shot-{name}.webp", 0)):
            if f.exists():
                full = f"/img/shot-{name}.webp"
                dims = ""
                try:
                    from PIL import Image
                    iw, ih = Image.open(f).size
                    dims = f' width="{iw}" height="{ih}"'
                except Exception:
                    pass
                return {"src": f"/img/{f.name}", "full": full, "dims": dims}
        return {"src": f"/img/shot-{name}.png", "full": f"/img/shot-{name}.png", "dims": ""}

    def download(self, iso):
        install = (ROOT / "docs/install.md").read_text()
        md = Markdown(self.doc_link)
        requirements = md.render(md_section(install, "Requirements"))
        limits = md.render(md_section(self.readme, "Known limitations").split("\nBug reports")[0])
        if iso:
            sig = f'<a class="btn" href="/downloads/{iso["name"]}.sig">Signature (.sig)</a>' if iso["sig"] else ""
            main = f"""<div class="card dl-main">
  <div class="dl-title"><img src="/img/logo.svg" alt=""><div><h2>DecKoOS {iso['version']}</h2><span>64-bit PC (x86_64) · UEFI · built {iso['date']:%B %-d, %Y}</span></div></div>
  <div class="hero-actions" style="justify-content:flex-start;margin:0">
    <a class="btn btn-primary btn-lg" href="/downloads/{iso['name']}" download>{icon('download')}Download ISO</a>
    <a class="btn" href="/downloads/{iso['name']}.sha256">SHA256 file</a>{sig}
  </div>
  <dl class="meta">
    <dt>File</dt><dd><code>{iso['name']}</code></dd>
    <dt>Size</dt><dd>{fmt_size(iso['size'])}</dd>
    <dt>SHA256</dt><dd><div class="hash"><code title="{iso['sha256']}">{iso['sha256']}</code><button class="copy" type="button" data-copy="{iso['sha256']}">{icon('copy')}Copy</button></div></dd>
    <dt>Signing key</dt><dd><div class="hash"><code>{FINGERPRINT}</code><button class="copy" type="button" data-copy="{FINGERPRINT}">{icon('copy')}Copy</button></div></dd>
  </dl>
</div>"""
            if iso["version"] != self.version:
                main += f"""<div class="notice info">{icon('info')}<div>This ISO installs DecKoOS {iso['version']}. Its
first update brings it to the newest release: run it from DecKoOS Hub, or with <code>deckos update</code>.</div></div>"""
        else:
            main = f"""<div class="card dl-main">
  <div class="dl-title"><img src="/img/logo.svg" alt=""><div><h2>DecKoOS {self.version}</h2><span>64-bit PC (x86_64) · UEFI</span></div></div>
  <p>A ready-made ISO isn't published here yet. You can build one yourself in about half an hour, on GitHub or on
  any Arch Linux machine.</p>
  <a class="btn btn-primary" href="/docs/install.html#get-deckoos">How to build the ISO {icon('arrow-right')}</a>
</div>"""
        verify_sig = f"""
<li><div><b>Check the signature</b><p>Import the DecKoOS key, then check the ISO was signed with it. gpg should say
"Good signature" from key {FINGERPRINT[-16:]}.</p></div></li>""" if iso and iso["sig"] else ""
        name = iso["name"] if iso else "deckos-VERSION-x86_64.iso"
        sig_cmds = f"""gpg --import deckos.gpg
gpg --verify {name}.sig {name}
""" if iso and iso["sig"] else ""
        body = f"""
<div class="page-head"><div class="wrap">
  <span class="kicker">Download</span>
  <h1>Get <span class="gradient-text">DecKoOS</span></h1>
  <p>Free and open source. Install it next to Windows, on free space, or on a drive of its own.</p>
</div></div>
<div class="wrap">
  <div class="dl-grid">
    <div class="stack">
      {main}
      <div class="card">
        <h3>Install in three steps</h3>
        <ol class="steps">
          <li><div><b>Write it to a USB stick</b><p>Copy the ISO onto a <a href="https://www.ventoy.net" rel="noopener">Ventoy</a> stick, or write it with <a href="https://rufus.ie" rel="noopener">Rufus</a> (DD Image mode) or <code>dd</code>. 8 GB or larger.</p></div></li>
          <li><div><b>Start from the stick</b><p>Open your PC's boot menu (usually F11, F12 or F8 right after power-on) and pick the UEFI entry. Secure Boot must be off.</p></div></li>
          <li><div><b>Pick where it goes</b><p>The installer shows your drives and only uses the partition or free space you choose. <a href="/docs/install.html">The full install guide</a>.</p></div></li>
        </ol>
      </div>
      <div class="card prose" id="verify">
        <h3>Check your download</h3>
        <p>Make sure the file arrived whole and is the one published here. On Linux:</p>
        <pre><code>sha256sum -c {name}.sha256
{sig_cmds}</code></pre>
        <p>On Windows, in PowerShell: <code>Get-FileHash {name}</code>, then compare it with the SHA256 above.</p>
        <p>DecKoOS signs with the key <code>{FINGERPRINT}</code> (<a href="/downloads/deckos.gpg">download it</a>).</p>
        {f'<ol class="steps" style="margin-top:8px">{verify_sig}</ol>' if verify_sig else ""}
      </div>
    </div>
    <div class="stack">
      <div class="card prose" id="requirements"><h3>What you need</h3>{requirements}</div>
      <div class="card"><h3>Already running DecKoOS?</h3><p style="color:var(--sub);margin:0">You don't need the ISO: updates
      arrive by themselves. Open DecKoOS Hub, or run <code>deckos update</code>.</p></div>
    </div>
  </div>
  <section id="limitations" style="padding-top:64px">
    <div class="card prose">
      <h2 style="margin-top:0">Known limitations</h2>
      {limits}
      <p>Bug reports are welcome: <a href="{GITHUB}/issues" rel="noopener">open an issue</a> with the output of
      <code>deckos report</code>, and for install problems, <code>deckos-install.log</code>.</p>
    </div>
  </section>
</div>
"""
        self.page("download.html", "Download", body, f"Download DecKoOS {iso['version'] if iso else self.version}: the ISO, "
                  "its checksum and signing key, requirements and how to install.", "/download.html")

    def releases_page(self):
        cards = "".join(self.release_card(r, "h2") for r in self.releases)
        changelog = Markdown(self.doc_link).render((ROOT / "CHANGELOG.md").read_text().split("\n", 1)[1].split("\n", 3)[-1])
        body = f"""
<div class="page-head"><div class="wrap">
  <span class="kicker">What's new</span>
  <h1>Every <span class="gradient-text">DecKoOS</span> release</h1>
  <p>Feature releases bring what's below; patch releases in between are fixes, and arrive quietly. Installed PCs
  get each release through DecKoOS Hub.</p>
</div></div>
<div class="wrap">
  <div class="release-list">{cards}</div>
  <section id="changelog"><div class="card prose"><h2 style="margin-top:0">Full changelog</h2>{changelog}</div></section>
</div>
"""
        self.page("releases.html", "What's new", body, "What each DecKoOS release brought: highlights, fixes and the full changelog.",
                  "/releases.html")

    def doc_link(self, url):
        """Links written for GitHub, made to work on the site."""
        if re.match(r"^[a-z]+:", url) or url.startswith("#") or url.startswith("/"):
            return url
        path, _, frag = url.partition("#")
        name = Path(path).name
        if name == "README.md" and frag == "known-limitations":
            return "/download.html#limitations"
        if name.endswith(".md") and Path(path).parent.name in ("", "docs", ".") and name[:-3] in DOC_NAMES:
            return f"/docs/{name[:-3]}.html" + (f"#{frag}" if frag else "")
        target = (ROOT / "docs" / path).resolve()
        try:
            rel = target.relative_to(ROOT)
        except ValueError:
            return url
        return f"{GITHUB}/blob/main/{rel.as_posix()}" + (f"#{frag}" if frag else "")

    def docs(self):
        def nav(current):
            parts = []
            for group, names in DOCS:
                links = "".join(f'<a href="/docs/{n}.html"{" aria-current=page" if n == current else ""}>{html.escape(self.doc_titles[n])}</a>'
                                for n in names)
                parts.append(f"<h4>{html.escape(group)}</h4>{links}")
            return f'<nav class="docs-nav" aria-label="Docs">{"".join(parts)}</nav>'

        order = [n for _, names in DOCS for n in names]
        cards = []
        for group, names in DOCS:
            items = []
            for n in names:
                intro = DOC_META[n][1]
                items.append(f'<a class="doc-card" href="/docs/{n}.html"><b>{html.escape(self.doc_titles[n])}</b><span>{html.escape(intro)}</span></a>')
            cards.append(f'<h2>{html.escape(group)}</h2><div class="doc-cards">{"".join(items)}</div>')
        index = f"""<div class="wrap docs" style="grid-template-columns:230px minmax(0,1fr)">{nav("")}
<div class="prose"><h1>Documentation</h1><p style="font-size:18px;color:var(--sub)">How to install DecKoOS, use it every day,
and how its parts work.</p>{"".join(cards)}</div></div>"""
        self.page("docs/index.html", "Docs", index, "DecKoOS documentation: installing, everyday use, the apps and how they work.", "/docs/")

        for i, n in enumerate(order):
            md = Markdown(self.doc_link)
            text = (ROOT / "docs" / f"{n}.md").read_text()
            content = md.render(text)
            toc = "".join(f'<a href="#{hid}">{md.inline(t)}</a>' for lvl, hid, t in md.headings if lvl == 2)
            prev_ = f'<a href="/docs/{order[i - 1]}.html">← {html.escape(self.doc_titles[order[i - 1]])}</a>' if i else "<span></span>"
            next_ = f'<a href="/docs/{order[i + 1]}.html">{html.escape(self.doc_titles[order[i + 1]])} →</a>' if i + 1 < len(order) else ""
            edit = f'<a href="{GITHUB}/edit/main/docs/{n}.md" rel="noopener">Edit this page on GitHub</a>'
            body = f"""<div class="wrap docs">{nav(n)}
<article class="prose">{content}<div class="doc-foot">{prev_}{edit}{next_}</div></article>
<aside class="toc" aria-label="On this page">{f"<h4>On this page</h4>{toc}" if toc else ""}</aside></div>"""
            self.page(f"docs/{n}.html", self.doc_titles[n], body, DOC_META[n][1], "/docs/")

    def source(self):
        aur = [ln.split()[0] for ln in (SHARE / "packages/aur.txt").read_text().splitlines()
               if ln.strip() and not ln.lstrip().startswith("#")] if (SHARE / "packages/aur.txt").exists() else []
        aur_links = ", ".join(f'<a href="https://aur.archlinux.org/packages/{html.escape(p)}" rel="noopener"><code>{html.escape(p)}</code></a>' for p in aur)
        tag = f"v{self.version}"
        body = f"""
<div class="page-head"><div class="wrap">
  <span class="kicker">Open source</span>
  <h1>Source code and licences</h1>
  <p>DecKoOS is open source, and so is nearly everything it's built from. Here's where the source of every part
  is, the licences that come with it, and the few parts that aren't open.</p>
</div></div>
<div class="wrap" style="max-width:900px">
  <div class="card prose">
    <h2 style="margin-top:0">DecKoOS's own code</h2>
    <p>The installer, the <code>deckos</code> tool, DecKoOS Hub, Store, Files, Terminal, Editor, the themes, icons and
    artwork are developed in the open on GitHub under the <a href="{GITHUB}/blob/main/LICENSE" rel="noopener">MIT licence</a>.
    Each release is tagged: this one is <a href="{GITHUB}/tree/{tag}" rel="noopener"><code>{tag}</code></a>.</p>
    <p><a class="btn" href="{GITHUB}" rel="noopener">{icon('code')}DecKoOS on GitHub</a></p>

    <h2>Everything else on the ISO</h2>
    <p>DecKoOS is built from packages made by other projects. Each keeps its own licence (GPL, LGPL, MIT, Apache and
    others); the licence texts are installed with every package in <code>/usr/share/licenses</code>. A few parts
    aren't open source but may be shared, under their makers' terms: Steam's client, and NVIDIA's driver on PCs with an
    NVIDIA card.</p>
    <div class="table"><table>
      <thead><tr><th>Where it comes from</th><th>Its source</th></tr></thead>
      <tbody>
        <tr><td>Arch Linux packages</td><td><a href="https://gitlab.archlinux.org/archlinux/packaging/packages" rel="noopener">Arch's package sources</a>, the build recipe and upstream source of each package</td></tr>
        <tr><td>CachyOS packages</td><td><a href="https://github.com/CachyOS/CachyOS-PKGBUILDS" rel="noopener">CachyOS-PKGBUILDS</a> and <a href="https://github.com/CachyOS/linux-cachyos" rel="noopener">linux-cachyos</a> (the kernel)</td></tr>
        <tr><td>Apps from the AUR, prebuilt on the USB stick</td><td>{aur_links or "none"}: each page links its build recipe and upstream source</td></tr>
        <tr><td>DecKoOS packages</td><td><a href="{GITHUB}/tree/{tag}/pkg" rel="noopener"><code>pkg/</code> in the DecKoOS repo</a></td></tr>
      </tbody>
    </table></div>

    <h2>Getting the exact source</h2>
    <p>For at least three years after each release, we'll give anyone a copy of the complete corresponding source
    code for any GPL-licensed program on that release's ISO, for no more than the cost of providing it. Ask by
    <a href="{GITHUB}/issues/new?title=Source+request" rel="noopener">opening an issue</a> naming the release and the
    package.</p>

    <h2>Trademarks</h2>
    <p>DecKoOS is an independent project. It's built on Arch Linux and CachyOS but isn't made, endorsed or supported
    by them, by KDE, or by Valve. Arch Linux, CachyOS, KDE, Plasma, Steam and Steam Deck are trademarks of their
    respective owners, used here only to say what DecKoOS is built on and works with. The DecKoOS name and logo
    belong to the DecKoOS project.</p>

    <h2>Fonts and artwork</h2>
    <p>This website uses <a href="https://rsms.me/inter/" rel="noopener">Inter</a> by Rasmus Andersson (SIL Open Font
    Licence), served from this site: it makes no requests to anyone else. Photos in DecKoOS's Vibes are public domain
    or CC0, credited in the source.</p>
  </div>
</div>
"""
        self.page("source.html", "Source and licences", body, "Where the source of every part of DecKoOS is, its licences and trademarks.",
                  "/source.html")

    def security(self):
        sec = (ROOT / "SECURITY.md").read_text().split("\n", 1)[1]
        md = Markdown(self.doc_link)
        body = f"""
<div class="page-head"><div class="wrap">
  <span class="kicker">Security</span>
  <h1>Keeping DecKoOS safe</h1>
  <p>How DecKoOS updates are signed, and how to tell us about a security problem.</p>
</div></div>
<div class="wrap" style="max-width:900px">
  <div class="stack">
    <div class="card prose">
      <h2 style="margin-top:0">Signed updates</h2>
      <p>Every DecKoOS package is signed with the DecKoOS key, and pacman checks that signature before it installs
      anything. Installed PCs trust this key and no other for DecKoOS's own packages.</p>
      <div class="hash" style="margin:0 0 18px"><code>{FINGERPRINT}</code><button class="copy" type="button" data-copy="{FINGERPRINT}">{icon('copy')}Copy</button></div>
      <p><a class="btn" href="/downloads/deckos.gpg">{icon('download')}Download the public key</a></p>
      <p>Updates go to PCs on the testing channel first. The stable channel, where new installs start, only moves
      once a release has been on testing.</p>
    </div>
    <div class="card prose"><h2 style="margin-top:0">Reporting a problem</h2>{md.render(sec)}
      <p><a class="btn btn-primary" href="{GITHUB}/security/advisories/new" rel="noopener">{icon('lock')}Report privately on GitHub</a></p>
    </div>
  </div>
</div>
"""
        self.page("security.html", "Security", body, "How DecKoOS updates are signed, and how to report a security problem privately.")

    def not_found(self):
        body = f"""<div class="page-head" style="text-align:center;padding:120px 0"><div class="wrap">
  <span class="kicker">404</span><h1>That page isn't here</h1>
  <p style="margin:0 auto 30px">It may have moved. The docs and downloads are a click away.</p>
  <div class="hero-actions"><a class="btn btn-primary" href="/">Home</a><a class="btn" href="/docs/">Docs</a></div>
</div></div>"""
        self.page("404.html", "Not found", body, "Page not found.")

    def extras(self):
        robots = "User-agent: *\nAllow: /\n" + (f"Sitemap: {self.url}/sitemap.xml\n" if self.url else "")
        (self.out / "robots.txt").write_text(robots)
        if self.url:
            today = datetime.date.today().isoformat()
            urls = "".join(f"<url><loc>{self.url}/{p.replace('index.html', '')}</loc><lastmod>{today}</lastmod></url>"
                           for p in self.pages if p != "404.html")
            (self.out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                                  f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')

    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.assets()
        iso = self.iso_files()
        self.home(iso)
        self.download(iso)
        self.releases_page()
        self.docs()
        self.source()
        self.security()
        self.not_found()
        self.extras()
        return iso


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the DecKoOS website.")
    ap.add_argument("--out", default=str(SITE / "public"), help="where the site goes (default: site/public)")
    ap.add_argument("--iso", help="the ISO to offer (default: the newest out/deckos-*-x86_64.iso)")
    ap.add_argument("--no-iso", action="store_true", help="offer no ISO (the download page explains how to build one)")
    ap.add_argument("--url", default=os.environ.get("DECKOS_SITE_URL", ""), help="the site's public address, for links and the sitemap")
    a = ap.parse_args(argv)
    site = Site(Path(a.out).resolve(), False if a.no_iso else a.iso, a.url)
    iso = site.build()
    print(f"built {len(site.pages)} pages in {site.out}" + (f", offering {iso['name']}" if iso else ", no ISO to offer"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
