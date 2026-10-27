"""DecKoOS Hub's Games page: one library for Steam, Heroic (Epic, GOG), Lutris and games in plain folders on the
drives (usr/lib/deckos/localgames), read straight from their own files (no logins, nothing running), with ProtonDB
ratings and a Play button."""
import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QProcess, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

import hub_style as S
import hub_system as sysinfo
from hub_pages import Page
from hub_widgets import Empty, button, label

import sys  # noqa: E402
for _sub in ("profiles", "gamedoctor", "localgames"):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / _sub))
import profiles  # noqa: E402
import localgames  # noqa: E402

LOCALGAMES = Path(localgames.__file__).resolve()
LOCAL = "My drives"  # the source name of games found in folders

HOME = Path.home()
STEAM_ROOTS = [HOME / ".local/share/Steam", HOME / ".steam/steam", HOME / ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
HEROIC_ROOTS = [HOME / ".config/heroic", HOME / ".var/app/com.heroicgameslauncher.hgl/config/heroic"]
LUTRIS = HOME / ".local/share/lutris"
PROTONDB_CACHE = HOME / ".cache/deckos/protondb.json"
# Steam installs these like games; they aren't.
NOT_GAMES = re.compile(r"^(Proton|Steam Linux Runtime|Steamworks Common|SteamVR)|Redistributable", re.I)
TIER_COLORS = {"platinum": "#B4C7DC", "gold": "#E5C258", "silver": "#A6A6A6", "bronze": "#CD7F32",
               "borked": S.DANGER, "native": S.SUCCESS}
COVER_W, COVER_H = 138, 207


def vdf(text):
    """Valve KeyValues ("key" "value" / "key" { ... }) to nested dicts; keys lower-cased."""
    root, stack, key = {}, [], None
    cur = root
    for tok in re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text):
        s, brace = tok
        if brace == "{":
            new = {}
            cur[(key or "").lower()] = new
            stack.append(cur)
            cur, key = new, None
        elif brace == "}":
            cur = stack.pop() if stack else root
        elif key is None:
            key = s
        else:
            cur[key.lower()] = s
            key = None
    return root


def _read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def steam_games():
    root = next((r for r in STEAM_ROOTS if (r / "steamapps").is_dir()), None)
    if not root:
        return []
    libs = {root}
    for lib in vdf(_read(root / "steamapps/libraryfolders.vdf")).get("libraryfolders", {}).values():
        if isinstance(lib, dict) and lib.get("path"):
            libs.add(Path(lib["path"]))
    last = {}
    for cfg in (root / "userdata").glob("*/config/localconfig.vdf"):
        apps = (vdf(_read(cfg)).get("userlocalconfigstore", {}).get("software", {}).get("valve", {})
                .get("steam", {}).get("apps", {}))
        for appid, a in apps.items():
            played = a.get("lastplayed", "0") if isinstance(a, dict) else "0"
            if isinstance(played, str) and played.isdigit():  # absent for apps never played
                last[appid] = max(last.get(appid, 0), int(played))
    games, cache = [], root / "appcache/librarycache"
    for lib in libs:
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            st = vdf(_read(acf)).get("appstate", {})
            appid, name = st.get("appid", ""), st.get("name", "")
            if not appid or not name or NOT_GAMES.search(name):
                continue
            art = next((p for p in (cache / f"{appid}_library_600x900.jpg", cache / appid / "library_600x900.jpg")
                        if p.exists()), None) or next(iter((cache / appid).glob("*/library_600x900.jpg")), None)
            games.append({"name": name, "source": "Steam", "id": appid, "size": int(st.get("sizeondisk") or 0),
                          "last": last.get(appid, 0), "art": art, "launch": ("steam", [f"steam://rungameid/{appid}"])})
    return games


def heroic_games():
    root = next((r for r in HEROIC_ROOTS if r.is_dir()), None)
    if not root:
        return []
    games = []
    try:
        installed = json.loads(_read(root / "legendaryConfig/legendary/installed.json") or "{}")
    except ValueError:
        installed = {}
    for app, g in installed.items():
        games.append({"name": g.get("title", app), "source": "Epic", "id": app, "size": int(g.get("install_size") or 0),
                      "last": 0, "art": None, "launch": ("xdg-open", [f"heroic://launch/legendary/{app}"])})
    try:
        gog = json.loads(_read(root / "gog_store/installed.json") or "{}").get("installed", [])
        titles = {g.get("app_name"): g.get("title") for g in
                  json.loads(_read(root / "store_cache/gog_library.json") or "{}").get("games", [])}
    except (ValueError, AttributeError):
        gog, titles = [], {}
    for g in gog:
        app = g.get("appName", "")
        games.append({"name": titles.get(app) or app, "source": "GOG", "id": app, "size": 0, "last": 0, "art": None,
                      "launch": ("xdg-open", [f"heroic://launch/gog/{app}"])})
    return games


def lutris_games():
    db = LUTRIS / "pga.db"
    if not db.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT id, name, slug, lastplayed FROM games WHERE installed = 1").fetchall()
        con.close()
    except sqlite3.Error:
        return []
    return [{"name": name, "source": "Lutris", "id": str(gid), "size": 0, "last": int(lp or 0),
             "art": next((p for p in (LUTRIS / f"coverart/{slug}.jpg", HOME / f".cache/lutris/coverart/{slug}.jpg")
                          if p.exists()), None), "launch": ("lutris", [f"lutris:rungameid/{gid}"])}
            for gid, name, slug, lp in rows]


DEMO_GAMES = [("Cyberpunk 2077", "Steam", "1091500", 71e9, 2), ("Elden Ring", "Steam", "1245620", 49e9, 5),
              ("Baldur's Gate 3", "Steam", "1086940", 122e9, 30), ("Helldivers 2", "Steam", "553850", 72e9, 1),
              ("Counter-Strike 2", "Steam", "730", 38e9, 9), ("Hades II", "Steam", "1145350", 9e9, 60),
              ("Fortnite", "Epic", "Fortnite", 31e9, 0), ("The Witcher 3", "GOG", "1207664643", 50e9, 0),
              ("Diablo IV", "Lutris", "12", 90e9, 14)]
DEMO_TIERS = {"1091500": "platinum", "1245620": "gold", "1086940": "platinum", "553850": "gold", "730": "native",
              "1145350": "platinum"}


DEMO_LOCAL = [
    {"name": "Baby Steps", "folder": "/mnt/BIG/Games/Baby Steps", "exe": "BabySteps.exe", "runner": "proton",
     "engine": "Unity", "arch": "64-bit", "needs": ["DirectX 11"], "blockers": [], "notes": [],
     "candidates": ["BabySteps.exe"], "sure": True, "appid": "1281040", "picked": False},
    {"name": "Expeditions - A MudRunner Game", "folder": "/mnt/BIG/Games/Expeditions - A MudRunner Game",
     "exe": "Sources/Bin/Expeditions.exe", "runner": "proton", "engine": "", "arch": "64-bit",
     "needs": ["DirectX 11", "Visual C++ runtime"], "blockers": [], "notes": [],
     "candidates": ["Sources/Bin/Expeditions.exe", "Sources/Bin/ExpeditionsLauncher.exe"], "sure": False,
     "appid": "", "picked": False},
    {"name": "Arena Shooter", "folder": "/mnt/SSD/Games/Arena Shooter", "exe": "Shooter.exe", "runner": "proton",
     "engine": "Unreal Engine", "arch": "64-bit", "needs": ["DirectX 12"],
     "blockers": ["EasyAntiCheat: its anti-cheat may refuse to run on Linux unless the game turned on Proton support"],
     "notes": [], "candidates": ["Shooter.exe"], "sure": True, "appid": "", "picked": False},
    {"name": "Old RPG", "folder": "/mnt/BIG/Games/Old RPG", "exe": "", "runner": "none", "engine": "", "arch": "",
     "needs": [], "blockers": [], "notes": ["Needs installing first: setup_old_rpg_1.0.exe sets it up in the game's "
                                            "own prefix."], "candidates": [], "sure": False, "appid": "",
     "picked": False, "installer": "setup_old_rpg_1.0.exe"},
]


def local_game(g):
    """A Games page entry from a localgames scan entry (a dict)."""
    art = localgames.COVERS / f"{g['appid']}.jpg" if g.get("appid") else None
    play = ["/usr/bin/deckos-play"] if Path("/usr/bin/deckos-play").exists() else ["python3", str(LOCALGAMES), "play"]
    try:
        last = (localgames.LOGS / f"{localgames.slug(g['name'])}.log").stat().st_mtime
    except OSError:
        last = 0
    return {"name": g["name"], "source": LOCAL, "id": g["folder"], "size": 0, "last": int(last),
            "art": art if art and art.exists() else None, "launch": (play[0], play[1:] + [g["folder"]]), "local": g}


def all_games():
    if sysinfo.DEMO:
        now = time.time()
        return [{"name": n, "source": s, "id": i, "size": int(sz), "last": int(now - d * 86400) if d else 0, "art": None,
                 "launch": ("true", [])} for n, s, i, sz, d in DEMO_GAMES]
    return steam_games() + heroic_games() + lutris_games()


def fmt_size(b):
    return f"{b / 1e9:.0f} GB" if b >= 1e9 else f"{b / 1e6:.0f} MB" if b else ""


def fmt_last(ts):
    if not ts:
        return "Never played"
    days = (time.time() - ts) / 86400
    return "Played today" if days < 1 else "Yesterday" if days < 2 else f"{int(days)} days ago" if days < 30 else \
        datetime.fromtimestamp(ts).strftime("%b %Y")


def cover(game):
    """Cover art at tile size: the launcher's own art, else a DecKoOS gradient with the title."""
    pm = QPixmap(COVER_W * 2, COVER_H * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, COVER_W, COVER_H), S.corner(8), S.corner(8))
    p.setClipPath(clip)
    art = QPixmap(str(game["art"])) if game.get("art") else QPixmap()
    if not art.isNull():
        p.drawPixmap(QRectF(0, 0, COVER_W, COVER_H), art, QRectF(art.rect()))
    else:
        g = QLinearGradient(0, 0, COVER_W, COVER_H)
        g.setColorAt(0, QColor(S.P.accent).darker(260))
        g.setColorAt(1, QColor(S.P.grad_b).darker(200))
        p.fillRect(QRectF(0, 0, COVER_W, COVER_H), g)
        p.setPen(QColor(S.TEXT))
        f = QFont("Inter Display", 12)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.drawText(QRectF(12, 12, COVER_W - 24, COVER_H - 24), Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap,
                   game["name"])
    p.end()
    return pm


class GameTile(QFrame):
    def __init__(self, game, tier, play):
        super().__init__()
        self.game = game
        self.setObjectName("tile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)  # the grid is walked with arrow keys or a d-pad: GamesPage.eventFilter
        self.setFixedWidth(S.scaled(COVER_W + 20))
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(4)
        art = QLabel()
        w = S.scaled(COVER_W)  # the cover grows with the text, so the card stays one piece
        pm = cover(game)
        art.setPixmap(pm if w == COVER_W else pm.scaledToWidth(w, Qt.SmoothTransformation))
        v.addWidget(art)
        name = label(game["name"], wrap=False)
        name.setToolTip(game["name"])
        name.setMaximumWidth(w)
        name.setText(name.fontMetrics().elidedText(game["name"], Qt.ElideRight, w))
        v.addWidget(name)
        loc = game.get("local")
        bits = [game["source"], fmt_size(game["size"])] if not loc else [
            "Linux" if loc["runner"] == "native" else loc["engine"] or "Windows", Path(loc["folder"]).parent.parent.name]
        v.addWidget(label("  ·  ".join(b for b in bits if b), "muted", wrap=False))
        self.tier = label("", "muted", wrap=False)
        self.tier.setTextFormat(Qt.RichText)
        self.set_tier(tier)
        v.addWidget(self.tier)
        has = bool(profiles.load().get(profile_id(game))) if not sysinfo.DEMO else game["name"].startswith("Cyber")
        prof = button("", slot=lambda: ProfileDialog(self, game).exec(), icon="sliders",
                      tip="Profile: what this game gets while it runs" + (" (set)" if has else ""))
        if has:
            prof.setIcon(S.icon("sliders", S.P.accent, 16))
        self.more = (lambda: LocalGameDialog(self, game).exec()) if loc else (lambda: ProfileDialog(self, game).exec())
        if loc:
            about = button("", slot=lambda: LocalGameDialog(self, game).exec(), icon="details",
                           tip="What this game needs, which program starts it, and Steam")
            if loc["blockers"] or not loc["sure"] or not loc["exe"]:
                about.setIcon(S.icon("alert", S.WARNING, 16))
            if loc.get("installer") and not loc["exe"]:
                playb = button("Install", "primary", lambda: play.__self__.install(game, playb),
                               icon="download", tip=f"Runs {loc['installer']} in the game's own prefix")
            else:
                playb = button("Play", "primary", lambda: play(game), icon="play")
                playb.setEnabled(bool(loc["exe"]))
            v.addWidget(_row(playb, about))  # its profile is in the details: three buttons squeeze Play
        else:
            playb = button("Play", "primary", lambda: play(game), icon="play")
            v.addWidget(_row(playb, prof))
        self.go = playb.click  # Enter on the tile: what its main button does (Play, or Install)
        for b in self.findChildren(QPushButton):
            b.setFocusPolicy(Qt.NoFocus)  # one stop per game; the tile's keys reach its buttons

    def set_tier(self, tier):
        loc = self.game.get("local")
        if loc and (loc["blockers"] or not loc["exe"] or not loc["sure"]):
            self.tier.setText(f"<span style='color:{S.WARNING}'>●</span> " + (
                "Needs installing" if not loc["exe"] else "May not run" if loc["blockers"] else "Check its program"))
        elif tier:
            self.tier.setText(f"<span style='color:{TIER_COLORS.get(tier, S.SUBTEXT)}'>●</span> ProtonDB "
                              f"{tier.capitalize()}")
        else:
            self.tier.setText("&nbsp;")


def _row(*widgets):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    for x in widgets:
        h.addWidget(x, 1 if x is widgets[0] else 0)
    return w


def profile_id(game):
    """What workload modes know the game by: Steam's App ID, else its name (Lutris)."""
    return str(game["id"]) if game.get("source") == "Steam" and game.get("id") else game["name"]


class ProfileDialog(QDialog):
    """A game's profile (usr/lib/deckos/profiles): applied when it starts, put back when it stops."""

    CHOICES = {
        "power": ("Power", [("As usual", ""), ("Performance", "performance"), ("Balanced", "balanced"),
                            ("Power saver", "power-saver")]),
        "ollama": ("Local AI models", [("As usual", ""), ("Unload them (frees graphics memory)", "unload"),
                                       ("Keep them loaded", "keep")]),
        "docker": ("Docker containers", [("As usual", ""), ("Pause them", "pause"), ("Keep them running", "keep")]),
    }

    def __init__(self, parent, game):
        super().__init__(parent)
        self.game, self.gid = game, profile_id(game)
        self.setObjectName("root")
        self.setWindowTitle(f"{game['name']}: profile")
        self.setMinimumWidth(480)
        current = profiles.load().get(self.gid, {})
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(10)
        v.addWidget(label(game["name"], "title"))
        v.addWidget(label("While this game runs. Everything goes back when it stops.", "sub"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.combos = {}
        for row, (key, (title, opts)) in enumerate(self.CHOICES.items()):
            box = QComboBox()
            for text, value in opts:
                box.addItem(text, value)
            box.setCurrentIndex(max(0, box.findData(current.get(key, ""))))
            grid.addWidget(label(title, "sub", wrap=False), row, 0)
            grid.addWidget(box, row, 1)
            self.combos[key] = box
        v.addLayout(grid)
        self.dnd = QCheckBox("Do not disturb (no notifications while playing)")
        self.dnd.setChecked(bool(current.get("dnd")))
        v.addWidget(self.dnd)
        if game.get("source") == "Steam" and not sysinfo.DEMO:
            v.addWidget(label(self.steam_side(), "muted"))
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def steam_side(self):
        """The rest of what this game gets, set elsewhere: Game Doctor's fixes and Steam's launch options."""
        bits = []
        try:
            import gamedoctor
            fixes = [gamedoctor.describe_fix(e["fix"], self.gid)[0] for e in gamedoctor.applied(self.gid)]
            if fixes:
                bits.append("Game Doctor: " + ", ".join(fixes))
            import steamfiles
            opts = steamfiles.launch_options(self.gid)
            if opts:
                bits.append(f"Launch options: {opts}")
        except Exception:  # Steam's files are best effort here
            pass
        return "<br>".join(bits) if bits else "No Game Doctor fixes or launch options for this game."

    def save(self):
        if not sysinfo.DEMO:
            for key, box in self.combos.items():
                profiles.set_(self.gid, key, box.currentData(), self.game["name"])
            profiles.set_(self.gid, "dnd", self.dnd.isChecked(), self.game["name"])
        self.accept()


class FoldersDialog(QDialog):
    """The folders Games on my drives looks in: found on their own (a Games folder at the top of each drive), or the
    person's own list."""

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.setObjectName("root")
        self.setWindowTitle("Folders with games")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(10)
        v.addWidget(label("Folders with games", "title"))
        v.addWidget(label("Each folder inside these is one game. Without a list of your own, DecKoOS looks in the "
                          "Games folder at the top of every drive, and in ~/Games.", "sub"))
        self.own = bool(localgames.load().get("roots")) if not sysinfo.DEMO else False
        self.paths = [str(p) for p in (["/mnt/BIG/Games", "/mnt/SSD/Games"] if sysinfo.DEMO else localgames.roots())]
        self.box = QVBoxLayout()
        v.addLayout(self.box)
        v.addWidget(_row(button("Add a folder…", slot=self.add, icon="folder-plus"),
                         button("Find them for me", slot=self.auto, icon="search",
                                tip="Forget this list: look in every drive's Games folder")))
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.draw()

    def draw(self):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not self.paths:
            self.box.addWidget(label("No folders: games in folders won't be listed.", "muted"))
        for p in self.paths:
            self.box.addWidget(_row(label(p, wrap=False), button("", slot=lambda _=False, x=p: self.drop(x),
                                                                   icon="close", tip="Stop looking here")))

    def add(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "A folder with games in it", "/mnt")
        if d and d not in self.paths:
            self.paths.append(d)
            self.own = True
            self.draw()

    def drop(self, p):
        self.paths.remove(p)
        self.own = True
        self.draw()

    def auto(self):
        self.own = False
        self.paths = [] if sysinfo.DEMO else [str(p) for p in localgames.default_roots()]
        self.draw()

    def save(self):
        if not sysinfo.DEMO:
            localgames.set_roots(self.paths if self.own else [])
            self.page.reload()
        self.accept()


class LocalGameDialog(QDialog):
    """A game from a folder: what DecKoOS worked out about it, and the person's say on the parts it can't know."""

    def __init__(self, parent, game):
        super().__init__(parent)
        self.game, self.loc = game, game["local"]
        loc = self.loc
        self.setObjectName("root")
        self.setWindowTitle(f"{loc['name']}: details")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(10)
        v.addWidget(label(loc["name"], "title"))
        v.addWidget(label(loc["folder"], "muted"))
        how = ("Runs as it is (a Linux game)" if loc["runner"] == "native" else
               "Runs with Proton, in a Wine prefix of its own" if loc["exe"] else "Nothing here starts a game yet")
        facts = [how] + ([f"Made with {loc['engine']}"] if loc["engine"] else []) + \
            ([f"Uses {', '.join(loc['needs'])}"] if loc["needs"] else []) + \
            ([f"Steam knows it (id {loc['appid']}): Proton's fixes for it are used"] if loc["appid"] else
             ["Steam doesn't know it by this name: it runs without game-specific fixes"])
        for f in facts:
            v.addWidget(label("•  " + f, "sub"))
        for b in loc["blockers"]:
            v.addWidget(label(f"<span style='color:{S.WARNING}'>⚠</span>  {b}", "sub"))
        for n in loc["notes"]:
            v.addWidget(label("ⓘ  " + n, "sub"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.exe = QComboBox()
        for c in loc["candidates"] or [""]:
            self.exe.addItem(c or "(none found)", c)
        self.exe.setCurrentIndex(max(0, self.exe.findData(loc["exe"])))
        self.exe.setEnabled(len(loc["candidates"]) > 1)
        grid.addWidget(label("Starts with", "sub", wrap=False), 0, 0)
        grid.addWidget(self.exe, 0, 1)
        if not loc["sure"] and loc["exe"]:
            grid.addWidget(label("DecKoOS isn't sure which of these starts the game: pick one if Play doesn't work.",
                                 "muted"), 1, 1)
        self.name = QLineEdit(loc["name"])
        grid.addWidget(label("Name", "sub", wrap=False), 2, 0)
        grid.addWidget(self.name, 2, 1)
        v.addLayout(grid)
        v.addWidget(_row(button("Open folder", slot=lambda: QProcess.startDetached("xdg-open", [loc["folder"]]),
                                icon="folder"),
                         button("Add my games to Steam", slot=self.to_steam, icon="gaming",
                                tip="Every game from your drives, as non-Steam games, so they're in Gaming Mode too"),
                         *([button("Last run", slot=lambda: QProcess.startDetached("xdg-open", [str(log)]), icon="doc",
                                   tip="What the game printed the last time it ran")]
                           if (log := (None if sysinfo.DEMO else localgames.log_of(loc["name"]))) else []),
                         button("Profile", slot=lambda: ProfileDialog(self, game).exec(), icon="sliders",
                                tip="What this game gets while it runs"),
                         button("Hide", slot=self.hide_game, icon="close", tip="Leave this folder out of Games")))
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _pick(self, key, value):
        if not sysinfo.DEMO:
            sysinfo.Job(self.parent(), ["python3", str(LOCALGAMES), "pick", self.loc["folder"], key, value], lambda *_: None)

    def save(self):
        if self.exe.currentData() and self.exe.currentData() != self.loc["exe"]:
            self._pick("exe", self.exe.currentData())
        if self.name.text().strip() and self.name.text().strip() != self.loc["name"]:
            self._pick("name", self.name.text().strip())
        self.accept()

    def hide_game(self):
        self._pick("hidden", "1")
        self.accept()

    def to_steam(self):
        if sysinfo.DEMO:
            return
        hub = self.parent().window()

        def done(out, code):
            msg = out.strip() if code == 0 else "Close Steam first, then try again: it rewrites its library when it exits."
            if hasattr(hub, "toast"):
                hub.toast(msg, "ok" if code == 0 else "bad")
        sysinfo.Job(hub, ["python3", str(LOCALGAMES), "steam"], done)


class GamesPage(Page):
    title = "Games"
    subtitle = "Steam, Heroic, Lutris and the games on your drives in one place."

    def build(self):
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games")
        self.search.addAction(S.icon("search", S.SUBTEXT, 16), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self.layout_tiles)
        self.source = QComboBox()
        self.source.addItems(["All launchers", "Steam", "Epic", "GOG", "Lutris", LOCAL])
        self.source.currentIndexChanged.connect(self.layout_tiles)
        self.sort = QComboBox()
        self.sort.addItems(["Recently played", "Name", "Size"])
        self.sort.currentIndexChanged.connect(self.layout_tiles)
        for w in (self.search, self.source, self.sort):
            self.head_actions.addWidget(w)
        self.head_actions.addWidget(button("Game Doctor", slot=lambda: QProcess.startDetached("deckos-gamedoctor", []),
                                           icon="alert", tip="Why the last game that closed right after starting did"))
        self.head_actions.addWidget(button("", slot=lambda: FoldersDialog(self).exec(), icon="folder",
                                           tip="Which folders on your drives have games in them"))
        self.head_actions.addWidget(button("", slot=self.reload, icon="refresh", tip="Look for games again"))
        host = QWidget()
        self.grid = QGridLayout(host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.lay.addWidget(host)
        self.empty = Empty("gaming", "No games found", "Install games in Steam, Heroic or Lutris, or keep them in a "
                           "Games folder on a drive, and they show up here.",
                           button("Open Steam", "primary", lambda: QProcess.startDetached("steam", []), icon="play"))
        self.empty.hide()
        self.lay.addWidget(self.empty)
        self.games, self.tiles, self.tiers, self.loaded, self.cols = [], {}, self.load_tiers(), False, 0

    def refresh(self):
        if not self.loaded:
            self.reload()

    # ---- data

    def reload(self):
        self.loaded = True
        self.games = all_games()
        for t in self.tiles.values():
            t.deleteLater()
        self.tiles = {}
        self.layout_tiles()
        self.fetch_tiers()
        # Games in folders: the drives can be slow to read, so the scan runs as its own process
        sysinfo.Job(self, ["python3", str(LOCALGAMES), "scan"], self.got_local, demo=(json.dumps(DEMO_LOCAL), 0))

    def got_local(self, out, code):
        try:
            found = json.loads(out) if code == 0 else []
        except ValueError:
            found = []
        self.games = [g for g in self.games if g["source"] != LOCAL] + [local_game(g) for g in found]
        for key in [k for k in self.tiles if k[0] == LOCAL]:
            self.tiles.pop(key).deleteLater()
        self.layout_tiles()
        if sysinfo.DEMO:
            return
        # Steam ids (Proton's fixes, covers, ProtonDB) for games that have none yet, a few at a time
        for g in [g for g in self.games if g["source"] == LOCAL and not g["art"]][:20]:
            loc = g["local"]
            if loc["appid"] and loc["appid"] in self.tiers:
                continue
            sysinfo.Job(self, ["python3", str(LOCALGAMES), "look-up", loc["name"]],
                        lambda o, c, gm=g: self.got_lookup(gm, o if c == 0 else ""))

    def got_lookup(self, game, out):
        try:
            res = json.loads(out)
        except ValueError:
            return
        if res.get("appid") and not game["local"]["appid"]:
            game["local"]["appid"] = res["appid"]
        if res.get("art"):
            game["art"] = Path(res["art"])
        tile = self.tiles.pop((LOCAL, game["id"]), None)
        if tile:
            tile.deleteLater()
            self.layout_tiles()
        appid = game["local"]["appid"]
        if appid and appid not in self.tiers:
            sysinfo.Job(self, ["curl", "-fsS", "--max-time", "6",
                               f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"],
                        lambda o, c, a=appid: self.got_tier(a, o if c == 0 else ""))

    @staticmethod
    def load_tiers():
        if sysinfo.DEMO:
            return dict(DEMO_TIERS)
        try:
            data = json.loads(PROTONDB_CACHE.read_text())
            week = time.time() - 7 * 86400
            return {k: v["tier"] for k, v in data.items() if v.get("at", 0) > week}
        except (OSError, ValueError, AttributeError):
            return {}

    def fetch_tiers(self):
        """ProtonDB ratings for Steam games, a week's cache, a few lookups at a time in the background."""
        if sysinfo.DEMO:
            return
        todo = [g["id"] for g in self.games if g["source"] == "Steam" and g["id"] not in self.tiers][:40]
        for appid in todo:
            sysinfo.Job(self, ["curl", "-fsS", "--max-time", "6",
                               f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"],
                        lambda out, code, a=appid: self.got_tier(a, out if code == 0 else ""))

    def got_tier(self, appid, out):
        try:
            tier = json.loads(out).get("tier", "") if out else ""
        except ValueError:
            tier = ""
        if not tier:
            return
        self.tiers[appid] = tier
        try:
            data = json.loads(PROTONDB_CACHE.read_text()) if PROTONDB_CACHE.exists() else {}
            data[appid] = {"tier": tier, "at": time.time()}
            PROTONDB_CACHE.parent.mkdir(parents=True, exist_ok=True)
            PROTONDB_CACHE.write_text(json.dumps(data))
        except (OSError, ValueError):
            pass
        for (src, gid), tile in self.tiles.items():
            if (src == "Steam" and gid == appid) or (src == LOCAL and tile.game.get("local", {}).get("appid") == appid):
                tile.set_tier(tier)

    # ---- grid

    def shown(self):
        q = self.search.text().strip().lower()
        src = self.source.currentText()
        out = [g for g in self.games if (not q or q in g["name"].lower()) and (src == "All launchers" or g["source"] == src)]
        key = {"Recently played": lambda g: (-g["last"], g["name"].lower()), "Name": lambda g: g["name"].lower(),
               "Size": lambda g: -g["size"]}[self.sort.currentText()]
        return sorted(out, key=key)

    def columns(self):
        return max(1, (self.width() - 60 + 12) // (S.scaled(COVER_W + 20) + 12))  # 30px page margins, 12px gaps

    def layout_tiles(self, *_args):
        cols = self.cols = self.columns()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().hide()
        games = self.shown()
        for i, g in enumerate(games):
            key = (g["source"], g["id"])
            tile = self.tiles.get(key)
            if not tile:
                appid = g["id"] if g["source"] == "Steam" else g.get("local", {}).get("appid")
                tile = self.tiles[key] = GameTile(g, self.tiers.get(appid) if appid else None, self.play)
            self.grid.addWidget(tile, i // cols, i % cols)
            tile.show()
            tile.installEventFilter(self)
        self.order = [self.tiles[(g["source"], g["id"])] for g in games]
        self.empty.setVisible(not games)

    def eventFilter(self, obj, e):
        """Arrow keys (a controller's d-pad through Steam Input) move between games; Enter plays (or installs);
        the menu key or I opens its details or profile."""
        if e.type() != QEvent.KeyPress or obj not in getattr(self, "order", []):
            return super().eventFilter(obj, e)
        i, k = self.order.index(obj), e.key()
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -self.cols, Qt.Key_Down: self.cols}.get(k)
        if step is not None:
            j = i + step
            if 0 <= j < len(self.order):
                self.order[j].setFocus()
                self.scroll_to(self.order[j])
            elif k == Qt.Key_Up:
                self.search.setFocus()
            return True
        if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            obj.go()
            return True
        if k in (Qt.Key_Menu, Qt.Key_I):
            obj.more()
            return True
        return super().eventFilter(obj, e)

    def scroll_to(self, w):
        area = self.findChild(QScrollArea)
        if area:
            area.ensureWidgetVisible(w, 20, 40)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.loaded and self.columns() != self.cols:
            self.layout_tiles()

    def install(self, game, btn):
        loc = game["local"]
        if sysinfo.DEMO:
            self.hub.toast(f"Installing {loc['name']} (demo).", "info")
            return
        btn.setEnabled(False)
        btn.setText("Installing…")
        self.hub.toast(f"Installing {loc['name']}: its installer opens in a moment.", "info")

        def done(out, code):
            if code == 0:
                self.hub.toast(f"{loc['name']} is installed: press Play.", "ok")
            elif code == 3:
                self.hub.toast(f"The installer closed, but no game program turned up. Pick it in {loc['name']}'s "
                               "details.", "bad")
            else:
                self.hub.toast(f"Couldn't install {loc['name']}: {out.strip() or 'the installer failed'}", "bad")
            self.reload()
        sysinfo.Job(self, ["python3", str(LOCALGAMES), "install", loc["folder"]], done)

    def play(self, game):
        exe, args = game["launch"]
        if sysinfo.DEMO:
            self.hub.toast(f"Starting {game['name']} (demo).", "info")
            return
        if QProcess.startDetached(exe, args):
            self.hub.toast(f"Starting {game['name']}…", "info")
        else:
            self.hub.toast(f"Couldn't start {game['source']}.", "bad")
