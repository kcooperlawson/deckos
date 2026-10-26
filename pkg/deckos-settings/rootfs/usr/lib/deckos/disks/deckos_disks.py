"""DecKoOS Disks: every disk, its partitions, its health, and whether the drives meant to mount at start-up will.

    deckos-disks [--demo [--screenshot DIR]]

The start-up check comes first: a banner that's green when every drive will mount after a restart and says which
won't (and why) when one wouldn't, with the fix. Changes go through `deckos disks` as root (pkexec); mounting for
now goes through udisks, as Files does. Reading needs no root and runs off the window's thread.

Format, delete and resize ask for the partition's name to be typed; every change carries the disk's fingerprint as
this window saw it, so root refuses if anything moved since. What can't be changed says why (disks.why_not).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

from PySide6.QtCore import QObject, QPointF, QProcess, QRectF, QRunnable, Qt, QThreadPool, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDoubleSpinBox, QFrame, QGridLayout,  # noqa: E402
                               QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget)

import disks as D  # noqa: E402
import hub_style as S  # noqa: E402
from hub_widgets import Card, Meter, Toast, button, icon_label, label, row  # noqa: E402

DEMO = "--demo" in sys.argv
FS_COLORS = {"ntfs": "#4C8DFF", "btrfs": "#3DD68C", "ext4": "#F5B84B", "ext3": "#F5B84B", "xfs": "#2AC3DE",
             "exfat": "#A27BFF", "vfat": "#8C94A6", "f2fs": "#FF8FB1", "swap": "#5A6172"}
KIND_ICON = {"nvme": "cpu", "ssd": "drives", "hdd": "drives", "usb": "eject"}
KIND_NAME = {"nvme": "NVMe SSD", "ssd": "SSD", "hdd": "Hard drive", "usb": "USB drive"}
STATE = {D.GOOD: (S.SUCCESS, "check"), D.WARN: (S.WARNING, "alert"), D.BAD: (S.DANGER, "alert"), D.INFO: (S.P.accent, "info")}
ROLE_NAME = {"system": "DecKoOS", "efi": "Boot (EFI)", "swap": "Swap", "windows": "Windows", "recovery": "Windows recovery",
             "reserved": "Reserved", "data": "Files"}

QSS = f"""
QFrame#banner {{ border-radius: 12px; }}
QFrame#banner QLabel {{ background: transparent; }}
QFrame#disk {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 11px; }}
QFrame#disk:hover {{ background: {S.RAISED}; }}
QFrame#disk QLabel {{ background: transparent; }}
QLabel#model {{ font-family: "Inter Display", "Inter"; font-size: 20pt; font-weight: 700; }}
QLabel#chip {{ background: {S.RAISED}; border: 1px solid {S.BORDER}; border-radius: 7px; padding: 3px 9px; }}
QDoubleSpinBox {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 7px; padding: 5px 8px; }}
QFrame#erase {{ background: {S.SURFACE}; border: 1px solid #5A2A2E; border-radius: 9px; }}
QFrame#erase QLabel {{ background: transparent; }}
"""


def drop(item):
    """Removes a layout item's widget (or whole sub-layout) from the window now, then frees it."""
    w = item.widget() if hasattr(item, "widget") else item
    if w is not None:
        w.hide()
        w.setParent(None)
        w.deleteLater()
    elif item.layout() is not None:
        lay = item.layout()
        while lay.count():
            drop(lay.takeAt(0))


def tint(color, alpha):
    c = QColor(color)
    c.setAlphaF(alpha)
    return c


def rgba(color, alpha):
    c = QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


# ------------------------------------------------------------------ the partition map

class PartitionBar(QWidget):
    """A disk from start to end: each partition sized by what it holds (a sliver still gets enough room to click),
    coloured by its file system, free space hatched. Click a partition (or free space) to see it."""

    def __init__(self, on_pick):
        super().__init__()
        self.on_pick = on_pick
        self.segments, self.picked, self.rects = [], None, []
        self.setFixedHeight(74)
        self.setCursor(Qt.PointingHandCursor)

    def set(self, disk, picked):
        self.segments, self.picked = disk.layout(), picked
        self.update()

    def widths(self):
        if not self.segments:  # nothing loaded yet
            return []
        total = sum(p.size for _, p in self.segments) or 1
        w = self.width()
        raw = [max(0.045, p.size / total) for _, p in self.segments]
        scale = w / sum(raw)
        return [r * scale for r in raw]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.rects = []
        x = 0.0
        for (kind, item), w in zip(self.segments, self.widths()):
            r = QRectF(x + 1.5, 1.5, max(4.0, w - 3), self.height() - 3)
            path = QPainterPath()
            path.addRoundedRect(r, 9, 9)
            picked = self.picked is not None and item == self.picked  # free space is made anew each time
            if kind == "free":
                p.fillPath(path, QColor(S.RAISED if picked else S.SURFACE))
                p.setBrush(Qt.NoBrush)  # an outline only (the last band's brush would fill it)
                p.setPen(QPen(QColor(S.P.accent if picked else S.BORDER), 2 if picked else 1, Qt.DashLine))
                p.drawPath(path)
                p.save()
                p.setClipPath(path)
                p.setPen(QPen(QColor(S.BORDER), 1))
                for i in range(int(r.left()) - 80, int(r.right()) + 80, 10):
                    p.drawLine(QPointF(i, r.bottom()), QPointF(i + 70, r.top()))
                p.restore()
                text, sub, color = "Free space", D.size(item.size), S.MUTED
            else:
                color = FS_COLORS.get(item.fstype, "#3A4050")
                p.fillPath(path, tint(color, 0.30 if picked else 0.18))
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(color) if picked else tint(color, 0.55), 2 if picked else 1))
                p.drawPath(path)
                # how full it is: a band along the bottom
                if item.used and (item.used + item.avail):
                    band = QRectF(r.left() + 6, r.bottom() - 9, (r.width() - 12) * item.used / (item.used + item.avail), 4)
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(color))
                    p.drawRoundedRect(band, 2, 2)
                text, sub = item.label or ROLE_NAME.get(item.role, item.name), D.size(item.size)
            self.rects.append((r, item))
            if r.width() > 54:
                p.setPen(QColor(S.TEXT if kind == "part" else S.SUBTEXT))
                p.setFont(QFont("Inter", 9, QFont.DemiBold))
                p.drawText(r.adjusted(10, 8, -8, 0), Qt.AlignLeft | Qt.AlignTop,
                           p.fontMetrics().elidedText(text, Qt.ElideRight, int(r.width() - 18)))
                p.setFont(QFont("Inter", 8))
                p.setPen(QColor(S.SUBTEXT))
                p.drawText(r.adjusted(10, 27, -8, 0), Qt.AlignLeft | Qt.AlignTop,
                           p.fontMetrics().elidedText(sub, Qt.ElideRight, int(r.width() - 18)))
            x += w
        p.end()

    def mousePressEvent(self, e):
        for r, part in self.rects:
            if r.contains(e.position()):
                self.on_pick(part)
                return


# ------------------------------------------------------------------ pieces

class DiskTile(QFrame):
    def __init__(self, disk, health, on_click):
        super().__init__()
        self.setObjectName("disk")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.on_click, self.disk = on_click, disk
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 11, 12, 11)
        h.setSpacing(11)
        h.addWidget(icon_label(KIND_ICON[disk.kind], S.P.accent, 22), 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(2)
        name = label(self.fontMetrics().elidedText(disk.model or disk.name, Qt.ElideRight, 170), None, wrap=False)
        name.setToolTip(disk.model or disk.name)
        v.addWidget(name)
        bits = [KIND_NAME[disk.kind], D.size(disk.size)] + ([f"{disk.temp:.0f} °C"] if disk.temp else [])
        v.addWidget(label(" · ".join(bits), "muted", wrap=False))
        h.addLayout(v, 1)
        if health:
            dot = label("●", None, wrap=False)
            dot.setStyleSheet(f"color: {STATE[health['state']][0]}; font-size: 12pt;")
            dot.setToolTip(health["text"])
            h.addWidget(dot, 0, Qt.AlignTop)

    def picked(self, on):
        self.setStyleSheet(f"QFrame#disk {{ background: {rgba(S.P.accent, 0.10)}; border-color: {rgba(S.P.accent, 0.55)}; }}"
                           if on else "")

    def mousePressEvent(self, _e):
        self.on_click(self.disk)


class Signals(QObject):
    done = Signal(object)


class Load(QRunnable):
    """The report (lsblk, fstab, this boot's log) off the window's thread."""

    def __init__(self):
        super().__init__()
        self.signals = Signals()

    def run(self):
        try:
            disks, entries = D.inventory(), D.fstab()
            self.signals.done.emit((disks, D.startup(disks, entries, D.context()), D.health_cache(), None))
        except Exception as e:  # shown, never a crash
            self.signals.done.emit(([], [], {}, str(e)))


class Change(QDialog):
    """A change to a disk, said plainly. With `word`, the button stays off until that name is typed (the partition's
    label, or its name when it has none); the fields (file system, name, size) are filled in by the caller."""

    def __init__(self, parent, title, text, action, word=None, danger=True):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.word = word
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(12)
        v.addWidget(label(title, "title", wrap=False))
        box = QFrame()
        box.setObjectName("erase" if danger else "")
        box.setAttribute(Qt.WA_StyledBackground, True)
        b = QHBoxLayout(box)
        b.setContentsMargins(14, 12, 14, 12)
        b.setSpacing(10)
        b.addWidget(icon_label("alert" if danger else "info", S.DANGER if danger else S.P.accent, 18), 0, Qt.AlignTop)
        b.addWidget(label(text, None), 1)
        v.addWidget(box)
        self.fields = QGridLayout()
        self.fields.setHorizontalSpacing(14)
        self.fields.setVerticalSpacing(8)
        v.addLayout(self.fields)
        self.typed = None
        if word:
            v.addWidget(label(f"Type <b>{word}</b> to confirm", "sub"))
            self.typed = QLineEdit()
            self.typed.setPlaceholderText(word)
            self.typed.textChanged.connect(self.check)
            v.addWidget(self.typed)
        self.go = button(action, "danger" if danger else "primary", self.accept)
        self.go.setFocusPolicy(Qt.StrongFocus)
        v.addWidget(row(button("Cancel", slot=self.reject), self.go, stretch=False), 0, Qt.AlignRight)
        self.check()

    def field(self, name, widget):
        n = self.fields.rowCount()
        self.fields.addWidget(label(name, "sub", wrap=False), n, 0)
        self.fields.addWidget(widget, n, 1)
        return widget

    def file_systems(self, current=""):
        box = QComboBox()
        for fs, (name, *_rest) in D.FORMATS.items():
            box.addItem(name, fs)
        box.setCurrentIndex(max(0, box.findData(current if current in D.FORMATS else "ext4")))
        return self.field("File system", box)

    def name(self, text=""):
        edit = QLineEdit(text)
        edit.setPlaceholderText("A name you'll see in Files (optional)")
        return self.field("Name", edit)

    def size(self, low, high, value):
        spin = QDoubleSpinBox()
        spin.setDecimals(1)
        spin.setSuffix(" GB")
        spin.setRange(low / 1e9, high / 1e9)
        spin.setSingleStep(1)
        spin.setValue(value / 1e9)
        return self.field("Size", spin)

    def check(self):
        self.go.setEnabled(self.typed is None or self.typed.text().strip() == self.word)


# ------------------------------------------------------------------ the window

class Disks(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DecKoOS Disks" + (" — Demo" if DEMO else ""))
        self.setWindowIcon(QIcon.fromTheme("deckos-disks", S.icon("drives", S.P.accent, 32)))
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(S.qss() + QSS)
        self.resize(1180, 800)
        self.setMinimumSize(960, 640)
        self.disks, self.checks, self.health = [], [], {}
        self.disk = self.part = None
        self.pool = QThreadPool.globalInstance()
        self.loads = set()

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 16)
        v.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(icon_label("drives", S.P.accent, 28))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("Disks", "title", wrap=False))
        titles.addWidget(label("Your drives, and whether they'll be there after a restart", "sub", wrap=False))
        head.addLayout(titles, 1)
        head.addWidget(button("Check health", slot=self.check_health, icon="shield",
                              tip="Reads each drive's own health report (SMART); asks for your password"))
        head.addWidget(button("Refresh", slot=self.refresh, icon="refresh"))
        v.addLayout(head)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        self.banner.setAttribute(Qt.WA_StyledBackground, True)
        b = QHBoxLayout(self.banner)
        b.setContentsMargins(18, 14, 18, 14)
        b.setSpacing(14)
        self.banner_icon = QWidget()
        self.banner_icon.setFixedSize(26, 26)
        bl = QHBoxLayout(self.banner_icon)
        bl.setContentsMargins(0, 0, 0, 0)
        b.addWidget(self.banner_icon, 0, Qt.AlignTop)
        bt = QVBoxLayout()
        bt.setSpacing(2)
        self.banner_title = label("", "cardTitle")
        self.banner_text = label("", "sub")
        bt.addWidget(self.banner_title)
        bt.addWidget(self.banner_text)
        b.addLayout(bt, 1)
        self.banner_actions = QHBoxLayout()
        b.addLayout(self.banner_actions)
        v.addWidget(self.banner)

        body = QHBoxLayout()
        body.setSpacing(16)
        side = QWidget()
        side.setFixedWidth(270)
        self.side = QVBoxLayout(side)
        self.side.setContentsMargins(0, 0, 0, 0)
        self.side.setSpacing(8)
        self.side.addStretch(1)
        body.addWidget(side)

        main = QWidget()
        m = QVBoxLayout(main)
        m.setContentsMargins(0, 0, 4, 0)
        m.setSpacing(14)
        self.model = label("", "model", wrap=False)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(6)
        m.addWidget(self.model)
        m.addLayout(self.chips)
        self.bar = PartitionBar(self.pick_part)
        m.addWidget(self.bar)
        self.detail = Card()
        self.detail.body.setContentsMargins(20, 18, 20, 18)
        self.detail.body.setSpacing(10)
        m.addWidget(self.detail)
        self.startup_card = Card("Start-up check", "Every drive that should mount after a restart", "clock")
        self.startup_list = QVBoxLayout()
        self.startup_list.setSpacing(6)
        self.startup_card.body.addLayout(self.startup_list)
        m.addWidget(self.startup_card)
        m.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(main)
        body.addWidget(scroll, 1)
        v.addLayout(body, 1)
        self.status = label("", "muted", wrap=False)
        v.addWidget(self.status)
        self.toast = Toast(self)
        self.refresh()

    # -- data

    def refresh(self):
        if DEMO:
            self.show_report(demo())
            return
        self.status.setText("Reading your drives…")
        job = Load()
        job.signals.done.connect(self.show_report)
        self.loads.add(job)
        job.signals.done.connect(lambda _r, j=job: self.loads.discard(j))
        self.pool.start(job)

    def show_report(self, result):
        self.disks, self.checks, self.health, error = result
        self.status.setText(f"Couldn't read everything: {error}" if error else
                            "Changes ask for your password. Drives outside DecKoOS's part of /etc/fstab are only shown.")
        while self.side.count() > 1:
            drop(self.side.takeAt(0))
        self.tiles = {}
        order = {"nvme": 0, "ssd": 1, "hdd": 2, "usb": 3}
        for d in sorted(self.disks, key=lambda d: (order[d.kind], d.name)):
            tile = DiskTile(d, self.health.get(d.path), self.pick_disk)
            self.tiles[d.path] = tile
            self.side.insertWidget(self.side.count() - 1, tile)
        self.render_banner()
        self.render_startup()
        keep = self.disk.path if self.disk else None
        first = next(iter(self.tiles.values())).disk if self.tiles else None  # the top of the list
        disk = next((d for d in self.disks if d.path == keep), None) or first
        if disk:
            self.pick_disk(disk, self.part.path if self.part else None)

    # -- the banner and the start-up list

    def problems(self):
        return [c for c in self.checks if c.state in (D.BAD, D.WARN)]

    def render_banner(self):
        bad = self.problems()
        worst = D.BAD if any(c.state == D.BAD for c in bad) else D.WARN if bad else D.GOOD
        color, icon = STATE[worst]
        self.banner.setStyleSheet(f"QFrame#banner {{ background: {rgba(color, 0.10)}; border: 1px solid {rgba(color, 0.40)}; }}")
        lay = self.banner_icon.layout()
        while lay.count():
            drop(lay.takeAt(0))
        lay.addWidget(icon_label(icon, color, 26))
        while self.banner_actions.count():
            drop(self.banner_actions.takeAt(0))
        drives = {c.part or c.target for c in self.checks if c.state != D.INFO}  # subvolumes count once
        if not bad:
            self.banner_title.setText(f"All {len(drives)} drives will mount after a restart" if drives else
                                      "No drives are set to mount at start-up")
            self.banner_text.setText("Each one is connected, named right in /etc/fstab, and mounted (or waiting to be "
                                     "opened). Drives you plug in later still show up in Files.")
            return
        first = bad[0]
        n = sum(1 for c in bad if c.state == D.BAD)
        self.banner_title.setText(first.title if len(bad) == 1 else
                                  f"{n} drive{'s' if n != 1 else ''} won't mount after a restart" if n else
                                  f"{len(bad)} drives need a look")
        self.banner_text.setText(first.text if len(bad) == 1 else "The start-up check below says which, and why.")
        action = self.action_button(first)
        if action:
            self.banner_actions.addWidget(action)

    def render_startup(self):
        while self.startup_list.count():
            drop(self.startup_list.takeAt(0))
        shown = self.grouped([c for c in self.checks if c.state != D.INFO])
        for c in shown:
            color, icon = STATE[c.state]
            line = QWidget()
            h = QHBoxLayout(line)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(10)
            h.addWidget(icon_label(icon, color, 16), 0, Qt.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(label(c.title, None, wrap=False))
            if c.state != D.GOOD:
                text.addWidget(label(c.text, "muted"))
            h.addLayout(text, 1)
            if not c.managed and c.state == D.GOOD:
                h.addWidget(label("set up at install" if c.target.split(", ")[0] in D.SYSTEM_TARGETS else "set up outside DecKoOS",
                                  "muted", wrap=False))
            if c.state != D.GOOD:
                b = self.action_button(c)
                if b:
                    h.addWidget(b)
            self.startup_list.addWidget(line)
        if not shown:
            self.startup_list.addWidget(label("Nothing is set to mount at start-up yet. Pick a drive and choose Mount at "
                                              "start-up.", "sub"))

    @staticmethod
    def grouped(checks):
        """One row per drive: the system's btrfs subvolumes (/, /home, /.snapshots...) are one partition."""
        out, seen = [], {}
        for c in checks:
            key = (c.part, c.state, c.managed) if c.state == D.GOOD and c.part else None
            if key and key in seen:
                first = seen[key]
                first.target += f", {c.target}"
                first.title = f"{first.target} mount at start-up"
                continue
            c = D.Check(**{k: getattr(c, k) for k in ("target", "part", "state", "title", "text", "fix", "managed")})
            if key:
                seen[key] = c
            out.append(c)
        for c in out:
            if c.target.count(",") >= 3:  # long lists stay readable
                parts = c.target.split(", ")
                c.title = f"{', '.join(parts[:3])} and {len(parts) - 3} more mount at start-up"
        return out

    def action_button(self, check):
        uuid = self.uuid_of(check.part)
        if check.fix == "repair" and uuid:
            return button("Repair", "primary", lambda: self.root(["repair", uuid], "Repaired"), icon="refresh")
        if check.fix == "add" and uuid:
            return button("Mount at start-up", "primary", lambda: self.root(["startup", "add", uuid], "Set to mount"),
                          icon="plus")
        if check.fix == "remove" and check.managed and check.state != D.GOOD:
            u = self.uuid_of(check.part) or ""
            return button("Stop mounting it", slot=lambda: self.root(["startup", "remove", u], "Removed"), icon="close") \
                if u else None
        return None

    def uuid_of(self, path):
        return next((p.uuid for d in self.disks for p in d.parts if p.path == path and p.uuid), "")

    # -- a disk and a partition

    def pick_disk(self, disk, part_path=None):
        self.disk = disk
        for path, tile in self.tiles.items():
            tile.picked(path == disk.path)
        self.model.setText(disk.model or disk.name)
        while self.chips.count():
            drop(self.chips.takeAt(0))
        health = self.health.get(disk.path)
        bits = [KIND_NAME[disk.kind], D.size(disk.size), (disk.table or "no partition table").upper()
                if disk.table in ("gpt", "dos") else (disk.table or "no partition table"), disk.path]
        if disk.temp:
            bits.insert(2, f"{disk.temp:.0f} °C")
        for b in bits:
            chip = label(b.replace("DOS", "MBR"), "chip", wrap=False)
            self.chips.addWidget(chip)
        if health:
            chip = label(f'<span style="color:{STATE[health["state"]][0]}">●</span> {health["text"]}', "chip", wrap=False)
            chip.setToolTip(" · ".join(x for x in (f"{health.get('hours')} hours on" if health.get("hours") else "",
                                                     f"{health.get('wear')}% worn" if health.get("wear") is not None else "")
                                       if x))
            self.chips.addWidget(chip)
        self.chips.addStretch(1)
        part = next((p for p in disk.parts if p.path == part_path), None) or \
            next((p for p in disk.parts if p.role in ("data", "system", "windows")), None) or \
            (disk.parts[0] if disk.parts else next((item for kind, item in disk.layout() if kind == "free"), None))
        self.pick_part(part)

    def pick_part(self, part):
        self.part = part
        self.bar.set(self.disk, part)
        lay = self.detail.body
        while lay.count():
            drop(lay.takeAt(0))
        if part is None:
            lay.addWidget(label("This disk has no partitions.", "sub"))
            return
        if isinstance(part, D.Free):
            self.show_free(part)
            return
        color = FS_COLORS.get(part.fstype, "#3A4050")
        top = QHBoxLayout()
        swatch = QFrame()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(f"background: {color}; border-radius: 4px;")
        top.addWidget(swatch, 0, Qt.AlignVCenter)
        top.addWidget(label(part.label or ROLE_NAME.get(part.role, part.name), "cardTitle", wrap=False))
        top.addWidget(label(f"{part.fstype or 'not formatted'} · {D.size(part.size)} · {ROLE_NAME.get(part.role, '')}",
                            "muted", wrap=False))
        top.addStretch(1)
        lay.addLayout(top)
        if part.used + part.avail:
            meter = Meter(8)
            meter.set(part.used / (part.used + part.avail), color)
            lay.addWidget(meter)
            lay.addWidget(label(f"{D.size(part.used)} used · {D.size(part.avail)} free", "muted", wrap=False))
        check = next((c for c in self.checks if c.part == part.path), None)
        if check:
            c_color, c_icon = STATE[check.state]
            st = QHBoxLayout()
            st.setSpacing(10)
            st.addWidget(icon_label(c_icon, c_color, 18), 0, Qt.AlignTop)
            words = QVBoxLayout()
            words.setSpacing(1)
            words.addWidget(label(f"<b>At start-up:</b> {check.title}", None))
            words.addWidget(label(check.text, "muted"))
            st.addLayout(words, 1)
            lay.addLayout(st)
        elif part.role in ("efi", "recovery", "reserved", "swap"):
            lay.addWidget(label({"efi": "The boot partition: the PC's firmware starts from it. Leave it as it is.",
                                 "recovery": "Windows keeps its repair tools here. Leave it as it is.",
                                 "reserved": "Windows keeps this space for itself. It holds no files.",
                                 "swap": "Overflow for memory."}[part.role], "muted"))
        actions = []
        a = self.action_button(check) if check else None
        if a:
            actions.append(a)
        entry_managed = check is not None and check.managed and check.fix == "remove" and check.state == D.GOOD
        if entry_managed:
            actions.append(button("Don't mount at start-up", slot=lambda: self.root(
                ["startup", "remove", part.uuid], "No longer mounts at start-up"), icon="close"))
        if part.mountpoints and part.role in ("data", "windows", "system"):
            actions.append(button("Open", slot=lambda: QProcess.startDetached("xdg-open", [part.mountpoints[0]]),
                                  icon="folder"))
        if part.mountable and not part.mountpoints and not check:
            actions.append(button("Mount for now", slot=lambda: self.udisks("mount", part), icon="play",
                                  tip="Until you unplug it or restart"))
        if part.mountpoints and part.role == "data" and not check:
            actions.append(button("Unmount", slot=lambda: self.udisks("unmount", part), icon="eject"))
        if actions:
            lay.addWidget(row(*actions))
        for w in self.edit_row(part):
            lay.addWidget(w)
        facts = [("Device", part.path), ("UUID", part.uuid or "—"), ("Type", part.ptype or "—")]
        if part.mountpoints:
            facts.insert(1, ("Mounted at", ", ".join(part.mountpoints[:3]) + ("…" if len(part.mountpoints) > 3 else "")))
        grid = QGridLayout()  # wraps rather than push the panel sideways (UUIDs are long)
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(0)
        for i, (k, val) in enumerate(facts):
            grid.addWidget(label(k, "muted", wrap=False), 0, i)
            v = label(val, None)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.setMinimumWidth(60)
            grid.addWidget(v, 1, i, Qt.AlignTop)
            grid.setColumnStretch(i, 1)
        lay.addLayout(grid)

    # -- partition editing

    def edit_row(self, part):
        """Format, Resize, Delete: the ones DecKoOS may do here, and a line saying why the others aren't there."""
        entries = D.fstab() if not DEMO else [  # the demo's fstab: the drives its checks say are in it
            D.Entry(c.part, c.target, "", [], 0, c.managed) for c in self.checks if c.part and c.state != D.INFO]
        why = {a: D.why_not(part, self.disk, entries, a) for a in ("format", "resize", "delete")}
        b = []
        if not why["format"]:
            b.append(button("Format…", slot=lambda: self.format_dialog(part), icon="refresh"))
        if not why["resize"]:
            b.append(button("Resize…", slot=lambda: self.resize_dialog(part), icon="sliders"))
        if not why["delete"]:
            b.append(button("Delete…", slot=lambda: self.delete_dialog(part), icon="trash"))
        if not b:
            return [label(f"<b>Not changed here:</b> {why['format']}", "muted")]
        missing = why["resize"] or why["delete"]
        return [row(*b)] + ([label(missing, "muted")] if missing else [])

    def describe(self, part):
        return f"{part.label or part.name} ({part.path}, {D.size(part.size)}, {part.fstype or 'not formatted'})"

    def format_dialog(self, part):
        d = Change(self, f"Format {part.label or part.name}",
                   f"Everything on {self.describe(part)} is erased. The partition itself stays where it is.",
                   "Erase and format", D.confirm_word(part))
        fs, name = d.file_systems(part.fstype), d.name(part.label)
        if d.exec():
            self.root(["format", part.path, fs.currentData(), name.text().strip(), "--confirm", d.typed.text().strip(),
                       "--layout", D.fingerprint(self.disk)], "Formatted", then=self.offer_startup)

    def delete_dialog(self, part):
        d = Change(self, f"Delete {part.label or part.name}",
                   f"{self.describe(part)} is taken out of the partition table and becomes free space. Its files "
                   "can't be opened afterwards. The table is saved first in /var/lib/deckos/disks/tables.",
                   "Delete partition", D.confirm_word(part))
        if d.exec():
            self.root(["delete", part.path, "--confirm", d.typed.text().strip(), "--layout", D.fingerprint(self.disk)],
                      "Deleted")

    def resize_dialog(self, part):
        room = self.disk.room_after(part)
        note = " Windows checks an NTFS drive at its next start after a resize." if part.fstype == "ntfs" else ""
        d = Change(self, f"Resize {part.label or part.name}",
                   f"{self.describe(part)}: only its end moves, so it can grow into the free space right after it "
                   f"({D.size(room) if room else 'none'}) or shrink down to what it holds. Keep a copy of anything "
                   f"that matters first.{note}", "Resize", D.confirm_word(part))
        high = part.size + room
        spin = d.size(D.MIN_PART, high, part.size)
        if d.exec():
            want = high if spin.value() >= spin.maximum() else int(spin.value() * 1e9)
            self.root(["resize", part.path, str(want), "--confirm", d.typed.text().strip(),
                       "--layout", D.fingerprint(self.disk)], "Resized")

    def show_free(self, gap):
        lay = self.detail.body
        top = QHBoxLayout()
        top.addWidget(icon_label("plus", S.SUBTEXT, 16), 0, Qt.AlignVCenter)
        top.addWidget(label("Free space", "cardTitle", wrap=False))
        top.addWidget(label(D.size(gap.size) + (" · the whole disk" if not self.disk.parts else ""), "muted", wrap=False))
        top.addStretch(1)
        lay.addLayout(top)
        why = D.why_not_create(self.disk)
        if why:
            lay.addWidget(label(f"<b>No new partition here:</b> {why}", "muted"))
            return
        lay.addWidget(label("Nothing uses this space yet. A new partition here leaves everything else on the disk as it "
                            "is." + ("" if self.disk.table else " The disk gets a partition table (GPT) first."), "muted"))
        lay.addWidget(row(button("New partition…", "primary", lambda: self.create_dialog(gap), icon="plus")))

    def create_dialog(self, gap):
        d = Change(self, "New partition", f"A new partition in {D.size(gap.size)} of free space on "
                   f"{self.disk.model or self.disk.name} ({self.disk.path}). Nothing else on the disk changes.",
                   "Make partition", danger=False)
        spin = d.size(D.MIN_PART, gap.size, gap.size)
        fs, name = d.file_systems("exfat" if self.disk.kind == "usb" else "ext4"), d.name()
        if d.exec():
            want = gap.size if spin.value() >= spin.maximum() else int(spin.value() * 1e9)
            self.root(["create", self.disk.path, str(gap.start), str(want), fs.currentData(), name.text().strip(),
                       "--layout", D.fingerprint(self.disk)], "Made", then=self.offer_startup)

    def offer_startup(self, out):
        """After formatting or a new partition: the start-up offer, which test-mounts before keeping anything."""
        info = dict(line.split(" ", 1) for line in out.splitlines()[1:] if " " in line)  # "uuid …", "fs …"
        uuid = info.get("uuid", "")
        if not uuid or info.get("fs") not in D.MOUNTABLE:
            return
        d = Change(self, "Mount it at start-up?", "Then it's in the same place after every restart. DecKoOS mounts it "
                   "once to test it before keeping the setting.", "Mount at start-up", danger=False)
        if d.exec():
            self.root(["startup", "add", uuid], "Set to mount")

    # -- changes

    def root(self, args, done_text, then=None):
        if DEMO:
            self.toast.show_message(f"Demo: deckos disks {' '.join(args)}", "info")
            return
        self.status.setText("Waiting for your password…")
        proc = QProcess(self)

        def finished(code, _s):
            out = bytes(proc.readAllStandardOutput()).decode().strip()
            err = bytes(proc.readAllStandardError()).decode().strip()
            proc.deleteLater()
            if code == 0:
                self.toast.show_message((out.splitlines() or [done_text])[0], "ok", 7000)
                if then:
                    then(out)
            elif code != 126:  # 126: the password prompt was closed
                self.toast.show_message((err or out or "That didn't work").removeprefix("refused: "), "bad", 9000)
            self.refresh()
        proc.finished.connect(finished)
        proc.start("pkexec", ["deckos", "disks", *args])

    def udisks(self, verb, part):
        if DEMO:
            self.toast.show_message(f"Demo: would {verb} {part.path}", "info")
            return
        proc = QProcess(self)
        proc.finished.connect(lambda code, _s: (self.toast.show_message(
            bytes(proc.readAllStandardOutput()).decode().strip() or f"{verb.capitalize()}ed", "ok" if code == 0 else "bad"),
            self.refresh()))
        proc.start("udisksctl", [verb, "-b", part.path])

    def check_health(self):
        self.root(["health"], "Health checked")


# ------------------------------------------------------------------ demo

def demo():
    P, K = D.Part, D.Disk
    G = 1e9
    nvme0 = K("nvme0n1", "/dev/nvme0n1", int(250 * G), "Samsung SSD 970 EVO Plus 250GB", "nvme", table="gpt", temp=41,
              parts=[P("nvme0n1p1", "/dev/nvme0n1p1", int(0.6 * G), 1 << 20, "vfat", "", "61E1-7852", "", "EFI System",
                       ["/boot/efi"], int(0.05 * G), int(0.55 * G)),
                     P("nvme0n1p2", "/dev/nvme0n1p2", int(249.4 * G), (1 << 20) + int(0.6 * G), "btrfs", "DecKoOS", "7ca4b8f1", "",
                       "Linux filesystem", ["/", "/home"], int(204.7 * G), int(41.6 * G))])
    nvme1 = K("nvme1n1", "/dev/nvme1n1", int(512 * G), "Micron 2400 512GB", "nvme", table="gpt", temp=38,
              parts=[P("nvme1n1p1", "/dev/nvme1n1p1", 16 << 20, 1 << 20, "", "", "", "", "Microsoft reserved"),
                     P("nvme1n1p2", "/dev/nvme1n1p2", int(511.1 * G), 17 << 20, "ntfs", "Windows", "E086D099", "",
                       "Microsoft basic data", ["/mnt/Windows"], int(295.7 * G), int(215.4 * G)),
                     P("nvme1n1p3", "/dev/nvme1n1p3", int(0.96 * G), int(511.2 * G), "ntfs", "", "E0663DA1", "",
                       "Windows recovery environment")])
    ssd = K("sda", "/dev/sda", int(1000 * G), "Samsung SSD 870 EVO 1TB", "sata", table="gpt",
            parts=[P("sda1", "/dev/sda1", int(1000 * G), 1 << 20, "ntfs", "Games", "4C3CACD8", "", "Microsoft basic data",
                     ["/mnt/Games"], int(796 * G), int(204 * G))])
    big = K("sdb", "/dev/sdb", int(8001 * G), "HGST Ultrastar 8TB", "usb", rotational=True, table="gpt",
            parts=[P("sdb1", "/dev/sdb1", 16 << 20, 17 << 10, "", "", "", "", "Microsoft reserved"),
                   P("sdb2", "/dev/sdb2", int(7600 * G), 17 << 20, "ntfs", "Media", "2E760E91", "", "Microsoft basic data")])
    stick = K("sdc", "/dev/sdc", int(128 * G), "SanDisk Ultra 128GB", "usb", removable=True, table="dos",
              parts=[P("sdc1", "/dev/sdc1", int(128 * G), 1 << 20, "exfat", "Photos", "4E21-0000", "", "HPFS/NTFS/exFAT")])
    disks = [nvme0, nvme1, ssd, big, stick]
    for d in disks:
        for n, p in enumerate(d.parts, 1):
            p.number = n
    C = D.Check
    checks = [C("/mnt/Media", "/dev/sdb2", D.BAD, "/mnt/Media: marked dirty, so it won't mount",
                "The PC was cut off while it was in use. Until the mark is cleared it fails at every start. Repair "
                "clears it; run chkdsk /f on it in Windows when you can.", "repair", True),
              C("/", "/dev/nvme0n1p2", D.GOOD, "/ mounts at start-up", "Mounted now."),
              C("/home", "/dev/nvme0n1p2", D.GOOD, "/home mounts at start-up", "Mounted now."),
              C("/boot/efi", "/dev/nvme0n1p1", D.GOOD, "/boot/efi mounts at start-up", "Mounted now."),
              C("/mnt/Windows", "/dev/nvme1n1p2", D.GOOD, "/mnt/Windows mounts at start-up", "Mounted now.", "remove", True),
              C("/mnt/Games", "/dev/sda1", D.GOOD, "/mnt/Games mounts at start-up", "Mounted now.", "remove", True),
              C("/dev/sdc1", "/dev/sdc1", D.INFO, "Photos: not set to mount at start-up",
                "exfat · 128 GB. Mount at start-up makes it appear in the same place after every restart.", "add")]
    health = {"/dev/nvme0n1": {"state": D.GOOD, "text": "Healthy", "hours": 6120, "wear": 4},
              "/dev/nvme1n1": {"state": D.GOOD, "text": "Healthy", "hours": 2210, "wear": 1},
              "/dev/sda": {"state": D.GOOD, "text": "Healthy", "hours": 9930},
              "/dev/sdb": {"state": D.WARN, "text": "8 damaged or waiting sectors: keep a backup, watch if it grows",
                           "hours": 31200}}
    return disks, checks, health, None


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Disks")
    app.setDesktopFileName("deckos-disks")
    app.setFont(QFont("Inter", 10))
    win = Disks()
    if "--screenshot" in sys.argv[:-1]:
        out = Path(sys.argv[sys.argv.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)
        win.show()

        def settle():  # wrapped labels lay out over a few passes; one processEvents() grabs them overlapping
            for _ in range(5):
                app.processEvents()
        settle()
        win.grab().save(str(out / "disks-problem.png"))
        big = next(d for d in win.disks if d.name == "sdb")
        win.pick_disk(big)
        settle()
        win.grab().save(str(out / "disks-repair.png"))
        gap = next(item for kind, item in big.layout() if kind == "free")
        win.pick_part(gap)
        settle()
        win.grab().save(str(out / "disks-free-space.png"))
        stick = next(d for d in win.disks if d.name == "sdc")
        win.pick_disk(stick)
        settle()
        win.grab().save(str(out / "disks-edit.png"))
        dialog = Change(win, "Format Photos", f"Everything on {win.describe(stick.parts[0])} is erased. The partition "
                        "itself stays where it is.", "Erase and format", "Photos")
        dialog.file_systems("exfat")
        dialog.name("Photos")
        dialog.typed.setText("Photos")
        dialog.show()
        settle()
        dialog.grab().save(str(out / "disks-format.png"))
        dialog.close()
        win.pick_disk(win.disks[0])
        win.checks = [c for c in win.checks if c.state != D.BAD]
        win.render_banner()
        win.render_startup()
        settle()
        win.grab().save(str(out / "disks-all-good.png"))
        sys.exit(0)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
