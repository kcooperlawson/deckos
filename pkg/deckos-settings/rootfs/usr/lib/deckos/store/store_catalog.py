"""DeckOS Store catalog: every app from the Arch/CachyOS repos and Flathub, plus AUR search.

App details (name, icon, description, screenshots, categories) come from the AppStream catalogs
Arch (archlinux-appstream-data) and Flathub (flatpak's appstream) already publish. An app that's in
both becomes one entry with two sources; installs prefer the repo, which updates with the system.
The AUR has no AppStream data, so it's searched live and shown as plain packages.

Parsing the catalogs takes a few seconds, so the result is cached in ~/.cache/deckos-store and
rebuilt only when a catalog file changes.
"""
import gzip
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEMO = "--demo" in sys.argv
CACHE = Path.home() / ".cache/deckos-store"
LANG_ATTR = "{http://www.w3.org/XML/1998/namespace}lang"
FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"

ARCH_XML = [Path("/usr/share/swcatalog/xml"), Path("/usr/share/app-info/xmls")]
ARCH_ICONS = [Path("/usr/share/swcatalog/icons"), Path("/usr/share/app-info/icons")]
FLATHUB_DIRS = [Path("/var/lib/flatpak/appstream/flathub/x86_64/active"),
                Path.home() / ".local/share/flatpak/appstream/flathub/x86_64/active"]

# Sidebar categories: (key, title, icon, freedesktop main categories)
CATEGORIES = [
    ("games", "Games", "gaming", {"Game"}),
    ("dev", "Development", "code", {"Development"}),
    ("graphics", "Graphics & Photos", "image", {"Graphics"}),
    ("media", "Audio & Video", "music", {"AudioVideo", "Audio", "Video"}),
    ("internet", "Internet", "globe", {"Network"}),
    ("office", "Office", "doc", {"Office"}),
    ("science", "Science & Education", "flask", {"Science", "Education"}),
    ("system", "System", "system", {"System"}),
    ("utilities", "Utilities", "sliders", {"Utility"}),
]

# DeckOS picks for the home page (AppStream ids, matched without case).
FEATURED = ["com.valvesoftware.steam", "com.discordapp.discord", "com.obsproject.studio", "com.spotify.client",
            "org.videolan.vlc", "org.kde.krita", "org.blender.blender", "org.gimp.gimp",
            "net.lutris.lutris", "com.heroicgameslauncher.hgl", "com.usebottles.bottles",
            "org.prismlauncher.prismlauncher", "com.visualstudio.code", "md.obsidian.obsidian",
            "org.libreoffice.libreoffice", "org.signal.signal"]

SOURCE_NAMES = {"repo": "Arch / CachyOS", "flathub": "Flathub", "aur": "AUR"}
SOURCE_ORDER = ["repo", "flathub", "aur"]


@dataclass
class App:
    key: str                      # lower-case AppStream id without ".desktop"
    name: str
    summary: str = ""
    description: str = ""         # simple HTML (p, ul, li)
    developer: str = ""
    icon: str = ""                # local file, a theme icon name, or ""
    icon_url: str = ""
    categories: list = field(default_factory=list)
    screenshots: list = field(default_factory=list)
    homepage: str = ""
    license: str = ""
    version: str = ""
    desktop_id: str = ""
    sources: dict = field(default_factory=dict)   # {"repo": pkgname, "flathub": app id, "aur": pkgname}

    def merge(self, other):
        for k, v in asdict(other).items():
            if k == "sources":
                self.sources.update(v)
            elif not getattr(self, k) and v:
                setattr(self, k, v)

    def best_source(self, installed=None):
        """Where it's installed from, else the preferred place to install it from."""
        if installed:
            for s in SOURCE_ORDER:
                if s in self.sources and installed.has(s, self.sources[s]):
                    return s
        return next((s for s in SOURCE_ORDER if s in self.sources), None)

    def section(self):
        cats = set(self.categories)
        return next((key for key, _t, _i, main in CATEGORIES if cats & main), "utilities")


def norm(app_id):
    app_id = app_id.strip().lower()
    return app_id[:-8] if app_id.endswith(".desktop") else app_id


# ------------------------------------------------------------------ AppStream parsing

def _text(el, tag):
    """The untranslated text of the first child `tag` (AppStream repeats elements per language)."""
    for c in el.findall(tag):
        if LANG_ATTR not in c.attrib:
            return (c.text or "").strip()
    return ""


def _description(el):
    desc = next((d for d in el.findall("description") if LANG_ATTR not in d.attrib), None)
    if desc is None:
        return ""
    out = []
    for c in desc:
        if LANG_ATTR in c.attrib:
            continue
        if c.tag == "p":
            out.append(f"<p>{_inline(c)}</p>")
        elif c.tag in ("ul", "ol"):
            items = "".join(f"<li>{_inline(li)}</li>" for li in c if LANG_ATTR not in li.attrib)
            out.append(f"<{c.tag}>{items}</{c.tag}>")
    return "".join(out)


def _inline(el):
    """Text with <em>/<code> kept, everything escaped."""
    import html
    parts = [html.escape(el.text or "")]
    for c in el:
        inner = html.escape("".join(c.itertext()))
        parts.append(f"<{c.tag}>{inner}</{c.tag}>" if c.tag in ("em", "code") else inner)
        parts.append(html.escape(c.tail or ""))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def parse_appstream(path, source, icon_dirs):
    """[App] for the desktop apps in one AppStream catalog file (.xml or .xml.gz)."""
    apps, origin = [], ""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as f:
        for event, el in ET.iterparse(f, events=("start", "end")):
            if event == "start":
                if el.tag == "components":
                    origin = el.get("origin", "")
                continue
            if el.tag != "component":
                continue
            if el.get("type") not in ("desktop-application", "desktop"):
                el.clear()
                continue
            app_id = _text(el, "id")
            name = _text(el, "name")
            if not app_id or not name:
                el.clear()
                continue
            app = App(key=norm(app_id), name=name, summary=_text(el, "summary"), description=_description(el))
            dev = el.find("developer")
            app.developer = _text(el, "developer_name") or (_text(dev, "name") if dev is not None else "")
            app.categories = [c.text for c in el.findall("categories/category") if c.text]
            app.homepage = next((u.text for u in el.findall("url") if u.get("type") == "homepage" and u.text), "")
            app.license = _text(el, "project_license")
            rel = el.find("releases/release")
            app.version = rel.get("version", "") if rel is not None else ""
            app.desktop_id = next((l.text for l in el.findall("launchable") if l.get("type") == "desktop-id"), "")
            for ss in el.findall("screenshots/screenshot"):
                imgs = [i for i in ss.findall("image") if LANG_ATTR not in i.attrib]
                src = next((i for i in imgs if i.get("type") == "source"), None)
                if src is None and imgs:  # else the largest thumbnail
                    src = max(imgs, key=lambda i: int(i.get("width") or 0))
                if src is not None and src.text:
                    app.screenshots.append(src.text.strip())
            _icon(el, app, origin, icon_dirs)
            if source == "repo":
                pkg = _text(el, "pkgname")
                if not pkg:
                    el.clear()
                    continue
                app.sources["repo"] = pkg
            else:
                bundle = next((b.text for b in el.findall("bundle") if b.get("type") == "flatpak" and b.text), "")
                app.sources["flathub"] = bundle.split("/")[1] if bundle.count("/") >= 2 else app_id.removesuffix(".desktop")
            apps.append(app)
            el.clear()
    return apps


def _icon(el, app, origin, icon_dirs):
    best = None
    for ic in el.findall("icon"):
        kind, text = ic.get("type"), (ic.text or "").strip()
        if kind == "cached" and text:
            size = int(ic.get("width") or 64)
            for base in icon_dirs:
                for folder in ([base / origin] if origin else []) + [base]:
                    p = folder / f"{size}x{size}" / text
                    if p.exists() and (best is None or size > best[0]):
                        best = (size, str(p))
        elif kind == "stock" and text and not app.icon:
            app.icon = text
        elif kind == "remote" and text:
            app.icon_url = text
    if best:
        app.icon = best[1]


# ------------------------------------------------------------------ the catalog

class Catalog:
    """All apps, keyed by AppStream id, with search and category lists."""

    def __init__(self):
        self.apps = {}
        self.status = ""

    def sources_available(self):
        arch = [p for d in ARCH_XML if d.is_dir() for p in sorted(d.glob("*.xml*"))]
        flathub = next((d / n for d in FLATHUB_DIRS for n in ("appstream.xml.gz", "appstream.xml")
                        if (d / n).exists()), None)
        return arch, flathub

    def load(self):
        """Parse (or load from cache) both catalogs. Slow: run it off the UI thread."""
        if DEMO:
            self.apps = {a.key: a for a in demo_apps()}
            self.status = f"{len(self.apps)} apps (demo)"
            return
        arch, flathub = self.sources_available()
        files = arch + ([flathub] if flathub else [])
        stamp = {str(p): p.stat().st_mtime for p in files}
        cache = CACHE / "catalog.json"
        try:
            data = json.loads(cache.read_text())
            if data.get("stamp") == stamp:
                self.apps = {a["key"]: App(**a) for a in data["apps"]}
                if not MENU_INDEX.exists() or MENU_INDEX.stat().st_mtime < cache.stat().st_mtime:
                    write_menu_index(self.apps)
                self._status(arch, flathub)
                return
        except (OSError, ValueError, TypeError):
            pass
        apps = {}
        catalogs = [(p, "repo", ARCH_ICONS) for p in arch] + ([(flathub, "flathub", [flathub.parent / "icons"])]
                                                             if flathub else [])
        for path, source, icons in catalogs:
            for a in parse_appstream(path, source, icons):
                if a.key in apps:
                    apps[a.key].merge(a)
                else:
                    apps[a.key] = a
        self.apps = apps
        CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"stamp": stamp, "apps": [asdict(a) for a in apps.values()]}))
        write_menu_index(apps)
        self._status(arch, flathub)

    def _status(self, arch, flathub):
        n_repo = sum("repo" in a.sources for a in self.apps.values())
        n_flat = sum("flathub" in a.sources for a in self.apps.values())
        self.status = f"{len(self.apps):,} apps · {n_repo:,} from Arch/CachyOS · {n_flat:,} from Flathub"

    def featured(self):
        return [self.apps[k] for k in FEATURED if k in self.apps]

    def in_category(self, key):
        apps = [a for a in self.apps.values() if a.section() == key]
        featured = set(FEATURED)
        return sorted(apps, key=lambda a: (a.key not in featured, not a.icon, not a.screenshots, a.name.lower()))

    def search(self, term):
        term = term.strip().lower()
        if not term:
            return []
        scored = []
        for a in self.apps.values():
            name = a.name.lower()
            score = (6 if name == term else 4 if name.startswith(term) else 3 if term in name else
                     2 if term in a.sources.get("repo", "") else 1 if term in a.summary.lower() else 0)
            if score:
                scored.append((-score, not a.icon, a.name.lower(), a))
        return [s[-1] for s in sorted(scored, key=lambda s: s[:3])[:120]]


MENU_INDEX = CACHE / "menu-index.json"


def write_menu_index(apps):
    """Just the fields DeckOS Menu's search needs (store_find.py), so its lookups start in milliseconds
    instead of reading the whole catalog with descriptions and screenshots."""
    rows = [{"key": a.key, "name": a.name, "summary": a.summary, "icon": a.icon, "desktop_id": a.desktop_id,
             "sources": a.sources} for a in apps.values()]
    tmp = MENU_INDEX.with_suffix(".tmp")
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(rows))
        tmp.replace(MENU_INDEX)
    except OSError:
        pass


def aur_search(term):
    """[(name, version, description, votes)] from the AUR, most popular first. Network."""
    if DEMO:
        return [("protonplus", "0.4.21-1", "A simple Wine and Proton-based compatibility tools manager", 312),
                ("spotify-adblock", "1.0.3-2", "Adblocker for Spotify", 287),
                ("heroic-games-launcher-bin", "2.15.2-1", "Native GOG, Epic and Amazon Games launcher", 655)]
    url = "https://aur.archlinux.org/rpc/v5/search/" + urllib.parse.quote(term) + "?by=name-desc"
    with urllib.request.urlopen(url, timeout=10) as r:
        results = json.load(r).get("results", [])
    results.sort(key=lambda p: -(p.get("Popularity") or 0))
    return [(p["Name"], p["Version"], p.get("Description") or "", p.get("NumVotes") or 0) for p in results[:40]]


# ------------------------------------------------------------------ what's installed

class Installed:
    """Installed repo packages, foreign (AUR) packages and Flatpak apps."""

    def __init__(self):
        self.repo, self.aur, self.flatpak = set(), set(), set()
        self.flathub_ready = False

    def refresh(self):
        if DEMO:  # starts with a few apps; demo installs and removals change it (see demo_apply)
            if not self.flathub_ready:
                self.repo, self.aur, self.flatpak, self.flathub_ready = {"steam", "obs-studio", "lutris"}, set(), \
                    {"com.discordapp.Discord", "md.obsidian.Obsidian"}, True
            return
        run = lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.split()
        try:
            self.repo = set(run(["pacman", "-Qq"]))
            self.aur = set(run(["pacman", "-Qqm"]))
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            self.flatpak = set(run(["flatpak", "list", "--app", "--columns=application"]))
            self.flathub_ready = "flathub" in run(["flatpak", "remotes", "--columns=name"])
        except (OSError, subprocess.SubprocessError):
            self.flatpak, self.flathub_ready = set(), False

    def demo_apply(self, action, source, ident):
        target = {"repo": self.repo, "aur": self.aur, "flathub": self.flatpak}[source]
        (target.add if action == "install" else target.discard)(ident)

    def has(self, source, ident):
        return ident in {"repo": self.repo, "aur": self.aur, "flathub": self.flatpak}.get(source, ())

    def app_installed(self, app):
        return any(self.has(s, i) for s, i in app.sources.items())


# ------------------------------------------------------------------ demo data

def demo_apps():
    rows = [
        ("com.valvesoftware.Steam", "Steam", "Launcher for the Steam software distribution service", "Valve", ["Game"],
         {"repo": "steam", "flathub": "com.valvesoftware.Steam"}),
        ("com.discordapp.Discord", "Discord", "Messaging, voice and video for gamers", "Discord Inc.", ["Network"],
         {"flathub": "com.discordapp.Discord", "repo": "discord"}),
        ("com.obsproject.Studio", "OBS Studio", "Live streaming and video recording software", "OBS Project",
         ["AudioVideo"], {"repo": "obs-studio", "flathub": "com.obsproject.Studio"}),
        ("com.spotify.Client", "Spotify", "Online music streaming service", "Spotify", ["Audio"],
         {"flathub": "com.spotify.Client"}),
        ("org.videolan.VLC", "VLC", "Play all your music and videos", "VideoLAN", ["AudioVideo"],
         {"repo": "vlc", "flathub": "org.videolan.VLC"}),
        ("org.kde.krita", "Krita", "Digital painting, creative freedom", "KDE", ["Graphics"],
         {"repo": "krita", "flathub": "org.kde.krita"}),
        ("org.blender.Blender", "Blender", "Free and open source 3D creation suite", "Blender Foundation",
         ["Graphics"], {"repo": "blender", "flathub": "org.blender.Blender"}),
        ("org.gimp.GIMP", "GIMP", "Create images and edit photographs", "The GIMP team", ["Graphics"],
         {"repo": "gimp", "flathub": "org.gimp.GIMP"}),
        ("net.lutris.Lutris", "Lutris", "Video game preservation platform", "Lutris Team", ["Game"],
         {"repo": "lutris", "flathub": "net.lutris.Lutris"}),
        ("com.heroicgameslauncher.hgl", "Heroic Games Launcher", "GOG, Epic Games and Amazon Prime Games launcher",
         "Heroic Team", ["Game"], {"flathub": "com.heroicgameslauncher.hgl"}),
        ("com.usebottles.bottles", "Bottles", "Run Windows software", "Bottles Developers", ["Utility"],
         {"flathub": "com.usebottles.bottles"}),
        ("org.prismlauncher.PrismLauncher", "Prism Launcher", "Custom Minecraft launcher", "Prism Launcher",
         ["Game"], {"repo": "prismlauncher", "flathub": "org.prismlauncher.PrismLauncher"}),
        ("com.visualstudio.code", "Visual Studio Code", "Code editing. Redefined.", "Microsoft", ["Development"],
         {"flathub": "com.visualstudio.code"}),
        ("md.obsidian.Obsidian", "Obsidian", "Markdown-based knowledge base", "Obsidian", ["Office"],
         {"flathub": "md.obsidian.Obsidian"}),
        ("org.libreoffice.LibreOffice", "LibreOffice", "The LibreOffice productivity suite", "The Document Foundation",
         ["Office"], {"repo": "libreoffice-fresh", "flathub": "org.libreoffice.LibreOffice"}),
        ("org.signal.Signal", "Signal", "Private messenger", "Signal Foundation", ["Network"],
         {"repo": "signal-desktop", "flathub": "org.signal.Signal"}),
        ("org.kde.kdenlive", "Kdenlive", "Video editor", "KDE", ["AudioVideo"], {"repo": "kdenlive"}),
        ("org.godotengine.Godot", "Godot", "Multi-platform 2D and 3D game engine", "Godot", ["Development"],
         {"repo": "godot", "flathub": "org.godotengine.Godot"}),
        ("org.mozilla.Thunderbird", "Thunderbird", "Email, calendar and chat", "Mozilla", ["Network"],
         {"repo": "thunderbird", "flathub": "org.mozilla.Thunderbird"}),
        ("com.github.tchx84.Flatseal", "Flatseal", "Manage Flatpak permissions", "Martin Abente Lahaye",
         ["Utility"], {"flathub": "com.github.tchx84.Flatseal"}),
    ]
    apps = []
    for app_id, name, summary, dev, cats, sources in rows:
        apps.append(App(key=norm(app_id), name=name, summary=summary, developer=dev, categories=cats,
                        sources=dict(sources), version="1.0", license="See project",
                        homepage="https://example.org", desktop_id=app_id + ".desktop",
                        description=f"<p>{summary}. This is demo data for working on the DeckOS Store layout.</p>"
                                    "<ul><li>Installs from the source you pick</li><li>Updates with DeckOS</li></ul>",
                        screenshots=["demo:1", "demo:2", "demo:3"]))
    return apps
