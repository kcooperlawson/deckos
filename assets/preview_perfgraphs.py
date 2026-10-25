"""Renders DecKoOS Performance without Plasma: the real plasmoid QML on stand-ins
(assets/preview_perfgraphs/: plasmoid, and a sensor module that plays a minute of desktop, then a game
starting at 22 s and a download every 17 s) over the wallpaper. Also catches QML errors.
    python assets/preview_perfgraphs.py [out.png]
"""
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QRect, QSize, Qt, QUrl, Signal, qInstallMessageHandler
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtQuick import QQuickView
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "pkg/deckos-settings/rootfs/usr/share"
MAIN = SHARE / "plasma/plasmoids/org.deckos.perfgraphs/contents/ui/main.qml"


class Clock(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._t = 0.0

    def get(self):
        return self._t

    def set(self, t):
        self._t = t
        self.changed.emit()

    t = Property(float, get, set, notify=changed)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets/perfgraphs-preview.png"
    errors = []
    qInstallMessageHandler(lambda _m, _c, msg: errors.append(msg))
    app = QGuiApplication(sys.argv)  # noqa: F841
    clock = Clock()
    view = QQuickView()
    view.engine().addImportPath(str(Path(__file__).resolve().parent / "preview_perfgraphs"))
    view.rootContext().setContextProperty("previewClock", clock)
    view.setColor(Qt.transparent)
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(MAIN)))
    if view.status() == QQuickView.Error:
        for e in view.errors():
            print(e.toString())
        sys.exit(1)
    root = view.rootObject()
    view.resize(QSize(340, int(root.property("Layout.preferredHeight") or 470)))
    view.show()
    for i in range(60):  # a minute of samples
        clock.t = float(i)
        root.tick.emit()
        QGuiApplication.processEvents()
    widget = view.grabWindow()

    scene = QImage(widget.width() + 120, widget.height() + 120, QImage.Format_ARGB32_Premultiplied)
    scene.fill(QColor("#0F1115"))
    p = QPainter(scene)
    wall = QSvgRenderer(str(SHARE / "deckos/branding/wallpaper.svg"))
    if wall.isValid():
        wall.setViewBox(QRect(1300, 80, scene.width() * 2, scene.height() * 2))
        wall.render(p)
    p.drawImage(60, 60, widget)
    p.end()
    scene.save(str(out))
    print("->", out)
    for e in errors:
        print("QML:", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
