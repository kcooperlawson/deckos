"""DecKoOS Welcome steps. Each builds once; `refresh()` runs whenever it's shown. Changes apply right
away, through `deckos` or Plasma's own tools as DecKoOS Hub does, and are noted for the summary
(`win.note`)."""
import shlex
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

import hub_style as S
import hub_system as sysinfo
import welcome_system as ws
from hub_pages import ACCENTS, RATES, RESOLUTIONS, AppearancePage
from hub_widgets import Card, Empty, Meter, RowItem, button, icon_label, label, restyle, row

preview_tile = AppearancePage.preview_tile  # the Hub's theme/wallpaper tile


def launch(cmd, *args):
    if not sysinfo.DEMO:
        QProcess.startDetached(cmd, list(args))


def settings(module):
    """A System Settings page (kcm_kscreen, kcm_bluetooth…)."""
    launch("systemsettings", module)


class Step(QWidget):
    """Kicker, title and subtitle above a centred, scrolling column of cards."""

    key, nav, title, subtitle = "", "", "", ""
    hint = ""     # footer text while the step is shown
    hub = ""      # where the same settings live in DecKoOS Hub, for the summary
    WIDTH = 860

    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        self.inner = QWidget()
        scroll.setWidget(self.inner)
        self.lay = QVBoxLayout(self.inner)
        self.lay.setContentsMargins(40, 28, 40, 28)
        self.lay.setSpacing(14)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.kicker = label("", "kicker")
        titles.addWidget(self.kicker)
        self.title_label = label(self.title, "title")
        titles.addWidget(self.title_label)
        self.subtitle_label = label(self.subtitle, "sub")
        titles.addWidget(self.subtitle_label)
        head.addLayout(titles, 1)
        self.head_actions = QHBoxLayout()
        self.head_actions.setSpacing(6)
        head.addLayout(self.head_actions)
        self.lay.addLayout(head)
        self.lay.addSpacing(4)
        self.build()
        self.lay.addStretch(1)

    def resizeEvent(self, e):
        # A readable column on wide windows: the margins grow, the cards don't.
        side = max(40, (self.width() - self.WIDTH) // 2)
        self.lay.setContentsMargins(side, 28, side, 28)
        super().resizeEvent(e)

    def build(self):
        pass

    def refresh(self):
        pass

    def note(self, thing, text, needs=None):
        self.win.note(f"{self.key}:{thing}", text, needs)

    @staticmethod
    def clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                Step.clear(item.layout())


class Choice(QFrame):
    """A selectable tile (the Hub's level-tile look): a marker, a title and a line of detail."""

    def __init__(self, marker, title, detail, slot):
        super().__init__()
        self.setObjectName("tile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(12)
        self.marker = QLabel(marker)
        self.marker.setFixedSize(30, 30)
        self.marker.setAlignment(Qt.AlignCenter)
        self.marker.setObjectName("cardTitle")
        h.addWidget(self.marker)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.head = label(title)
        v.addWidget(self.head)
        v.addWidget(label(detail, "sub"))
        h.addLayout(v, 1)
        self.slot = slot
        self.set_picked(False)

    def set_picked(self, on):
        self.setProperty("picked", on)
        restyle(self)
        self.marker.setStyleSheet(f"background: {S.P.accent if on else S.BORDER}; border-radius: 15px; color: white;")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.slot()


def state_row(icon, title, detail, state):
    """RowItem coloured by state: ok / warn / bad / off."""
    color = {"ok": S.SUCCESS, "warn": S.WARNING, "bad": S.DANGER}.get(state, S.SUBTEXT)
    return RowItem(icon, title, detail, color)


# ------------------------------------------------------------------ 1. welcome

class WelcomeStep(Step):
    key, nav = "welcome", "Welcome"
    title = "Welcome to DecKoOS"
    subtitle = "A few minutes to make it yours. Every step is optional, and changes apply as you make them."
    hint = "You can come back to any step from the list on the left."

    def build(self):
        hero = QFrame()
        hero.setObjectName("card")
        hero.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(hero)
        v.setContentsMargins(28, 26, 28, 24)
        v.setSpacing(10)
        mark = QSvgWidget(str(S.BRANDING / "wordmark.svg"))
        mark.setFixedSize(306, 80)  # the wordmark's own 804×210 proportions
        v.addWidget(mark)
        v.addSpacing(4)
        v.addWidget(label("DecKoOS is an Arch Linux desktop built for gaming and local AI. It runs KDE Plasma on fast "
                          "CachyOS packages, switches to a console-style Steam <b>Gaming Mode</b> when you want the "
                          "couch, and takes snapshots so a bad update is one reboot away from undone. Your Windows "
                          "drives stay as they are, readable and writable.", "sub"))
        facts = [self.win.gpu.name, sysinfo.cpu_name(), sysinfo.deckos_version()]
        v.addWidget(label("  ·  ".join(f for f in facts if f), "muted"))
        self.lay.addWidget(hero)

        self.lay.addWidget(label("A QUICK TOUR", "kicker"))
        grid = QGridLayout()
        grid.setSpacing(10)
        gaming = sysinfo.installed("gamescope-session-plus")
        for i, (ic, title, text, action) in enumerate((
                ("system", "DecKoOS Hub",
                 "Your system at a glance: live stats, the display fix, drives, updates, snapshots, the firewall "
                 "and the look. It's in the panel.", button("Open the Hub", slot=self.win.open_hub, icon="external")),
                ("store", "DecKoOS Store",
                 "Apps from Arch, CachyOS, Flathub and the AUR in one place: search, click Install, done.",
                 button("Open the Store", slot=lambda: launch("deckos-store"), icon="external")),
                ("gaming", "Gaming Mode",
                 "Steam's Big Picture full screen, like a Steam Deck. Start it from the panel or the login screen; "
                 "come back with Steam › Power › Switch to Desktop." if gaming else
                 "Steam's Big Picture full screen, like a Steam Deck. It comes with the Gaming software, which the "
                 "Software step can add.", None))):
            card = Card(None, None)
            head = QHBoxLayout()
            head.setSpacing(10)
            head.addWidget(icon_label(ic, S.P.accent, 22))
            head.addWidget(label(title, "cardTitle", wrap=False), 1)
            card.body.addLayout(head)
            text = label(text, "sub")
            text.setAlignment(Qt.AlignTop)
            card.body.addWidget(text, 1)
            if action:
                card.body.addWidget(row(action))
            grid.addWidget(card, 0, i)
            grid.setColumnStretch(i, 1)
        self.lay.addLayout(grid)

        how = Card("How this works")
        for ic, text in (("check", "Changes happen as you make them. There's nothing to save at the end."),
                         ("chevron", "<b>Skip this step</b> moves on and leaves things as they are."),
                         ("info", "Anything that needs your password asks for it, and DecKoOS Hub has all of it "
                                  "again later.")):
            h = QHBoxLayout()
            h.setSpacing(10)
            h.addWidget(icon_label(ic, S.SUBTEXT, 16), 0, Qt.AlignTop)
            h.addWidget(label(text, "sub"), 1)
            how.body.addLayout(h)
        self.lay.addWidget(how)


# ------------------------------------------------------------------ 2. look

def scheme_preview(dark, w=176, h=99):
    """A tiny desktop in the scheme's colours: wallpaper, a window with an accent button, the panel."""
    pm = QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    bg, win, line, text, panel = (("#0B0D11", "#171A21", "#262B36", "#5A6172", "#0F1115") if dark else
                                  ("#D9DEE8", "#FCFCFC", "#D5D9E0", "#B8BEC9", "#EFF0F1"))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(bg))
    p.drawRoundedRect(QRectF(0, 0, w, h), 6, 6)
    p.setBrush(QColor(win))
    p.setPen(QColor(line))
    p.drawRoundedRect(QRectF(22, 12, w - 44, h - 36), 5, 5)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(text))
    for i, width in enumerate((70, 92, 54)):
        p.drawRoundedRect(QRectF(32, 24 + i * 10, width, 4), 2, 2)
    p.setBrush(QColor(S.P.accent))
    p.drawRoundedRect(QRectF(w - 70, h - 42, 36, 11), 4, 4)
    p.setBrush(QColor(panel))
    p.drawRoundedRect(QRectF(0, h - 14, w, 14), 0, 0)
    p.setBrush(QColor(S.P.accent))
    p.drawEllipse(QRectF(6, h - 11, 8, 8))
    p.end()
    return pm


class LookStep(Step):
    key, nav, hub = "look", "Look", "Appearance"
    title = "Make it look like you"
    subtitle = "Theme, light or dark, accent colour, wallpaper and desktop style."
    hint = "Everything here changes on the spot; pick again to change it back."

    def build(self):
        self.look = sysinfo.current_look()
        themes = Card("Theme", "Global theme", "appearance")
        themes.body.addWidget(label("Colours, wallpaper and the desktop's look in one go.", "sub"))
        self.theme_grid = QGridLayout()
        self.theme_grid.setSpacing(10)
        themes.body.addLayout(self.theme_grid)
        self.lay.addWidget(themes)

        dark, light = ws.color_schemes()
        self.scheme = ws.current_scheme()
        self.schemes = [(dark, "Dark", "DecKoOS slate")] + ([(light, "Light", "Breeze Light" if light == "BreezeLight"
                                                             else "DecKoOS light")] if light else [])
        if len(self.schemes) > 1:  # only offered when a light scheme is installed
            mode = Card("Colours", "Light or dark", "sliders")
            note = "DecKoOS's own apps (Hub, Store, this window) stay dark." if light == "BreezeLight" else ""
            if note:
                mode.body.addWidget(label(note, "muted"))
            self.mode_grid = QHBoxLayout()
            self.mode_grid.setSpacing(10)
            mode.body.addLayout(self.mode_grid)
            self.lay.addWidget(mode)

        accent = Card("Accent colour", "Buttons, highlights and selections", "drop")
        self.swatches = QButtonGroup(self)
        sw_row = QHBoxLayout()
        sw_row.setSpacing(10)
        for name, color in ACCENTS:
            b = QPushButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setFixedSize(30, 30)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton#swatch {{ background: {color}; }}")
            b.clicked.connect(lambda _c, c=color, n=name: self.set_accent(c, n))
            self.swatches.addButton(b)
            sw_row.addWidget(b)
            b.setChecked(color.lower() == S.P.accent.lower())
        sw_row.addStretch(1)
        accent.body.addLayout(sw_row)
        self.lay.addWidget(accent)

        walls = Card("Wallpaper", "Desktop background", "image")
        self.wall_grid = QGridLayout()
        self.wall_grid.setSpacing(10)
        walls.body.addLayout(self.wall_grid)
        walls.body.addWidget(row(button("Choose an image…", slot=self.pick_wallpaper, icon="folder")))
        self.lay.addWidget(walls)

        style = Card("Desktop style", "Panel, menus and icons", "display")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.plasma = QComboBox()
        self.plasma.addItem("DecKoOS", "deckos")
        self.plasma.addItem("Breeze", "default")
        self.plasma.setCurrentIndex(max(0, self.plasma.findData(sysinfo.current_plasma_style())))
        self.plasma.currentIndexChanged.connect(lambda _i: self.apply(
            ["plasma-apply-desktoptheme", self.plasma.currentData()], "style", f"Plasma style: {self.plasma.currentText()}"))
        self.icons = QComboBox()
        for name, theme in (("DecKoOS", "DeckOS"), ("Papirus Dark", "Papirus-Dark"), ("Breeze Dark", "breeze-dark")):
            self.icons.addItem(name, theme)
        self.icons.setCurrentIndex(max(0, self.icons.findData(sysinfo.current_icons())))
        self.icons.currentIndexChanged.connect(lambda _i: self.apply(
            ["/usr/lib/plasma-changeicons", self.icons.currentData()], "icons", f"Icons: {self.icons.currentText()}"))
        grid.addWidget(label("Plasma style", "sub", wrap=False), 0, 0)
        grid.addWidget(self.plasma, 0, 1)
        grid.addWidget(label("Icons", "sub", wrap=False), 1, 0)
        grid.addWidget(self.icons, 1, 1)
        grid.setColumnStretch(2, 1)
        style.body.addLayout(grid)
        style.body.addWidget(label("DecKoOS icons are Papirus with folders in the DecKoOS blue.", "muted"))
        self.lay.addWidget(style)

    def apply(self, cmd, thing, text):
        if sysinfo.DEMO:
            ok = True
        else:
            ok = QProcess.startDetached(cmd[0], cmd[1:])
        if ok:
            self.note(thing, text)
        self.win.toast(text if ok else f"Couldn't run {Path(cmd[0]).name}.", "ok" if ok else "warn")

    def set_theme(self, tid, name):
        self.look = tid
        self.apply(["deckos", "theme", "apply", tid], "theme", f"Theme: {name}")
        self.refresh()

    def set_scheme(self, scheme, name):
        self.scheme = scheme
        self.apply(["plasma-apply-colorscheme", scheme], "colours", f"Colours: {name}")
        self.refresh()

    def set_accent(self, color, name):
        self.apply(["deckos", "accent", "apply", color], "accent", f"Accent colour: {name}")
        self.win.set_accent(color)
        self.refresh()  # the light/dark previews use the accent

    def refresh(self):
        self.clear(self.theme_grid)
        for i, (tid, name, desc, preview) in enumerate(sysinfo.look_and_feels()):
            self.theme_grid.addWidget(preview_tile(preview, name, desc, tid == self.look,
                                                   lambda t=tid, n=name: self.set_theme(t, n)), 0, i)
        self.theme_grid.setColumnStretch(4, 1)
        if len(self.schemes) > 1:
            self.clear(self.mode_grid)
            for scheme, name, desc in self.schemes:
                tile = preview_tile(None, name, desc, scheme == self.scheme,
                                    lambda s=scheme, n=name: self.set_scheme(s, n), small=True)
                tile.findChild(QLabel).setPixmap(scheme_preview(name == "Dark"))
                self.mode_grid.addWidget(tile)
            self.mode_grid.addStretch(1)
        self.clear(self.wall_grid)
        for i, (path, name, preview) in enumerate(sysinfo.wallpapers()[:4]):
            self.wall_grid.addWidget(preview_tile(preview, name, "", False, lambda p=path, n=name: self.apply(
                ["deckos", "wallpaper", str(p)], "wallpaper", f"Wallpaper: {n}"), small=True), 0, i)
        self.wall_grid.setColumnStretch(4, 1)

    def pick_wallpaper(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a wallpaper", str(Path.home() / "Pictures"),
                                              "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.apply(["deckos", "wallpaper", path], "wallpaper", f"Wallpaper: {Path(path).name}")


# ------------------------------------------------------------------ 3. display

class DisplayStep(Step):
    key, nav, hub = "display", "Display", "Display"
    title = "Your screens"
    subtitle = "Sharp text at the right size, and screens that stay on."
    hint = "Screen scale changes right away. The blackout fix takes effect after a restart."

    def build(self):
        screens = Card("Screens", "Size of text and windows", "display")
        screens.body.addWidget(label("Bigger scale makes everything larger. 4K screens usually look best at 150%, "
                                     "1440p at 100–125%.", "sub"))
        self.screen_box = QVBoxLayout()
        self.screen_box.setSpacing(6)
        screens.body.addLayout(self.screen_box)
        screens.body.addWidget(row(button("Arrange screens…", slot=lambda: settings("kcm_kscreen"), icon="external",
                                          tip="Position, resolution, refresh rate and which screen is main")))
        self.lay.addWidget(screens)

        fix = Card("Blackout fix", "Screens that blink black for a second", "alert")
        self.levels = []
        if not self.win.gpu.amd:
            fix.body.addWidget(label(f"This fix is for AMD Radeon cards. Your {self.win.gpu.name} doesn't need it.",
                                     "sub"))
            self.lay.addWidget(fix)
            return
        self.recommended, why = sysinfo.display_recommend()
        fix.body.addWidget(label("Some Radeon cards drop the picture for a second or two when the memory clock "
                                 "switches, mostly with high-refresh or several screens. Each level removes another "
                                 "cause, at the cost of a little idle power. Start with the recommended one and step "
                                 "up only if a screen still blinks.", "sub"))
        if why:
            fix.body.addWidget(label(f"Recommended for your setup: level {self.recommended} ({why}).", "muted"))
        for i, (name, desc, cost) in enumerate(sysinfo.LEVELS):
            title = f"<b>{name}</b>"
            if i == self.recommended:
                title += f" &nbsp;<span style='color:{S.P.accent}'>recommended</span>"
            tile = Choice(str(i), title, f"{desc} <span style='color:{S.MUTED}'>Cost: {cost}.</span>",
                          lambda n=i: self.pick(n))
            fix.body.addWidget(tile)
            self.levels.append(tile)
        self.apply_btn = button("Use this level", "primary", self.apply, icon="check")
        self.level_note = label("", "muted", wrap=False)
        fix.body.addWidget(row(self.apply_btn, self.level_note, spacing=12))
        self.lay.addWidget(fix)
        self.current = sysinfo.display_level()
        self.pick(self.recommended)  # preselected; applying still asks for the password

    def pick(self, n):
        self.picked = n
        for i, t in enumerate(self.levels):
            t.set_picked(i == n)
        self.apply_btn.setEnabled(n != self.current)
        self.level_note.setText("You're on this level now." if n == self.current else
                                f"You're on level {self.current} now. Needs your password and a restart.")

    def apply(self):
        n = self.picked

        def done(ok):
            if ok:
                self.current = n
                self.note("level", f"Display fix: level {n} ({sysinfo.LEVELS[n][0]})", "reboot")
                self.win.toast(f"Display fix level {n} saved. It takes effect after a restart.", "ok")
                self.pick(n)
            else:
                self.win.toast("Display fix not changed.", "warn")
        self.win.privileged(["display", "set", str(n)], done)

    def refresh(self):
        self.clear(self.screen_box)
        found = ws.screens()
        if not found:
            self.screen_box.addWidget(label("Couldn't read your screens (kscreen-doctor). System Settings › Display "
                                            "has the same settings.", "muted"))
        for s in found:
            combo = QComboBox()
            scales = ws.SCALES if s["scale"] in ws.SCALES else sorted([*ws.SCALES, s["scale"]])
            for sc in scales:
                combo.addItem(f"{sc * 100:g}%", sc)
            combo.setCurrentIndex(scales.index(s["scale"]))
            combo.currentIndexChanged.connect(lambda _i, c=combo, out=s: self.set_scale(out, c.currentData()))
            mode = f"{s['width']}×{s['height']}" + (f" at {s['refresh']} Hz" if s["refresh"] else "")
            detail = f"{s['name']}  ·  {mode}" + ("  ·  main screen" if s["primary"] and len(found) > 1 else "")
            self.screen_box.addWidget(RowItem("display", s["label"], detail,
                                              right=[label("Scale", "sub", wrap=False), combo]))

    def set_scale(self, out, scale):
        ok = sysinfo.DEMO or QProcess.startDetached("kscreen-doctor", [f"output.{out['name']}.scale.{scale:g}"])
        if ok:
            self.note(f"scale-{out['name']}", f"{out['label']}: scale {scale * 100:g}%")
        self.win.toast(f"{out['label']} is now at {scale * 100:g}%." if ok else "Couldn't run kscreen-doctor.",
                       "ok" if ok else "warn")


# ------------------------------------------------------------------ 4. software

# Popular apps: name, what it is, theme icon names to try, DecKoOS icon when there's none, source, package.
POPULAR = [
    ("Spotify", "Music and podcasts", ("com.spotify.Client", "spotify-client", "spotify"), "music",
     "flathub", "com.spotify.Client"),
    ("Discord", "Voice, video and text chat", ("discord", "com.discordapp.Discord"), "globe", "repo", "discord"),
    ("OBS Studio", "Record and stream", ("com.obsproject.Studio", "obs"), "play", "repo", "obs-studio"),
    ("VS Code", "Code editor from Microsoft", ("visual-studio-code", "vscode", "code"), "code",
     "aur", "visual-studio-code-bin"),
    ("VLC", "Plays every video and audio file", ("vlc",), "play", "repo", "vlc"),
    ("Obsidian", "Notes in plain Markdown files", ("md.obsidian.Obsidian", "obsidian"), "doc",
     "flathub", "md.obsidian.Obsidian"),
    ("GIMP", "Photo editing", ("gimp",), "image", "repo", "gimp"),
    ("LibreOffice", "Documents, spreadsheets, slides", ("libreoffice-startcenter", "libreoffice-main"), "doc",
     "repo", "libreoffice-fresh"),
]
SOURCE_LABELS = {"repo": "Arch", "flathub": "Flathub", "aur": "AUR"}


class _Loaded(QObject):
    done = Signal()


class SoftwareStep(Step):
    key, nav, hub = "software", "Software", "System"
    title = "Get your software"
    subtitle = "Add what you skipped at install, and the apps most people want first."
    hint = "Installs keep going while you carry on with the other steps."

    def build(self):
        self.head_actions.addWidget(button("Open DecKoOS Store", slot=lambda: launch("deckos-store"), icon="store",
                                           tip="Every app from Arch, CachyOS, Flathub and the AUR"))
        groups = Card("Software groups", "The installer's optional extras", "package")
        groups.body.addWidget(label("Each opens a terminal that asks for your password, then installs everything in "
                                    "the group. Log out and back in afterwards.", "sub"))
        self.group_box = QVBoxLayout()
        self.group_box.setSpacing(6)
        groups.body.addLayout(self.group_box)
        self.lay.addWidget(groups)

        apps = Card("Popular apps", "One click each", "store")
        self.app_grid = QGridLayout()
        self.app_grid.setSpacing(8)
        apps.body.addLayout(self.app_grid)
        apps.body.addWidget(label("Arch apps ask for your password; Flathub apps don't. Everything else is in the "
                                  "DecKoOS Store.", "muted"))
        self.lay.addWidget(apps)

        from store_catalog import Installed  # the Store's view of what's installed (pacman, AUR, Flatpak)
        self.installed, self.loaded = Installed(), False
        self.signal = _Loaded()
        self.signal.done.connect(self.paint_apps)
        self.app_rows = {}
        for i, (name, what, icons, fallback, source, pkg) in enumerate(POPULAR):
            theme = next((QIcon.fromTheme(n) for n in icons if QIcon.hasThemeIcon(n)), None)
            pm = theme.pixmap(28, 28) if theme else S.pixmap(fallback, S.SUBTEXT, 22)
            r = RowItem(None, f"<b>{name}</b> &nbsp;<span style='color:{S.MUTED}'>{SOURCE_LABELS[source]}</span>",
                        what)
            ic = QLabel()
            ic.setPixmap(pm)
            ic.setFixedSize(28, 28)
            ic.setAlignment(Qt.AlignCenter)
            r.layout().insertWidget(0, ic)
            right = QVBoxLayout()
            right.setSpacing(4)
            btn = button("Install", slot=lambda _c=False, k=i: self.install(k), icon="download")
            done = label(f"<span style='color:{S.SUCCESS}'>Installed</span>", wrap=False)
            meter = Meter(4)
            meter.setFixedWidth(96)
            for w in (btn, done, meter):
                w.hide()
                right.addWidget(w, 0, Qt.AlignRight)
            r.layout().addLayout(right)
            self.app_rows[f"welcome-{pkg}"] = (btn, done, meter)
            self.app_grid.addWidget(r, i // 2, i % 2)
        self.app_grid.setColumnStretch(0, 1)
        self.app_grid.setColumnStretch(1, 1)
        self.win.apps.changed.connect(self.job_changed)
        self.win.apps.done.connect(self.job_done)

    def refresh(self):
        self.clear(self.group_box)
        for key, title, desc, ic, cmd in sysinfo.GROUPS:
            ok = sysinfo.installed(cmd)
            started = f"software:group-{key}" in self.win.changes
            if ok:
                right = [label(f"<span style='color:{S.SUCCESS}'>Installed</span>", wrap=False)]
            elif started:
                right = [label("Installing in a terminal", "muted", wrap=False)]
            else:
                right = [button("Add", slot=lambda _c=False, k=key, t=title: (self.win.add_group(k, t), self.refresh()),
                                icon="plus")]
            self.group_box.addWidget(RowItem(ic, title, desc, S.SUCCESS if ok else S.SUBTEXT, right))
        if not self.loaded:
            self.reload()

    def reload(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        self.installed.refresh()
        self.loaded = True
        self.signal.done.emit()

    def paint_apps(self):
        for _n, _w, _i, _f, source, pkg in POPULAR:
            btn, done, meter = self.app_rows[f"welcome-{pkg}"]
            job = self.win.apps.by_key.get(f"welcome-{pkg}")
            busy, have = job is not None and job.ok is None, self.installed.has(source, pkg)
            btn.setVisible(not have)
            btn.setEnabled(self.loaded and not busy)
            btn.setText(job.text.replace("&", "&&") if busy else "Try again" if job and not job.ok else "Install")
            done.setVisible(have and not busy)
            meter.setVisible(busy)
            meter.set(job.progress if busy else 0)

    def install(self, i):
        name, _w, _i, _f, source, pkg = POPULAR[i]
        if source == "flathub" and not self.installed.flathub_ready and not self.win.apps.by_key.get("flathub-setup"):
            self.win.apps.add("flathub-setup", "setup-flathub", "flathub", "", "Flathub")
        self.win.apps.add(f"welcome-{pkg}", "install", source, pkg, name)
        self.note(f"app-{pkg}", f"Installing {name}…")
        self.paint_apps()

    def job_changed(self, key):
        if key in self.app_rows:
            self.paint_apps()

    def job_done(self, key, ok, msg):
        job = self.win.apps.by_key[key]
        if key == "flathub-setup":
            self.installed.flathub_ready = ok
        elif key in self.app_rows:
            if ok:
                if sysinfo.DEMO:
                    self.installed.demo_apply("install", job.source, job.ident)
                else:
                    self.reload()
            self.note(f"app-{job.ident}", f"{job.title} installed" if ok else f"{job.title} didn't install: {msg}")
            self.paint_apps()
        self.win.toast(msg, "ok" if ok else "bad", 6000)


# ------------------------------------------------------------------ 5. gaming

class GamingStep(Step):
    key, nav, hub = "gaming", "Gaming", "Gaming"
    title = "Ready to play"
    subtitle = "Gaming Mode's screen, Steam games on Windows drives, and controllers."
    hint = "Gaming Mode settings apply the next time you switch to it."

    def build(self):
        if not sysinfo.installed("gamescope-session-plus"):
            card = Card()
            card.body.addWidget(Empty("gaming", "Gaming isn't installed",
                                      "Steam with Gaming Mode, Proton, Lutris, Heroic, MangoHud, Discord, OBS and the "
                                      "Xbox Wireless Adapter driver come as one group.",
                                      button("Add Gaming", "primary", lambda: self.win.add_group("gaming", "Gaming"),
                                             icon="plus")))
            self.lay.addWidget(card)
            self.res = None
            return
        conf = ws.gaming_conf()
        mode = Card("Gaming Mode", "Screen settings", "play")
        mode.body.addWidget(label("Gaming Mode runs Steam full screen at this resolution. Pick your main screen's.",
                                  "sub"))
        self.match_box = QHBoxLayout()
        self.match_box.setSpacing(10)
        mode.body.addLayout(self.match_box)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.res = QComboBox()
        cur = f"{conf.get('SCREEN_WIDTH', '3840')}x{conf.get('SCREEN_HEIGHT', '2160')}"
        self.res.addItems(RESOLUTIONS if cur in RESOLUTIONS else [cur, *RESOLUTIONS])
        self.res.setCurrentText(cur)
        self.rate = QComboBox()
        self.rate.addItems(RATES)
        self.rate.setCurrentText((conf.get("CUSTOM_REFRESH_RATES") or "144").split(",")[-1])
        self.res.currentTextChanged.connect(self.save_screen)
        self.rate.currentTextChanged.connect(self.save_screen)
        grid.addWidget(label("Resolution", "sub", wrap=False), 0, 0)
        grid.addWidget(self.res, 0, 1)
        grid.addWidget(label("Refresh rate", "sub", wrap=False), 1, 0)
        grid.addWidget(self.rate, 1, 1)
        grid.setColumnStretch(2, 1)
        mode.body.addLayout(grid)
        self.vrr = QCheckBox("Variable refresh rate (FreeSync, G-Sync)")
        self.vrr.setChecked(conf.get("ADAPTIVE_SYNC") == "1")
        self.vrr.toggled.connect(lambda on: self.save("ADAPTIVE_SYNC", "1" if on else "0", "vrr",
                                                      f"Gaming Mode VRR {'on' if on else 'off'}"))
        self.hdr = QCheckBox("HDR (turn it on in the monitor's menu too)")
        self.hdr.setChecked(conf.get("ENABLE_GAMESCOPE_HDR") == "1")
        self.hdr.toggled.connect(lambda on: self.save("ENABLE_GAMESCOPE_HDR", "1" if on else "0", "hdr",
                                                      f"Gaming Mode HDR {'on' if on else 'off'}"))
        mode.body.addWidget(self.vrr)
        mode.body.addWidget(self.hdr)
        mode.body.addWidget(label("If a screen flickers with VRR on, turn it off: some monitors blink with it.",
                                  "muted"))
        self.lay.addWidget(mode)

        steam = Card("Steam on Windows drives", "Play the games you already have", "drives")
        steam.body.addWidget(label("Steam can use a library on a Windows drive, but Windows games need their Proton "
                                   "settings on a Linux drive. In Steam, add the library folder (Settings › Storage), "
                                   "close Steam, then run this once. The games stay where they are.", "sub"))
        self.steam_box = QHBoxLayout()
        steam.body.addLayout(self.steam_box)
        self.lay.addWidget(steam)

        pads = Card("Controllers", "Plug in and play", "gaming")
        pads.body.addWidget(label("Xbox, PlayStation and Switch Pro controllers work over USB and Bluetooth; Steam "
                                  "Input handles the buttons in games.", "sub"))
        self.pad_box = QVBoxLayout()
        self.pad_box.setSpacing(6)
        pads.body.addLayout(self.pad_box)
        pads.body.addWidget(row(button("Pair a Bluetooth controller…", slot=lambda: settings("kcm_bluetooth"),
                                       icon="external")))
        self.lay.addWidget(pads)

    def refresh(self):
        if self.res is None:
            return
        self.clear(self.match_box)
        main = next(iter(ws.screens()), None)
        if main and main["width"]:
            res, rate = f"{main['width']}x{main['height']}", main["refresh"]
            best = str(max((int(r) for r in RATES if int(r) <= rate), default=60))
            same = self.res.currentText() == res and self.rate.currentText() == best
            self.match_box.addWidget(icon_label("display", S.SUCCESS if same else S.P.accent, 18))
            self.match_box.addWidget(label(f"Your main screen: <b>{main['label']}</b>, {main['width']}×{main['height']} "
                                           f"at {rate} Hz" + (" (matches)" if same else ""), "sub"), 1)
            if not same:
                self.match_box.addWidget(button("Use my screen", "primary", lambda: self.match(res, best),
                                                icon="check"))
        self.clear(self.steam_box)
        ntfs = sysinfo.drives()
        b = button("Fix Steam libraries", slot=self.steam_ntfs, icon="terminal")
        b.setEnabled(bool(ntfs))
        self.steam_box.addWidget(b)
        self.steam_box.addWidget(label(f"{len(ntfs)} Windows drive{'s' if len(ntfs) != 1 else ''} mounted." if ntfs
                                       else "No Windows drives are mounted.", "muted", wrap=False))
        self.steam_box.addStretch(1)

        self.clear(self.pad_box)
        installed, loaded, plugged = ws.xone()
        if not installed:
            self.pad_box.addWidget(state_row("alert", "Xbox Wireless Adapter: driver missing",
                                             "The USB dongle needs xone, part of the Gaming group "
                                             "(Software step › Gaming).", "warn"))
        elif plugged:
            self.pad_box.addWidget(state_row("check", "Xbox Wireless Adapter: plugged in and ready",
                                             "Hold the pair button on the adapter, then on the controller.", "ok"))
        else:
            self.pad_box.addWidget(state_row("check", "Xbox Wireless Adapter: driver ready" +
                                             ("" if loaded else " (loads when you plug it in)"),
                                             "Plug in the USB adapter, press its pair button, then the "
                                             "controller's.", "ok"))

    def match(self, res, rate):
        for combo, value in ((self.res, res), (self.rate, rate)):
            combo.blockSignals(True)
            if combo.findText(value) < 0:
                combo.insertItem(0, value)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        self.save_screen()
        self.refresh()

    def save(self, key, value, thing, text):
        self.win.write_gaming({key: value})
        self.note(thing, text)
        self.win.toast("Saved. Takes effect next time you enter Gaming Mode.", "ok")

    def save_screen(self):
        w, _, h = self.res.currentText().partition("x")
        top = int(self.rate.currentText())
        self.win.write_gaming({"SCREEN_WIDTH": w, "SCREEN_HEIGHT": h,
                               "CUSTOM_REFRESH_RATES": ",".join(r for r in RATES if int(r) <= top)})
        self.note("screen", f"Gaming Mode: {w}×{h} at up to {top} Hz")
        self.win.toast(f"Gaming Mode will use {w}×{h} at up to {top} Hz.", "ok")

    def steam_ntfs(self):
        self.win.terminal("deckos steam-ntfs")
        self.note("steam-ntfs", "Moved Proton settings off Windows drives (deckos steam-ntfs)")


# ------------------------------------------------------------------ 6. your files

class FilesStep(Step):
    key, nav, hub = "files", "Your files", "System"
    title = "Keep your files safe"
    subtitle = "Snapshots to undo mistakes, a backup on another drive, and your Windows drives."
    hint = "Snapshots and backups can be set up later in DecKoOS Hub › System."

    def build(self):
        snaps = Card("Snapshots", "Undo a deleted or broken file", "snapshot")
        snaps.body.addWidget(label("Hourly snapshots of your home folder, kept for a couple of weeks. They take little "
                                   "space and bring back a file from earlier today or last week.", "sub"))
        self.snap_box = QVBoxLayout()
        self.snap_box.setSpacing(6)
        snaps.body.addLayout(self.snap_box)
        self.lay.addWidget(snaps)

        backup = Card("Backup", "A copy on another drive", "download")
        backup.body.addWidget(label("Snapshots live on the same disk. A backup on another drive (a Windows drive is "
                                    "fine) survives that disk failing. Caches and Steam games are left out; the drive "
                                    "is remembered for next time.", "sub"))
        self.backup_box = QVBoxLayout()
        self.backup_box.setSpacing(6)
        backup.body.addLayout(self.backup_box)
        self.lay.addWidget(backup)

        drives = Card("Windows drives", "Mounted as they are, nothing reformatted", "drives")
        drives.actions.addWidget(button("Rescan", slot=self.rescan, icon="refresh", tip="Adds new NTFS drives"))
        drives.actions.addWidget(button("Open in Files", slot=lambda: launch("dolphin", "/mnt"), icon="folder"))
        drives.actions.addWidget(button("Move in from Windows", slot=lambda: launch("deckos-movein"), icon="arrow-right",
                                        tip="Folders, wallpaper, browser, Steam games and apps from Windows"))
        self.drive_box = QVBoxLayout()
        self.drive_box.setSpacing(6)
        drives.body.addLayout(self.drive_box)
        self.lay.addWidget(drives)

    def refresh(self):
        self.clear(self.snap_box)
        if sysinfo.home_snapshots_on():
            self.snap_box.addWidget(state_row("check", "Your home folder has hourly snapshots",
                                              "Browse them in DecKoOS Hub › System, or /home/.snapshots.", "ok"))
        else:
            self.snap_box.addWidget(state_row("alert", "No snapshots of your files yet",
                                              "System snapshots cover updates, not /home.", "warn"))
            self.snap_box.addWidget(row(button("Turn on home snapshots", "primary", self.enable_home,
                                               icon="snapshot")))
        self.clear(self.backup_box)
        dest, last = sysinfo.backup_info()
        if dest:
            self.backup_box.addWidget(state_row("drives", f"Backing up to {dest}", f"Last backup: {last or 'never'}",
                                                "ok" if last else "info"))
            self.backup_box.addWidget(row(button("Back up now", slot=lambda: self.backup(dest), icon="download"),
                                          button("Change drive…", slot=self.pick_backup, icon="drives")))
        else:
            self.backup_box.addWidget(row(button("Back up to…", "primary", self.pick_backup, icon="download")))
        self.clear(self.drive_box)
        ds = sysinfo.drives()
        if not ds:
            self.drive_box.addWidget(label("No Windows drives are mounted. Plug one in or connect it, then Rescan.",
                                           "muted"))
        for mount, used, total, ro, fs in ds:
            right = label(f"<span style='color:{S.WARNING}'>read-only</span>" if ro else
                          f"<span style='color:{S.SUBTEXT}'>{sysinfo.size(used)} of {sysinfo.size(total)}</span>",
                          wrap=False)
            self.drive_box.addWidget(RowItem("drives", mount, fs, S.WARNING if ro else S.SUBTEXT, [right]))
        if any(d[3] for d in ds):
            self.drive_box.addWidget(label("A read-only drive usually means Windows Fast Startup is on. In Windows, "
                                           "open Terminal as administrator, run <b>powercfg /h off</b> and shut down "
                                           "normally.", "sub"))
            self.drive_box.addWidget(row(button("Diagnose", slot=lambda: self.win.terminal("deckos drives doctor"),
                                                icon="info")))

    def enable_home(self):
        def done(ok):
            if ok:
                self.note("home", "Hourly snapshots of your home folder: on")
            self.win.data.invalidate()
            self.win.toast("Home snapshots are on." if ok else "Home snapshots not changed.", "ok" if ok else "warn")
            self.refresh()
        self.win.privileged(["home", "enable"], done)

    def pick_backup(self):
        dest = QFileDialog.getExistingDirectory(self, "Back up your files to…", "/mnt" if Path("/mnt").is_dir() else "")
        if dest:
            self.backup(dest)

    def backup(self, dest):
        self.win.terminal(f"deckos backup {shlex.quote(dest)}")
        self.note("backup", f"Backing up your home folder to {dest}")
        self.win.toast("Backing up in a terminal.", "info")

    def rescan(self):
        self.win.privileged(["drives", "rescan"], lambda ok: (self.refresh(), self.win.toast(
            "Drives rescanned." if ok else "Rescan cancelled.", "ok" if ok else "warn")))


# ------------------------------------------------------------------ 7. privacy and updates

class UpdatesStep(Step):
    key, nav, hub = "updates", "Privacy & updates", "System"
    title = "Privacy and updates"
    subtitle = "What DecKoOS does and doesn't send, how it stays current, and the firewall."
    hint = "A snapshot is taken before every update, so a bad one can be rolled back from the boot menu."

    def build(self):
        up = Card("Updates", "Arch, CachyOS, DecKoOS and Flatpak apps", "update")
        self.channel = label("", "sub")
        up.body.addWidget(self.channel)
        self.up_row = QVBoxLayout()
        up.body.addLayout(self.up_row)
        self.check_btn = button("Check now", slot=lambda: self.check(True), icon="refresh")
        self.update_btn = button("Update now", "primary", self.run_update, icon="update",
                                 tip="Runs deckos update in a terminal: everything, AUR apps included")
        up.body.addWidget(row(self.update_btn, self.check_btn))
        self.lay.addWidget(up)

        fw = Card("Firewall", "Incoming connections", "shield")
        self.fw_box = QVBoxLayout()
        fw.body.addLayout(self.fw_box)
        self.fw_btn = button("", slot=self.toggle_firewall)
        fw.body.addWidget(row(self.fw_btn, button("Firewall settings…", slot=lambda: settings("kcm_firewall"),
                                                  icon="external")))
        self.lay.addWidget(fw)

        priv = Card("Privacy", "What leaves your computer", "eye")
        for ic, text in (
                ("check", "DecKoOS doesn't collect usage data or crash reports."),
                ("globe", "It goes online for updates, the DecKoOS Store's app lists, and the apps you install."),
                ("info", "KDE's own feedback is off unless you turn it on.")):
            h = QHBoxLayout()
            h.setSpacing(10)
            h.addWidget(icon_label(ic, S.SUBTEXT, 16), 0, Qt.AlignTop)
            h.addWidget(label(text, "sub"), 1)
            priv.body.addLayout(h)
        priv.body.addWidget(row(button("KDE feedback settings…", slot=lambda: settings("kcm_feedback"),
                                       icon="external")))
        self.lay.addWidget(priv)
        self.checked = False

    def refresh(self):
        on = sysinfo.update_channel_on()
        self.channel.setText(
            f"<span style='color:{S.SUCCESS}'>●</span> DecKoOS's own updates (the Hub, tools, themes) come from the "
            "signed DecKoOS repo, along with Arch and CachyOS." if on else
            f"<span style='color:{S.WARNING}'>●</span> DecKoOS's own updates aren't set up on this install yet. "
            "Arch and CachyOS updates still arrive.")
        if not self.checked:
            self.check(False)
        self.win.data.firewall(self.show_firewall)

    def check(self, fresh):
        self.checked = True
        self.clear(self.up_row)
        self.up_row.addWidget(state_row("refresh", "Checking for updates…", "", "info"))
        self.update_btn.setEnabled(False)
        self.win.data.updates(self.show_updates, fresh=fresh)

    def show_updates(self, n, aur, err):
        self.clear(self.up_row)
        if err:
            self.up_row.addWidget(state_row("alert", "Couldn't check for updates", err, "warn"))
        elif n + aur == 0:
            self.up_row.addWidget(state_row("check", "Everything is up to date", "Arch, CachyOS and AUR packages.",
                                            "ok"))
        else:
            self.up_row.addWidget(state_row("update", f"{n + aur} update{'s' if n + aur != 1 else ''} waiting",
                                            f"{n} from Arch and CachyOS" + (f", {aur} from the AUR" if aur else "") +
                                            ". Updating now is a good idea on a fresh install.", "warn"))
        self.update_btn.setEnabled(not err and n + aur > 0)

    def run_update(self):
        self.win.terminal("deckos update")
        self.note("update", "Updated DecKoOS (in a terminal)", "reboot")
        self.win.toast("Updating in a terminal. Restart afterwards if the kernel was updated.", "info", 7000)

    def show_firewall(self, on, svcs):
        self.clear(self.fw_box)
        if on:
            self.fw_box.addWidget(state_row("shield", "On: blocking incoming connections",
                                            "Open for: " + (", ".join(svcs) or "nothing"), "ok"))
        else:
            self.fw_box.addWidget(RowItem("shield-off", "Off: incoming connections are allowed",
                                          "Turn it on unless you need it off for something specific.", S.DANGER))
        self.fw_on = on
        self.fw_btn.setText("Turn off" if on else "Turn on")
        self.fw_btn.setObjectName("" if on else "primary")
        self.fw_btn.setIcon(S.icon("shield-off" if on else "shield", S.TEXT if on else "white", 16))
        restyle(self.fw_btn)

    def toggle_firewall(self):
        on = self.fw_on

        def done(ok):
            if ok:
                self.note("firewall", "Firewall turned off" if on else "Firewall turned on")
            self.win.data.invalidate()
            self.win.data.firewall(self.show_firewall)
            self.win.toast(("Firewall off." if on else "Firewall on.") if ok else "Firewall not changed.",
                           "ok" if ok else "warn")
        self.win.privileged_cmd(["systemctl", "disable" if on else "enable", "--now", "firewalld"], done)


# ------------------------------------------------------------------ 8. extras

SHORTCUTS = [  # Plasma's defaults
    ("Meta", "Open the app menu"), ("Alt+Space", "Search apps, files, maths (KRunner)"),
    ("Meta+E", "Files"), ("Ctrl+Alt+T", "Terminal"),
    ("Meta+W", "Overview of windows and desktops"), ("Alt+Tab", "Switch windows"),
    ("Meta+←  →", "Snap a window to half the screen"), ("Meta+PgUp", "Maximise a window"),
    ("Meta+D", "Show the desktop"), ("Meta+L", "Lock the screen"),
    ("Print", "Take a screenshot"), ("Meta+V", "Clipboard history"),
    ("Meta+.", "Emoji"), ("Ctrl+Esc", "System Monitor"),
]


def keycaps(combo):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(3)
    for i, k in enumerate(combo.split("+")):
        if i:
            h.addWidget(label("+", "muted", wrap=False))
        h.addWidget(label(k, "key", wrap=False))
    h.addStretch(1)
    return w


class ExtrasStep(Step):
    key, nav, hub = "extras", "Extras", "Appearance"
    title = "A few extras"
    subtitle = "Spotify in the DecKoOS look, Claude Code, and the shortcuts worth knowing."
    hint = "The Spotify look and Claude Code run in a terminal, so you can see what they do."

    def build(self):
        spotify = Card("Spotify", "The DecKoOS look for Spotify", "music")
        spotify.body.addWidget(label("Restyles the official Spotify app with DecKoOS colours, bordered panels and the "
                                     "gradient play buttons, using Spicetify. Spotify updates undo it; apply it again "
                                     "after one.", "sub"))
        self.spotify_box = QHBoxLayout()
        self.spotify_box.setSpacing(6)
        spotify.body.addLayout(self.spotify_box)
        self.lay.addWidget(spotify)

        claude = Card("Claude Code", "An AI coding agent in your terminal", "terminal")
        claude.body.addWidget(label("Ask it to explain, write or fix code in any project folder: run <b>claude</b> "
                                    "there. It needs a Claude account.", "sub"))
        self.claude_box = QHBoxLayout()
        self.claude_box.setSpacing(6)
        claude.body.addLayout(self.claude_box)
        self.lay.addWidget(claude)

        if sysinfo.have("kdeconnect-app"):
            phone = Card("Your phone", "KDE Connect", "globe")
            phone.body.addWidget(label("Notifications, files, the clipboard and media controls between your phone and "
                                       "DecKoOS. Install KDE Connect on the phone, then pair it here. The firewall "
                                       "already lets it through.", "sub"))
            phone.body.addWidget(row(button("Pair a phone…", slot=lambda: launch("kdeconnect-app"), icon="external")))
            self.lay.addWidget(phone)

        keys = Card("Keyboard shortcuts", "Worth knowing on day one", "keyboard")
        keys.actions.addWidget(button("All shortcuts…", slot=lambda: settings("kcm_keys"), icon="external"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        half = (len(SHORTCUTS) + 1) // 2
        for i, (combo, what) in enumerate(SHORTCUTS):
            col = 0 if i < half else 2
            grid.addWidget(keycaps(combo), i % half, col)
            grid.addWidget(label(what, "sub", wrap=False), i % half, col + 1)
        grid.setColumnMinimumWidth(0, 130)
        grid.setColumnMinimumWidth(2, 130)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        keys.body.addLayout(grid)
        keys.body.addWidget(label("Meta is the Windows key.", "muted"))
        self.lay.addWidget(keys)

    def refresh(self):
        self.clear(self.spotify_box)
        if ws.spotify_installed():
            self.spotify_box.addWidget(button("Apply DecKoOS look", "primary", self.spotify, icon="appearance"))
            self.spotify_box.addWidget(button("Back to stock", slot=lambda: self.win.terminal("deckos spotify restore"),
                                              icon="refresh"))
            self.spotify_box.addWidget(label("Open Spotify and log in once first.", "muted", wrap=False))
        else:
            self.spotify_box.addWidget(button("Get Spotify", slot=lambda: self.win.go_to("software"), icon="download"))
            self.spotify_box.addWidget(label("Spotify isn't installed yet: the Software step has it.", "muted",
                                             wrap=False))
        self.spotify_box.addStretch(1)
        self.clear(self.claude_box)
        have = sysinfo.installed("claude")
        self.claude_box.addWidget(button("Update" if have else "Install", "" if have else "primary", self.claude,
                                         icon="download"))
        self.claude_box.addWidget(button("Open a terminal", slot=lambda: launch("deckos-terminal"), icon="terminal"))
        if have:
            self.claude_box.addWidget(label(f"<span style='color:{S.SUCCESS}'>●</span> Installed", "sub", wrap=False))
        self.claude_box.addStretch(1)

    def spotify(self):
        self.win.terminal("deckos spotify theme")
        self.note("spotify", "DecKoOS look for Spotify")

    def claude(self):
        self.win.terminal("curl -fsSL https://claude.ai/install.sh | bash")
        self.note("claude", "Installed Claude Code (in a terminal)")


# ------------------------------------------------------------------ 9. done

class DoneStep(Step):
    key, nav = "done", "Done"
    title = "You're all set"
    subtitle = "Here's what changed. Everything stays changeable in DecKoOS Hub."
    hint = "Finish closes this window. It's in the app menu as DecKoOS Welcome if you want it again."

    def build(self):
        self.head_actions.addWidget(button("Open DecKoOS Hub", "primary", self.win.open_hub, icon="external"))
        self.changed = Card("What changed", None, "check")
        self.changed_box = QVBoxLayout()
        self.changed_box.setSpacing(6)
        self.changed.body.addLayout(self.changed_box)
        self.lay.addWidget(self.changed)

        self.restart = Card("One more thing", None, "power")
        self.restart_text = label("", "sub")
        self.restart.body.addWidget(self.restart_text)
        self.restart_btns = QHBoxLayout()
        self.restart.body.addLayout(self.restart_btns)
        self.lay.addWidget(self.restart)

        self.skipped = Card("Skipped", "Whenever you're ready", "chevron")
        self.skipped_box = QVBoxLayout()
        self.skipped_box.setSpacing(6)
        self.skipped.body.addLayout(self.skipped_box)
        self.lay.addWidget(self.skipped)

    def refresh(self):
        self.clear(self.changed_box)
        changes = list(self.win.changes.values())
        if not changes:
            self.changed_box.addWidget(label("Nothing yet, and that's fine: DecKoOS's defaults are ready to go.", "sub"))
        for text, needs in changes:
            detail = {"reboot": "After a restart", "relogin": "After logging out and back in"}.get(needs, "")
            self.changed_box.addWidget(RowItem("check", text, detail, S.SUCCESS))

        needs = {n for _t, n in changes if n}
        self.restart.setVisible(bool(needs))
        self.clear(self.restart_btns)
        if "reboot" in needs:
            self.restart_text.setText("Some changes take effect after a restart. Finish what's running in any "
                                      "terminals first.")
            self.restart_btns.addWidget(button("Restart now", slot=lambda: self.session("logoutAndReboot"),
                                               icon="power"))
        elif "relogin" in needs:
            self.restart_text.setText("New software groups need you to log out and back in once they've installed.")
            self.restart_btns.addWidget(button("Log out now", slot=lambda: self.session("logout"), icon="switch"))
        self.restart_btns.addStretch(1)

        self.clear(self.skipped_box)
        skipped = self.win.skipped()
        self.skipped.setVisible(bool(skipped))
        for step in skipped:
            b = button("Go back", slot=lambda _c=False, k=step.key: self.win.go_to(k))
            self.skipped_box.addWidget(RowItem("chevron", step.nav, f"Also in DecKoOS Hub › {step.hub}", S.MUTED, [b]))

    @staticmethod
    def session(action):
        """Plasma's own restart / log out, with its confirmation and app saving."""
        if not sysinfo.DEMO:
            QProcess.startDetached("qdbus6", ["org.kde.Shutdown", "/Shutdown", f"org.kde.Shutdown.{action}"])


STEPS = [WelcomeStep, LookStep, DisplayStep, SoftwareStep, GamingStep, FilesStep, UpdatesStep, ExtrasStep, DoneStep]
