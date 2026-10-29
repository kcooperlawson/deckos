"""Loads DecKoOS's desktop widgets (Now Playing, Clock, Weather, Focus, Note) for real, without Plasma: their QML on
stand-ins for the Plasma-only modules (assets/preview_widgets/: the plasmoid host, a Spotify-like player, the command
runner), with Kirigami and DecKoOS's own look module as they are. Any QML error fails it (exit 1): a widget Plasma
can't load shows nothing at all on the desktop. Then it draws each Vibe's set over its scene's photo into
assets/widgets-preview-VIBE.png.
    python assets/preview_widgets.py [--check]
"""
import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtQuick import QQuickView, QQuickWindow, QSGRendererInterface

ROOT = Path(__file__).resolve().parent.parent
RFS = ROOT / "pkg/deckos-settings/rootfs"
WIDGETS = RFS / "usr/share/plasma/plasmoids"
WALL = RFS / "usr/share/plasma/wallpapers/org.deckos.vibe/contents/images"
sys.path.insert(0, str(RFS / "usr/lib/deckos/vibes"))
import vibes  # noqa: E402

# id: (extra settings, size)
WIDGET = {
    "org.deckos.bigclock": ({"name": "Keagan", "seconds": False}, (460, 250)),
    "org.deckos.nowplaying": ({}, (404, 216)),
    "org.deckos.weather": ({"place": "Lisbon", "latitude": 38.72, "longitude": -9.14, "fahrenheit": False},
                           (300, 128)),
    "org.deckos.focus": ({"workMinutes": 25, "breakMinutes": 5}, (220, 240)),
    "org.deckos.note": ({"text": ""}, (300, 180)),
    "org.deckos.calendar": ({"mondayFirst": True}, (300, 280)),
    "org.deckos.countdown": ({"title": "Holiday", "date": "2026-12-24"}, (260, 170)),
    "org.deckos.photos": ({"folder": str(WALL), "minutes": 5}, (360, 240)),
}
errors = []


class Player(QObject):
    """A Spotify-like player halfway through a song, shaped like Plasma's MPRIS PlayerContainer."""
    changed = Signal()

    def __init__(self, art):
        super().__init__()
        self._art = art

    playbackStatus = Property(int, lambda s: 2, notify=changed)  # Playing
    track = Property(str, lambda s: "Midnight City", notify=changed)
    artist = Property(str, lambda s: "M83", notify=changed)
    artUrl = Property(str, lambda s: s._art, notify=changed)
    position = Property(float, lambda s: 132_000_000.0, notify=changed)
    length = Property(float, lambda s: 244_000_000.0, notify=changed)

    @Slot()
    def updatePosition(self):
        pass

    @Slot()
    def PlayPause(self):
        pass

    @Slot()
    def Next(self):
        pass

    @Slot()
    def Previous(self):
        pass


def main():
    # Software only without a screen: it can't draw Shapes or effects, which the DecKo look is made of
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        QQuickWindow.setGraphicsApi(QSGRendererInterface.Software)
    qInstallMessageHandler(lambda mode, ctx, msg: errors.append(msg) if "rror" in msg or "is not a type" in msg
                           or "not installed" in msg or "ReferenceError" in msg or "TypeError" in msg else None)
    app = QGuiApplication(sys.argv)
    shots = {}
    styles = ["deckos"] + list(vibes.VIBES)
    art = QUrl.fromLocalFile(str(WALL / "cozy.jpg")).toString()  # any picture will do as album art
    views = []
    player = Player(art)
    for style in styles:
        v = vibes.VIBES.get(style, {"colorA": "#4C8DFF", "colorB": "#7A5CFF"})
        for wid, (extra, size) in WIDGET.items():
            view = QQuickView()
            view.setColor(QColor(0, 0, 0, 0))
            eng = view.engine()
            eng.addImportPath(str(Path(__file__).resolve().parent / "preview_widgets"))  # stand-ins first
            eng.addImportPath(str(RFS / "usr/lib/qt6/qml"))
            view.rootContext().setContextProperty("previewConfig", {"style": style, "colorA": v["colorA"],
                                                                     "colorB": v["colorB"], **extra})
            view.rootContext().setContextProperty("previewPlayer", player)
            view.setSource(QUrl.fromLocalFile(str(WIDGETS / wid / "contents/ui/main.qml")))
            if view.status() == QQuickView.Error:
                errors.extend(f"{wid}: {e.toString()}" for e in view.errors())
                continue
            view.resize(*size)
            view.show()
            views.append((style, wid, view))

    def shoot():
        for style, wid, view in views:
            shots.setdefault(style, {})[wid] = view.grabWindow()
        if "--check" not in sys.argv:
            compose(shots)
        app.quit()
    QTimer.singleShot(1500, shoot)
    app.exec()
    if errors:
        print("QML problems:\n  " + "\n  ".join(dict.fromkeys(errors)))
        return 1
    print(f"all {len(WIDGET)} widgets load in {len(styles)} styles")
    return 0


def compose(shots):
    """Each Vibe's set on its scene's photo (Neon has no photo: its night-sky colours), like a desktop."""
    for style, imgs in shots.items():
        canvas = QImage(1920, 1080, QImage.Format_RGB32)
        photo = WALL / f"{style}.jpg"
        canvas.fill(QColor("#140B2E" if style == "neon" else "#0F1115"))
        p = QPainter(canvas)
        if photo.exists():
            p.drawImage(canvas.rect(), QImage(str(photo)))
            p.fillRect(canvas.rect(), QColor(0, 0, 0, 60))
        spots = {"org.deckos.bigclock": (80, 70), "org.deckos.nowplaying": (1420, 860),
                 "org.deckos.weather": (1540, 80), "org.deckos.focus": (1600, 560), "org.deckos.note": (90, 820),
                 "org.deckos.calendar": (620, 80), "org.deckos.countdown": (980, 80), "org.deckos.photos": (620, 420)}
        for wid, img in imgs.items():
            p.drawImage(*spots[wid], img)
        p.end()
        out = Path(__file__).resolve().parent / f"widgets-preview-{style}.png"
        canvas.save(str(out))
        print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
