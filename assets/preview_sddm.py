"""Renders the DeckOS login screen without SDDM: stand-ins for SDDM's objects (users, sessions,
keyboard, power), then a screenshot. Also writes the theme's preview.png (System Settings shows it).
    python assets/preview_sddm.py [out.png] [--failed]
"""
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication, QStandardItem, QStandardItemModel
from PySide6.QtQuick import QQuickView, QQuickWindow, QSGRendererInterface

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "pkg/deckos-settings/rootfs/usr/share/sddm/themes/deckos"
BRANDING = ROOT / "pkg/deckos-settings/rootfs/usr/share/deckos/branding"


class Sddm(QObject):
    loginFailed = Signal()
    loginSucceeded = Signal()

    @Property(str, constant=True)
    def hostName(self):
        return "deckos"

    canPowerOff = Property(bool, lambda self: True, constant=True)
    canReboot = Property(bool, lambda self: True, constant=True)
    canSuspend = Property(bool, lambda self: True, constant=True)

    @Slot(str, str, int)
    def login(self, user, password, session):
        print(f"login({user!r}, {'*' * len(password)}, session {session})")
        self.loginFailed.emit()

    @Slot()
    def powerOff(self):
        print("powerOff")

    @Slot()
    def reboot(self):
        print("reboot")

    @Slot()
    def suspend(self):
        print("suspend")


class Model(QStandardItemModel):
    def __init__(self, roles, rows, last=0):
        super().__init__()
        self._roles = {Qt.UserRole + i: r.encode() for i, r in enumerate(roles)}
        self.setItemRoleNames(self._roles)
        for r in rows:
            item = QStandardItem()
            for role, value in zip(self._roles, r):
                item.setData(value, role)
            self.appendRow(item)
        self._last = last

    lastIndex = Property(int, lambda self: self._last, constant=True)
    count = Property(int, lambda self: self.rowCount(), constant=True)


def main():
    out = Path(next((a for a in sys.argv[1:] if not a.startswith("--")), THEME / "preview.png"))
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    app = QGuiApplication(sys.argv)
    view = QQuickView()
    ctx = view.rootContext()
    sddm = Sddm()
    users = Model(["name", "realName", "icon", "needsPassword"], [["keagan", "Keagan", "", True]])
    # SDDM's order: alphabetical by file, so Gaming Mode is first and lastIndex is 0 on a first login.
    sessions = Model(["name", "file"], [["DeckOS Gaming Mode", "deckos-gaming.desktop"],
                                       ["Plasma (Wayland)", "plasma.desktop"]], last=0)
    ctx.setContextProperty("sddm", sddm)
    ctx.setContextProperty("userModel", users)
    ctx.setContextProperty("sessionModel", sessions)
    ctx.setContextProperty("config", {"background": QUrl.fromLocalFile(str(BRANDING / "wallpaper.svg")).toString(),
                                      "wordmark": QUrl.fromLocalFile(str(BRANDING / "wordmark.svg")).toString(),
                                      "accent": "#4C8DFF", "accentB": "#7A5CFF"})
    ctx.setContextProperty("keyboard", {"capsLock": False, "currentLayout": 0,
                                        "layouts": [{"shortName": "us"}, {"shortName": "de"}]})
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(THEME / "Main.qml")))
    if view.status() == QQuickView.Error:
        for e in view.errors():
            print(e.toString())
        sys.exit(1)
    view.resize(1920, 1080)
    view.show()
    if "--failed" in sys.argv:
        QTimer.singleShot(200, sddm.loginFailed.emit)

    def shoot():
        view.grabWindow().save(str(out))
        print(f"-> {out}")
        app.quit()
    QTimer.singleShot(1500, shoot)
    app.exec()


if __name__ == "__main__":
    main()
