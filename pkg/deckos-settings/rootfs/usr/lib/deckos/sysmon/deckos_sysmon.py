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

from PySide6.QtCore import QEvent, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout,  # noqa: E402
                               QHeaderView, QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import hub_style as S  # noqa: E402
import sysmon as sm  # noqa: E402
from hub_widgets import Sparkline, button, icon_label, label, restyle  # noqa: E402

DEMO = "--demo" in sys.argv
COLS = ["Name", "CPU", "Memory", "Disk", "User"]
UPLOAD = "#0EA08E"  # the second network line (same validated pair as DecKoOS Performance)

QSS = f"""
QTreeWidget {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 10px; padding: 4px;
    alternate-background-color: {S.SURFACE}; outline: 0; }}
QTreeWidget::item {{ height: 30px; border: none; }}
QTreeWidget::item:selected {{ background: rgba(76, 141, 255, 0.16); color: {S.TEXT}; }}
QTreeWidget::item:hover {{ background: {S.RAISED}; }}
QHeaderView::section {{ background: transparent; color: {S.SUBTEXT}; border: none; border-bottom: 1px solid {S.BORDER};
    padding: 6px 8px; font-weight: 600; }}
QFrame#device {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 10px; }}
QFrame#device[picked="true"] {{ background: rgba(76, 141, 255, 0.10); border-color: rgba(76, 141, 255, 0.45); }}
QLabel#big {{ font-family: "Inter Display", "Inter"; font-size: 22pt; font-weight: 600; }}
QPushButton#danger:disabled {{ background: {S.RAISED}; color: {S.MUTED}; }}
QPushButton#seg {{ padding: 6px 14px; border-radius: 8px; background: transparent; border: 1px solid transparent; }}
QPushButton#seg:checked {{ background: {S.RAISED}; border-color: {S.BORDER}; color: {S.TEXT}; }}
"""


def pct(v):
    return f"{v:.0f}%" if v >= 1 or v == 0 else f"{v:.1f}%"


def rate(v):
    return sm.size(v) + "/s"


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
        for c, width in zip(range(1, len(COLS)), (90, 100, 110, 120)):
            h.setSectionResizeMode(c, QHeaderView.Fixed)
            self.tree.setColumnWidth(c, width)
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
        return S.icon("grid", S.SUBTEXT, 18)

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
    """A row in the device list: name, the value now, a small graph. Click to see it large."""

    def __init__(self, key, icon, name, mon, color=None):
        super().__init__()
        self.key, self.mon = key, mon
        self.setObjectName("device")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("picked", False)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 8)
        v.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(7)
        head.addWidget(icon_label(icon, S.SUBTEXT, 15))
        self.name = label(self.fontMetrics().elidedText(name, Qt.ElideRight, 140), None, wrap=False)
        self.name.setToolTip(name)
        head.addWidget(self.name, 1)
        self.value = label("—", "sub", wrap=False)
        head.addWidget(self.value)
        v.addLayout(head)
        self.spark = Sparkline(points=60, height=28, fixed=True, color=color)
        v.addWidget(self.spark)

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
        self.title = label("", "cardTitle", wrap=False)
        self.subtitle = label("", "sub", wrap=False)
        d.addWidget(self.title)
        d.addWidget(self.subtitle)
        self.big = Sparkline(points=60, height=0, fixed=True)
        self.big.setMinimumHeight(220)
        d.addWidget(self.big, 1)
        self.second = Sparkline(points=60, height=0, fixed=True, color=UPLOAD)  # network upload, drawn over
        self.second.setParent(self.big)
        self.scale = label("", "muted", wrap=False)
        d.addWidget(self.scale)
        self.cores = QGridLayout()
        self.cores.setSpacing(6)
        d.addLayout(self.cores)
        self.stats = QGridLayout()
        self.stats.setHorizontalSpacing(28)
        self.stats.setVerticalSpacing(4)
        d.addLayout(self.stats)
        h.addWidget(detail, 1)
        self.core_sparks = []
        self.stat_labels = []

    def device(self, key, icon, name, color=None):
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
        dev = self.device("cpu", "cpu", "Processor")
        dev.value.setText(pct(snap.cpu))
        dev.spark.push(snap.cpu / 100)
        self.push("cpu", snap.cpu / 100)
        info["cpu"] = ("Processor", f"{pct(snap.cpu)} in use" + (f" · {snap.cpu_temp:.0f} °C" if snap.cpu_temp else ""),
                       "0–100% of all cores",
                       [("Speed", f"{snap.cpu_mhz / 1000:.2f} GHz" if snap.cpu_mhz else "—"),
                        ("Cores", str(len(snap.cores)) or "—"),
                        ("Processes", str(len(snap.procs))),
                        ("Up for", self.uptime(snap.uptime))])

        mem = snap.mem_used / snap.mem_total if snap.mem_total else 0
        dev = self.device("mem", "memory", "Memory")
        dev.value.setText(f"{sm.gib(snap.mem_used)}")
        dev.spark.push(mem)
        self.push("mem", mem)
        info["mem"] = ("Memory", f"{sm.gib(snap.mem_used)} of {sm.gib(snap.mem_total)} in use", "0 – all memory",
                       [("Available", sm.gib(snap.mem_total - snap.mem_used)),
                        ("Swap", f"{sm.gib(snap.swap_used)} of {sm.gib(snap.swap_total)}" if snap.swap_total else "Off")])

        for i, g in enumerate(snap.gpus):
            key = f"gpu{i}"
            dev = self.device(key, "gpu", g.name if len(snap.gpus) == 1 or i else g.name)
            dev.value.setText(pct(g.busy))
            dev.spark.push(g.busy / 100)
            self.push(key, g.busy / 100)
            info[key] = (g.name, f"{pct(g.busy)} busy" + (f" · {g.temp:.0f} °C" if g.temp else ""), "0–100% busy",
                         [("Video memory", f"{sm.gib(g.vram_used)} of {sm.gib(g.vram_total)}"),
                          ("Power", f"{g.power:.0f} W" if g.power else "—"),
                          ("Card", g.card)])

        for name, (r, w) in sorted(snap.disks.items()):
            key = f"disk:{name}"
            dev = self.device(key, "drives", f"Disk {name}")
            dev.value.setText(rate(r + w))
            busy = r + w
            # Disks have no fixed top: scale to 3 GB/s, a fast NVMe's sustained speed
            dev.spark.push(min(1.0, busy / 3e9) ** 0.5)
            self.push(key, min(1.0, r / 3e9) ** 0.5, min(1.0, w / 3e9) ** 0.5)
            info[key] = (f"Disk {name}", f"Reading {rate(r)} · writing {rate(w)}",
                         "0 – 3 GB/s (square-root scale, so small activity still shows)",
                         [("Read", rate(r)), ("Write", rate(w))])

        down, up = snap.net
        dev = self.device("net", "network", "Network", None)
        dev.value.setText(rate(down))
        # 0 – 1 Gbit/s on a square-root scale
        dev.spark.push(min(1.0, down / 1.25e8) ** 0.5)
        self.push("net", min(1.0, down / 1.25e8) ** 0.5, min(1.0, up / 1.25e8) ** 0.5)
        info["net"] = ("Network", f"Down {rate(down)} · up {rate(up)}",
                       "0 – 1 Gbit/s (square-root scale) · blue down, teal up",
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
            if dev.property("picked") != (k == self.current):
                dev.setProperty("picked", k == self.current)
                restyle(dev)
        title, sub, scale, stats = self.info[self.current]
        self.title.setText(title)
        self.subtitle.setText(sub)
        self.scale.setText(f"Last 60 seconds · {scale}")
        hist, hist2 = self.history.get(self.current, ([], []))
        self.big.data.clear()
        self.big.data.extend(hist)
        self.big.update()
        self.second.setVisible(bool(hist2))
        self.second.setGeometry(self.big.rect())
        self.second.data.clear()
        self.second.data.extend(hist2)
        self.second.update()
        # The labels are made once and reused: rebuilding them every second flickers
        while len(self.stat_labels) < len(stats):
            i = len(self.stat_labels)
            pair = (label("", "muted", wrap=False), label("", None, wrap=False))
            self.stats.addWidget(pair[0], 0, i)
            self.stats.addWidget(pair[1], 1, i)
            self.stat_labels.append(pair)
        for i, (name, value) in enumerate(self.stat_labels):
            shown = i < len(stats)
            name.setVisible(shown)
            value.setVisible(shown)
            if shown:
                name.setText(stats[i][0])
                value.setText(f"<b>{stats[i][1]}</b>")
        # one small graph per core under the processor
        show_cores = self.current == "cpu" and snap is not None and snap.cores
        while len(self.core_sparks) < (len(snap.cores) if show_cores else 0):
            sp = Sparkline(points=30, height=26, fixed=True)
            self.cores.addWidget(sp, len(self.core_sparks) // 8, len(self.core_sparks) % 8)
            self.core_sparks.append(sp)
        for i, sp in enumerate(self.core_sparks):
            sp.setVisible(self.current == "cpu")
            if show_cores and i < len(snap.cores):
                sp.push(snap.cores[i] / 100)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.second.setGeometry(self.big.rect())


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
        self.summary = label("", "sub", wrap=False)
        head.addWidget(self.summary)
        v.addLayout(head)

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
        self.summary.setText(f"Processor {pct(s.cpu)}   ·   Memory {sm.gib(s.mem_used)}"
                             + (f"   ·   Graphics {pct(gpu.busy)}" if gpu else ""))
        self.perf.show(s)
        self.procs.show(s)

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
