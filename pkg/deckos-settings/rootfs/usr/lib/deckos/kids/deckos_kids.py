"""Kid mode's desktop: the child's theme (kids_themes), DecKoOS's own games (kids_games), big tiles for the apps a
parent approved, the time left (when there's a limit) and "I'm done". Starts at login in a child's account
(`deckos-kids --session`, from the autostart kids.py writes). Counts the minutes used today and, at the end of the
time, says so kindly and logs out.

    deckos-kids --session | --demo [--theme ID] [--screenshot FILE]
"""
import os
import pwd
import re
import shlex
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QProcess, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QStackedLayout, QVBoxLayout, QWidget)

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub"), str(HERE.parent / "gamepanel")]
import hub_style as S  # noqa: E402
import kids  # noqa: E402
import kids_games  # noqa: E402
import kids_themes  # noqa: E402
from deckos_gamepanel import Pad  # noqa: E402  the Gaming Mode panel's controller reader (evdev)

DEMO = "--demo" in sys.argv
DEMO_THEME = sys.argv[sys.argv.index("--theme") + 1] if "--theme" in sys.argv[:-1] else "space"
DEMO_TILES = [{"name": n, "icon": i, "exec": ""} for n, i in (
    ("Paint", "kolourpaint"), ("Tux Paint", "tuxpaint"), ("GCompris", "gcompris-qt"), ("Potato Guy", "ktuberling"),
    ("Blocks", "kblocks"), ("Cards", "kpat"), ("Letters", "klettres"), ("The web", "firefox"))]


class Tile(QPushButton):
    """A big rounded tile: the app's icon on a bright colour, its name underneath."""

    def __init__(self, app, colour):
        super().__init__()
        self.app, self.colour = app, QColor(colour)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(200, 200)
        self.emoji = app.get("emoji", "")  # DecKoOS's own games draw a picture, not an app icon
        self.icon_ = QIcon() if self.emoji else QIcon.fromTheme(app["icon"]) if app["icon"] and \
            not app["icon"].startswith("/") else QIcon(app["icon"])
        self.setFocusPolicy(Qt.StrongFocus)
        # No parent: setGraphicsEffect owns it, and two owners crashed Qt when the app closed
        self.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=24, offset=QPointF(0, 6), color=QColor(0, 0, 0, 90)))

    def keyPressEvent(self, e):  # arrows and Enter go to KidMode, which moves by rows and columns
        e.ignore()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(6, 6, -6, -6)
        path = QPainterPath()
        path.addRoundedRect(r, S.corner(28), S.corner(28))
        c = self.colour.lighter(112) if self.underMouse() or self.hasFocus() else self.colour
        p.fillPath(path, c)
        if self.hasFocus():  # thick enough to see from the couch
            p.setPen(QPen(QColor("#FFFFFF"), 5))
            p.drawPath(path)
        pm = self.icon_.pixmap(QSize(96, 96))
        if self.emoji:
            kids_themes.emoji(p, self.emoji, r.center().x(), r.top() + 74, 64)
        elif not pm.isNull():
            p.drawPixmap(r.center().x() - 48, r.top() + 24, pm)
        else:
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Inter Display", 54, QFont.Bold))
            p.drawText(r.adjusted(0, 0, 0, -50), Qt.AlignCenter, self.app["name"][:1])
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Inter Display", 16, QFont.DemiBold))
        p.drawText(r.adjusted(10, 0, -10, -18), Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, self.app["name"])


class TimeRing(QWidget):
    """The time left as a ring that empties, with the minutes inside: easy to read before reading numbers."""

    def __init__(self, colour):
        super().__init__()
        self.setFixedSize(96, 96)
        self.colour, self.frac, self.text = QColor(colour), 1.0, ""

    def set(self, frac, text):
        self.frac, self.text = frac, text
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(8, 8, 80, 80)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawEllipse(r)
        if self.frac is not None:
            pen = QPen(self.colour, 9)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(r.adjusted(5, 5, -5, -5), 90 * 16, int(-360 * 16 * max(0.0, min(1.0, self.frac))))
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Inter Display", 13 if len(self.text) > 3 else 17, QFont.Bold))
        p.drawText(r, Qt.AlignCenter, self.text)


def heading(text, colour):
    lab = QLabel(text)
    lab.setStyleSheet(f"font-family: 'Inter Display'; font-size: 20pt; font-weight: 700; color: {colour}; "
                      "background: transparent;")
    return lab


class KidMode(QWidget):
    def __init__(self):
        super().__init__()
        self.name = "mia" if DEMO else pwd.getpwuid(os.getuid()).pw_name
        self.conf = ({**kids.DEFAULTS, "display": "Mia", "minutes": "60", "theme": DEMO_THEME} if DEMO
                     else kids.read_conf(self.name) or {**kids.DEFAULTS, "display": self.name.title()})
        self.state = kids.state_file(self.name)
        self.theme = kids_themes.theme(self.conf.get("theme"))
        self.scene = kids_themes.Scene(self.theme["id"])
        self.frame = 0
        ink = self.theme["text"]
        self.setWindowTitle("Kid mode")
        self.setObjectName("root")
        self.stack = QStackedLayout(self)
        home = QWidget()
        home.setAttribute(Qt.WA_TranslucentBackground)
        self.stack.addWidget(home)
        v = QVBoxLayout(home)
        v.setContentsMargins(48, 32, 48, 28)
        v.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(16)
        friend = QLabel(self.theme["friend"])
        friend.setStyleSheet(f"font-family: '{kids_themes.EMOJI}'; font-size: 44pt; background: transparent;")
        head.addWidget(friend)
        hi = QVBoxLayout()
        hi.setSpacing(0)
        hello = QLabel(f"{self.greeting()}, {self.conf['display'] or self.name.title()}!")
        hello.setStyleSheet(f"font-family: 'Inter Display'; font-size: 34pt; font-weight: 800; color: {ink}; "
                            "background: transparent;")
        hi.addWidget(hello)
        sub = QLabel("What do you want to do?")
        sub.setStyleSheet(f"font-size: 15pt; color: {ink}; background: transparent;")
        hi.addWidget(sub)
        head.addLayout(hi, 1)
        self.ring = TimeRing(self.theme["tiles"][3])
        head.addWidget(self.ring)
        done = QPushButton("  I'm done")
        done.setIcon(S.icon("log-out", "#FFFFFF", 22))
        done.setIconSize(QSize(22, 22))
        done.setCursor(Qt.PointingHandCursor)
        done.setStyleSheet(f"QPushButton {{ font-size: 15pt; font-weight: 700; padding: 14px 24px; color: white; "
                           f"background: {self.theme['tiles'][0]}; border: none; border-radius: 26px; }}")
        done.clicked.connect(self.finish)
        head.addWidget(done)
        v.addLayout(head)

        self.banner = QLabel()
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setStyleSheet("font-size: 17pt; font-weight: 700; padding: 14px; border-radius: 22px; "
                                  "background: rgba(0, 0, 0, 120); color: #FFE08A;")
        self.banner.hide()
        v.addWidget(self.banner)

        grid_holder = QWidget()
        grid_holder.setAttribute(Qt.WA_TranslucentBackground)
        col = QVBoxLayout(grid_holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        self.tiles, self.cols = [], 5
        colours = self.theme["tiles"]
        apps = DEMO_TILES if DEMO else kids.approved(self.name)
        games = [{"name": n, "icon": "", "exec": "", "emoji": e, "game": g} for g, n, e in kids_games.GAMES] \
            if self.conf.get("builtin", "on") != "off" else []
        for title, items in (("Play", games), ("My apps", apps)):
            if not items:
                continue
            col.addWidget(heading(title, ink))
            # Each grid on a widget of its own: a free layout added with addLayout crashed PySide when it closed
            holder = QWidget()
            holder.setAttribute(Qt.WA_TranslucentBackground)
            grid = QGridLayout(holder)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(18)
            for i, app in enumerate(items):
                t = Tile(app, colours[(len(self.tiles)) % len(colours)])
                t.clicked.connect(lambda _c=False, a=app: self.launch(a))
                grid.addWidget(t, i // self.cols, i % self.cols)
                self.tiles.append(t)
            grid.setColumnStretch(self.cols, 1)
            col.addWidget(holder)
        if not apps:
            empty = QLabel("Ask a grown-up to add your apps in DecKoOS Hub.")
            empty.setStyleSheet(f"font-size: 15pt; color: {ink}; background: transparent;")
            col.addWidget(empty)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_holder)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
                             "QScrollBar:vertical { background: transparent; width: 10px; }"
                             "QScrollBar::handle:vertical { background: rgba(255, 255, 255, 110); border-radius: 5px; "
                             "min-height: 40px; }"
                             "QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page "
                             "{ background: none; height: 0; }")
        v.addWidget(scroll, 1)

        if self.tiles:
            self.tiles[0].setFocus()
        # The scene moves a few times a second, and only while this window is the one on screen
        self.anim = QTimer(self, interval=160, timeout=self.animate)
        if not DEMO:
            self.anim.start()
        # A controller works like the arrow keys and Enter: from the couch, no mouse needed
        self.pad = Pad()
        self.pad.key.connect(self.pad_key)
        if not DEMO:
            self.pad.start()
        self.cap = int(self.conf.get("volume") or 100) / 100
        if self.cap < 1 and not DEMO:
            # Volume changes as they happen (pactl subscribe), not polling: anything over the cap goes back to it
            self.volume = QProcess(self)
            self.volume.readyReadStandardOutput.connect(self.volume_changed)
            self.volume.start("pactl", ["subscribe"])
            self.volume_changed()
        self.ended = False
        self.leaving = False  # logging out: let the window close, or Plasma says an app is blocking the logout
        QApplication.instance().commitDataRequest.connect(self.session_ending)
        self.tick()
        # The time service (root) counts the minutes; this only shows them
        self.timer = QTimer(self, timeout=self.tick, interval=30_000)
        self.timer.start()

    @staticmethod
    def greeting():
        h = time.localtime().tm_hour
        return "Good morning" if 5 <= h < 12 else "Good afternoon" if h < 17 else "Good evening" if h < 22 else "Hi"

    def animate(self):
        if self.stack.currentIndex() == 0 and self.isActiveWindow() and not self.isMinimized():
            self.frame += 1
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        self.scene.paint(p, QRectF(self.rect()), self.frame)

    def volume_changed(self):
        if hasattr(self, "volume"):
            out = bytes(self.volume.readAllStandardOutput()).decode(errors="replace")
            if out and "sink" not in out:
                return
        r = QProcess()
        r.start("wpctl", ["get-volume", "@DEFAULT_AUDIO_SINK@"])
        r.waitForFinished(2000)
        m = re.search(r"Volume: ([\d.]+)", bytes(r.readAllStandardOutput()).decode())
        if m and float(m.group(1)) > self.cap + 0.005:
            QProcess.execute("wpctl", ["set-volume", "@DEFAULT_AUDIO_SINK@", f"{self.cap:.2f}"])

    def pad_key(self, key):
        if not self.isActiveWindow():  # not while an app has the controller
            return
        if self.stack.currentIndex() > 0:  # one of DecKoOS's own games is open: it takes the keys
            game = self.stack.currentWidget()
            game.back.emit() if key == Qt.Key_Escape else game.key(key)
            return
        self.move(key)

    def move(self, key):
        if not self.tiles:
            return
        i = next((n for n, t in enumerate(self.tiles) if t.hasFocus()), 0)
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.tiles[i].click()
            return
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -self.cols, Qt.Key_Down: self.cols}.get(key)
        if step is not None:
            self.tiles[max(0, min(len(self.tiles) - 1, i + step))].setFocus()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.move(e.key())
        else:
            super().keyPressEvent(e)

    def launch(self, app):
        if self.ended:
            return
        if app.get("game"):  # DecKoOS's own games open right here
            game = kids_games.make(app["game"], self.theme["id"])
            game.back.connect(lambda g=game: self.close_game(g))
            self.stack.addWidget(game)
            self.stack.setCurrentWidget(game)
            return
        if DEMO:
            return
        argv = app.get("argv") or shlex.split(app["exec"])
        if argv:
            QProcess.startDetached(argv[0], argv[1:])

    def close_game(self, game):
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(game)
        game.deleteLater()
        if self.tiles:
            self.tiles[0].setFocus()

    def tick(self):
        used = 20.0 if DEMO else kids.minutes_used(self.state)
        left = kids.time_left(self.conf, used)
        if left is None:
            self.ring.set(None, "😊")
            return
        total = max(1.0, float(self.conf.get("minutes") or 0) or left)
        self.ring.set(left / total, f"{int(left)}m" if left >= 1 else "0")
        if 0 < left <= 5:
            self.banner.setText(f"{int(left) or 1} more minute{'s' if left >= 2 else ''}: time to finish up!")
            self.banner.show()
        if left <= 0 and not self.ended:
            self.ended = True
            self.banner.setText("Time's up for today! Saving and logging out in a minute.")
            self.banner.show()
            if not DEMO:  # the time service ends the session; this is in case it isn't running
                QTimer.singleShot(150_000, self.finish)

    def session_ending(self, *_):
        self.leaving = True

    def finish(self):
        if DEMO:
            return
        self.leaving = True
        # Log out without asking: back to the login screen, where a grown-up's password brings their session back
        QProcess.startDetached("qdbus6", ["org.kde.Shutdown", "/Shutdown", "logout"])

    def closeEvent(self, e):
        if not DEMO and not self.leaving:  # it's the child's desktop: minimise instead of going away
            e.ignore()
            self.showMinimized()


# What a child's panels may hold: the kid taskbar (their tiles and windows), volume and the clock. A menu or
# anything else would open apps the parent didn't approve.
KID_WIDGETS = {"org.deckos.taskbar", "org.kde.plasma.volume", "org.kde.plasma.digitalclock"}


def panel_widgets():
    """[[widget plugin, …] per panel], or None while the desktop shell isn't answering."""
    p = QProcess()
    p.start("qdbus6", ["org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
                       "panels().forEach(function (p) { print(p.widgets().map(function (w) { return w.type; })"
                       ".join(',') + '\\n'); });"])
    if not p.waitForFinished(10000) or p.exitCode() != 0:
        return None
    return [ln.split(",") for ln in bytes(p.readAllStandardOutput()).decode().splitlines() if ln.strip()]


def kid_panels_ok(panels):
    """Every panel holds only what a child may use, and there is one (their tiles are on it)."""
    return bool(panels) and all(set(w) <= KID_WIDGETS for w in panels)


def first_login():
    """The child's panels, checked at every login: the kid taskbar, volume and a clock, no menu (it would show
    every app). New children start with it (their look, org.deckos.kids); anything else found is replaced."""
    # This starts with the session, often before the desktop shell is ready: wait for it (up to 30 s)
    panels = None
    for _ in range(30):
        panels = panel_widgets()
        if panels is not None:
            break
        time.sleep(1)
    if panels is not None and not kid_panels_ok(panels):
        QProcess.execute("deckos", ["layout", "set", "kids"])


def main():
    if DEMO:  # the real icons on any machine that has the theme (offscreen renders have no theme set)
        QIcon.setThemeName("Papirus")
    app = QApplication(sys.argv)
    app.setApplicationName("Kid mode")
    app.setDesktopFileName("deckos-kids")
    app.setFont(QFont("Inter", 11))
    app.setStyleSheet(S.qss())
    w = KidMode()
    if "--screenshot" in sys.argv:
        w.resize(1280, 800)
        w.show()
        out = sys.argv[sys.argv.index("--screenshot") + 1]
        QTimer.singleShot(600, lambda: (w.grab().save(out), app.exit(0)))
    elif "--session" in sys.argv:
        first_login()
        w.showMaximized()
    else:
        w.resize(1280, 800)
        w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
