"""Renders DecKoOS Quick Settings without Plasma: the real plasmoid QML, with stand-ins for the Plasma
modules it imports (assets/qml-stubs: Wi-Fi, Bluetooth, sound, brightness, media… with demo data),
over the DecKoOS wallpaper with the panel button below the popup. Also catches QML errors.
    python assets/preview_quicksettings.py [out.png]
"""
import sys
from enum import IntEnum
from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import (Property, QAbstractListModel, QEnum, QModelIndex, QObject, QSize, Qt, QTimer, QUrl, Signal,
                            Slot, qInstallMessageHandler)
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtQml import QQmlComponent, qmlRegisterType, qmlRegisterUncreatableType
from PySide6.QtQuick import QQuickImageProvider, QQuickView, QQuickWindow, QSGRendererInterface
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "pkg/deckos-settings/rootfs/usr/share"
UI = SHARE / "plasma/plasmoids/org.deckos.quicksettings/contents/ui"
STUBS = ROOT / "assets/qml-stubs"

# What `deckos quick-status` / `deckos updates` would print.
DEMO_COMMANDS = {
    "deckos quick-status": "display=1\ngaming=1\nfirewall=1\nauto=1\nmode=normal\nactivity=developing\nlabel=Developing\nicon=code\nwhy=cargo running; working in code\npinned=0\nctxon=1\nrepo=11\naur=1\nchecked=9999999999\n",
    "deckos updates": "repo=11\naur=1\nchecked=9999999999\n",
}

HARNESS = """
import QtQuick
Rectangle {
    width: 1280; height: 900
    color: "black"
    Image { anchors.fill: parent; source: wallpaper; fillMode: Image.PreserveAspectCrop }
    Backend { id: backend; expanded: true }
    Rectangle {  // the popup frame Plasma's dialog background draws
        x: parent.width - width - 40; y: parent.height - height - 90
        width: popup.width + 24; height: popup.height + 24
        radius: 14; color: "#0F1115"; border.color: "#262B36"
        FullRepresentation { id: popup; x: 12; y: 12; width: implicitWidth; backend: backend }
    }
    Rectangle {  // a piece of the dock with the panel button
        x: parent.width - 220; y: parent.height - 66; width: 180; height: 52
        radius: 14; color: "#171A21"; border.color: "#262B36"
        CompactRepresentation { x: 64; y: 4; width: 44; height: 44; backend: backend; expanded: true }
    }
}
"""


# The stand-ins QML can't express (uppercase methods, a property called "default") are Python types.

def prop(kind, name, default):
    """A notifying read/write Python property."""
    attr, sig = "_" + name, Signal()

    def get(self):
        return getattr(self, attr, default)

    def put(self, value):
        setattr(self, attr, value)
        getattr(self, name + "Changed").emit()
    return sig, Property(kind, get, put, notify=sig)


class Sink(QObject):
    descriptionChanged, description = prop(str, "description", "")
    volumeChanged, volume = prop(float, "volume", 0.0)
    mutedChanged, muted = prop(bool, "muted", False)
    defaultChanged, default = prop(bool, "default", False)

    def __init__(self, description, volume, default=False):
        super().__init__()
        self.description, self.volume, self.default = description, volume, default


class PulseObjectFilterModel(QAbstractListModel):
    """org.kde.plasma.private.volume: two outputs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sinks = [Sink("Speakers (Radeon HDMI)", 42000, True), Sink("Headset", 30000)]
        for s in self.sinks:
            s.defaultChanged.connect(lambda s=s: s.default and [o.setProperty("default", False)
                                                                  for o in self.sinks if o is not s])

    def rowCount(self, parent=QModelIndex()):
        return len(self.sinks)

    def roleNames(self):
        return {Qt.UserRole: b"PulseObject"}

    def data(self, index, role=Qt.DisplayRole):
        return self.sinks[index.row()] if role == Qt.UserRole else None

    countChanged = Signal()
    count = Property(int, lambda self: len(self.sinks), notify=countChanged)
    sourceModel = Property(QObject, lambda self: None, lambda self, v: None)
    filterOutInactiveDevices = Property(bool, lambda self: True, lambda self, v: None)
    filterVirtualDevices = Property(bool, lambda self: True, lambda self, v: None)


class SinkModel(QObject):
    pass


class PlaybackStatus(QObject):
    @QEnum
    class Status(IntEnum):
        Unknown, Stopped, Playing, Paused = range(4)


class Player(QObject):
    playbackStatusChanged, playbackStatus = prop(int, "playbackStatus", 2)
    positionChanged, position = prop(float, "position", 83e6)
    identity = Property(str, lambda self: "Spotify", constant=True)
    track = Property(str, lambda self: "Midnight City", constant=True)
    artist = Property(str, lambda self: "M83", constant=True)
    artUrl = Property(str, lambda self: QUrl.fromLocalFile(str(SHARE / "deckos/branding/store-logo.svg")).toString(),
                      constant=True)
    length = Property(float, lambda self: 244e6, constant=True)
    canControl = Property(bool, lambda self: True, constant=True)
    canGoNext = Property(bool, lambda self: True, constant=True)
    canGoPrevious = Property(bool, lambda self: True, constant=True)

    @Slot()
    def updatePosition(self):
        pass

    @Slot()
    def Play(self):
        self.playbackStatus = 2

    @Slot()
    def Pause(self):
        self.playbackStatus = 3

    @Slot()
    def Next(self):
        print("next")

    @Slot()
    def Previous(self):
        print("previous")


class Mpris2Model(QObject):
    """org.kde.plasma.private.mpris: one player, Spotify playing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = Player(self)

    currentPlayer = Property(QObject, lambda self: self._player, constant=True)


class DeckIcons(QQuickImageProvider):
    """image://deck/<rrggbb|none>/<url>: /usr/share/deckos/... from the repo, #000 recoloured."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, ident, size, requested):
        color, _, url = ident.partition("/")
        path = unquote(url).replace("file:///usr/share/", "")
        data = (SHARE / path).read_text()
        if color != "none":
            data = data.replace("#000", "#" + color[-6:])
        w = requested.width() if requested.width() > 0 else 48
        h = requested.height() if requested.height() > 0 else 48
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        QSvgRenderer(data.encode()).render(p)
        p.end()
        size.setWidth(w) if hasattr(size, "setWidth") else None
        return img


def main():
    # QML warnings (a missing stand-in, a typo) go to stdout, not the Windows debugger.
    qInstallMessageHandler(lambda _type, _ctx, msg: print(msg))
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "assets/quicksettings-preview.png")
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    app = QGuiApplication(sys.argv)
    qmlRegisterType(PulseObjectFilterModel, "org.kde.plasma.private.volume", 1, 0, "PulseObjectFilterModel")
    qmlRegisterType(SinkModel, "org.kde.plasma.private.volume", 1, 0, "SinkModel")
    qmlRegisterType(Mpris2Model, "org.kde.plasma.private.mpris", 1, 0, "Mpris2Model")
    qmlRegisterUncreatableType(PlaybackStatus, "org.kde.plasma.private.mpris", 1, 0, "PlaybackStatus", "enum")
    view = QQuickView()
    engine = view.engine()
    engine.addImportPath(str(STUBS))
    engine.addImageProvider("deck", DeckIcons())
    ctx = view.rootContext()
    ctx.setContextProperty("demoCommands", DEMO_COMMANDS)
    ctx.setContextProperty("wallpaper", QUrl.fromLocalFile(str(SHARE / "deckos/branding/wallpaper.svg")).toString())
    comp = QQmlComponent(engine)
    comp.setData(HARNESS.encode(), QUrl.fromLocalFile(str(UI / "_preview.qml")))
    root = comp.create(ctx)
    if root is None:
        for e in comp.errors():
            print(e.toString())
        sys.exit(1)
    view.setContent(QUrl.fromLocalFile(str(UI / "_preview.qml")), comp, root)
    view.resize(QSize(1280, 900))
    view.show()

    def shoot():
        view.grabWindow().save(str(out))
        print(f"-> {out}")
        app.quit()
    QTimer.singleShot(1500, shoot)
    app.exec()


if __name__ == "__main__":
    main()
