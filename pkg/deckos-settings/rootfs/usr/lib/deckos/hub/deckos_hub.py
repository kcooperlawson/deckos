"""DecKoOS Hub: one window for what DecKoOS adds. A live overview, the display fix, Gaming Mode,
drives, AI and dev tools, updates, snapshots, firewall, software and appearance.

Same visual language as the installer: slate surfaces, 1px borders, 10px
radii, Inter, DecKoOS line icons, and the accent gradient on primary actions.
    deckos-hub            the real thing
    deckos-hub --demo     canned data, for working on the UI anywhere (Windows included)
    deckos-hub --page system [--update]
                          open on a page (DecKoOS Quick Settings uses this), and start the update
"""
import os
import platform
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QProcess, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

import hub_style as S
import hub_system as sysinfo
from hub_games import GamesPage
from hub_pages import AiDevPage, AppearancePage, DisplayPage, DrivesPage, GamingPage, HomePage, SystemPage
from hub_timeline import TimelinePage
from hub_widgets import Toast, label

PAGES = [("home", "Home", "home", HomePage), ("timeline", "Timeline", "clock", TimelinePage),
         ("games", "Games", "grid", GamesPage),
         ("display", "Display", "display", DisplayPage),
         ("gaming", "Gaming", "gaming", GamingPage), ("drives", "Drives", "drives", DrivesPage),
         ("aidev", "AI & Dev", "ai", AiDevPage), ("system", "System", "system", SystemPage),
         ("appearance", "Appearance", "appearance", AppearancePage)]
USER_GAMING_CONF = Path.home() / ".config/deckos/gaming.conf"


class HubData:
    """Slow lookups (updates, snapshots, firewall) run in the background and are cached, so pages
    can ask freely; callers queue while a lookup is running."""

    TTL = {"updates": 900, "snapshots": 60, "undo": 60, "firewall": 30}

    def __init__(self, owner):
        self.owner = owner
        self.cache, self.waiting = {}, {}

    def invalidate(self):
        self.cache.clear()

    def _get(self, key, fresh, cb, start):
        hit = self.cache.get(key)
        if hit and not fresh and time.time() - hit[0] < self.TTL[key.split(":")[0]]:
            cb(*hit[1])
            return
        first = key not in self.waiting
        self.waiting.setdefault(key, []).append(cb)
        if first:
            start(lambda *result: self._done(key, result))

    def _done(self, key, result):
        self.cache[key] = (time.time(), result)
        for cb in self.waiting.pop(key, []):
            cb(*result)

    def updates(self, cb, fresh=False):
        """cb(repo_count, aur_count, error_text)"""
        self.update_list(lambda repo, aur, err: cb(len(repo), len(aur), err), fresh)

    def update_list(self, cb, fresh=False):
        """cb([(name, old, new)] from the repos, [(name, old, new)] from the AUR, error_text)"""
        def start(done):
            if not sysinfo.have("checkupdates"):
                done([], [], "checkupdates isn't installed (pacman-contrib).")
                return

            def repo(out, code):
                if code not in (0, 2):
                    done([], [], "No connection to the package mirrors.")
                    return
                pkgs = sysinfo.parse_updates(out)
                if not sysinfo.have("paru"):
                    done(pkgs, [], "")
                    return
                sysinfo.Job(self.owner, ["paru", "-Qua"], lambda o, _c: done(pkgs, sysinfo.parse_updates(o), ""),
                            demo=("r2modman-bin 3.1.50-1 -> 3.1.52-1", 0))
            sysinfo.Job(self.owner, ["checkupdates"], repo, demo=(sysinfo.DEMO_UPDATES, 0))
        self._get("updates", fresh, cb, start)

    def snapshots(self, cb, fresh=False, config="root"):
        """cb([(number, date, description, important)] newest first, or None). config: root or home."""
        self._get(f"snapshots:{config}", fresh, cb, lambda done: sysinfo.Job(
            self.owner, ["snapper", "--jsonout", "-c", config, "list"],
            lambda out, code: done(sysinfo.parse_snapshots(out) if code == 0 else None),
            demo=(sysinfo.DEMO_SNAPSHOTS if config == "root" else sysinfo.DEMO_HOME_SNAPSHOTS, 0)))

    def undoable(self, cb, fresh=False):
        """cb([(pre_number, date, what)] newest first, or None): updates `deckos undo` can take back."""
        self._get("undo", fresh, cb, lambda done: sysinfo.Job(
            self.owner, [sysinfo.DECKOS, "undo", "--tsv"],
            lambda out, code: done(sysinfo.parse_undoable(out) if code == 0 else None),
            demo=(sysinfo.DEMO_UNDOABLE, 0)))

    def firewall(self, cb, fresh=False):
        """cb(running, [open services])"""
        def start(done):
            def state(out, _code):
                if out.strip() != "active":
                    done(False, [])
                    return
                # Reading the zone is polkit's FirewallD1.config.info: 50-deckos.rules lets wheel do it
                # without a password. Without that rule it would ask, so a failure just shows no list.
                sysinfo.Job(self.owner, ["firewall-cmd", "--list-services"],
                            lambda o, c: done(True, o.split() if c == 0 else []), demo=("kdeconnect steam-streaming", 0))
            sysinfo.Job(self.owner, ["systemctl", "is-active", "firewalld"], state, demo=("active", 0))
        self._get("firewall", fresh, cb, start)


class Hub(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("DecKoOS Hub")
        self.setWindowIcon(QIcon.fromTheme("deckos-hub", QIcon(str(S.BRANDING / "hub-logo.svg"))))
        self.resize(1180, 800)
        self.setMinimumSize(940, 620)
        self.gpu = sysinfo.Gpu()
        self.stats = sysinfo.Stats(self.gpu)
        self.data = HubData(self)
        self.jobs = []

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(224)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 20, 14, 16)
        sl.setSpacing(3)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        tile = QSvgWidget(str(S.BRANDING / "logo.svg"))
        tile.setFixedSize(34, 34)
        brand.addWidget(tile)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("DecKoOS Hub", "brand", wrap=False))
        names.addWidget(label("Your system, at a glance", "muted", wrap=False))
        brand.addLayout(names, 1)
        sl.addLayout(brand)
        sl.addSpacing(18)

        self.stack = QStackedWidget()
        self.pages, self.nav = {}, {}
        self.nav_group = QButtonGroup(self)
        for key, title, ic, cls in PAGES:
            b = QPushButton("  " + title.replace("&", "&&"))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(lambda _c, k=key: self.navigate(k))
            self.nav_group.addButton(b)
            self.nav[key] = (b, ic)
            sl.addWidget(b)
            page = cls(self)
            self.pages[key] = page
            self.stack.addWidget(page)
        self.paint_nav()
        sl.addStretch(1)
        host = "deckos" if sysinfo.DEMO else platform.node()
        kernel = "7.0.3-2-cachyos" if sysinfo.DEMO else platform.release()
        sl.addWidget(label(f"{host}<br>{kernel}", "muted"))
        outer.addWidget(side)
        outer.addWidget(self.stack, 1)

        self.toast_box = Toast(self)
        self.navigate("home")
        self.tick()
        self.timer = QTimer(self, timeout=self.tick, interval=2000)
        self.timer.start()

    # ---- navigation and shared actions (pages call these)

    def paint_nav(self):
        for b, ic in self.nav.values():
            b.setIcon(S.icon(ic, S.SUBTEXT, 18, active=S.TEXT))

    def navigate(self, key, action=None):
        b, _ = self.nav[key]
        b.setChecked(True)
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        page.refresh()
        if action == "update" and key == "system":
            page.check_updates()

    def tick(self):
        stats = self.stats.sample()
        self.pages["home"].tick(stats)  # always, so the graphs have history when Home is opened
        cur = self.stack.currentWidget()
        if cur is not self.pages["home"]:
            cur.tick(stats)

    def toast(self, text, kind="info", ms=5000):
        self.toast_box.show_message(text, kind, ms)

    # No sampling (or playerctl every 2 s) while nobody can see the Hub
    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            self.timer.stop() if self.isMinimized() else self.resume()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def showEvent(self, e):
        super().showEvent(e)
        if hasattr(self, "timer"):
            self.resume()

    def resume(self):
        if not self.timer.isActive():
            self.tick()
            self.timer.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast_box.isVisible():
            self.toast_box.move(self.width() - self.toast_box.width() - 22,
                                self.height() - self.toast_box.height() - 20)

    @staticmethod
    def terminal(command):
        """Runs a command in Konsole and keeps the window open so the output can be read."""
        QProcess.startDetached("deckos-terminal", ["--hold", "-e", "bash", "-lc", command])

    def privileged(self, args, done=None):
        """`deckos ARGS` as root through pkexec (asks for the password); done(ok) afterwards."""
        self.privileged_cmd([sysinfo.DECKOS, *args], done)

    def privileged_cmd(self, cmd, done=None):
        if sysinfo.DEMO:
            QTimer.singleShot(300, lambda: done and done(True))
            return
        proc = QProcess(self)
        self.jobs.append(proc)

        def finished(code, _status):
            self.jobs.remove(proc)
            proc.deleteLater()
            if done:
                done(code == 0)
        proc.finished.connect(finished)
        proc.start("pkexec", cmd)

    def add_group(self, key):
        self.terminal(f"deckos software add {key}")
        self.toast("Installing in a terminal. Reopen the Hub when it's done.", "info", 7000)

    def to_gaming(self):
        sysinfo.Job(self, ["/usr/lib/deckos/gaming-session", "--check"], self.gaming_checked, demo=("", 0))

    def gaming_checked(self, out, code):
        if code != 0:
            QMessageBox.warning(self, "Gaming Mode isn't ready", out.strip() or "Gaming Mode's session files are missing.")
            return
        if QMessageBox.question(self, "Gaming Mode", "Switch to Gaming Mode?\n\nOpen apps will close, so save your "
                                "work first.") == QMessageBox.Yes and not sysinfo.DEMO:
            QProcess.startDetached("sudo", ["-n", "/usr/lib/deckos/session-switch", "gaming", "--delay", "1"])

    @staticmethod
    def write_gaming(values):
        conf = {**sysinfo.conf(USER_GAMING_CONF), **values}
        if sysinfo.DEMO:
            return
        USER_GAMING_CONF.parent.mkdir(parents=True, exist_ok=True)
        USER_GAMING_CONF.write_text("# Written by DecKoOS Hub\n" + "".join(f"{k}={v}\n" for k, v in conf.items()))

    def set_accent(self, color):
        """Restyles the Hub live with a new accent (the desktop gets it from plasma-apply-colorscheme)."""
        S.P.set_accent(color)
        QApplication.instance().setStyleSheet(S.qss())
        self.paint_nav()
        for w in self.findChildren(QWidget):
            w.update()


def main():
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "kde")
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Hub")
    app.setDesktopFileName("deckos-hub")
    app.setFont(QFont("Inter", 10))
    app.setStyleSheet(S.qss())
    w = Hub()
    if "--page" in sys.argv[:-1]:
        page = sys.argv[sys.argv.index("--page") + 1]
        if page in w.pages:
            w.navigate(page)
            if page == "system" and "--update" in sys.argv:
                w.pages["system"].run_update()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
