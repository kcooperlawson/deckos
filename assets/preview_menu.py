"""Renders DeckOS Menu without Plasma: the real plasmoid QML with stand-ins for Plasma's modules
(assets/preview_menu/: plasmoid, Kirigami, plasma5support, KUser) and canned kicker models (below),
over the wallpaper and dock. Store suggestions come from the real store_find.py --demo.
    python assets/preview_menu.py [home|search|apps|all] [out.png]
App icons are stand-ins (coloured tiles); the real menu uses your icon theme's.
"""
import os
import re
import subprocess
import sys
from enum import IntEnum
from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler, Property, QEnum, QAbstractListModel, QModelIndex, QObject, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QImage, QPainter
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuick import QQuickImageProvider, QQuickItem, QQuickView, QQuickWindow, QSGRendererInterface
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "pkg/deckos-settings/rootfs/usr/share"
MENU = SHARE / "plasma/plasmoids/org.deckos.menu/contents/ui/main.qml"
STORE = ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/store"
URI = "org.kde.plasma.private.kicker"

# name: (line icon, tile colour) for the stand-in app icons
ICONS = {"firefox": ("globe", "#C2410C"), "dolphin": ("folder", "#2563EB"), "konsole": ("terminal", "#1F2937"),
         "steam": ("gaming", "#1E3A5F"), "code": ("code", "#1D6FB8"), "deckos": ("system", "#4C5BD4"),
         "deckos-store": ("store", "#6D4BE0"), "settings": ("sliders", "#374151"), "kate": ("doc", "#0E7490"),
         "gwenview": ("image", "#0F766E"), "spectacle": ("display", "#B45309"), "kcalc": ("calculator", "#475569"),
         "heroic": ("play", "#7C3AED"), "kdenlive": ("display", "#1D4ED8"), "haruna": ("play", "#BE185D"),
         "text": ("doc", "#334155"), "video": ("play", "#334155"), "folder": ("folder", "#2563EB"),
         "cyberpunk": ("gaming", "#A16207"), "category": ("grid", "#334155")}

ROLES = ["display", "decoration", "description", "group", "favoriteId", "url", "hasActionList", "actionList",
         "isParent", "hasChildren", "disabled", "isNewlyInstalled"]
APPS = [("Firefox", "firefox", "Web browser", "Internet"), ("Dolphin", "dolphin", "File manager", "System"),
        ("Konsole", "konsole", "Terminal", "System"), ("Steam", "steam", "Games", "Games"),
        ("VS Code", "code", "Code editor", "Development"), ("DeckOS Hub", "deckos", "DeckOS settings", "System"),
        ("DeckOS Store", "deckos-store", "Apps for DeckOS", "System"), ("System Settings", "settings", "", "Settings"),
        ("Kate", "kate", "Text editor", "Development"), ("Gwenview", "gwenview", "Image viewer", "Graphics"),
        ("Spectacle", "spectacle", "Screenshots", "Graphics"), ("KCalc", "kcalc", "Calculator", "Office"),
        ("Heroic", "heroic", "Game launcher", "Games"), ("Kdenlive", "kdenlive", "Video editor", "Multimedia"),
        ("Haruna", "haruna", "Media player", "Multimedia")]


def row(display, icon, desc="", group="", **kw):
    return dict(display=display, decoration=icon, description=desc, group=group, favoriteId=kw.get("fav", ""),
                hasActionList=False, actionList=[], isParent=kw.get("parent", False),
                hasChildren=kw.get("parent", False), disabled=False, isNewlyInstalled=kw.get("new", False))


class Rows(QAbstractListModel):
    """A kicker-style list model; Q_PROPERTYs set from QML are accepted and ignored."""
    countChanged = Signal()
    refreshed = Signal()

    def __init__(self, rows=(), parent=None):
        super().__init__(parent)
        self.rows = list(rows)

    def roleNames(self):
        return {Qt.DisplayRole: b"display", Qt.DecorationRole: b"decoration",
                **{Qt.UserRole + i: r.encode() for i, r in enumerate(ROLES) if r not in ("display", "decoration")}}

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def data(self, index, role):
        name = self.roleNames().get(role, b"").decode()
        return self.rows[index.row()].get(name) if index.isValid() else None

    def reset(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()
        self.countChanged.emit()

    count = Property(int, lambda self: len(self.rows), notify=countChanged)

    @Slot(int, str, "QVariant", result=bool)
    def trigger(self, r, action, arg):
        print("trigger", self.rows[r]["display"], action)
        return True

    @Slot()
    def refresh(self):
        self.refreshed.emit()


def setting(*names, typ="QVariant"):
    """Write-only-ish properties for the settings QML assigns (flat, sorted, appletInterface…)."""
    def make(n):
        return Property(typ, lambda self: getattr(self, "_" + n, None), lambda self, v: setattr(self, "_" + n, v))
    return {n: make(n) for n in names}


class Favorites(Rows):
    enabled = Property(bool, lambda self: True, constant=True)
    maxFavorites = Property(int, lambda self: -1, constant=True)

    @Slot(str)
    def initForClient(self, _c):
        pass

    @Slot("QVariant")
    def portOldFavorites(self, _f):
        pass

    @Slot(str, result=bool)
    def isFavorite(self, fid):
        return any(r["favoriteId"] == fid for r in self.rows)

    @Slot(str)
    def addFavorite(self, fid):
        print("pin", fid)

    @Slot(str)
    def removeFavorite(self, fid):
        print("unpin", fid)

    @Slot(int, int)
    def moveRow(self, a, b):
        print("move", a, b)


RootBase = type("RootBase", (Rows,), setting(
    "autoPopulate", "appletInterface", "appNameFormat", "flat", "sorted", "showSeparators", "showTopLevelItems",
    "showAllApps", "showAllAppsCategorized", "showRecentApps", "showRecentDocs", "showPowerSession",
    "showFavoritesPlaceholder", "showRootSeparator", "highlightNewlyInstalledApps"))


class RootModel(RootBase):
    def __init__(self, parent=None):
        apps = [row(n, i, d, n[0], fav=i + ".desktop", new=(n == "Heroic")) for n, i, d, _c in APPS]
        cats = sorted({c for *_x, c in APPS})
        super().__init__([row("All Applications", "category", parent=True)] +
                         [row(c, "category", parent=True) for c in cats], parent)
        self.models = [Rows(sorted(apps, key=lambda r: r["display"].lower()), self)] + \
            [Rows([a for a, x in zip(apps, APPS) if x[3] == c], self) for c in cats]
        self.favs = Favorites([a for a in apps if a["decoration"] in (
            "firefox", "dolphin", "konsole", "steam", "code", "deckos", "deckos-store", "settings", "kate",
            "gwenview", "spectacle", "kcalc", "heroic")][:12], self)
        self.system = Rows([row(t, "", fav=f) for f, t in (("lock-screen", "Lock"), ("logout", "Log out"),
                            ("suspend", "Sleep"), ("reboot", "Restart"), ("shutdown", "Shut down"))], self)

    favoritesModel = Property(QObject, lambda self: self.favs, constant=True)
    systemFavoritesModel = Property(QObject, lambda self: self.system, constant=True)

    @Slot(int, result=QObject)
    def modelForRow(self, r):
        return self.models[r] if 0 <= r < len(self.models) else None


RUNNER = [("Kdenlive", "kdenlive", "Video editor", "Applications"), ("Haruna", "haruna", "Media player · plays video", "Applications"),
          ("Display & Monitor", "settings", "Resolution, refresh rate, video outputs", "System Settings"),
          ("cyberpunk-video.mp4", "video", "~/Videos", "Files"), ("video-notes.md", "text", "~/Documents", "Files")]


class RunnerModel(type("RunnerBase", (Rows,), setting("appletInterface", "mergeResults", "runners", "favoritesModel"))):
    queryChanged = Signal()

    def __init__(self, parent=None):
        super().__init__([], parent)
        self._query = ""
        self.matches = Rows([], self)

    def get_query(self):
        return self._query

    def set_query(self, q):
        self._query = q
        hits = [row(*r) for r in RUNNER if q and q.lower()[:3] in (r[0] + r[2]).lower()]
        self.matches.reset(hits)
        self.reset([{}] if hits else [])
        self.queryChanged.emit()

    query = Property(str, get_query, set_query, notify=queryChanged)
    querying = Property(bool, lambda self: False, constant=True)

    @Slot(int, result=QObject)
    def modelForRow(self, r):
        return self.matches


class RecentUsageModel(type("RecentBase", (Rows,), setting("favoritesModel", "ordering"))):
    # Plasma's IncludeUsage enum: on real Plasma shownItems only takes these names, never a number.
    @QEnum
    class IncludeUsage(IntEnum):
        AppsAndDocs = 0
        OnlyApps = 1
        OnlyDocs = 2

    def __init__(self, parent=None):
        super().__init__([], parent)

    def set_shown(self, v):
        self._shown = v
        self.reset([row("Cyberpunk 2077", "cyberpunk", "Played 2 hours ago"), row("VS Code", "code", "Opened today"),
                    row("Konsole", "konsole", "Opened today")] if v == 1 else
                   [row("deckos-notes.md", "text", "~/Documents"), row("gameplay-0420.mp4", "video", "~/Videos"),
                    row("DeckOS", "folder", "~/Documents/My Programs")])

    shownItems = Property(int, lambda self: getattr(self, "_shown", 0), set_shown)


class SystemModel(type("SystemBase", (Rows,), setting("favoritesModel"))):
    def __init__(self, parent=None):
        super().__init__([row(t, "", fav=f) for f, t in (("lock-screen", "Lock"), ("logout", "Log out"),
                          ("suspend", "Sleep"), ("reboot", "Restart"), ("shutdown", "Shut down"))], parent)


class Shell(QObject):
    """The plasma5support "executable" engine, for the commands the menu runs."""
    @Slot(str, result="QVariantList")
    def run(self, cmd):
        m = re.search(r"store_find\.py.* -- '(.*)'$", cmd)
        if m:
            out = subprocess.run([sys.executable, str(STORE / "store_find.py"), "--demo", "--limit", "4", "--",
                                  m.group(1)], capture_output=True, text=True, cwd=STORE).stdout
            return [0, out]
        print("exec", cmd)
        return [0, ""]


class Icons(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, ident, size, req):
        name, _, color = ident.partition("?")
        img = QImage(req if req.isValid() and req.width() > 0 else QSize(48, 48), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        if not name:  # an icon asked for before its name is bound: blank, as Plasma draws it
            return img
        data = (SHARE / f"deckos/icons/{name}.svg").read_text().replace("#000", color or "#8C94A6")
        p = QPainter(img)
        QSvgRenderer(data.encode()).render(p)
        p.end()
        return img


SCENE = """
import QtQuick
Rectangle {
    width: 1600; height: 900; color: "#0F1115"
    Image { anchors.fill: parent; source: wallpaper; fillMode: Image.PreserveAspectCrop }
    Rectangle {  // the dock (stand-in for the real panel)
        id: dock; width: 470; height: 50; radius: 12; y: 836; anchors.horizontalCenter: parent.horizontalCenter
        color: "#F2171A21"; border.color: "#262B36"
        Rectangle { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 34; height: 34; radius: 8
                    color: Qt.rgba(0.3, 0.55, 1, 0.25); border.color: "#4C8DFF"
            Image { anchors.centerIn: parent; width: 24; height: 24; source: logo; sourceSize: Qt.size(48, 48) } }
        Text { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
               text: "19:42"; color: "#E8EAF0"; font.pixelSize: 13 }
    }
    Rectangle {  // the DeckOS Plasma style's dialog frame
        id: plate; objectName: "plate"; width: 640 + 16; height: 596 + 16; radius: 14
        anchors.horizontalCenter: parent.horizontalCenter; y: dock.y - height - 10
        color: "#F2171A21"; border.color: "#262B36"
    }
    Loader {
        id: applet; objectName: "applet"; source: menuUrl; visible: false
        onLoaded: {
            item.fullRepresentation.createObject(plate, { x: 8, y: 8, objectName: "popup" });
            item.expanded = true;
        }
    }
}
"""


def log(mode, ctx, msg):
    print(msg)


def main():
    qInstallMessageHandler(log)
    mode = next((a for a in sys.argv[1:] if a in ("home", "search", "apps", "all")), "all")
    out = next((a for a in sys.argv[1:] if a.endswith(".png")), None)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    app = QGuiApplication(sys.argv)
    for f in (SHARE / "fonts/deckos").glob("*.otf"):
        QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont("Inter Display", 10))
    for cls in (RootModel, RunnerModel, RecentUsageModel, SystemModel):
        qmlRegisterType(cls, URI, 0, 1, cls.__name__)
    shell = Shell()
    modes = ["home", "search", "apps"] if mode == "all" else [mode]
    shots = []

    for m in modes:
        view = QQuickView()
        engine = view.engine()
        engine.addImportPath(str(Path(__file__).resolve().parent / "preview_menu"))
        engine.addImageProvider("ic", Icons())
        ctx = view.rootContext()
        ctx.setContextProperty("previewShell", shell)
        ctx.setContextProperty("previewIcons", {k: [v[0], v[1]] for k, v in ICONS.items()})
        ctx.setContextProperty("menuUrl", QUrl.fromLocalFile(str(MENU)).toString())
        ctx.setContextProperty("wallpaper", QUrl.fromLocalFile(str(SHARE / "deckos/branding/wallpaper.svg")).toString())
        ctx.setContextProperty("logo", QUrl.fromLocalFile(str(SHARE / "deckos/branding/logo.svg")).toString())
        scene = Path(os.environ.get("TEMP", "/tmp")) / "deckos-menu-scene.qml"
        scene.write_text(SCENE)
        view.setSource(QUrl.fromLocalFile(str(scene)))
        root = view.rootObject()
        applet = root.findChild(QObject, "applet").property("item")
        if applet is None:
            for e in view.errors():
                print(e.toString())
            sys.exit("main.qml didn't load (see the warnings above)")
        popup = root.findChild(QQuickItem, "popup")
        view.show()
        search = popup.findChild(QObject, "search")
        if m == "search":
            search.setProperty("text", os.environ.get("DECKOS_MENU_QUERY", "video"))
        elif m == "apps":
            popup.setProperty("page", 1)
        img = []
        QTimer.singleShot(1500, lambda v=view, i=img: (i.append(v.grabWindow()), app.quit()))
        app.exec()
        target = out if out and len(modes) == 1 else str(ROOT / f"assets/menu-preview-{m}.png")
        img[0].save(target)
        print("->", target)
        shots.append(view)


if __name__ == "__main__":
    main()
