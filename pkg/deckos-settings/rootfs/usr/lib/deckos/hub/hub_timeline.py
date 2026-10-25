"""DecKoOS Hub's Timeline: what happened on this PC (DecKoOS Pulse), newest first, a day at a time, with Undo
where it can be taken back. It watches the timeline files, so it changes the moment something happens.
RecentCard is the same list, the last few, for Home."""
import sys
import time
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QProcess, Qt, QTimer
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


class Timeline(QWidget):
    """The rows themselves, shared by the page and Home's card."""

    def __init__(self, hub, limit=200, compact=False):
        super().__init__()
        self.hub, self.limit, self.compact = hub, limit, compact
        self.group = "All"
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
        self.timeline = Timeline(self.hub)
        self.chip_group.idClicked.connect(self.pick)
        card = Card("", "", "")
        card.body.addWidget(self.timeline)
        self.lay.addWidget(card)

    def pick(self, i):
        self.timeline.group = GROUPS[i]
        self.timeline.refresh()

    def refresh(self):
        self.timeline.refresh()


class RecentCard(Card):
    """Home's last few events, with a link to the whole timeline."""

    def __init__(self, hub):
        super().__init__("Recently", "On this PC", "clock")
        self.timeline = Timeline(hub, limit=4, compact=True)
        self.actions.addWidget(button("Timeline", slot=lambda: hub.navigate("timeline"), icon="arrow-right"))
        self.body.addWidget(self.timeline)
