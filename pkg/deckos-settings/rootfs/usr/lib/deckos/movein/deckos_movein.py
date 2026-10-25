"""DecKoOS Move In's window: what's on Windows worth bringing over, ticked, and brought over in one go.

    deckos-movein                       find Windows on this PC's drives
    deckos-movein --demo [--screenshot FILE]
"""
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

from PySide6.QtCore import QObject, QProcess, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QScrollArea,  # noqa: E402
                               QVBoxLayout, QWidget)

import hub_style as S  # noqa: E402
import movein  # noqa: E402
from hub_widgets import Card, Empty, button, icon_label, label, row  # noqa: E402

DEMO = "--demo" in sys.argv
GROUPS = [("drives", "Your Windows drives", "drives"), ("folders", "Your folders", "folder"),
          ("wallpaper", "Your desktop", "image"), ("browser", "Your browser", "globe"), ("games", "Your games", "gaming"),
          ("apps", "Your apps", "package"), ("fonts", "Your fonts", "doc"), ("wifi", "What can't come over", "lock")]
QSS = f"""
QLabel#big {{ font-family: "Inter Display", "Inter"; font-size: 17pt; font-weight: 600; }}
QCheckBox {{ font-weight: 600; spacing: 8px; }}
QCheckBox:disabled {{ color: {S.SUBTEXT}; }}
"""


class Worker(QObject):
    """movein.apply on a thread; progress and the result arrive on the UI thread."""
    progress = Signal(str)
    done = Signal(object)

    def start(self, items):
        threading.Thread(target=lambda: self.done.emit(movein.apply(items, self.progress.emit)), daemon=True).start()


class MoveIn(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Move in from Windows")
        self.resize(820, 900)
        self.setStyleSheet(S.qss() + QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        self.lay = QVBoxLayout(page)
        self.lay.setContentsMargins(28, 24, 28, 24)
        self.lay.setSpacing(14)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        foot = QFrame()
        foot.setStyleSheet(f"background: {S.SURFACE}; border-top: 1px solid {S.BORDER};")
        f = QHBoxLayout(foot)
        f.setContentsMargins(28, 12, 28, 12)
        self.status = label("", "sub")
        f.addWidget(self.status, 1)
        self.again_btn = button("Look again", slot=self.load, icon="refresh")
        self.go_btn = button("Bring them over", "primary", self.bring, icon="arrow-right")
        f.addWidget(self.again_btn)
        f.addWidget(self.go_btn)
        outer.addWidget(foot)
        self.worker = Worker(self)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.user = None
        self.load()

    # ------------------------------------------------------------- what's there

    def clear(self):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.deleteLater()

    def load(self, *_):
        self.win, self.items = demo() if DEMO else movein.scan(self.user)
        self.clear()
        head = QWidget()
        h = QVBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 4)
        h.setSpacing(4)
        h.addWidget(label("MOVE IN FROM WINDOWS", "kicker"))
        h.addWidget(label("Bring your Windows stuff over", "big"))
        self.lay.addWidget(head)
        if not self.win:
            self.lay.addWidget(Empty("drives", "No Windows found",
                                     "If Windows is on this PC, open its drive in DecKoOS Files (or run sudo deckos drives "
                                     "rescan), then press Look again."))
            self.lay.addStretch(1)
            self.go_btn.setEnabled(False)
            return
        self.user = self.user or (self.win.users[0] if self.win.users else None)
        intro = (f"Windows is on {self.win.root}. Nothing on it is changed: folders are shown from there, everything "
                 "else is copied, and anything changed here keeps a backup.")
        self.lay.addWidget(label(intro, "sub"))
        if len(self.win.users) > 1:
            pick = QComboBox()
            pick.addItems(self.win.users)
            pick.setCurrentText(self.user)
            pick.currentTextChanged.connect(self.pick_user)
            self.lay.addWidget(row(label("Whose things:"), pick))
        self.boxes = {}
        for kind, title, icon in GROUPS:
            mine = [i for i in self.items if i.kind == kind]
            if not mine:
                continue
            card = Card(title, None, icon)
            for item in mine:
                card.body.addWidget(self.item_row(item))
            self.lay.addWidget(card)
        self.lay.addStretch(1)
        self.go_btn.setEnabled(any(i.ready for i in self.items))
        self.status.setText("Tick what you want, then Bring them over.")

    def pick_user(self, name):
        self.user = name
        self.load()

    def item_row(self, item):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 2, 0, 6)
        v.setSpacing(2)
        box = QCheckBox(item.title)
        box.setChecked(item.ready and item.picked)
        box.setEnabled(item.ready)
        box.toggled.connect(lambda on, i=item: setattr(i, "picked", on))
        self.boxes[item.key] = box
        v.addWidget(box)
        detail = label(item.detail, "sub")
        detail.setContentsMargins(26, 0, 0, 0)
        v.addWidget(detail)
        if item.kind == "apps":
            for app in item.data["apps"]:
                # each row on its own widget: a free QHBoxLayout added with addLayout is freed twice by
                # PySide on exit (a crash)
                holder = QWidget()
                line = QHBoxLayout(holder)
                line.setContentsMargins(26, 2, 0, 0)
                line.addWidget(label(f"{app.get('name') or app['windows'].title()} → <b>{app['linux']}</b>"), 1)
                if app["installed"]:
                    line.addWidget(icon_label("check", S.SUCCESS, 16))
                else:
                    line.addWidget(button("Get", slot=lambda _=False, s=app["search"]: self.get_app(s), icon="store"))
                v.addWidget(holder)
        return w

    def get_app(self, search):
        if not DEMO:
            QProcess.startDetached("deckos-store", ["--search", search])

    # ------------------------------------------------------------- bringing it over

    def bring(self):
        picked = [i for i in self.items if i.ready and i.picked]
        if not picked:
            self.status.setText("Nothing ticked.")
            return
        self.go_btn.setEnabled(False)
        self.again_btn.setEnabled(False)
        for box in self.boxes.values():
            box.setEnabled(False)
        if DEMO:
            QTimer.singleShot(300, lambda: self.on_done([(i.key, True, "done (demo)") for i in picked]))
        else:
            self.worker.start(self.items)

    def on_progress(self, title):
        self.status.setText(f"Now: {title}…")

    def on_done(self, results):
        ok = sum(1 for _, good, _ in results if good)
        card = Card("Done" if ok == len(results) else "Done, with some problems", None,
                    "check" if ok == len(results) else "alert")
        titles = {i.key: i.title for i in self.items}
        for key, good, msg in results:
            holder = QWidget()
            line = QHBoxLayout(holder)
            line.setContentsMargins(0, 0, 0, 0)
            line.addWidget(icon_label("check" if good else "alert", S.SUCCESS if good else S.DANGER, 16))
            line.addWidget(label(f"<b>{titles.get(key, key)}</b>: {msg}"), 1)
            card.body.addWidget(holder)
        self.lay.insertWidget(1, card)
        self.status.setText(f"{ok} of {len(results)} brought over. Run it again any time: what's here already is skipped.")
        self.again_btn.setEnabled(True)


def demo():
    win = movein.Windows(Path("/mnt/Windows"), ["alex"], [Path("/mnt/Windows"), Path("/run/media/alex/Games")])
    I = movein.Item
    items = [
        I("drives", "drives", "Mount your Windows drives at every start", "/run/media/alex/Games only stays until you "
          "restart; games and folders on it would vanish from Steam and the sidebar. This adds it to /mnt."),
        I("folder:Documents", "folders", "Windows Documents", "In DecKoOS Files' sidebar, straight from the Windows drive: "
          "nothing is copied.", data={"path": "", "icon": ""}),
        I("folder:Pictures", "folders", "Windows Pictures", "In DecKoOS Files' sidebar, straight from the Windows drive: "
          "nothing is copied.", data={"path": "", "icon": ""}),
        I("wallpaper", "wallpaper", "Your Windows wallpaper", "Copied to Pictures and set as the desktop background."),
        I("firefox:x", "browser", "Firefox: bookmarks, history, passwords, add-ons", "Profile tk0z.default-release, last "
          "used 21 Oct 2026, 412.6 MB. Becomes Firefox's profile here; the current one stays, in Firefox's profile manager."),
        I("bookmarks:Microsoft Edge", "browser", "Microsoft Edge bookmarks", "64 bookmarks, saved as a file Firefox "
          "imports. Saved passwords are locked to Windows: export them in Microsoft Edge and import that file in Firefox."),
        I("steam:/run/media/alex/Games/SteamLibrary", "games", "Steam games: 4 on Games", "Kerbal Space Program, Forza "
          "Horizon 6, American Truck Simulator, BeamNG.drive. Added to Steam here as a library, so nothing downloads again."),
        I("other-games", "games", "Other games: 9 folders", "007 First Light, Clone Hero and 7 more. Epic and GOG games: "
          "sign in to Heroic and use Import for each folder.", picked=False),
        I("apps", "apps", "Your apps: 6 with a DecKoOS match", "2 to get; the Store opens on each.", data={"apps": [
            {"name": "Discord", "linux": "Discord", "search": "discord", "installed": True},
            {"name": "Visual Studio 2022", "linux": "VS Code or JetBrains Rider", "search": "code", "installed": False},
            {"name": "WinRAR", "linux": "Ark (already installed)", "search": "ark", "installed": True},
            {"name": "Microsoft Edge", "linux": "Firefox, or Microsoft Edge from the Store", "search": "edge",
             "installed": False}]}),
        I("wifi", "wifi", "Wi-Fi networks: 4", "Home, Office and 2 more. Their passwords are encrypted by Windows, so "
          "connect once from the panel.", ready=False, picked=False),
    ]
    return win, items


def main():
    args = sys.argv[1:]
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Move In")
    app.setDesktopFileName("deckos-movein")
    app.setFont(QFont("Inter", 10))
    w = MoveIn()
    w.show()
    if "--screenshot" in args:
        out = args[args.index("--screenshot") + 1]

        def shoot():
            page = w.findChild(QScrollArea).widget()
            page.resize(page.width(), page.sizeHint().height())
            page.grab().save(out)
            app.exit(0)
        QTimer.singleShot(500, shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
