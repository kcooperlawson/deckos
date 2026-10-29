"""DecKoOS's tour: what's here and where it lives, one picture at a time, each with a button to try it. From DecKoOS
Welcome (its first and last steps), the Hub's Home, the app menu (`deckos-tour`) and the live USB. Pictures come
from usr/share/deckos/tour (assets/tour_images.py makes them).

    deckos-tour [--demo] [--screenshot DIR]     arrows or the buttons move, Esc closes
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "hub")]
from PySide6.QtCore import QProcess, QRectF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget  # noqa: E402
import hub_style as S  # noqa: E402
from hub_widgets import button, label  # noqa: E402

PICTURES = Path("/usr/share/deckos/tour")
_CHECKOUT = HERE.parents[2] / "share/deckos/tour"  # running from a checkout: rootfs/usr/lib/deckos/welcome
# (picture, title, what it is, button text, command): the command is what the button starts; "" for none
SLIDES = [
    ("desktop", "Welcome to DecKoOS",
     "A desktop made for playing, making and listening. This tour takes a minute: each stop shows where something "
     "lives, with a button to try it.", "", []),
    ("menu", "Everything starts here",
     "The menu finds apps, files and settings as you type, and DecKoOS's own actions too: type \"backup\", "
     "\"undo\" or \"gaming mode\".", "", []),
    ("quicksettings", "Quick Settings",
     "Wi-Fi, sound, brightness, Do Not Disturb and Gaming Mode in one place, plus what DecKoOS thinks you're doing "
     "right now. Correct it there if it's wrong.", "", []),
    ("hub", "DecKoOS Hub: your PC in one place",
     "Live stats, updates, snapshots, drives and every setting. If you're looking for a setting, it's here; "
     "Ctrl+F searches all of them.", "Open the Hub", ["deckos-hub"]),
    ("vibes", "Vibes",
     "A whole mood in one click: a living wallpaper on a real photo that moves with your music, matching colours, "
     "sounds and widgets. Or make one from your own photo.", "Pick a Vibe", ["deckos-hub", "--page", "appearance"]),
    ("music", "Vibe mode",
     "Whatever's playing, Spotify included, takes over every screen as one stage. Four looks; press V to switch, "
     "Esc to leave.", "Try Vibe mode", ["deckos-music"]),
    ("games", "All your games, one library",
     "Steam, Heroic, Lutris and games in plain folders, with how well each runs. Game Doctor steps in when one "
     "won't start, and Gaming Mode is Steam full screen, like a Steam Deck.", "See my games",
     ["deckos-hub", "--page", "games"]),
    ("timeline", "Undo almost anything",
     "Every change, yours or DecKoOS's, lands on the timeline with an Undo button. Updates take a snapshot first, "
     "so a bad one is one restart away from gone.", "Open the timeline", ["deckos-hub", "--page", "timeline"]),
    ("assistant", "A local AI that can do things",
     "Meta+Space opens the Assistant. It runs on your graphics card, nothing leaves the PC, and it asks before it "
     "changes anything.", "Ask it something", ["deckos-assistant"]),
    ("sysmon", "See what's running",
     "Ctrl+Shift+Esc opens System Monitor: apps by name, every resource in its own colour. System Doctor explains "
     "problems in plain words, with a fix.", "Open System Monitor", ["deckos-sysmon"]),
    ("files", "Your files",
     "DecKoOS Files and DecKoOS Terminal, in the same look. Your Windows drives are there too, as they are.",
     "Open Files", ["deckos-files"]),
    ("backup", "Before a reinstall",
     "Hub › System › Before a reinstall packs your whole home folder onto another drive, checks it, and puts it all "
     "back afterwards. Welcome finds the backup by itself after you reinstall.", "Show me",
     ["deckos-hub", "--page", "system"]),
]


def picture_dir():
    return PICTURES if PICTURES.is_dir() else _CHECKOUT


class Picture(QWidget):
    """The slide's screenshot, scaled to fit with rounded corners and a thin accent edge."""

    def __init__(self):
        super().__init__()
        self.pm = QPixmap()
        self.setMinimumHeight(320)

    def show_picture(self, path):
        self.pm = QPixmap(str(path))
        self.update()

    def paintEvent(self, _e):
        if self.pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        pm = self.pm.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        r = QRectF((self.width() - pm.width()) / 2, (self.height() - pm.height()) / 2, pm.width(), pm.height())
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.setClipPath(path)
        p.drawPixmap(r.topLeft(), pm)
        p.setClipping(False)
        edge = QColor(S.P.accent)
        edge.setAlpha(120)
        p.setPen(edge)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)


class Tour(QWidget):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.at = 0
        self.setWindowTitle("DecKoOS tour")
        self.setObjectName("tour")
        self.resize(1180, 860)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(14)
        self.count = label("", "muted")
        lay.addWidget(self.count)
        self.picture = Picture()
        lay.addWidget(self.picture, 1)
        self.title = QLabel()
        self.title.setObjectName("hero")
        lay.addWidget(self.title)
        self.text = label("", "sub")
        self.text.setWordWrap(True)
        lay.addWidget(self.text)
        foot = QHBoxLayout()
        self.dots = QLabel()
        foot.addWidget(self.dots)
        foot.addStretch(1)
        self.try_btn = button("", slot=self.try_it, icon="external")
        foot.addWidget(self.try_btn)
        self.back = button("Back", slot=lambda: self.go(self.at - 1))
        foot.addWidget(self.back)
        self.next = button("Next", "primary", self.forward)
        foot.addWidget(self.next)
        lay.addLayout(foot)
        self.setStyleSheet(S.qss() + '#tour { background: %s; } QLabel#hero { font-family: "Inter Display", '
                           '"Inter"; font-size: 22pt; font-weight: 600; }' % S.BG)
        self.go(0)

    def go(self, i):
        self.at = max(0, min(len(SLIDES) - 1, i))
        pic, title, text, try_text, _cmd = SLIDES[self.at]
        self.picture.show_picture(picture_dir() / f"{pic}.jpg")
        self.title.setText(title)
        self.text.setText(text)
        self.count.setText(f"TOUR · {self.at + 1} OF {len(SLIDES)}")
        self.try_btn.setText(try_text.replace("&", "&&"))
        self.try_btn.setVisible(bool(try_text))
        self.back.setEnabled(self.at > 0)
        self.next.setText("Done" if self.at == len(SLIDES) - 1 else "Next")
        dot = lambda on: f"<span style='color:{S.P.accent if on else S.BORDER}'>●</span>"  # noqa: E731
        self.dots.setText(" ".join(dot(n == self.at) for n in range(len(SLIDES))))

    def forward(self):
        if self.at == len(SLIDES) - 1:
            self.close()
        else:
            self.go(self.at + 1)

    def try_it(self):
        cmd = SLIDES[self.at][4]
        if cmd and not self.demo:
            QProcess.startDetached(cmd[0], cmd[1:])

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Right, Qt.Key_Space, Qt.Key_PageDown):
            self.forward()
        elif e.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.go(self.at - 1)
        elif e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


def main(argv):
    app = QApplication.instance() or QApplication(argv)
    app.setDesktopFileName("deckos-tour")
    S.load_style()
    tour = Tour(demo="--demo" in argv)
    tour.show()
    if "--screenshot" in argv:
        out = Path(argv[argv.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)

        def shoot(n=0):
            tour.go(n)
            QTimer.singleShot(150, lambda: (tour.grab().save(str(out / f"tour-{n + 1:02}.png")),
                                            shoot(n + 1) if n + 1 < len(SLIDES) else app.quit()))
        QTimer.singleShot(300, shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
