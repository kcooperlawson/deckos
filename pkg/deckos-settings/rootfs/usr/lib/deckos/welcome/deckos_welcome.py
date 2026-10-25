"""DecKoOS Welcome: the first-login tour. A few optional steps through what people change first
(look, display, software, gaming, backups, updates, extras), each applied right away, then a
summary of what changed.

Same look as DecKoOS Hub, whose style, widgets and helpers it shares.
    deckos-welcome               the real thing (app menu, DecKoOS Hub)
    deckos-welcome --autostart   at login: the launcher skips it once ~/.config/deckos/welcome-done exists
    deckos-welcome --demo        canned data, no system changes, for working on the UI anywhere
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "hub"), str(HERE.parent / "store")]  # the Hub's look and helpers, the Store's installs

from PySide6.QtCore import QPointF, QProcess, QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap  # noqa: E402
from PySide6.QtSvgWidgets import QSvgWidget  # noqa: E402
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QMessageBox,  # noqa: E402
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

import hub_style as S  # noqa: E402
import hub_system as sysinfo  # noqa: E402
import welcome_system as ws  # noqa: E402
from deckos_hub import Hub, HubData  # noqa: E402
from hub_widgets import Meter, Toast, button, label  # noqa: E402
from store_jobs import Jobs  # noqa: E402
from welcome_pages import STEPS  # noqa: E402

EXTRA_QSS = """
#footer {{ background: {bg}; border-top: 1px solid {border}; }}
QPushButton#flat {{ background: transparent; border: none; color: {sub}; }}
QPushButton#flat:hover {{ color: {text}; background: {surface}; }}
QLabel#hero {{ font-family: "Inter Display", "Inter"; font-size: 24pt; font-weight: 600; }}
QLabel#key {{ background: {raised}; border: 1px solid {border}; border-bottom: 2px solid {border}; border-radius: 5px;
    padding: 1px 7px; font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; }}
"""


def qss():
    return S.styled(S._qss() + EXTRA_QSS.format(bg=S.SIDEBAR, border=S.BORDER, sub=S.SUBTEXT, text=S.TEXT, surface=S.SURFACE,
                                      raised=S.RAISED))


def step_icon(number, state, size=22, ratio=2.0):
    """The step list's marker: a numbered circle, a check once done, a dash when skipped."""
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(ratio, ratio)
    r = QRectF(1, 1, size - 2, size - 2)
    if state == "current":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(S.P.accent))
    elif state == "done":
        c = QColor(S.SUCCESS)
        c.setAlpha(46)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
    else:
        p.setPen(QPen(QColor(S.BORDER if state == "skipped" else S.MUTED), 1.2))
        p.setBrush(Qt.NoBrush)
    p.drawEllipse(r)
    if state == "done":
        p.drawPixmap(QRectF(5, 5, size - 10, size - 10), S.pixmap("check", S.SUCCESS, size - 10, ratio),
                     QRectF(0, 0, (size - 10) * ratio, (size - 10) * ratio))
    elif state == "skipped":
        pen = QPen(QColor(S.MUTED), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(size / 2 - 3.5, size / 2), QPointF(size / 2 + 3.5, size / 2))
    else:
        f = QFont("Inter", 8)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor("white" if state == "current" else S.SUBTEXT))
        p.drawText(r, Qt.AlignCenter, str(number))
    p.end()
    pm.setDevicePixelRatio(ratio)
    return QIcon(pm)


class Welcome(QWidget):
    # The Hub's helpers for running things, shared as they are: a terminal that stays open, `deckos`
    # through pkexec, and the user's Gaming Mode settings.
    terminal = staticmethod(Hub.terminal)
    write_gaming = staticmethod(Hub.write_gaming)
    privileged = Hub.privileged
    privileged_cmd = Hub.privileged_cmd

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("Welcome to DecKoOS")
        self.setWindowIcon(QIcon.fromTheme("deckos", QIcon(str(S.BRANDING / "logo.svg"))))
        self.resize(1140, 780)
        self.setMinimumSize(940, 640)
        self.gpu = sysinfo.Gpu()
        self.data = HubData(self)
        self.apps = Jobs(self)  # app installs from the Software step; closing waits for them
        self.jobs = []
        self.changes = {}  # key -> (text, needs: None / "reboot" / "relogin"), for the summary
        self.closing = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.build_rail())
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.progress = Meter(3)
        main.addWidget(self.progress)
        self.stack = QStackedWidget()
        main.addWidget(self.stack, 1)
        main.addWidget(self.build_footer())
        outer.addLayout(main, 1)

        self.steps, self.state = [], []
        for i, cls in enumerate(STEPS):
            page = cls(self)
            page.kicker.setText(f"STEP {i + 1} OF {len(STEPS)}" if 0 < i < len(STEPS) - 1 else
                                ("WELCOME" if i == 0 else "ALL DONE"))
            self.steps.append(page)
            self.state.append("pending")
            self.stack.addWidget(page)
            self.add_nav(i, page.nav)
        self.toast_box = Toast(self.stack)  # above the footer, so it never covers Next
        self.apps.done.connect(self.app_done)
        self.current = -1
        self.go(0)

    # ---- frame

    def build_rail(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(236)
        self.rail = QVBoxLayout(side)
        self.rail.setContentsMargins(14, 20, 14, 16)
        self.rail.setSpacing(3)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        tile = S.brand_widget("logo.svg")
        tile.setFixedSize(34, 34)
        brand.addWidget(tile)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("DecKoOS Welcome", "brand", wrap=False))
        names.addWidget(label("Set things up your way", "muted", wrap=False))
        brand.addLayout(names, 1)
        self.rail.addLayout(brand)
        self.rail.addSpacing(18)
        self.nav, self.nav_group = [], QButtonGroup(self)
        self.nav_box = QVBoxLayout()
        self.nav_box.setSpacing(3)
        self.rail.addLayout(self.nav_box)
        self.rail.addStretch(1)
        self.startup = QCheckBox("Show at startup")
        self.startup.setCursor(Qt.PointingHandCursor)
        self.startup.setChecked(ws.show_at_startup())
        self.startup.toggled.connect(ws.set_show_at_startup)
        self.rail.addWidget(self.startup)
        self.rail.addWidget(label("Open it again any time from the app menu or DecKoOS Hub.", "muted"))
        return side

    def add_nav(self, i, title):
        b = QPushButton("  " + title.replace("&", "&&"))
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        b.setIconSize(QSize(22, 22))
        b.clicked.connect(lambda _c, k=i: self.go(k))
        self.nav_group.addButton(b)
        self.nav.append(b)
        self.nav_box.addWidget(b)

    def build_footer(self):
        bar = QFrame()
        bar.setObjectName("footer")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 12, 24, 12)
        h.setSpacing(8)
        self.hint = label("", "muted", wrap=False)
        h.addWidget(self.hint, 1)
        self.skip_btn = button("Skip this step", "flat", self.skip)
        self.back_btn = button("Back", slot=lambda: self.go(self.current - 1), icon="chevron-left")
        self.next_btn = button("Next", "primary", self.next)
        self.next_btn.setMinimumWidth(120)
        for b in (self.skip_btn, self.back_btn, self.next_btn):
            h.addWidget(b)
        return bar

    # ---- moving between steps

    def go(self, i):
        i = max(0, min(len(self.steps) - 1, i))
        if self.current >= 0 and self.state[self.current] == "current":
            self.state[self.current] = "pending"
        self.current = i
        self.state[i] = "current"
        self.nav[i].setChecked(True)
        page = self.steps[i]
        self.stack.setCurrentWidget(page)
        page.refresh()
        last = i == len(self.steps) - 1
        self.progress.set(i / (len(self.steps) - 1))
        self.back_btn.setVisible(i > 0)
        self.skip_btn.setVisible(0 < i < len(self.steps) - 1)
        self.next_btn.setText("Get started" if i == 0 else "Finish" if last else
                              f"Next: {self.steps[i + 1].nav}".replace("&", "&&"))
        self.hint.setText(page.hint)
        self.paint_nav()

    def leave(self, how):
        """Marks the current step done or skipped (a skipped step that changed something counts as done)."""
        changed = any(k.startswith(self.steps[self.current].key + ":") for k in self.changes)
        self.state[self.current] = "done" if how == "done" or changed else "skipped"

    def next(self):
        if self.current == len(self.steps) - 1:
            self.close()
            return
        self.leave("done")
        self.go(self.current + 1)

    def skip(self):
        self.leave("skipped")
        self.go(self.current + 1)

    def paint_nav(self):
        for i, b in enumerate(self.nav):
            b.setIcon(step_icon(i + 1, self.state[i]))

    def go_to(self, key):
        self.go(next(i for i, p in enumerate(self.steps) if p.key == key))

    def skipped(self):
        return [p for p, s in zip(self.steps[1:-1], self.state[1:-1]) if s != "done"]

    # ---- what steps call

    def note(self, key, text, needs=None):
        """Records a change for the summary; `key` is "step:thing", so a later change replaces it."""
        self.changes[key] = (text, needs)

    def toast(self, text, kind="info", ms=5000):
        self.toast_box.show_message(text, kind, ms)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast_box.isVisible():
            self.toast_box.move(self.stack.width() - self.toast_box.width() - 22,
                                self.stack.height() - self.toast_box.height() - 20)

    def add_group(self, key, title):
        self.terminal(f"deckos software add {key}")
        self.note(f"software:group-{key}", f"Started adding {title} (in a terminal)", "relogin")
        self.toast(f"Adding {title} in a terminal. It needs your password.", "info", 7000)

    def set_accent(self, color):
        """Restyles the window live with a new accent (the desktop gets it from plasma-apply-colorscheme)."""
        S.P.set_accent(color)
        QApplication.instance().setStyleSheet(qss())
        self.paint_nav()
        S.refresh_brand(self)
        for w in self.findChildren(QWidget):
            w.update()

    def open_hub(self):
        if not sysinfo.DEMO:
            QProcess.startDetached("deckos-hub", [])

    def app_done(self, _key, _ok, _msg):
        if self.closing and not self.apps.queue:  # the finished job is still `current` here
            QApplication.instance().quit()

    def closeEvent(self, e):
        ws.mark_seen()
        if self.apps.current and self.apps.current.ok is None and not self.closing:
            name = self.apps.current.title
            if QMessageBox.question(self, "Apps are still installing",
                                    f"{name} is still installing. Close DecKoOS Welcome when it's done?\n\n"
                                    "Stopping now could leave it half installed.",
                                    QMessageBox.Yes | QMessageBox.Cancel) == QMessageBox.Yes:
                self.closing = True
                self.hide()
            e.ignore()
            return
        super().closeEvent(e)


def main():
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "kde")
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Welcome")
    app.setDesktopFileName("deckos-welcome")
    app.setFont(QFont("Inter", 10))
    app.setStyleSheet(qss())
    app.setQuitOnLastWindowClosed(False)  # closing may wait for app installs to finish (see closeEvent)
    w = Welcome()
    w.destroyed.connect(app.quit)
    w.setAttribute(Qt.WA_DeleteOnClose)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
