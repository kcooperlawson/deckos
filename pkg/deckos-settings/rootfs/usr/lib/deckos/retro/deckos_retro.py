"""DecKoOS Retro: your retro games in one place. It finds them, installs the emulators they need, checks
for BIOS files, and adds them to Steam for Gaming Mode. It never downloads games or BIOS files.

    deckos-retro                      the window
    deckos-retro --play FILE          start one game (what the Steam shortcuts run)
    deckos-retro --demo [--screenshot DIR]
"""
import os
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

import retro  # noqa: E402

CONF = Path.home() / ".config/deckos/retro-folders"
DEMO = "--demo" in sys.argv

# tile colour per console (the plates' hues)
COLORS = {"nes": "#C9363F", "snes": "#6A5ACD", "n64": "#2F8F4E", "gb": "#6B8E23", "gbc": "#8E44AD", "gba": "#5E3FE0",
          "nds": "#4A5568", "gamecube": "#5B3E96", "wii": "#3C8DBC", "genesis": "#3B4A63", "sms": "#B83232",
          "gamegear": "#2D3748", "segacd": "#374151", "saturn": "#4B5563", "dreamcast": "#E67E22", "pce": "#D35400",
          "psx": "#5A6377", "ps2": "#1E3A8A", "psp": "#2B3445", "arcade": "#B7791F"}


def folders():
    try:
        saved = [Path(line) for line in CONF.read_text().splitlines() if line.strip()]
    except OSError:
        saved = []
    defaults = [retro.LIBRARY] + [p for p in (Path.home() / "ROMs", Path.home() / "roms", Path.home() / "Games/ROMs")
                                  if p.is_dir()]
    return list(dict.fromkeys(saved or defaults))


def save_folders(paths):
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text("".join(f"{p}\n" for p in paths))


def play(path):
    """Starts the game at `path` with its emulator, replacing this process (so Steam sees the game)."""
    path = Path(path).resolve()
    game = next((g for g in retro.scan(folders() + [path.parent]) if path in g.files or g.path == path), None)
    if game is None:
        sys.exit(f"DecKoOS Retro doesn't know what console {path.name} is for.")
    blocked = retro.ready(game.system)
    if blocked:
        # From Gaming Mode there's no terminal: say it where it'll be seen
        subprocess.run(["kdialog", "--sorry", f"{retro.BY_ID[game.system].name} isn't set up yet. Open DecKoOS Retro "
                        f"on the desktop to {'install its emulator' if blocked == 'emulator' else 'add its BIOS'}."])
        sys.exit(1)
    cmd = retro.command(game)
    os.execvp(cmd[0], cmd)


if "--play" in sys.argv[:-1]:
    play(sys.argv[sys.argv.index("--play") + 1])

from PySide6.QtCore import QObject, QProcess, QSize, Qt, Signal  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout,  # noqa: E402
                               QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

import hub_style as S  # noqa: E402
from hub_widgets import Empty, button, icon_label, label  # noqa: E402

QSS = f"""
QListWidget#library {{ background: transparent; border: none; outline: 0; }}
QListWidget#library::item {{ border-radius: 10px; padding: 4px; color: {S.TEXT}; }}
QListWidget#library::item:selected {{ background: rgba(76, 141, 255, 0.16); }}
QListWidget#library::item:hover {{ background: {S.RAISED}; }}
QPushButton#seg {{ padding: 6px 14px; border-radius: 8px; background: transparent; border: 1px solid transparent; }}
QPushButton#seg:checked {{ background: {S.RAISED}; border-color: {S.BORDER}; color: {S.TEXT}; }}
"""


class Worker(QObject):
    """fn on a thread; the result (or the error) arrives on the UI thread."""
    done = Signal(object, object, str)

    def start(self, tag, fn, *args):
        def go():
            try:
                self.done.emit(tag, fn(*args), "")
            except Exception as e:  # shown, not a traceback
                self.done.emit(tag, None, str(e) or type(e).__name__)
        threading.Thread(target=go, daemon=True).start()


def cover(game, size=QSize(150, 200)):
    """A box for the game in its console's colour: no artwork is downloaded, so it's drawn."""
    pm = QPixmap(size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    base = QColor(COLORS.get(game.system, "#374151"))
    p.setPen(Qt.NoPen)
    p.setBrush(base.darker(150))
    p.drawRoundedRect(0, 3, size.width(), size.height() - 3, S.corner(12), S.corner(12))
    p.setBrush(base)
    p.drawRoundedRect(0, 0, size.width(), size.height() - 4, S.corner(12), S.corner(12))
    p.setBrush(QColor(255, 255, 255, 30))
    p.drawRoundedRect(0, 0, size.width(), 34, S.corner(12), S.corner(12))
    for x in (9, size.width() - 9):  # screw heads, the DecKoOS motif
        for y in (9, size.height() - 13):
            p.setBrush(QColor(255, 255, 255, 70))
            p.drawEllipse(x - 2.2, y - 2.2, 4.4, 4.4)
    p.setPen(QColor(255, 255, 255, 200))
    f = QFont("Inter", 8)
    f.setBold(True)
    f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
    p.setFont(f)
    p.drawText(14, 6, size.width() - 28, 24, Qt.AlignVCenter | Qt.AlignLeft,
               p.fontMetrics().elidedText(retro.BY_ID[game.system].name.upper(), Qt.ElideRight, size.width() - 28))
    p.setPen(QColor("#FFFFFF"))
    f = QFont("Inter Display", 13)
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.drawText(14, 44, size.width() - 28, size.height() - 80, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, game.title)
    p.setPen(QColor(255, 255, 255, 170))
    p.setFont(QFont("Inter", 8))
    extra = " · ".join(x for x in (game.region, f"{game.discs} discs" if game.discs > 1 else "") if x)
    p.drawText(14, size.height() - 34, size.width() - 28, 18, Qt.AlignLeft, extra)
    p.end()
    return pm


class Retro(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DecKoOS Retro")
        self.setWindowIcon(QIcon.fromTheme("input-gaming"))
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(S.qss() + QSS)
        self.resize(1120, 760)
        self.games = []
        self.worker = Worker()
        self.worker.done.connect(self.done)

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 14)
        v.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(icon_label("gaming", S.P.accent, 26))
        head.addWidget(label("Retro", "title", wrap=False))
        head.addSpacing(20)
        self.segs = QButtonGroup(self)
        for i, (text, icon) in enumerate((("Library", "grid"), ("Consoles", "gaming"))):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setIcon(S.icon(icon, S.SUBTEXT, 16))
            b.setCursor(Qt.PointingHandCursor)
            self.segs.addButton(b, i)
            head.addWidget(b)
        head.addStretch(1)
        head.addWidget(button("Add a folder", slot=self.add_folder, icon="folder-plus",
                              tip="A folder where you keep games: DecKoOS Retro looks through it"))
        self.steam_button = button("Add to Steam", "primary", self.add_to_steam, icon="gaming",
                                   tip="Puts your games in Steam, so they're in Gaming Mode")
        head.addWidget(self.steam_button)
        v.addLayout(head)

        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        self.status = label("", "muted", wrap=False)
        v.addWidget(self.status)
        self.segs.idClicked.connect(self.stack.setCurrentIndex)

        # library
        lib = QWidget()
        lv = QVBoxLayout(lib)
        lv.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your games")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.fill_library)
        top.addWidget(self.search, 1)
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(self.fill_library)
        top.addWidget(self.filter)
        lv.addLayout(top)
        self.list = QListWidget()
        self.list.setObjectName("library")
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(150, 200))
        self.list.setGridSize(QSize(170, 222))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setUniformItemSizes(True)
        self.list.itemActivated.connect(self.play_item)
        lv.addWidget(self.list, 1)
        self.empty = Empty("gaming", "No games found yet",
                           f"Put your games in {retro.LIBRARY} (one folder per console is made for you), or add a "
                           "folder where you already keep them. DecKoOS Retro doesn't download games.")
        lv.addWidget(self.empty)
        self.stack.addWidget(lib)

        # consoles
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self.consoles = QVBoxLayout(inner)
        self.consoles.setContentsMargins(0, 0, 0, 0)
        self.consoles.setSpacing(10)
        scroll.setWidget(inner)
        self.stack.addWidget(scroll)

        self.segs.button(0).setChecked(True)
        if not DEMO:
            retro.setup_folders()
        self.rescan()

    # ---- scanning

    def rescan(self):
        self.status.setText("Looking for games…")
        if DEMO:
            self.done("scan", demo_games(), "")
        else:
            self.worker.start("scan", retro.scan, folders())

    def done(self, tag, result, error):
        if error:
            self.status.setText(f"Something went wrong: {error}")
            return
        if tag == "scan":
            self.games = result
            self.status.setText(f"{len(self.games)} games in {', '.join(str(f) for f in folders())}"
                                if self.games else "")
            current = self.filter.currentData()
            self.filter.blockSignals(True)
            self.filter.clear()
            self.filter.addItem("All consoles", "")
            for sid in sorted({g.system for g in self.games}, key=lambda s: retro.BY_ID[s].name):
                n = sum(1 for g in self.games if g.system == sid)
                self.filter.addItem(f"{retro.BY_ID[sid].name} ({n})", sid)
            self.filter.setCurrentIndex(max(0, self.filter.findData(current)))
            self.filter.blockSignals(False)
            self.fill_library()
            self.fill_consoles()
        elif tag == "steam":
            added, removed = result
            self.status.setText(f"Steam: {added} added" + (f", {removed} removed" if removed else "") +
                                ". They're under the DecKoOS Retro collection.")
            if QMessageBox.question(self, "Open Steam?", "Your games are in Steam now. Open Steam?") == QMessageBox.Yes:
                QProcess.startDetached("steam", [])
        elif tag == "bios":
            names = ", ".join(name for _, name in result) or "nothing DecKoOS Retro recognises"
            self.status.setText(f"BIOS files added: {names}")
            self.fill_consoles()

    def fill_library(self):
        self.list.clear()
        query = self.search.text().strip().lower()
        system = self.filter.currentData()
        shown = [g for g in self.games if (not system or g.system == system) and query in g.title.lower()]
        for g in shown:
            item = QListWidgetItem(QIcon(cover(g)), "")
            item.setToolTip(f"{g.title}\n{retro.BY_ID[g.system].name}\n{g.path}")
            item.setData(Qt.UserRole, g)
            self.list.addItem(item)
        self.list.setVisible(bool(shown))
        self.empty.setVisible(not self.games)

    def fill_consoles(self):
        while self.consoles.count():
            w = self.consoles.takeAt(0).widget()
            if w:
                w.deleteLater()
        counts = {}
        for g in self.games:
            counts[g.system] = counts.get(g.system, 0) + 1
        todo = [s for s in counts if (demo_ready(s) if DEMO else retro.ready(s)) == "emulator"]
        if todo:
            box = QFrame()
            box.setObjectName("card")
            box.setAttribute(Qt.WA_StyledBackground, True)
            h = QHBoxLayout(box)
            h.setContentsMargins(18, 14, 18, 14)
            h.addWidget(label(f"<b>{len(todo)} of your consoles need their emulator.</b> DecKoOS Retro can install "
                              "them all now (from the Arch repos and Flathub).", "sub"), 1)
            h.addWidget(button("Set up everything", "primary", lambda: self.install(todo), icon="download"))
            self.consoles.addWidget(box)
        for s in sorted(retro.SYSTEMS, key=lambda s: (s.id not in counts, s.name)):
            self.consoles.addWidget(self.console_row(s, counts.get(s.id, 0)))
        self.consoles.addStretch(1)

    def console_row(self, s, n):
        row = QFrame()
        row.setObjectName("card")
        row.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 10, 16, 10)
        dot = QFrame()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"background: {COLORS.get(s.id, '#374151')}; border-radius: 6px;")
        h.addWidget(dot)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(label(f"<b>{s.name}</b>  <span style='color:{S.SUBTEXT}'>"
                             f"{n} game{'s' if n != 1 else ''}</span>", None, wrap=False))
        state = demo_ready(s.id) if DEMO else retro.ready(s.id)
        emu = "RetroArch" if s.core else s.package.split(".")[-1]
        if state == "emulator":
            detail, color = f"Needs its emulator ({emu})", S.WARNING
        elif state == "bios":
            missing = [b for b, st in (demo_bios(s.id) if DEMO else retro.bios_status(s.id)) if st == "missing" and b.required]
            detail = "Needs a BIOS from your own console: " + ", ".join(
                f"{b.name}" + (f" ({b.note})" if b.note else "") for b in missing)
            color = S.WARNING
        else:
            detail, color = f"Ready · {emu}", S.SUCCESS
        text.addWidget(label(f"<span style='color:{color}'>{detail}</span>", "sub"))
        h.addLayout(text, 1)
        if state == "emulator":
            h.addWidget(button("Install", slot=lambda _=False, sid=s.id: self.install([sid]), icon="download"))
        elif state == "bios":
            h.addWidget(button("Add BIOS…", slot=self.add_bios, icon="folder",
                               tip="Pick the folder with your BIOS backups: files are recognised by their contents"))
        return row

    # ---- actions

    def install(self, systems):
        pac, flat = retro.packages_for(systems)
        if DEMO:
            self.status.setText(f"Demo mode · would install {', '.join(pac + flat)}")
            return
        proc = QProcess(self)
        proc.finished.connect(lambda code, _s: (self.status.setText(
            "Emulators installed." if code == 0 else "The emulators didn't install. Try again, or see Terminal."),
            self.fill_consoles()))
        self.status.setText("Installing emulators…")
        proc.start("deckos", ["retro", "install", *pac, *flat])

    def add_bios(self):
        folder = QFileDialog.getExistingDirectory(self, "Folder with your BIOS backups", str(Path.home()))
        if folder:
            self.worker.start("bios", retro.import_bios, folder)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "A folder where you keep games", str(Path.home()))
        if folder:
            save_folders(folders() + [Path(folder)])
            self.rescan()

    def play_item(self, item):
        g = item.data(Qt.UserRole)
        if DEMO:
            self.status.setText(f"Demo mode · would start {g.title}")
            return
        blocked = retro.ready(g.system)
        if blocked:
            self.segs.button(1).click()
            self.status.setText(f"{retro.BY_ID[g.system].name} isn't set up yet: "
                                f"{'install its emulator' if blocked == 'emulator' else 'add its BIOS'} first.")
            return
        cmd = retro.command(g, fullscreen=False)
        QProcess.startDetached(cmd[0], cmd[1:])
        self.status.setText(f"Starting {g.title}…")

    def add_to_steam(self):
        if not self.games:
            self.status.setText("No games to add yet.")
            return
        if DEMO:
            self.status.setText(f"Demo mode · would add {len(self.games)} games to Steam")
            return
        import steamfiles
        if steamfiles.steam_running():
            if QMessageBox.question(self, "Close Steam?", "Steam has to be closed while its game list changes. "
                                    "Close Steam now? It opens again afterwards.") != QMessageBox.Yes:
                return

            def close_then_sync():
                if not steamfiles.close_steam():
                    raise RuntimeError("Steam didn't close")
                return retro.sync_steam(self.games)
            self.status.setText("Closing Steam…")
            self.worker.start("steam", close_then_sync)
        else:
            self.worker.start("steam", retro.sync_steam, self.games)


# ------------------------------------------------------------------ demo

def demo_games():
    G = retro.Game
    rows = [("snes", "Chrono Trigger", "USA", 1), ("snes", "Super Metroid", "USA", 1), ("n64", "The Legend of Zelda",
            "USA", 1), ("gba", "Golden Sun", "USA", 1), ("psx", "Final Fantasy VII", "USA", 3),
            ("psx", "Metal Gear Solid", "USA", 2), ("ps2", "Shadow of the Colossus", "USA", 1),
            ("gamecube", "Super Smash Bros. Melee", "USA", 1), ("genesis", "Sonic the Hedgehog 2", "World", 1),
            ("dreamcast", "Jet Set Radio", "USA", 1), ("nes", "Super Mario Bros. 3", "USA", 1),
            ("psp", "Patapon", "USA", 1), ("nds", "Pokémon Platinum", "USA", 1), ("arcade", "Street Fighter II", "", 1)]
    return [G(path=Path(f"/home/deck/Games/Retro/{s}/{t}"), system=s, title=t, region=r, discs=d) for s, t, r, d in rows]


def demo_ready(sid):
    return {"ps2": "emulator", "psx": "bios", "dreamcast": "emulator"}.get(sid, "")


def demo_bios(sid):
    return [(b, "missing") for b in retro.BY_ID[sid].bios]


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Retro")
    app.setDesktopFileName("deckos-retro")
    app.setFont(QFont("Inter", 10))
    w = Retro()
    w.show()
    if "--screenshot" in sys.argv[:-1]:
        out = Path(sys.argv[sys.argv.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)
        for i, name in enumerate(("library", "consoles")):
            w.segs.button(i).click()
            app.processEvents()
            w.grab().save(str(out / f"retro-{name}.png"))
        sys.exit(0)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
