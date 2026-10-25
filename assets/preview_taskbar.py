"""Renders DeckOS Taskbar without Plasma: the real plasmoid QML on stand-ins for Plasma's modules
(assets/preview_taskbar/) and canned apps, as the dock (icons) and the Classic panel (titles) over the
wallpaper. Also catches QML errors.
    python assets/preview_taskbar.py [out.png]
App icons are stand-ins (coloured tiles); the real taskbar uses your icon theme's.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QUrl, qInstallMessageHandler
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtQuick import QQuickImageProvider, QQuickView
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "pkg/deckos-settings/rootfs/usr/share"
MAIN = SHARE / "plasma/plasmoids/org.deckos.taskbar/contents/ui/main.qml"

# icon: (DeckOS line icon, tile colour)
ICONS = {"dolphin": ("folder", "#2563EB"), "terminal": ("terminal", "#1F2937"), "firefox": ("globe", "#C2410C"),
         "steam": ("gaming", "#1E3A5F"), "deckos": ("system", "#4C5BD4"), "code": ("code", "#1D6FB8"),
         "discord": ("music", "#5865F2"), "kate": ("doc", "#0E7490")}


def app(name, icon, title="", launcher=False, active=False, windows=1, attention=False, starting=False):
    return dict(AppName=name, decoration=icon, display=title or name, GenericName="", IsLauncher=launcher,
                IsStartup=starting, IsActive=active, IsGroupParent=windows > 1, ChildCount=windows,
                IsDemandingAttention=attention, IsMinimized=False, CanLaunchNewInstance=True, IsClosable=True,
                LauncherUrlWithoutIcon=f"applications:{icon}.desktop")


APPS = [app("Files", "dolphin", "Downloads — DeckOS Files"),
        app("DeckOS Terminal", "terminal", launcher=True),
        app("Firefox", "firefox", "DeckOS 0.7.0 release — Mozilla Firefox", active=True, windows=3),
        app("Steam", "steam"),
        app("DeckOS Hub", "deckos", launcher=True),
        app("VS Code", "code", "Task.qml — deckos — Visual Studio Code", windows=2),
        app("Discord", "discord", "#general — Discord", attention=True),
        app("Kate", "kate", starting=True)]


class AppIcons(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, ident, size, req):
        line, colour = ICONS.get(ident, ("grid", "#334155"))
        s = req.width() if req.isValid() and req.width() > 0 else 96
        img = QImage(QSize(s, s), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(colour))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, s, s, s * 0.22, s * 0.22)
        svg = SHARE / f"deckos/icons/{line}.svg"
        if svg.exists():
            QSvgRenderer(svg.read_text().replace("#000", "#FFFFFF").encode()).render(
                p, QRect(s // 5, s // 5, s - 2 * (s // 5), s - 2 * (s // 5)))
        p.end()
        return img


def render(labels, size):
    view = QQuickView()
    engine = view.engine()
    engine.addImportPath(str(Path(__file__).resolve().parent / "preview_taskbar"))
    engine.addImageProvider("app", AppIcons())
    engine.rootContext().setContextProperty("previewLabels", labels)
    engine.rootContext().setContextProperty("previewApps", APPS)
    view.setColor(Qt.transparent)
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.resize(size)
    view.setSource(QUrl.fromLocalFile(str(MAIN)))
    if view.status() == QQuickView.Error:
        for e in view.errors():
            print(e.toString())
        sys.exit(1)
    view.show()
    QGuiApplication.processEvents()
    return view.grabWindow()


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets/taskbar-preview.png"
    errors = []
    qInstallMessageHandler(lambda _m, _c, msg: errors.append(msg))
    app_ = QGuiApplication(sys.argv)  # noqa: F841
    dock, classic = render(False, QSize(8 * 54, 52)), render(True, QSize(1240, 44))

    scene = QImage(1280, 260, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(scene)
    p.setRenderHint(QPainter.Antialiasing)
    scene.fill(QColor("#0F1115"))
    wall = QSvgRenderer(str(SHARE / "deckos/branding/wallpaper.svg"))
    if wall.isValid():
        wall.setViewBox(QRect(0, 340, 1920, 390))  # a band through the middle
        wall.render(p)
    p.setPen(QPen(QColor("#262B36"), 1))
    p.setBrush(QColor(23, 26, 33, 242))
    dx = (1280 - dock.width() - 24) // 2
    p.drawRoundedRect(dx, 40, dock.width() + 24, 54, 14, 14)
    p.drawImage(dx + 12, 42, dock)
    p.drawRect(-1, 260 - 46, 1282, 47)
    p.drawImage(20, 260 - 45, classic)
    p.end()
    scene.save(str(out))
    print("->", out)
    for e in errors:
        print("QML:", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
