"""Renders the DecKoOS Vibe wallpaper's scenes without Plasma: each scene QML with the visualizer on top, fed made-up
levels (no audio, no WebSocket), into assets/vibe-preview-SCENE.png, and the small previews DecKoOS Hub's Vibe
tiles show (the wallpaper package's contents/previews/KEY.jpg, committed). Colours are each Vibe's from vibes.py.
    python assets/preview_vibes.py [SCENE...]
"""
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView, QQuickWindow, QSGRendererInterface

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "pkg/deckos-settings/rootfs/usr/share/plasma/wallpapers/org.deckos.vibe/contents/ui"
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/vibes"))
import vibes  # noqa: E402

QML = """
import QtQuick
Item {
    width: 1920; height: 1080
    Loader { anchors.fill: parent; source: "%(scene)s"
             onLoaded: { item.colorA = "%(a)s"; item.colorB = "%(b)s"; item.running = true;
                         // a made-up song mid-chorus: the scenes react to it themselves
                         item.bass = 0.75; item.mid = 0.6; item.high = 0.5; item.energy = 0.7;
                         if ("levels" in item) item.levels = %(levels)s; } }
    Visualizer { id: vis; anchors.fill: parent; style: "%(style)s"; visible: %(overlay)s
                 colorA: "%(a)s"; colorB: "%(b)s"; levels: %(levels)s }
}
"""


def main():
    want = [a for a in sys.argv[1:] if not a.startswith("-")] or list(vibes.VIBES)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.Software)
    app = QGuiApplication(sys.argv)
    # A made-up song: bass heavy, falling off towards the treble
    levels = [round(max(0.05, 0.9 * math.exp(-i / 18) + 0.25 * abs(math.sin(i * 0.7))), 2) for i in range(48)]
    views = []
    for key in want:
        v = vibes.VIBES[key]
        qml = UI / f".preview-{key}.qml"
        qml.write_text(QML % {"scene": v["scene"].title() + "Scene.qml", "a": v["colorA"], "b": v["colorB"],
                              "style": v["visualizer"] if v["visualizer"] != "none" else "bars",
                              "overlay": "true" if v["visualizer"] != "none" else "false", "levels": levels})
        view = QQuickView()
        view.setSource(QUrl.fromLocalFile(str(qml)))
        view.show()
        views.append((key, view, qml))

    def shoot():
        for key, view, qml in views:
            out = Path(__file__).resolve().parent / f"vibe-preview-{key}.png"
            img = view.grabWindow()
            img.save(str(out))
            small = UI.parent / "previews" / f"{key}.jpg"
            small.parent.mkdir(exist_ok=True)
            img.scaledToWidth(464, Qt.SmoothTransformation).save(str(small), quality=85)
            qml.unlink()
            print("wrote", out)
        app.quit()
    QTimer.singleShot(2500, shoot)  # let the animations run a little
    app.exec()


if __name__ == "__main__":
    main()
