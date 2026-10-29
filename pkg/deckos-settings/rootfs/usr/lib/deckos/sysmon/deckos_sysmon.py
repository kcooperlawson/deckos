"""DecKoOS System Monitor: what's running and how hard the PC is working, in the DecKoOS look.

    deckos-sysmon [--page processes|performance]
    deckos-sysmon --demo [--screenshot DIR]

Processes: one row per app with its processes inside, sorted by what they use, with End and Force
stop. Performance: processor, memory, graphics cards, disks and network, each with a live graph.
Samples once a second, and not at all while the window is minimized or hidden.
"""
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath,  # noqa: E402
                           QPen, QShortcut)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout,  # noqa: E402
                               QHeaderView, QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import hub_style as S  # noqa: E402
import sysmon as sm  # noqa: E402
from hub_widgets import Sparkline, button, icon_label, label  # noqa: E402

DEMO = "--demo" in sys.argv
COLS = ["Name", "CPU", "Memory", "Disk", "User"]
# One colour per kind of resource, the same everywhere in the window (and fixed, so they stay apart whatever the
# accent): processor blue, memory violet, graphics green, disks amber, network cyan.
KIND = {"cpu": "#4C8DFF", "mem": "#A27BFF", "gpu": "#3DD68C", "disk": "#F5B84B", "net": "#2AC3DE"}
UPLOAD = "#7BE0F0"  # the network's second line: upload, beside cyan download

QSS = f"""
QTreeWidget {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 2px; padding: 4px;
    alternate-background-color: {S.SURFACE}; outline: 0; }}
QTreeWidget::item {{ height: 30px; border: none; }}
QTreeWidget::item:selected {{ background: rgba(76, 141, 255, 0.16); color: {S.TEXT}; }}
QTreeWidget::item:hover {{ background: {S.RAISED}; }}
QHeaderView::section {{ background: transparent; color: {S.SUBTEXT}; border: none; border-bottom: 1px solid {S.BORDER};
    padding: 6px 8px; font-weight: 600; }}
QFrame#device, QFrame#stat {{ background: transparent; border: none; }}  /* notched plates: hub_style */
QLabel#big {{ font-family: "Chakra Petch", "Inter"; font-size: 22pt; font-weight: 600; }}
QLabel#headline {{ font-family: "Chakra Petch", "Inter"; font-size: 26pt; font-weight: 700; }}
QLabel#devValue {{ font-weight: 700; }}
QFrame#stat QLabel {{ background: transparent; }}
QLabel#statValue {{ font-family: "Chakra Petch", "Inter"; font-size: 14pt; font-weight: 600; }}
QLabel#chip {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 2px; padding: 5px 11px; }}
QLabel#mode {{ background: rgba(61, 214, 140, 0.12); border: 1px solid rgba(61, 214, 140, 0.35); color: #9BEBC4;
    border-radius: 2px; padding: 5px 11px; font-weight: 600; }}
QPushButton#danger:disabled {{ background: {S.RAISED}; color: {S.MUTED}; }}
QPushButton#seg {{ padding: 6px 14px; border-radius: 2px; background: transparent; border: 1px solid transparent; }}
QPushButton#seg:checked {{ background: {S.RAISED}; border-color: {S.BORDER}; color: {S.TEXT}; }}
"""


def pct(v):
    return f"{v:.0f}%" if v >= 1 or v == 0 else f"{v:.1f}%"


def rate(v):
    return sm.size(v) + "/s"


def tint(color, alpha):
    c = QColor(color)
    c.setAlphaF(alpha)
    return c


class Graph(QWidget):
    """The large graph: a scale, the last 60 seconds as smooth lines with a glow, and a dot where each is now.
    series: [(values 0..1, colour)]; the first one also gets a soft fill."""

    def __init__(self):
        super().__init__()
        self.series, self.ticks = [], ("100%", "50%", "0%")
        self.setMinimumHeight(250)

    def set(self, series, ticks):
        self.series, self.ticks = series, ticks
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(2, 8, self.width() - 58, self.height() - 34)
        p.setFont(QFont("Inter", 8))
        for i in range(5):
            y = area.top() + area.height() * i / 4
            p.setPen(QPen(QColor(S.BORDER), 1, Qt.SolidLine if i == 4 else Qt.DashLine))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            if i % 2 == 0:
                p.setPen(QColor(S.MUTED))
                p.drawText(QRectF(area.right() + 8, y - 9, 50, 18), Qt.AlignLeft | Qt.AlignVCenter, self.ticks[i // 2])
        p.setPen(QColor(S.MUTED))
        p.drawText(QRectF(area.left(), area.bottom() + 6, 120, 18), Qt.AlignLeft, "60 seconds ago")
        p.drawText(QRectF(area.right() - 120, area.bottom() + 6, 120, 18), Qt.AlignRight, "now")
        for n, (values, color) in enumerate(self.series):
            if len(values) < 2:
                continue
            step = area.width() / 59
            x0 = area.right() - step * (len(values) - 1)
            pts = [QPointF(x0 + i * step, area.bottom() - v * area.height()) for i, v in enumerate(values)]
            line = QPainterPath(pts[0])
            for a, b in zip(pts, pts[1:]):  # smooth, without overshooting the samples
                line.cubicTo(QPointF(a.x() + step / 2, a.y()), QPointF(b.x() - step / 2, b.y()), b)
            if n == 0:
                fill = QPainterPath(line)
                fill.lineTo(pts[-1].x(), area.bottom())
                fill.lineTo(pts[0].x(), area.bottom())
                fill.closeSubpath()
                grad = QLinearGradient(0, area.top(), 0, area.bottom())
                grad.setColorAt(0, tint(color, 0.32))
                grad.setColorAt(1, tint(color, 0.0))
                p.fillPath(fill, grad)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(tint(color, 0.16), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(line)
            p.setPen(QPen(QColor(color), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(line)
            p.setPen(Qt.NoPen)
            p.setBrush(tint(color, 0.25))
            p.drawEllipse(pts[-1], 8, 8)
            p.setBrush(QColor(color))
            p.drawEllipse(pts[-1], 4, 4)
        p.end()


class Heat(QStyledItemDelegate):
    """Shades the CPU, memory and disk cells by how much they use, in that resource's colour, so the heavy apps stand
    out at a glance."""

    def __init__(self, mon):
        super().__init__()
        self.mon = mon

    def paint(self, painter, option, index):
        num = index.data(SORT)
        col = index.column()
        if num and col in (1, 2, 3) and self.mon.snap:
            total = self.mon.snap.mem_total or 1
            frac = {1: num / 100, 2: num / total, 3: num / 1e8}[col]
            if frac > 0.002:
                color = {1: KIND["cpu"], 2: KIND["mem"], 3: KIND["disk"]}[col]
                painter.fillRect(option.rect.adjusted(1, 2, -1, -2), tint(color, min(0.5, 0.06 + 0.55 * min(1, frac) ** 0.6)))
        super().paint(painter, option, index)


# ------------------------------------------------------------------ demo data

class DemoSampler:
    """Believable numbers for --demo: a game running, a download, a busy browser."""

    APPS = [("Cyberpunk 2077", "cyberpunk", 1, 6.1e9, 38.0, 4e6), ("Firefox", "firefox", 11, 4.4e9, 6.0, 2e5),
            ("Steam", "steam", 9, 1.6e9, 2.2, 3.1e7), ("Discord", "discord", 8, 1.2e9, 1.4, 1e4),
            ("DecKoOS Files", "org.deckos.files", 1, 2.1e8, 0.2, 0),
            ("KWin", "kwin", 1, 2.8e8, 3.1, 0), ("Plasma", "plasmashell", 1, 5.7e8, 0.8, 0),
            ("ollama", "", 1, 3.2e8, 0.0, 0), ("pipewire", "", 1, 2.7e7, 0.4, 0)]

    def __init__(self):
        self.t = 0

    def sample(self, with_procs=True):
        self.t += 1
        t = self.t
        wave = lambda base, amp, per: base + amp * math.sin(t / per) + amp * 0.3 * math.sin(t / 2.3)  # noqa: E731
        procs = []
        pid = 1200
        for name, _icon, n, mem, cpu, io in self.APPS:
            for i in range(n):
                pid += 7
                procs.append(sm.Proc(pid=pid, ppid=1, name=name, command=f"/usr/bin/{name.lower()} --child {i}",
                                     user="deck", uid=1000, state="S",
                                     threads=12, rss=int(mem / n), ticks=0, cpu=max(0.0, wave(cpu / n, cpu / n / 4, 3 + i)),
                                     io=0, io_rate=io / n * (1 + math.sin(t / 4)) / 2))
        gpu = sm.Gpu(card="card1", name="Radeon RX 9070 XT", busy=min(99.0, wave(93, 4, 3)), vram_used=int(9.4e9),
                     vram_total=int(17.1e9), temp=wave(71, 2, 7), power=wave(286, 18, 4))
        igpu = sm.Gpu(card="card0", name="Radeon 610M", busy=0.0, vram_used=int(4e7), vram_total=int(5.4e8),
                      temp=42.0, power=3.5)
        return sm.Snapshot(when=t, cpu=wave(41, 9, 5), cores=[max(1.0, wave(41 + (c % 5) * 7 - 14, 12, 2 + c / 3))
                                                              for c in range(16)],
                           cpu_temp=wave(68, 3, 8), cpu_mhz=wave(4850, 120, 3), mem_used=int(15.2e9),
                           mem_total=int(32.6e9), swap_used=0, swap_total=int(16.3e9), gpus=[gpu, igpu],
                           disks={"nvme0n1": (wave(4.1e7, 3e7, 4), wave(2e6, 1.5e6, 6)), "sda": (0.0, 0.0)},
                           net=(wave(3.1e7, 6e6, 3), wave(4.2e5, 1e5, 5)), procs=procs, uptime=3 * 3600 + 1240)


DEMO_MODE = {"mode": "gaming", "game": "Cyberpunk 2077", "vram": "9100000000"}


# ------------------------------------------------------------------ processes

SORT = Qt.UserRole + 1  # the number behind a CPU / memory / disk cell


class Row(QTreeWidgetItem):
    """Sorts the number columns by their numbers, not their text ("9 MB" < "10 GB")."""

    def __lt__(self, other):
        c = self.treeWidget().sortColumn() if self.treeWidget() else 0
        a, b = self.data(c, SORT), other.data(c, SORT)
        if a is not None and b is not None:
            return a < b
        return self.text(c).lower() < other.text(c).lower()

class ProcessesPage(QWidget):
    def __init__(self, mon):
        super().__init__()
        self.mon = mon
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search apps and processes")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.mon.refresh_view())
        top.addWidget(self.search, 1)
        self.mine = QCheckBox("Only my apps")
        self.mine.setChecked(True)
        self.mine.toggled.connect(lambda _c: self.mon.refresh_view())
        top.addWidget(self.mine)
        self.end = button("End", slot=lambda: self.stop(False), icon="close", tip="Ask it to close (Delete)")
        self.force = button("Force stop", "danger", lambda: self.stop(True), icon="stop",
                            tip="Stop it at once; unsaved work is lost")
        top.addWidget(self.end)
        top.addWidget(self.force)
        v.addLayout(top)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLS))
        self.tree.setHeaderLabels(COLS)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(1, Qt.DescendingOrder)
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c, width in zip(range(1, len(COLS)), (110, 140, 140, 110)):
            h.setSectionResizeMode(c, QHeaderView.Fixed)
            self.tree.setColumnWidth(c, width)
        self.tree.setItemDelegate(Heat(mon))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.menu)
        self.tree.itemSelectionChanged.connect(self.selection_changed)
        QShortcut(QKeySequence.Delete, self.tree, lambda: self.stop(False), context=Qt.WidgetShortcut)
        v.addWidget(self.tree, 1)
        self.apps = {}  # name: (item, {pid: item})
        self.selection_changed()

    def show(self, snap):
        query = self.search.text().strip().lower()
        uid = 1000 if DEMO else __import__("os").getuid()
        groups = sm.group(p for p in snap.procs if not self.mine.isChecked() or p.uid == uid)
        if query:
            groups = {n: ps for n, ps in groups.items()
                      if query in n.lower() or any(query in p.command.lower() for p in ps)}
        self.tree.setSortingEnabled(False)  # re-sorted once at the end, not per cell
        for name in list(self.apps):
            if name not in groups:
                item, _ = self.apps.pop(name)
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        for name, ps in groups.items():
            if name not in self.apps:
                item = Row(self.tree)
                item.setText(0, name)
                item.setIcon(0, self.app_icon(name, ps))
                self.apps[name] = (item, {})
            item, kids = self.apps[name]
            self.fill(item, sum(p.cpu for p in ps), sum(p.rss for p in ps), sum(p.io_rate for p in ps),
                      ", ".join(sorted({p.user for p in ps})))
            item.setData(0, Qt.UserRole, [p.pid for p in ps])
            item.setText(0, name if len(ps) == 1 else f"{name}  ({len(ps)})")
            item.setToolTip(0, ps[0].command if len(ps) == 1 else f"{len(ps)} processes")
            if len(ps) == 1:  # one process: the app row is the process
                for pid in list(kids):
                    item.removeChild(kids.pop(pid))
                continue
            alive = {p.pid for p in ps}
            for pid in list(kids):
                if pid not in alive:
                    item.removeChild(kids.pop(pid))
            for p in ps:
                kid = kids.get(p.pid)
                if kid is None:
                    kid = kids[p.pid] = Row(item)
                    kid.setData(0, Qt.UserRole, [p.pid])
                kid.setText(0, self.short(p.command))
                kid.setToolTip(0, f"{p.command}\nProcess {p.pid}")
                self.fill(kid, p.cpu, p.rss, p.io_rate, p.user)
        self.tree.setSortingEnabled(True)

    @staticmethod
    def short(command):
        return command if len(command) < 90 else command[:87] + "…"

    @staticmethod
    def fill(item, cpu, rss, io, user):
        for c, text, num in ((1, pct(cpu), cpu), (2, sm.size(rss), rss), (3, rate(io) if io >= 1000 else "—", io)):
            item.setText(c, text)
            item.setData(c, SORT, float(num))
            item.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
        item.setText(4, "    " + user)  # clear of the right-aligned numbers

    def app_icon(self, name, ps):
        exe = Path(ps[0].command.split()[0]).name if ps[0].command else ""
        for key in (exe, name.lower()):
            entry = sm.apps().get(key)
            if entry and entry[1] and QIcon.hasThemeIcon(entry[1]):
                return QIcon.fromTheme(entry[1])
        found = next((icon for app, icon, *_ in DemoSampler.APPS if app == name and icon), None) if DEMO else None
        if found and QIcon.hasThemeIcon(found):
            return QIcon.fromTheme(found)
        return S.icon("system", S.MUTED, 18)  # a background program, not an app

    def selected_pids(self):
        pids = []
        for item in self.tree.selectedItems():
            pids += item.data(0, Qt.UserRole) or []
        return pids

    def selection_changed(self):
        on = bool(self.selected_pids())
        self.end.setEnabled(on)
        self.force.setEnabled(on)

    def menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        m = QMenu(self)
        m.addAction("End", lambda: self.stop(False))
        m.addAction("Force stop", lambda: self.stop(True))
        m.addSeparator()
        m.addAction("Copy command", lambda: QApplication.clipboard().setText(item.toolTip(0).split("\n")[0]))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def stop(self, force):
        pids = self.selected_pids()
        items = self.tree.selectedItems()
        if not pids:
            return
        what = items[0].text(0).split("  (")[0] if len(items) == 1 else f"{len(items)} items"
        if force and QMessageBox.question(
                self, "Force stop?", f"{what} will stop at once. Anything it hasn't saved is lost.") != QMessageBox.Yes:
            return
        if DEMO:
            self.mon.status.setText(f"Demo mode · {what} would be {'stopped' if force else 'asked to close'}.")
            return
        others = []
        for pid in pids:
            why = sm.stop(pid, force)
            if why == "permission":
                others.append(pid)
        if others:
            # Another user's (often root's): the system's own password prompt
            sig = "-KILL" if force else "-TERM"
            subprocess.Popen(["pkexec", "kill", sig, *map(str, others)])
        self.mon.status.setText(f"{what}: {'stopped' if force else 'asked to close'}.")


# ------------------------------------------------------------------ performance

class Device(QFrame):
    """A row in the device list, in its resource's colour: name, the value now, a small graph. Click to see it large."""

    def __init__(self, key, icon, name, mon, color):
        super().__init__()
        self.key, self.mon, self.color = key, mon, color
        self.setObjectName("device")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 8)
        v.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(icon_label(icon, color, 16))
        self.name = label(self.fontMetrics().elidedText(name, Qt.ElideRight, 130), None, wrap=False)
        self.name.setToolTip(name)
        head.addWidget(self.name, 1)
        self.value = label("—", "devValue", wrap=False)
        head.addWidget(self.value)
        v.addLayout(head)
        self.spark = Sparkline(points=60, height=30, fixed=True, color=color)
        v.addWidget(self.spark)
        self.picked(False)

    def picked(self, on):
        self.setProperty("picked", on)  # a plate tinted in its resource's colour (hub_style)
        self.setProperty("plateColor", QColor(self.color))
        self.update()

    def mousePressEvent(self, _e):
        self.mon.perf.pick(self.key)


class PerformancePage(QWidget):
    def __init__(self, mon):
        super().__init__()
        self.mon = mon
        self.devices = {}
        self.history = {}  # key: [values 0..1] for the large graph
        self.current = "cpu"
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)
        side = QWidget()
        side.setFixedWidth(250)
        self.side = QVBoxLayout(side)
        self.side.setContentsMargins(0, 0, 0, 0)
        self.side.setSpacing(8)
        self.side.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(side)
        scroll.setFixedWidth(262)
        h.addWidget(scroll)

        detail = QFrame()
        detail.setObjectName("card")
        detail.setAttribute(Qt.WA_StyledBackground, True)
        d = QVBoxLayout(detail)
        d.setContentsMargins(22, 18, 22, 18)
        d.setSpacing(10)
        top = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        self.title = label("", "cardTitle", wrap=False)
        self.subtitle = label("", "sub", wrap=False)
        names.addWidget(self.title)
        names.addWidget(self.subtitle)
        top.addLayout(names, 1)
        self.headline = label("", "headline", wrap=False)
        top.addWidget(self.headline, 0, Qt.AlignTop)
        d.addLayout(top)
        self.big = Graph()
        d.addWidget(self.big, 1)
        self.scale = label("", "muted", wrap=False)
        d.addWidget(self.scale)
        self.cores = QGridLayout()
        self.cores.setSpacing(6)
        d.addLayout(self.cores)
        self.stats = QHBoxLayout()
        self.stats.setSpacing(10)
        d.addLayout(self.stats)
        h.addWidget(detail, 1)
        self.core_sparks = []
        self.stat_labels = []

    def device(self, key, icon, name, color):
        if key not in self.devices:
            dev = Device(key, icon, name, self.mon, color)
            self.side.insertWidget(self.side.count() - 1, dev)
            self.devices[key] = dev
        return self.devices[key]

    def push(self, key, frac, frac2=None):
        hist = self.history.setdefault(key, ([], []))
        hist[0].append(max(0.0, min(1.0, frac)))
        del hist[0][:-60]
        if frac2 is not None:
            hist[1].append(max(0.0, min(1.0, frac2)))
            del hist[1][:-60]

    def show(self, snap):
        info = {}
        dev = self.device("cpu", "cpu", "Processor", KIND["cpu"])
        dev.value.setText(pct(snap.cpu))
        dev.spark.push(snap.cpu / 100)
        self.push("cpu", snap.cpu / 100)
        info["cpu"] = ("Processor", f"{len(snap.cores)} cores" + (f" · {snap.cpu_temp:.0f} °C" if snap.cpu_temp else ""),
                       "0–100% of all cores", pct(snap.cpu), KIND["cpu"], ("100%", "50%", "0%"),
                       [("Speed", f"{snap.cpu_mhz / 1000:.2f} GHz" if snap.cpu_mhz else "—"),
                        ("Cores", str(len(snap.cores)) or "—"),
                        ("Processes", str(len(snap.procs))),
                        ("Up for", self.uptime(snap.uptime))])

        mem = snap.mem_used / snap.mem_total if snap.mem_total else 0
        dev = self.device("mem", "memory", "Memory", KIND["mem"])
        dev.value.setText(f"{sm.gib(snap.mem_used)}")
        dev.spark.push(mem)
        self.push("mem", mem)
        info["mem"] = ("Memory", f"of {sm.gib(snap.mem_total)} in use", "0 – all memory", sm.gib(snap.mem_used), KIND["mem"],
                       (sm.gib(snap.mem_total), sm.gib(snap.mem_total / 2), "0"),
                       [("Available", sm.gib(snap.mem_total - snap.mem_used)),
                        ("Swap", f"{sm.gib(snap.swap_used)} of {sm.gib(snap.swap_total)}" if snap.swap_total else "Off")])

        for i, g in enumerate(snap.gpus):
            key = f"gpu{i}"
            dev = self.device(key, "gpu", g.name, KIND["gpu"])
            dev.value.setText(pct(g.busy))
            dev.spark.push(g.busy / 100)
            self.push(key, g.busy / 100)
            info[key] = (g.name, "busy" + (f" · {g.temp:.0f} °C" if g.temp else "") + (f" · {g.power:.0f} W" if g.power else ""),
                         "0–100% busy", pct(g.busy), KIND["gpu"], ("100%", "50%", "0%"),
                         [("Video memory", f"{sm.gib(g.vram_used)} of {sm.gib(g.vram_total)}"),
                          ("Power", f"{g.power:.0f} W" if g.power else "—"),
                          ("Card", g.card)])

        for name, (r, w) in sorted(snap.disks.items()):
            key = f"disk:{name}"
            dev = self.device(key, "drives", f"Disk {name}", KIND["disk"])
            dev.value.setText(rate(r + w))
            busy = r + w
            # Disks have no fixed top: scale to 3 GB/s, a fast NVMe's sustained speed
            dev.spark.push(min(1.0, busy / 3e9) ** 0.5)
            self.push(key, min(1.0, r / 3e9) ** 0.5, min(1.0, w / 3e9) ** 0.5)
            info[key] = (f"Disk {name}", f"reading {rate(r)} · writing {rate(w)}",
                         "0 – 3 GB/s (square-root scale, so small activity still shows) · amber read, white write",
                         rate(r + w), KIND["disk"], ("3 GB/s", "750 MB/s", "0"),
                         [("Read", rate(r)), ("Write", rate(w))])

        down, up = snap.net
        dev = self.device("net", "network", "Network", KIND["net"])
        dev.value.setText(rate(down))
        # 0 – 1 Gbit/s on a square-root scale
        dev.spark.push(min(1.0, down / 1.25e8) ** 0.5)
        self.push("net", min(1.0, down / 1.25e8) ** 0.5, min(1.0, up / 1.25e8) ** 0.5)
        info["net"] = ("Network", f"down · up {rate(up)}",
                       "0 – 1 Gbit/s (square-root scale) · cyan down, light up", rate(down), KIND["net"],
                       ("1 Gbit/s", "250 Mbit/s", "0"),
                       [("Download", rate(down)), ("Upload", rate(up))])

        self.info = info
        if self.current not in info:
            self.current = "cpu"
        self.render(snap)

    @staticmethod
    def uptime(sec):
        h, m = int(sec // 3600), int(sec % 3600 // 60)
        return f"{h} h {m} min" if h else f"{m} min"

    def pick(self, key):
        self.current = key
        self.render(None)

    def render(self, snap):
        for k, dev in self.devices.items():
            dev.picked(k == self.current)
        title, sub, scale, headline, color, ticks, stats = self.info[self.current]
        self.title.setText(title)
        self.subtitle.setText(sub)
        self.headline.setText(headline)
        self.headline.setStyleSheet(f"color: {color};")
        self.scale.setText(f"Last 60 seconds · {scale}")
        hist, hist2 = self.history.get(self.current, ([], []))
        second = UPLOAD if self.current == "net" else S.TEXT
        self.big.set([(list(hist), color)] + ([(list(hist2), second)] if hist2 else []), ticks)
        # The tiles are made once and reused: rebuilding them every second flickers
        while len(self.stat_labels) < len(stats):
            tile = QFrame()
            tile.setObjectName("stat")
            tile.setAttribute(Qt.WA_StyledBackground, True)
            t = QVBoxLayout(tile)
            t.setContentsMargins(12, 9, 12, 9)
            t.setSpacing(1)
            pair = (label("", "muted", wrap=False), label("", "statValue", wrap=False), tile)
            t.addWidget(pair[0])
            t.addWidget(pair[1])
            self.stats.addWidget(tile, 1)
            self.stat_labels.append(pair)
        for i, (name, value, tile) in enumerate(self.stat_labels):
            tile.setVisible(i < len(stats))
            if i < len(stats):
                name.setText(stats[i][0])
                value.setText(stats[i][1])
        # one small graph per core under the processor
        show_cores = self.current == "cpu" and snap is not None and snap.cores
        while len(self.core_sparks) < (len(snap.cores) if show_cores else 0):
            sp = Sparkline(points=30, height=26, fixed=True, color=KIND["cpu"])
            self.cores.addWidget(sp, len(self.core_sparks) // 8, len(self.core_sparks) % 8)
            self.core_sparks.append(sp)
        for i, sp in enumerate(self.core_sparks):
            sp.setVisible(self.current == "cpu")
            if show_cores and i < len(snap.cores):
                sp.push(snap.cores[i] / 100)


# ------------------------------------------------------------------ window

class Monitor(QWidget):
    def __init__(self, page="processes"):
        super().__init__()
        self.setWindowTitle("DecKoOS System Monitor")
        self.setWindowIcon(QIcon.fromTheme("deckos"))
        self.resize(1080, 720)
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(S.qss() + QSS)
        self.sampler = DemoSampler() if DEMO else sm.Sampler()
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 14)
        v.setSpacing(14)

        head = QHBoxLayout()
        head.addWidget(icon_label("gauge", S.P.accent, 26))
        head.addWidget(label("System Monitor", "title", wrap=False))
        head.addSpacing(20)
        self.segs = QButtonGroup(self)
        for i, (text, icon) in enumerate((("Processes", "list"), ("Performance", "gauge"))):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setIcon(S.icon(icon, S.SUBTEXT, 16))
            b.setCursor(Qt.PointingHandCursor)
            self.segs.addButton(b, i)
            head.addWidget(b)
        head.addStretch(1)
        self.chips = {}
        for key, name in (("cpu", "CPU"), ("mem", "RAM"), ("gpu", "GPU")):
            chip = label("", "chip", wrap=False)
            chip.setTextFormat(Qt.RichText)
            self.chips[key] = (chip, name)
            head.addWidget(chip)
        v.addLayout(head)
        # While a game runs: what DecKoOS did to make room for it, on a line of its own
        self.mode = label("", "mode")  # wraps rather than widen the window
        self.mode.hide()
        v.addWidget(self.mode)

        self.stack = QStackedWidget()
        self.procs = ProcessesPage(self)
        self.perf = PerformancePage(self)
        self.stack.addWidget(self.procs)
        self.stack.addWidget(self.perf)
        v.addWidget(self.stack, 1)
        self.status = label("", "muted", wrap=False)
        v.addWidget(self.status)
        self.segs.idClicked.connect(self.stack.setCurrentIndex)
        start = 1 if page == "performance" else 0
        self.segs.button(start).setChecked(True)
        self.stack.setCurrentIndex(start)

        self.snap = None
        self.timer = QTimer(self, interval=1000, timeout=self.tick)
        self.sampler.sample()  # the baseline the first rates are measured from
        if DEMO:
            for _ in range(59):  # a minute of history, so the graphs have something to show
                self.perf.show(self.sampler.sample())
        QTimer.singleShot(250 if not DEMO else 0, self.tick)
        self.timer.start()

    def tick(self):
        self.snap = self.sampler.sample()
        self.refresh_view()

    def refresh_view(self):
        s = self.snap
        if not s:
            return
        gpu = s.gpus[0] if s.gpus else None
        values = {"cpu": pct(s.cpu), "mem": sm.gib(s.mem_used), "gpu": pct(gpu.busy) if gpu else None}
        for key, (chip, name) in self.chips.items():
            chip.setVisible(values[key] is not None)
            if values[key] is not None:
                chip.setText(f'<span style="color:{KIND[key]}">●</span>&nbsp; {name} <b>{values[key]}</b>')
        m = DEMO_MODE if DEMO else sm.mode()
        if m.get("mode") == "gaming":
            freed = float(m.get("vram") or 0)
            game = m.get("game") or "a game"
            self.mode.setText(f"Gaming mode · {game}  ·  " +
                              (f"{freed / 1e9:.1f} GB of graphics memory freed, " if freed >= 1e8 else "local AI unloaded, ") +
                              "Docker paused, indexing stopped until it ends")
        self.mode.setVisible(m.get("mode") == "gaming")
        self.tree_totals(s)
        self.perf.show(s)
        self.procs.show(s)

    def tree_totals(self, s):
        """The column headers carry the PC's totals, as a reminder of what the rows add up to."""
        head = self.procs.tree.headerItem()
        head.setText(1, f"CPU  {pct(s.cpu)}")
        head.setText(2, f"Memory  {sm.gib(s.mem_used)}")
        head.setText(3, f"Disk  {rate(sum(r + w for r, w in s.disks.values()))}")

    # No sampling while nobody can see the window (as in DecKoOS Hub)
    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                self.timer.stop()
            elif not self.timer.isActive():
                self.tick()
                self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def showEvent(self, e):
        super().showEvent(e)
        if hasattr(self, "timer") and not self.timer.isActive():
            self.timer.start()


def main():
    app = QApplication(sys.argv)
    if DEMO and QIcon.themeName() in ("", "hicolor"):  # offscreen: no Plasma theme to pick the icons
        QIcon.setThemeSearchPaths(QIcon.themeSearchPaths() + ["/usr/share/icons"])
        QIcon.setThemeName("Papirus-Dark")
    app.setApplicationName("DecKoOS System Monitor")
    app.setDesktopFileName("deckos-sysmon")
    app.setFont(QFont("Inter", 10))
    page = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv[:-1] else "processes"
    win = Monitor(page)
    if "--screenshot" in sys.argv[:-1]:
        out = Path(sys.argv[sys.argv.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)
        win.show()
        win.tick()
        for i, name in enumerate(("processes", "performance")):
            win.segs.button(i).click()
            app.processEvents()
            win.grab().save(str(out / f"sysmon-{name}.png"))
        sys.exit(0)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
