"""DecKoOS Downloads, the window: paste or drop a link, watch it come in, pause, resume, open it when it's done.

    deckos-downloads [URL] [--demo [--screenshot DIR]]

The downloading itself is the user service (downloads.py serve), so closing the window changes nothing. This reads
the queue file whenever it changes (a file watcher; no timers of its own while nothing moves) and changes it
through downloads.py. A link on the clipboard is offered when the window opens.
"""
import sys
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

from PySide6.QtCore import QFileSystemWatcher, QPointF, QRectF, QSize, Qt, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QLinearGradient,  # noqa: E402
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLineEdit, QScrollArea,  # noqa: E402
                               QVBoxLayout, QWidget)

import downloads as D  # noqa: E402
import hub_style as S  # noqa: E402
from hub_widgets import Empty, Meter, Toast, button, icon_label, label  # noqa: E402

DEMO = "--demo" in sys.argv
# A file's badge: its kind's colour and a short word for it
KINDS = [({"iso", "img", "qcow2", "vhd", "vdi"}, "#A27BFF", "DISC"),
         ({"zip", "7z", "rar", "tar", "gz", "xz", "zst", "bz2", "tgz"}, "#F5B84B", "PACK"),
         ({"mkv", "mp4", "webm", "mov", "avi", "m4v"}, "#FF8FB1", "VIDEO"),
         ({"flac", "mp3", "ogg", "opus", "wav", "m4a"}, "#2AC3DE", "AUDIO"),
         ({"appimage", "exe", "msi", "deb", "rpm", "flatpakref", "sh", "run"}, "#3DD68C", "APP"),
         ({"pdf", "epub", "doc", "docx", "odt", "txt", "md"}, "#FF6B6B", "DOC"),
         ({"png", "jpg", "jpeg", "webp", "gif", "svg", "avif"}, "#4C8DFF", "IMAGE")]

QSS = f"""
QFrame#dlItem, QFrame#dlLink, QFrame#dlSpeed {{ background: transparent; border: none; }}
QFrame#dlItem QLabel, QFrame#dlLink QLabel, QFrame#dlSpeed QLabel {{ background: transparent; }}
QLabel#appTitle {{ font-family: "{S.HUD}", "Inter Display"; font-size: 19pt; font-weight: 700; }}
QLabel#name {{ font-size: 10.5pt; font-weight: 600; }}
QLabel#speed {{ font-family: "{S.HUD}"; font-size: 30pt; font-weight: 700; }}
QLabel#unit {{ font-family: "{S.HUD}"; font-size: 12pt; font-weight: 600; color: {S.SUBTEXT}; }}
QLabel#stateDone {{ color: {S.SUCCESS}; }}
QLabel#stateBad {{ color: {S.DANGER}; }}
QLabel#stateWait {{ color: {S.WARNING}; }}
QLineEdit#link {{ background: {S.BG}; border: 1px solid {S.BORDER}; border-radius: 2px; padding: 11px 14px;
    font-size: 11pt; selection-background-color: {S.P.accent}; }}
QLineEdit#link:focus {{ border-color: {S.P.accent}; }}
QPushButton#icon {{ padding: 7px; }}
"""


def kind(name):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if name.lower().endswith((".tar.gz", ".tar.xz", ".tar.zst")):
        ext = "tar"
    for exts, colour, word in KINDS:
        if ext in exts:
            return colour, word
    return S.SUBTEXT, (ext[:4].upper() or "FILE")


def speed_parts(bps):
    for unit, step in (("GB/s", 1e9), ("MB/s", 1e6), ("KB/s", 1e3)):
        if bps >= step:
            v = bps / step
            return (f"{v:.1f}" if v < 100 else f"{v:.0f}"), unit
    return "0", "MB/s"


class Badge(QWidget):
    """A notched tile in the file kind's colour with its word, and while it comes in, a lit edge that fills
    clockwise with the download."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(52, 52)
        self.colour, self.word, self.frac, self.active = S.SUBTEXT, "FILE", 0.0, False

    def set(self, name, frac, active):
        self.colour, self.word = kind(name)
        self.frac, self.active = frac, active
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = S.notch_path(r, 11)
        c = QColor(self.colour)
        fill = QLinearGradient(r.topLeft(), r.bottomRight())
        a, b = QColor(c), QColor(c)
        a.setAlphaF(0.28)
        b.setAlphaF(0.08)
        fill.setColorAt(0, a)
        fill.setColorAt(1, b)
        p.fillPath(path, fill)
        edge = QColor(c)
        edge.setAlphaF(0.35)
        p.setPen(QPen(edge, 1))
        p.drawPath(path)
        if self.active and self.frac > 0:  # the edge lights up as the file arrives
            length = path.length()
            pen = QPen(QColor(c), 2)
            pen.setDashPattern([max(0.01, self.frac * length / 2), 10000])
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.drawPath(path)
        p.setPen(QColor(c).lighter(130))
        f = QFont(S.HUD, 8 if len(self.word) > 4 else 9, QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        p.setFont(f)
        p.drawText(r, Qt.AlignCenter, self.word)


class SpeedGraph(QWidget):
    """The last two minutes of speed, every download together: a line on a soft fill in the accent's gradient,
    scaled to the fastest moment, with faint guides."""

    def __init__(self):
        super().__init__()
        self.data = deque([0.0] * 240, maxlen=240)
        self.setMinimumHeight(86)

    def push(self, v):
        self.data.append(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 4
        p.setPen(QPen(QColor(S.BORDER), 1, Qt.DotLine))
        for i in (1, 2, 3):
            p.drawLine(QPointF(0, h * i / 4), QPointF(w, h * i / 4))
        top = max(max(self.data), 1.0) * 1.15
        step = w / (len(self.data) - 1)
        pts = [QPointF(i * step, 2 + h * (1 - v / top)) for i, v in enumerate(self.data)]
        line = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):  # smoothed: midpoints joined by curves
            mid = (a + b) / 2
            line.quadTo(a, mid)
        line.lineTo(pts[-1])
        area = QPainterPath(line)
        area.lineTo(w, h + 4)
        area.lineTo(0, h + 4)
        area.closeSubpath()
        g = QLinearGradient(0, 0, 0, h)
        ca, cb = QColor(S.P.accent), QColor(S.P.grad_b)
        ca.setAlpha(90)
        cb.setAlpha(0)
        g.setColorAt(0, ca)
        g.setColorAt(1, cb)
        p.fillPath(area, g)
        lg = QLinearGradient(0, 0, w, 0)
        lg.setColorAt(0, QColor(S.P.grad_b))
        lg.setColorAt(1, QColor(S.P.accent))
        p.setPen(QPen(lg, 2))
        p.drawPath(line)
        if self.data[-1] > 0:  # where it is now
            p.setPen(Qt.NoPen)
            glow = QColor(S.P.accent)
            glow.setAlpha(60)
            p.setBrush(glow)
            p.drawEllipse(pts[-1], 7, 7)
            p.setBrush(QColor(S.P.accent))
            p.drawEllipse(pts[-1], 3.5, 3.5)


class Item(QFrame):
    """One download: badge, name, what's happening, a segmented meter while it comes in, and its buttons."""

    def __init__(self, win, job):
        super().__init__()
        self.win, self.id = win, job["id"]
        self.setObjectName("dlItem")
        self.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 12, 12)
        h.setSpacing(14)
        self.badge = Badge()
        h.addWidget(self.badge, 0, Qt.AlignVCenter)
        mid = QVBoxLayout()
        mid.setSpacing(5)
        self.name = label("", "name", wrap=False)
        self.line = label("", "sub", wrap=False)
        self.meter = Meter(5)
        mid.addWidget(self.name)
        mid.addWidget(self.line)
        mid.addWidget(self.meter)
        h.addLayout(mid, 1)
        self.pct = label("", "big", wrap=False)
        self.pct.setMinimumWidth(64)
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self.pct)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(6)
        h.addLayout(self.buttons)
        self.shown = None
        self.set(job)

    def icon_button(self, name, tip, slot, kind=None):
        b = button("", kind=kind or "icon", icon=name, tip=tip, slot=slot)
        b.setIconSize(QSize(17, 17))
        b.setFixedSize(38, 36)
        return b

    def set(self, job):
        self.job = job
        st = job["state"]
        frac = job["got"] / job["size"] if job.get("size") else 0
        coming = st in ("downloading", "queued", "waiting", "paused")
        self.badge.set(job["name"], frac, st == "downloading")
        self.name.setText(self.name.fontMetrics().elidedText(job["name"], Qt.ElideMiddle, 520))
        self.name.setToolTip(f"{job['name']}\n{job['url']}")
        self.line.setText(D.describe(job))
        self.line.setObjectName({"done": "stateDone", "failed": "stateBad", "waiting": "stateWait"}.get(st, "sub"))
        self.line.setStyle(self.line.style())
        self.meter.setVisible(coming)
        self.meter.set(frac, S.MUTED if st == "paused" else S.WARNING if st == "waiting" else None)
        self.pct.setVisible(coming and bool(job.get("size")))
        self.pct.setText(f"{frac * 100:.0f}%")
        self.setProperty("picked", st == "downloading")
        self.update()
        if self.shown != st:  # rebuild the buttons only when what you can do changes
            self.shown = st
            while self.buttons.count():
                w = self.buttons.takeAt(0).widget()
                w.setParent(None)
                w.deleteLater()
            for b in self.actions(st):
                self.buttons.addWidget(b)

    def actions(self, st):
        go = self.win.act
        if st in ("downloading", "queued", "waiting"):
            return [self.icon_button("pause", "Pause", lambda: go(self.id, "pause")),
                    self.icon_button("close", "Cancel and delete what's come so far", lambda: go(self.id, "cancel"))]
        if st == "paused":
            return [self.icon_button("play", "Resume", lambda: go(self.id, "resume"), "primary"),
                    self.icon_button("close", "Cancel and delete what's come so far", lambda: go(self.id, "cancel"))]
        if st == "failed":
            return [self.icon_button("refresh", "Try again", lambda: go(self.id, "resume"), "primary"),
                    self.icon_button("close", "Remove from the list", lambda: go(self.id, "remove"))]
        if st == "done":
            return [button("Open", "primary", slot=self.open),
                    self.icon_button("folder", "Show in its folder", self.reveal),
                    self.icon_button("close", "Remove from the list (the file stays)", lambda: go(self.id, "remove"))]
        return [self.icon_button("close", "Remove from the list", lambda: go(self.id, "remove"))]

    def path(self):
        return Path(self.job["folder"]) / self.job["name"]

    def open(self):
        if not DEMO:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path())))

    def reveal(self):
        if DEMO:
            return
        from PySide6.QtDBus import QDBusConnection, QDBusMessage
        msg = QDBusMessage.createMethodCall("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                                            "org.freedesktop.FileManager1", "ShowItems")
        msg.setArguments([[QUrl.fromLocalFile(str(self.path())).toString()], ""])
        if not QDBusConnection.sessionBus().send(msg):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.job["folder"]))


class Downloads(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DecKoOS Downloads" + (" — Demo" if DEMO else ""))
        self.setWindowIcon(QIcon.fromTheme("deckos-downloads", S.icon("download", S.P.accent, 32)))
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(S.qss() + QSS)
        self.setAcceptDrops(True)
        self.resize(980, 720)
        self.setMinimumSize(720, 520)
        self.items, self.jobs = {}, []
        self.folder = Path("~/Downloads").expanduser() if DEMO else D.saved_folder() or D.downloads_dir()

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 18)
        v.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(icon_label("download", S.P.accent, 30))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("DecKoOS Downloads", "appTitle", wrap=False))
        self.summary = label("", "sub", wrap=False)
        titles.addWidget(self.summary)
        head.addLayout(titles, 1)
        head.addWidget(button("Downloads folder", icon="folder", slot=self.open_folder))
        v.addLayout(head)

        # the link bar
        bar = QFrame()
        bar.setObjectName("dlLink")
        bv = QVBoxLayout(bar)
        bv.setContentsMargins(18, 16, 18, 14)
        bv.setSpacing(10)
        line = QHBoxLayout()
        line.setSpacing(10)
        self.link = QLineEdit()
        self.link.setObjectName("link")
        self.link.setPlaceholderText("Paste a link, or drop one here…")
        self.link.setClearButtonEnabled(True)
        self.link.returnPressed.connect(self.download)
        self.link.textChanged.connect(self.check_link)
        line.addWidget(self.link, 1)
        self.go = button("Download", "primary", slot=self.download, icon="download")
        self.go.setMinimumHeight(44)
        line.addWidget(self.go)
        bv.addLayout(line)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addWidget(icon_label("folder", S.MUTED, 14))
        self.where = label("", "muted", wrap=False)
        foot.addWidget(self.where)
        foot.addWidget(button("Change", slot=self.pick_folder))
        foot.addStretch(1)
        foot.addWidget(icon_label("refresh", S.MUTED, 14))
        foot.addWidget(label("Picks up where it stopped if the connection drops, even after a restart", "muted",
                             wrap=False))
        bv.addLayout(foot)
        v.addWidget(bar)

        # the speed of everything together
        self.speed_card = QFrame()
        self.speed_card.setObjectName("dlSpeed")
        sh = QHBoxLayout(self.speed_card)
        sh.setContentsMargins(20, 14, 20, 14)
        sh.setSpacing(22)
        nums = QVBoxLayout()
        nums.setSpacing(0)
        nums.addWidget(label("RIGHT NOW", "kicker"))
        speed_row = QHBoxLayout()
        speed_row.setSpacing(6)
        self.speed = label("0", "speed", wrap=False)
        self.unit = label("MB/s", "unit", wrap=False)
        speed_row.addWidget(self.speed)
        speed_row.addWidget(self.unit, 0, Qt.AlignBottom)
        speed_row.addStretch(1)
        nums.addLayout(speed_row)
        self.togo = label("", "sub", wrap=False)
        nums.addWidget(self.togo)
        sh.addLayout(nums)
        self.graph = SpeedGraph()
        sh.addWidget(self.graph, 1)
        v.addWidget(self.speed_card)

        # the list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        self.list = QVBoxLayout(holder)
        self.list.setContentsMargins(0, 0, 4, 0)
        self.list.setSpacing(8)
        self.scroll.setWidget(holder)
        v.addWidget(self.scroll, 1)
        self.empty = Empty("download", "Nothing downloading",
                           "Paste a link above. Big files keep going through dropped connections, sleep and "
                           "restarts, and land in your Downloads folder.")
        for lab in self.empty.findChildren(type(self.summary)):
            if lab.wordWrap():
                lab.setFixedWidth(440)  # wrapped text measured too narrow on the first pass and got cut
                lab.setFixedHeight(lab.heightForWidth(440))
        self.toast = Toast(self)

        self.set_where()
        self.check_link("")
        if DEMO:
            self.jobs = demo_jobs()
            self.demo_timer = QTimer(self, interval=500, timeout=self.demo_tick)
            self.demo_timer.start()
        else:
            D.STATE.mkdir(parents=True, exist_ok=True)
            self.watch = QFileSystemWatcher([str(D.STATE)], self)  # the queue is replaced, not written in place
            self.soon = QTimer(self, singleShot=True, interval=80, timeout=self.reload)
            self.watch.directoryChanged.connect(lambda _: self.soon.start())
            # nothing changes the file while nothing's downloading: the graph still has to fall back to zero
            self.idle = QTimer(self, interval=500, timeout=self.idle_tick)
            self.jobs = D.load()
        self.show_jobs()
        QTimer.singleShot(0, self.offer_clipboard)

    # ---- the queue

    def reload(self):
        self.jobs = D.load()
        self.show_jobs()

    def idle_tick(self):
        self.graph.push(0)
        if max(self.graph.data) == 0:
            self.idle.stop()

    def show_jobs(self):
        active = [j for j in self.jobs if j["state"] in D.ACTIVE + ("paused",)]
        done = [j for j in self.jobs if j["state"] in D.FINISHED]
        active.sort(key=lambda j: j["added"])
        done.sort(key=lambda j: -(j.get("finished") or j["added"]))
        while self.list.count():  # take the layout apart; Items are kept and put back
            it = self.list.takeAt(0)
            w = it.widget()
            if w is not None and not isinstance(w, Item) and w is not self.empty:
                w.setParent(None)
                w.deleteLater()
        keep = {j["id"] for j in self.jobs}
        for jid in [k for k in self.items if k not in keep]:
            gone = self.items.pop(jid)
            gone.hide()
            gone.setParent(None)
            gone.deleteLater()
        if not self.jobs:
            self.list.addWidget(self.empty)
            self.empty.show()
        else:
            self.empty.hide()
        for title, group, extra in (("Downloading", active, None), ("Finished", done, "clear")):
            if not group:
                continue
            row = QHBoxLayout()
            head = QWidget()
            head.setLayout(row)
            row.setContentsMargins(4, 6, 0, 0)
            row.addWidget(label(f"{title.upper()}  ·  {len(group)}", "kicker"))
            row.addStretch(1)
            if extra:
                row.addWidget(button("Clear the list", slot=self.clear))
            self.list.addWidget(head)
            for j in group:
                item = self.items.get(j["id"])
                if item is None:
                    item = self.items[j["id"]] = Item(self, j)
                else:
                    item.set(j)
                self.list.addWidget(item)
        self.list.addStretch(1)
        self.speed_card.setVisible(bool(self.jobs))
        self.show_totals(active)

    def show_totals(self, active):
        moving = [j for j in active if j["state"] == "downloading"]
        bps = sum(j.get("speed", 0) for j in moving)
        self.graph.push(bps)
        if not DEMO and not moving and max(self.graph.data) > 0:
            self.idle.start()
        n, u = speed_parts(bps)
        self.speed.setText(n)
        self.unit.setText(u)
        left = sum(max(0, j["size"] - j["got"]) for j in active if j.get("size"))
        if moving and bps and left:
            self.togo.setText(f"{D.size_text(left)} to go · about {D.time_text(left / bps)}")
        elif active:
            self.togo.setText("Waiting" if not any(j["state"] == "paused" for j in active) else "Paused")
        else:
            self.togo.setText("Nothing coming in")
        self.speed_card.setProperty("picked", bool(moving))
        self.speed_card.update()
        done = sum(1 for j in self.jobs if j["state"] == "done")
        parts = []
        if moving:
            parts.append(f"{len(moving)} downloading")
        if len(active) > len(moving):
            parts.append(f"{len(active) - len(moving)} waiting or paused")
        if done:
            parts.append(f"{done} finished")
        self.summary.setText(" · ".join(parts) or "Big files that don't give up")

    # ---- what you do

    def check_link(self, text):
        self.go.setEnabled(D.valid_url(text.strip()))

    def set_where(self):
        home = str(Path.home())
        shown = str(self.folder)
        self.where.setText("Saves to " + ("~" + shown[len(home):] if shown.startswith(home) else shown))

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Save downloads to", str(self.folder))
        if d:
            self.folder = Path(d)
            self.set_where()
            if not DEMO:
                D.save_folder(self.folder if self.folder != D.downloads_dir() else None)

    def download(self, url=None):
        url = (url or self.link.text()).strip()
        if not D.valid_url(url):
            self.toast.show_message("That isn't a web link: it needs to start with https://", "warn")
            return
        if DEMO:
            self.jobs.append({"id": str(len(self.jobs)), "url": url, "folder": str(self.folder),
                              "name": D.name_from_url(url) or "download", "state": "downloading", "got": 0,
                              "size": 3.2e9, "speed": 0, "added": time.time(), "finished": 0, "error": ""})
            self.show_jobs()
        else:
            try:
                j = D.add(url, self.folder)
            except (ValueError, OSError) as e:
                self.toast.show_message(str(e), "bad")
                return
            self.reload()
            self.toast.show_message(f"Downloading {j['name']}", "ok", 3000)
        self.link.clear()

    def act(self, job_id, how):
        if DEMO:
            for j in self.jobs:
                if j["id"] == job_id:
                    if how == "remove":
                        self.jobs.remove(j)
                    else:
                        j["state"] = {"pause": "paused", "resume": "downloading", "cancel": "cancelled"}[how]
                    break
            self.show_jobs()
            return
        try:
            D.change(job_id, how)
        except ValueError:
            pass
        self.reload()

    def clear(self):
        if DEMO:
            self.jobs = [j for j in self.jobs if j["state"] not in D.FINISHED]
            self.show_jobs()
        else:
            D.clear()
            self.reload()

    def open_folder(self):
        if not DEMO:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    def offer_clipboard(self):
        """A link copied just before opening the window goes into the box, ready to go (not downloaded unasked)."""
        text = (QGuiApplication.clipboard().text() or "").strip()
        if not self.link.text() and D.valid_url(text) and all(j["url"] != text for j in self.jobs):
            self.link.setText(text)
            self.link.selectAll()
            self.link.setFocus()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        urls = [u.toString() for u in md.urls() if u.scheme() in ("http", "https", "ftp")] if md.hasUrls() else []
        if not urls and md.hasText():
            urls = [t for t in md.text().split() if D.valid_url(t)]
        for u in urls:
            self.download(u)
        if not urls:
            self.toast.show_message("Drop a web link here (a file already on the PC doesn't need downloading)", "warn")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.move(self.width() - self.toast.width() - 22, self.height() - self.toast.height() - 20)

    # ---- demo

    def demo_tick(self):
        for j in self.jobs:
            if j["state"] == "downloading":
                j["speed"] = j.get("base", 30e6) * (0.8 + 0.4 * abs(((time.time() * 0.7 + hash(j["id"])) % 2) - 1))
                j["got"] = min(j["size"], j["got"] + j["speed"] * 0.5)
                if j["got"] >= j["size"]:
                    j.update(state="done", speed=0, finished=time.time())
            else:
                j["speed"] = 0
        self.show_jobs()


def demo_jobs():
    now = time.time()
    folder = str(Path("~/Downloads").expanduser())
    rows = [("CachyOS-desktop-linux-251012.iso", "downloading", 1.2e9, 3.1e9, 41e6, ""),
            ("Blender-4.5-linux-x64.tar.xz", "downloading", 40e6, 368e6, 9e6, ""),
            ("Big Buck Bunny 4K.mkv", "waiting", 1.4e9, 6.1e9, 0, "Connection lost, trying again in 12 s"),
            ("OBS-Studio-31.1.AppImage", "paused", 64e6, 210e6, 0, ""),
            ("Proton-GE-10-17.tar.gz", "done", 498e6, 498e6, 0, ""),
            ("handbook.pdf", "done", 8.4e6, 8.4e6, 0, ""),
            ("old-mirror-file.zip", "failed", 0, 0, 0, "The server said no (404 Not Found)")]
    out = []
    for i, (name, st, got, size, speed, err) in enumerate(rows):
        out.append({"id": f"d{i}", "url": f"https://example.org/{name}", "folder": folder, "name": name, "state": st,
                    "got": got, "size": size, "speed": speed, "base": speed or 30e6, "added": now - 600 + i,
                    "finished": now - 60 * i if st in D.FINISHED else 0, "error": err})
    return out


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Downloads")
    app.setDesktopFileName("deckos-downloads")
    app.setFont(QFont("Inter", 10))
    win = Downloads()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--screenshot" in sys.argv[:-1]:
        out = Path(sys.argv[sys.argv.index("--screenshot") + 1])
        args = []
        out.mkdir(parents=True, exist_ok=True)
        win.show()
        import math
        for i in range(240):  # two minutes of history, as if it had been open a while
            win.graph.push(max(0, 46e6 + 9e6 * math.sin(i / 9) + 5e6 * math.sin(i / 2.3) - (240 - i) * 9e4))
        win.demo_tick()
        app.processEvents()
        win.link.setText("https://example.org/files/steam-deck-recovery.img.bz2")
        app.processEvents()
        win.grab().save(str(out / "downloads.png"))
        win.jobs = []
        win.link.clear()
        win.show_jobs()
        app.processEvents()
        win.grab().save(str(out / "downloads-empty.png"))
        return 0
    if args and D.valid_url(args[0]):
        win.link.setText(args[0])
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
