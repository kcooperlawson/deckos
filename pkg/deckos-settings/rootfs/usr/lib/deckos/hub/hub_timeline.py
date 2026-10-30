"""DecKoOS Hub's Timeline: what happened on this PC (DecKoOS Pulse), newest first, a day at a time, with Undo
where it can be taken back. It watches the timeline files, so it changes the moment something happens.
RecentCard is the same list, the last few, for Home."""
import sys
import time
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QProcess, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
import pulse  # noqa: E402

import hub_style as S  # noqa: E402
import hub_system as sysinfo  # noqa: E402
from hub_pages import Page  # noqa: E402
from hub_widgets import Card, Empty, RowItem, button, label  # noqa: E402

PULSE = Path(__file__).resolve().parent.parent / "pulse/pulse.py"
GROUPS = ("All", "System", "Apps", "Look", "Games", "Health")


def demo_entries():
    now = time.time()
    rows = [(300, "game-start", "Playing Cyberpunk 2077", "", "Workload modes", None),
            (2400, "gamedoctor", "Elden Ring: Turn off fast sync", "", "Game Doctor",
             ["deckos", "gamedoctor", "undo", "1245620", "no-fsync"]),
            (5400, "theme", "Theme: DecKoOS Ember", "", "Appearance", ["deckos", "theme", "apply", "org.deckos.desktop"]),
            (8000, "install", "Installed obs-studio", "", "pacman", ["deckos", "undo", "57"]),
            (90000, "update", "Updated to DecKoOS 0.9.4", "mesa, linux-cachyos, deckos-settings and 31 more", "pacman",
             ["deckos", "undo", "55"]),
            (93000, "drives", "Drives linked: 3", "", "Drives", None),
            (180000, "retro", "Steam: 14 retro games added", "", "DecKoOS Retro", None),
            (260000, "accent", "Accent colour changed", "", "Appearance", ["deckos", "accent", "apply", "#4C8DFF"])]
    out = []
    for i, (ago, kind, title, detail, app, undo) in enumerate(rows):
        out.append({"id": f"demo{i}", "time": now - ago, "kind": kind, "title": title, "detail": detail, "app": app,
                    "undo": undo, "undone": False, "can_undo": bool(undo), "source": "system" if app == "pacman"
                    else "user"})
    return out


def day_of(ts):
    t, n = time.localtime(ts), time.localtime()
    if (t.tm_year, t.tm_yday) == (n.tm_year, n.tm_yday):
        return "Today"
    if time.localtime(time.time() - 86400)[:3] == t[:3]:
        return "Yesterday"
    return time.strftime("%A %d %B", t)


# The colour of each group in the day strip: games green, the look violet, apps amber, health red, the system the accent
GROUP_COLOURS = {"Games": "#3DD68C", "Look": "#A27BFF", "Apps": "#F5B84B", "Health": "#FF6B6B"}
DAYS = 14


def day_key(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


class DayStrip(QWidget):
    """The last two weeks at a glance: a column of LED segments per day, one segment per thing that happened (up to
    ten), coloured by what it was. Click a day to see only it; click it again for everything."""
    picked = Signal(object)  # a day's key, or None

    def __init__(self):
        super().__init__()
        self.setFixedHeight(104)
        self.setCursor(Qt.PointingHandCursor)
        self.counts, self.day = {}, None

    def show_rows(self, rows):
        self.counts = {}
        for r in rows:
            group = pulse.KINDS.get(r["kind"], ("", "System"))[1]
            self.counts.setdefault(day_key(r["time"]), []).append(group)
        self.update()

    def days(self):
        now = time.time()
        return [now - (DAYS - 1 - i) * 86400 for i in range(DAYS)]

    def mousePressEvent(self, e):
        w = self.width() / DAYS
        key = day_key(self.days()[min(DAYS - 1, int(e.position().x() // w))])
        self.day = None if key == self.day else key
        self.update()
        self.picked.emit(self.day)

    def paintEvent(self, _):
        p = QPainter(self)
        w = self.width() / DAYS
        seg_h, gap = 5, 2
        for i, ts in enumerate(self.days()):
            key = day_key(ts)
            x = i * w
            if key == self.day:
                S.paint_plate(p, QRectF(x + 2, 0, w - 4, self.height()), S.P.tint, 6, lit=True)
            groups = self.counts.get(key, [])[:10]
            for j, g in enumerate(groups):  # stacked from the bottom, like a level meter
                c = QColor(GROUP_COLOURS.get(g, S.P.accent))
                y = self.height() - 24 - (j + 1) * (seg_h + gap)
                p.fillRect(QRectF(x + w * 0.22, y, w * 0.56, seg_h), c)
            if not groups:
                p.fillRect(QRectF(x + w * 0.22, self.height() - 24 - seg_h - gap, w * 0.56, seg_h), QColor(S.BORDER))
            f = QFont(S.HUD, 8)
            f.setWeight(QFont.DemiBold)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
            p.setFont(f)
            today = key == day_key(time.time())
            p.setPen(QColor(S.TEXT if key == self.day or today else S.SUBTEXT))
            p.drawText(QRectF(x, self.height() - 20, w, 18), Qt.AlignCenter,
                       "TODAY" if today else time.strftime("%a %d", time.localtime(ts)).upper())
        p.end()


class Timeline(QWidget):
    """The rows themselves, shared by the page and Home's card."""

    def __init__(self, hub, limit=200, compact=False):
        super().__init__()
        self.hub, self.limit, self.compact = hub, limit, compact
        self.group = "All"
        self.day = None  # one day's key (the day strip), or None for all
        self.demo_rows = demo_entries() if sysinfo.DEMO else None
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(6)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(lambda _p: QTimer.singleShot(150, self.refresh))
        self.watcher.directoryChanged.connect(lambda _p: QTimer.singleShot(150, self.refresh))
        self.refresh()

    def watch(self):
        """Watch the files (or their folders, until they exist): nothing is polled."""
        for path in (pulse.user_file(), pulse.system_file()):
            target = str(path) if path.exists() else str(path.parent)
            if Path(target).exists() and target not in self.watcher.files() + self.watcher.directories():
                self.watcher.addPath(target)

    def rows(self):
        rows = self.demo_rows if self.demo_rows is not None else pulse.entries(self.limit)
        rows = [r for r in rows if r["kind"] != "undo" or not self.compact]  # Home leaves out the undo notes
        if self.group != "All":
            rows = [r for r in rows if pulse.KINDS.get(r["kind"], ("", "System"))[1] == self.group]
        if self.day:
            rows = [r for r in rows if day_key(r["time"]) == self.day]
        return rows[:self.limit]

    def refresh(self):
        if not sysinfo.DEMO:
            self.watch()
        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = self.rows()
        if not rows:
            self.box.addWidget(label("Nothing yet. Updates, game fixes, theme changes and the games you play show "
                                     "up here, with Undo where they can be taken back.", "sub"))
            return
        day = None
        for r in rows:
            d = day_of(r["time"])
            if d != day and not self.compact:
                self.box.addWidget(label(d.upper(), "kicker"))
                day = d
            icon = pulse.KINDS.get(r["kind"], ("info", ""))[0]
            detail = " · ".join(x for x in (pulse.when(r["time"]), r.get("app", ""), r.get("detail", "")) if x)
            right = []
            if r.get("undone"):
                right.append(label(f"<span style='color:{S.MUTED}'>undone</span>", None, wrap=False))
            elif r.get("can_undo"):
                b = button("Undo", slot=lambda _=False, e=r: self.undo(e), icon="undo",
                           tip="Asks for your password" if r["source"] == "system" else "Puts it back")
                right.append(b)
            color = S.MUTED if r.get("undone") else S.DANGER if r["kind"] == "crash" else S.P.accent
            self.box.addWidget(RowItem(icon, r["title"], detail, color, right))

    def undo(self, entry):
        if sysinfo.DEMO:
            entry["undone"], entry["can_undo"] = True, False
            self.hub.toast(f"Undid: {entry['title']}", "ok")
            self.refresh()
            return
        proc = QProcess(self)
        proc.finished.connect(lambda code, _s: (
            self.hub.toast(f"Undid: {entry['title']}" if code == 0 else
                           (bytes(proc.readAllStandardError()).decode(errors="replace").strip() or "That didn't work."),
                           "ok" if code == 0 else "warn"), self.refresh(), proc.deleteLater()))
        proc.start(sys.executable, [str(PULSE), "undo", entry["id"]])


class TimelinePage(Page):
    title = "Timeline"
    subtitle = "What happened on this PC, newest first. Undo takes a change back."

    def build(self):
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        for i, name in enumerate(GROUPS):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == 0)
            self.chip_group.addButton(b, i)
            chips.addWidget(b)
        chips.addStretch(1)
        self.lay.addLayout(chips)
        self.strip = DayStrip()
        strip_card = Card("Two weeks", "What happened, day by day", "clock")
        strip_card.body.addWidget(self.strip)
        self.lay.addWidget(strip_card)
        self.timeline = Timeline(self.hub)
        self.strip.picked.connect(self.pick_day)
        self.chip_group.idClicked.connect(self.pick)
        card = Card("", "", "")
        card.body.addWidget(self.timeline)
        self.lay.addWidget(card)

    def pick(self, i):
        self.timeline.group = GROUPS[i]
        self.refresh()

    def pick_day(self, key):
        self.timeline.day = key
        self.timeline.refresh()

    def refresh(self):
        self.timeline.refresh()
        day, self.timeline.day = self.timeline.day, None  # the strip counts every day, in the group picked
        self.strip.show_rows(self.timeline.rows() if self.timeline.demo_rows is not None else
                             [r for r in pulse.entries(2000) if self.timeline.group == "All"
                              or pulse.KINDS.get(r["kind"], ("", "System"))[1] == self.timeline.group])
        self.timeline.day = day


class RecentCard(Card):
    """Home's last few events, with a link to the whole timeline."""

    def __init__(self, hub):
        super().__init__("Recently", "On this PC", "clock")
        self.timeline = Timeline(hub, limit=4, compact=True)
        self.actions.addWidget(button("Timeline", slot=lambda: hub.navigate("timeline"), icon="arrow-right"))
        self.body.addWidget(self.timeline)
