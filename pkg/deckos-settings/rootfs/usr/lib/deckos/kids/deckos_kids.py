"""Kid mode's desktop: big tiles for the apps a parent approved, the time left (when there's a limit) and "I'm done".
Starts at login in a child's account (`deckos-kids --session`, from the autostart kids.py writes). Counts the
minutes used today and, at the end of the time, says so kindly and logs out.

    deckos-kids --session | --demo [--screenshot FILE]
"""
import os
import pwd
import shlex
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath
from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]
import hub_style as S  # noqa: E402
import kids  # noqa: E402

DEMO = "--demo" in sys.argv
# Bright, friendly tile colours (one per tile, in turn)
COLOURS = ["#FF7A59", "#4C8DFF", "#3DD68C", "#F5B84B", "#B36BFF", "#FF5C9A", "#22C7B8", "#7A5CFF"]
DEMO_TILES = [{"name": n, "icon": i, "exec": ""} for n, i in (
    ("Paint", "kolourpaint"), ("Tux Paint", "tuxpaint"), ("GCompris", "gcompris-qt"), ("Potato Guy", "ktuberling"),
    ("Blocks", "kblocks"), ("Cards", "kpat"), ("Letters", "klettres"), ("The web", "firefox"))]


class Tile(QPushButton):
    """A big rounded tile: the app's icon on a bright colour, its name underneath."""

    def __init__(self, app, colour):
        super().__init__()
        self.app, self.colour = app, QColor(colour)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(220, 220)
        self.icon_ = QIcon.fromTheme(app["icon"]) if app["icon"] and not app["icon"].startswith("/") \
            else QIcon(app["icon"])
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(6, 6, -6, -6)
        path = QPainterPath()
        path.addRoundedRect(r, S.corner(28), S.corner(28))
        c = self.colour.lighter(112) if self.underMouse() or self.hasFocus() else self.colour
        p.fillPath(path, c)
        if self.hasFocus():
            p.setPen(QColor("#FFFFFF"))
            p.drawPath(path)
        pm = self.icon_.pixmap(QSize(104, 104))
        if not pm.isNull():
            p.drawPixmap(r.center().x() - 52, r.top() + 26, pm)
        else:
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Inter Display", 54, QFont.Bold))
            p.drawText(r.adjusted(0, 0, 0, -50), Qt.AlignCenter, self.app["name"][:1])
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Inter Display", 16, QFont.DemiBold))
        p.drawText(r.adjusted(10, 0, -10, -18), Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, self.app["name"])


class KidMode(QWidget):
    def __init__(self):
        super().__init__()
        self.name = "mia" if DEMO else pwd.getpwuid(os.getuid()).pw_name
        self.conf = ({**kids.DEFAULTS, "display": "Mia", "minutes": "60"} if DEMO
                     else kids.read_conf(self.name) or {**kids.DEFAULTS, "display": self.name.title()})
        self.state = kids.state_file(self.name)
        self.setWindowTitle("Kid mode")
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(48, 36, 48, 36)
        v.setSpacing(24)

        head = QHBoxLayout()
        hello = QLabel(f"Hi {self.conf['display'] or self.name.title()}!")
        hello.setStyleSheet("font-family: 'Inter Display'; font-size: 34pt; font-weight: 700;")
        head.addWidget(hello, 1)
        self.clock = QLabel()
        self.clock.setStyleSheet(f"font-size: 15pt; color: {S.SUBTEXT}; padding: 8px 16px; "
                                 f"background: {S.SURFACE}; border-radius: 18px;")
        head.addWidget(self.clock)
        done = QPushButton("  I'm done")
        done.setIcon(S.icon("log-out", "#FFFFFF", 22))
        done.setIconSize(QSize(22, 22))
        done.setObjectName("primary")
        done.setStyleSheet("font-size: 15pt; padding: 12px 22px;")
        done.clicked.connect(self.finish)
        head.addWidget(done)
        v.addLayout(head)

        self.banner = QLabel()
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setStyleSheet(f"font-size: 17pt; padding: 16px; border-radius: 16px; background: {S.SURFACE}; "
                                  f"color: {S.WARNING};")
        self.banner.hide()
        v.addWidget(self.banner)

        grid_holder = QWidget()
        grid = QGridLayout(grid_holder)
        grid.setSpacing(18)
        tiles = DEMO_TILES if DEMO else kids.approved(self.name)
        if not tiles:
            empty = QLabel("No apps yet. Ask a grown-up to pick some in DecKoOS Hub.")
            empty.setStyleSheet(f"font-size: 18pt; color: {S.SUBTEXT};")
            grid.addWidget(empty, 0, 0)
        for i, app in enumerate(tiles):
            t = Tile(app, COLOURS[i % len(COLOURS)])
            t.clicked.connect(lambda _c=False, a=app: self.launch(a))
            grid.addWidget(t, i // 5, i % 5)
        grid.setColumnStretch(5, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_holder)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.addWidget(scroll, 1)

        self.ended = False
        self.tick()
        self.timer = QTimer(self, timeout=lambda: self.tick(add=1.0), interval=60_000)
        self.timer.start()

    def launch(self, app):
        if DEMO or self.ended:
            return
        argv = shlex.split(app["exec"])
        if argv:
            QProcess.startDetached(argv[0], argv[1:])

    def tick(self, add=0.0):
        if add and not DEMO:
            kids.add_minutes(self.state, add)
        used = 20.0 if DEMO else kids.minutes_used(self.state)
        left = kids.time_left(self.conf, used)
        if left is None:
            self.clock.setText("Have fun!")
            return
        self.clock.setText(f"{int(left)} min left" if left >= 1 else "Time's up")
        if 0 < left <= 5:
            self.banner.setText(f"{int(left) or 1} more minute{'s' if left >= 2 else ''}: time to finish up!")
            self.banner.show()
        if left <= 0 and not self.ended:
            self.ended = True
            self.banner.setText("Time's up for today! Saving and logging out in a minute.")
            self.banner.show()
            if not DEMO:
                QTimer.singleShot(60_000, self.finish)

    def finish(self):
        if DEMO:
            return
        # Log out without asking: back to the login screen, where a grown-up's password brings their session back
        QProcess.startDetached("qdbus6", ["org.kde.Shutdown", "/Shutdown", "logout"])

    def closeEvent(self, e):
        if not DEMO:  # it's the child's desktop: minimise instead of going away
            e.ignore()
            self.showMinimized()


def first_login():
    """The child's panel: a taskbar and a clock, no menu (it would show every app). Once, then it's theirs."""
    mark = Path.home() / ".config/deckos/kids-layout-done"
    if mark.exists():
        return
    if QProcess.execute("deckos", ["layout", "set", "kids"]) == 0:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.touch()


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
