"""DeckOS Builder — start, watch and collect DeckOS ISO builds; put them on a Ventoy USB.

Runs on Windows and Linux (PySide6 + the GitHub CLI `gh`, signed in with `gh auth login`).
On an Arch/DeckOS machine it can also build the ISO locally with build.sh.

Same look as Steady Downloader and DeckOS Hub: slate cards, 1px borders, Inter, and the
blue-violet gradient on primary actions and progress.
"""
import email.utils
import hashlib
import json
import os
import platform
import shutil
import string
import subprocess
import sys
import time
import urllib.request
import webbrowser
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QTextCursor
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QVBoxLayout,
                               QWidget)

HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parent
BRANDING = REPO_DIR / "pkg/deckos-settings/rootfs/usr/share/deckos/branding"
FONTS = REPO_DIR / "pkg/deckos-settings/rootfs/usr/share/fonts/deckos"
WORKFLOW = "build-iso.yml"
ARTIFACT = "deckos-iso"
IS_WINDOWS = platform.system() == "Windows"
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0  # CREATE_NO_WINDOW: no console flashes on Windows

BG, SURFACE, BORDER, HOVER, PRESSED = "#0F1115", "#171A21", "#262B36", "#2A2F3B", "#353B49"
TEXT, SUBTEXT, MUTED = "#E8EAF0", "#8C94A6", "#5A6172"
ACCENT, ACCENT_HOVER, GRAD_A, GRAD_B = "#4C8DFF", "#6AA2FF", "#4C8DFF", "#7A5CFF"
SUCCESS, WARNING, DANGER = "#3DD68C", "#F5B84B", "#FF6B6B"

QSS = f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: "Inter", "Inter Display", "Segoe UI"; font-size: 10pt; }}
#root, QScrollArea, QScrollArea > QWidget > QWidget, QSplitter {{ background: {BG}; border: none; }}
QLabel#title {{ font-family: "Inter Display", "Inter"; font-size: 16.5pt; font-weight: 600; }}
QLabel#sub {{ color: {SUBTEXT}; }}
QLabel#kicker {{ color: {SUBTEXT}; font-size: 8.5pt; font-weight: 600; }}
QLabel#cardTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#big {{ font-family: "Inter Display", "Inter"; font-size: 14pt; font-weight: 600; }}
#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#card QLabel, #card QCheckBox {{ background: transparent; }}
#row {{ background: transparent; border-top: 1px solid {BORDER}; }}
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 12px; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {PRESSED}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ color: white; font-weight: 600; border: none; padding: 8px 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {GRAD_A}, stop:1 {GRAD_B}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_HOVER}, stop:1 #8E75FF); }}
QPushButton#primary:disabled {{ background: {BORDER}; color: {MUTED}; }}
QPushButton#link {{ background: transparent; border: none; color: {ACCENT}; padding: 2px 4px; }}
QPushButton#link:hover {{ color: {ACCENT_HOVER}; text-decoration: underline; }}
QComboBox, QLineEdit {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 5px 10px; }}
QComboBox QAbstractItemView {{ background: #22262F; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {PRESSED}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QPlainTextEdit {{ background: #0B0D11; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px;
    font-family: "JetBrainsMono Nerd Font", "Cascadia Mono", "Consolas", monospace; font-size: 9pt; color: #C8CDD8; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {HOVER}; border-radius: 4px; margin: 2px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: #22262F; color: {TEXT}; border: 1px solid {BORDER}; }}
"""


# ------------------------------------------------------------------ GitHub (via gh)

def gh_path():
    found = shutil.which("gh")
    if found:
        return found
    for p in (r"C:\Program Files\GitHub CLI\gh.exe", "/usr/bin/gh", "/usr/local/bin/gh"):
        if Path(p).exists():
            return p
    return None


def gh(*args, check=True):
    exe = gh_path()
    if not exe:
        raise RuntimeError("GitHub CLI (gh) is not installed")
    r = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=NO_WINDOW)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f"gh {' '.join(args)} failed")
    return r.stdout


def gh_json(path):
    return json.loads(gh("api", path) or "null")


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


class Clock:
    """GitHub's time, not this PC's: the offset comes from the API's Date header."""
    offset = 0.0

    @classmethod
    def sync(cls):
        try:
            with urllib.request.urlopen(urllib.request.Request("https://api.github.com", method="HEAD"), timeout=8) as r:
                server = email.utils.parsedate_to_datetime(r.headers["Date"])
            cls.offset = (server - datetime.now(timezone.utc)).total_seconds()
        except Exception:
            cls.offset = 0.0

    @classmethod
    def now(cls):
        return datetime.fromtimestamp(time.time() + cls.offset, timezone.utc)


def fmt_duration(sec):
    sec = max(0, int(sec))
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} min" if m >= 10 else f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


def fmt_ago(ts):
    sec = (Clock.now() - ts).total_seconds()
    if sec < 90:
        return "just now"
    if sec < 3600:
        return f"{int(sec // 60)} min ago"
    if sec < 86400:
        return f"{int(sec // 3600)} h ago"
    return ts.astimezone().strftime("%b %d")


def run_state(run):
    if run["status"] != "completed":
        return ("Queued", WARNING) if run["status"] in ("queued", "waiting", "pending", "requested") else ("Building", ACCENT)
    return {"success": ("Passed", SUCCESS), "cancelled": ("Cancelled", MUTED),
            "skipped": ("Skipped", MUTED)}.get(run["conclusion"], ("Failed", DANGER))


# ------------------------------------------------------------------ USB (Ventoy)

def ventoy_drives():
    """[(mount path, label, free bytes)] for mounted Ventoy data partitions."""
    out = []
    if IS_WINDOWS:
        import ctypes
        buf = ctypes.create_unicode_buffer(261)
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if not os.path.exists(root):
                continue
            if ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0) and buf.value == "Ventoy":
                out.append((root, buf.value, shutil.disk_usage(root).free))
    else:
        try:
            data = json.loads(subprocess.run(["lsblk", "-J", "-o", "LABEL,MOUNTPOINT"], capture_output=True, text=True).stdout)
        except (OSError, ValueError):
            return out
        def walk(devs):
            for d in devs:
                if d.get("label") == "Ventoy" and d.get("mountpoint"):
                    out.append((d["mountpoint"], "Ventoy", shutil.disk_usage(d["mountpoint"]).free))
                walk(d.get("children") or [])
        walk(data.get("blockdevices", []))
    return out


def sha256(path, progress, label, start=0.0, span=1.0):
    h, done, total = hashlib.sha256(), 0, os.path.getsize(path)
    with open(path, "rb") as f:
        while chunk := f.read(8 << 20):
            h.update(chunk)
            done += len(chunk)
            progress(start + span * done / total, f"{label} {done * 100 // total}%")
    return h.hexdigest()


# ------------------------------------------------------------------ background work

class Signals(QObject):
    done = Signal(object, object)  # result, error
    progress = Signal(float, str)


class Task(QRunnable):
    def __init__(self, fn, on_done, on_progress=None):
        super().__init__()
        self.fn, self.sig = fn, Signals()
        self.sig.done.connect(on_done)
        if on_progress:
            self.sig.progress.connect(on_progress)

    def run(self):
        try:
            self.sig.done.emit(self.fn(lambda f, t="": self.sig.progress.emit(f, t)), None)
        except Exception as e:  # shown in the UI, never fatal
            self.sig.done.emit(None, e)


# ------------------------------------------------------------------ widgets

class Meter(QWidget):
    """Thin rounded bar with the brand gradient; value 0..1."""

    def __init__(self, height=6):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(height)

    def set(self, v):
        self.value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.rect()
        rad = r.height() / 2
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(r, rad, rad)
        if self.value > 0:
            g = QLinearGradient(0, 0, r.width(), 0)
            g.setColorAt(0, QColor(GRAD_A))
            g.setColorAt(1, QColor(GRAD_B))
            p.setBrush(g)
            p.drawRoundedRect(0, 0, max(r.height(), int(r.width() * self.value)), r.height(), rad, rad)


def label(text="", obj=None, wrap=True, rich=False):
    l = QLabel(text)
    l.setWordWrap(wrap)
    if obj:
        l.setObjectName(obj)
    if rich:
        l.setTextFormat(Qt.RichText)
    return l


def button(text, kind=None, slot=None, tip=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    if kind:
        b.setObjectName(kind)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    return b


def pill(text, color):
    return (f'<span style="color:{color}; font-weight:600">●</span>&nbsp;'
            f'<span style="color:{color}; font-weight:600">{text}</span>')


class Card(QFrame):
    def __init__(self, kicker, title=None):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 14, 18, 16)
        self.body.setSpacing(8)
        self.body.addWidget(label(kicker.upper(), "kicker"))
        if title:
            self.title = label(title, "cardTitle")
            self.body.addWidget(self.title)


def hrow(*widgets, stretch_at=None):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    for i, x in enumerate(widgets):
        if i == stretch_at:
            h.addStretch(1)
        h.addWidget(x)
    if stretch_at is None or stretch_at >= len(widgets):
        h.addStretch(1)
    return w


# ------------------------------------------------------------------ main window

class Builder(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("DeckOS Builder")
        self.setWindowIcon(QIcon(str(BRANDING / "logo.svg")))
        self.resize(1120, 840)
        self.setMinimumSize(760, 560)
        self.settings = QSettings("DeckOS", "Builder")
        self.pool = QThreadPool.globalInstance()
        self.runs, self.jobs, self.current, self.busy = [], [], None, False
        self._tasks = set()
        self.typical = self.settings.value("typical_iso_seconds", 1800, type=int)
        self.local_proc = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(16)
        outer.addLayout(self.header())

        split = QSplitter(Qt.Vertical)
        split.setHandleWidth(10)
        top = QWidget()
        cols = QHBoxLayout(top)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(self.current_card())
        left.addWidget(self.usb_card())
        left.addStretch(1)
        cols.addLayout(left, 5)
        cols.addWidget(self.history_card(), 6)
        split.addWidget(top)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Build logs and messages appear here.")
        self.log.setMaximumBlockCount(5000)
        split.addWidget(self.log)
        split.setSizes([620, 160])
        outer.addWidget(split, 1)
        self.status = label("", "sub")
        outer.addWidget(self.status)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.render_current)
        self.tick.start(1000)
        QTimer.singleShot(50, self.startup)

    # ---- layout pieces

    def header(self):
        h = QHBoxLayout()
        tile = QSvgWidget(str(BRANDING / "logo.svg"))
        tile.setFixedSize(44, 44)
        h.addWidget(tile)
        h.addSpacing(12)
        t = QVBoxLayout()
        t.setSpacing(1)
        t.addWidget(label("DeckOS Builder", "title"))
        self.subtitle = label("Connecting to GitHub…", "sub")
        t.addWidget(self.subtitle)
        h.addLayout(t, 1)
        self.repo_box = QLineEdit(self.settings.value("repo", "") or "")
        self.repo_box.setPlaceholderText("owner/repo")
        self.repo_box.setFixedWidth(220)
        self.repo_box.editingFinished.connect(self.repo_changed)
        h.addWidget(self.repo_box)
        if not IS_WINDOWS and (shutil.which("pacman") or Path("/etc/arch-release").exists()):
            h.addWidget(button("Build on this PC", slot=self.build_local, tip="Runs build.sh here (Arch/DeckOS only)"))
        self.build_btn = button("Build ISO", "primary", self.start_build, "Starts the 'Build DeckOS ISO' workflow on GitHub")
        h.addWidget(self.build_btn)
        return h

    def current_card(self):
        c = Card("Current build")
        self.cur_state = label("", rich=True)
        self.cur_title = label("No builds yet", "big")
        self.cur_meta = label("", "sub")
        self.cur_meter = Meter(8)
        self.cur_steps = label("", rich=True, wrap=False)
        self.cur_steps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.cancel_btn = button("Cancel", slot=self.cancel_build)
        self.open_btn = button("Open on GitHub", slot=lambda: self.current and webbrowser.open(self.current["html_url"]))
        self.cur_log_btn = button("Show log", slot=lambda: self.current and self.show_log(self.current))
        for w in (self.cur_state, self.cur_title, self.cur_meta):
            c.body.addWidget(w)
        c.body.addSpacing(4)
        c.body.addWidget(self.cur_meter)
        c.body.addSpacing(4)
        c.body.addWidget(self.cur_steps)
        c.body.addWidget(hrow(self.cancel_btn, self.cur_log_btn, self.open_btn))
        return c

    def usb_card(self):
        c = Card("USB", "Ventoy drive")
        self.usb_combo = QComboBox()
        self.usb_combo.setMinimumWidth(280)
        self.usb_info = label("", "sub")
        self.remove_old = QCheckBox("Remove older DeckOS ISOs from the USB")
        self.remove_old.setChecked(self.settings.value("remove_old", False, type=bool))
        self.remove_old.toggled.connect(lambda v: self.settings.setValue("remove_old", v))
        self.usb_meter = Meter(6)
        self.usb_meter.hide()
        self.usb_btn = button("Copy newest ISO to USB", "primary", self.copy_to_usb)
        c.body.addWidget(hrow(self.usb_combo, button("Rescan", slot=self.scan_usb)))
        c.body.addWidget(self.usb_info)
        c.body.addWidget(self.remove_old)
        c.body.addWidget(self.usb_meter)
        c.body.addWidget(hrow(self.usb_btn, button("Open ISO folder", slot=self.open_out)))
        return c

    def history_card(self):
        c = Card("Builds", "Recent ISO builds")
        holder = QWidget()
        self.hist = QVBoxLayout(holder)
        self.hist.setContentsMargins(0, 0, 0, 0)
        self.hist.setSpacing(0)
        self.hist.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(holder)
        scroll.setStyleSheet(f"QScrollArea, QScrollArea > QWidget > QWidget {{ background: {SURFACE}; }}")
        c.body.addWidget(scroll, 1)
        self.dl_meter = Meter(6)
        self.dl_meter.hide()
        self.dl_label = label("", "sub")
        c.body.addWidget(self.dl_meter)
        c.body.addWidget(self.dl_label)
        return c

    # ---- helpers

    def say(self, text, log=True):
        self.status.setText(text)
        if log:
            self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def append_log(self, text):
        self.log.appendPlainText(text)
        self.log.moveCursor(QTextCursor.End)

    def bg(self, fn, done, progress=None):
        # Hold a reference until the result arrives: otherwise Python frees the task's signal
        # object and the queued "done" never reaches the window.
        holder = []

        def finish(res, err):
            self._tasks.discard(holder[0])
            done(res, err)

        task = Task(fn, finish, progress)
        task.setAutoDelete(False)
        holder.append(task)
        self._tasks.add(task)
        self.pool.start(task)

    def out_dir(self):
        d = Path(self.settings.value("out_dir", str(REPO_DIR / "out")))
        if not d.exists() and sys.platform.startswith("linux"):
            # On DeckOS (btrfs) a subvolume of its own, so /home snapshots don't keep old ISOs.
            d.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["btrfs", "subvolume", "create", str(d)], capture_output=True)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def repo(self):
        return self.repo_box.text().strip()

    # ---- startup / repo

    def startup(self):
        def work(_):
            Clock.sync()
            if not gh_path():
                raise RuntimeError("GitHub CLI (gh) not found. Install it: winget install GitHub.cli  (Linux: pacman -S github-cli)")
            st = subprocess.run([gh_path(), "auth", "status"], capture_output=True, text=True, creationflags=NO_WINDOW)
            if st.returncode != 0:
                raise RuntimeError("Not signed in to GitHub. Run:  gh auth login")
            repo = self.repo
            if not repo:
                try:
                    url = subprocess.run(["git", "-C", str(REPO_DIR), "remote", "get-url", "origin"], capture_output=True,
                                         text=True, creationflags=NO_WINDOW).stdout.strip()
                    repo = url.rstrip("/").removesuffix(".git").split("github.com")[-1].lstrip(":/")
                except OSError:
                    repo = ""
            return repo or "kcooperlawson/deckos"

        def done(repo, err):
            if err:
                self.subtitle.setText(str(err))
                self.say(str(err))
                self.build_btn.setEnabled(False)
                return
            if not self.repo:
                self.repo_box.setText(repo)
            self.repo_changed()
            self.scan_usb()

        self.bg(work, done)

    def repo_changed(self):
        self.settings.setValue("repo", self.repo)
        self.subtitle.setText(f"github.com/{self.repo}  ·  {WORKFLOW}  ·  times use GitHub's clock")
        self.refresh()

    # ---- polling

    def refresh(self):
        if self.busy or not self.repo:
            return
        self.busy = True
        repo = self.repo

        def work(_):
            runs = gh_json(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?per_page=12")["workflow_runs"]
            cur = runs[0] if runs else None
            jobs = gh_json(f"repos/{repo}/actions/runs/{cur['id']}/jobs")["jobs"] if cur else []
            # Typical ISO build time = last successful iso job.
            typical = None
            for r in runs:
                if r["conclusion"] == "success":
                    j = [x for x in gh_json(f"repos/{repo}/actions/runs/{r['id']}/jobs")["jobs"] if x["name"] == "iso"]
                    if j and j[0]["completed_at"]:
                        typical = (parse_ts(j[0]["completed_at"]) - parse_ts(r["run_started_at"])).total_seconds()
                    break
            return runs, cur, jobs, typical

        def done(res, err):
            self.busy = False
            if err:
                self.say(f"GitHub: {err}")
                self.timer.start(60000)
                return
            prev = self.current
            self.runs, self.current, self.jobs, typical = res
            if typical:
                self.typical = int(typical)
                self.settings.setValue("typical_iso_seconds", self.typical)
            self.render_current()
            self.render_history()
            active = self.current and self.current["status"] != "completed"
            self.timer.start(15000 if active else 60000)
            if prev and self.current and prev["id"] == self.current["id"] and prev["status"] != "completed" \
                    and self.current["status"] == "completed":
                self.finished(self.current)

        self.bg(work, done)

    def finished(self, run):
        state, _ = run_state(run)
        QApplication.alert(self)
        self.say(f"Build #{run['run_number']} {state.lower()}")
        if state == "Failed":
            self.show_log(run, failed_only=True)
        elif state == "Passed" and self.settings.value("auto_download", True, type=bool):
            self.download(run)

    # ---- rendering

    def render_current(self):
        run = self.current
        if not run:
            return
        state, color = run_state(run)
        started = parse_ts(run["run_started_at"]) or parse_ts(run["created_at"])
        end = parse_ts(run["updated_at"]) if run["status"] == "completed" else Clock.now()
        elapsed = (end - started).total_seconds()
        self.cur_state.setText(pill(state, color) + f'&nbsp;&nbsp;<span style="color:{SUBTEXT}">#{run["run_number"]}</span>')
        msg = (run.get("head_commit") or {}).get("message", run["display_title"]).splitlines()[0]
        self.cur_title.setText(msg)
        active = run["status"] != "completed"
        if active:
            left = self.typical - elapsed
            if left > 60:
                eta = f"about {fmt_duration(left)} left (last build took {fmt_duration(self.typical)})"
            else:
                eta = f"longer than the last build ({fmt_duration(self.typical)}) — still working"
            self.cur_meta.setText(f"Running {fmt_duration(elapsed)}  ·  {eta}")
            self.cur_meter.set(min(0.97, elapsed / max(self.typical, 1)) if left > 60 else 0.97)
        else:
            self.cur_meta.setText(f"{state} in {fmt_duration(elapsed)}  ·  {fmt_ago(end)}")
            self.cur_meter.set(1.0 if state == "Passed" else 0.0)
        self.cancel_btn.setVisible(active)
        lines = []
        done_jobs = [j for j in self.jobs if j["status"] == "completed" and j["conclusion"] in ("success", "skipped")]
        if done_jobs:
            lines.append("&nbsp;&nbsp;".join(f'<span style="color:{SUCCESS}">✓</span> <span style="color:{SUBTEXT}">{j["name"]}</span>'
                                             for j in done_jobs))
        for j in self.jobs:
            if j in done_jobs:
                continue
            for s in j.get("steps", []):
                if s["name"].startswith(("Set up job", "Post ", "Complete job", "Initialize containers", "Stop containers")):
                    continue
                if s["status"] == "completed":
                    icon = {"success": f'<span style="color:{SUCCESS}">✓</span>', "skipped": f'<span style="color:{MUTED}">–</span>'}.get(
                        s["conclusion"], f'<span style="color:{DANGER}">✕</span>')
                elif s["status"] == "in_progress":
                    icon = f'<span style="color:{ACCENT}">●</span>'
                else:
                    icon = f'<span style="color:{MUTED}">○</span>'
                name = s["name"].replace("Run ", "").split(" (")[0]
                if len(name) > 52:
                    name = name[:50] + "…"
                tail = ""
                if s["status"] == "in_progress" and s.get("started_at"):
                    tail = f'&nbsp;<span style="color:{SUBTEXT}">{fmt_duration((Clock.now() - parse_ts(s["started_at"])).total_seconds())}</span>'
                lines.append(f'{icon}&nbsp; <span style="color:{SUBTEXT}">{j["name"]}</span>&nbsp; {name}{tail}')
        self.cur_steps.setText("<br>".join(lines))
        # Rich-text labels under-report their height; size it from the line count instead.
        self.cur_steps.setMinimumHeight(len(lines) * self.cur_steps.fontMetrics().lineSpacing() + 6)

    def render_history(self):
        while self.hist.count() > 1:
            w = self.hist.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, run in enumerate(self.runs):
            row = QFrame()
            row.setObjectName("row" if i else "")
            g = QHBoxLayout(row)
            g.setContentsMargins(2, 10, 2, 10)
            state, color = run_state(run)
            started = parse_ts(run["run_started_at"]) or parse_ts(run["created_at"])
            end = parse_ts(run["updated_at"]) if run["status"] == "completed" else Clock.now()
            msg = (run.get("head_commit") or {}).get("message", run["display_title"]).splitlines()[0]
            if len(msg) > 46:
                msg = msg[:44].rstrip() + "…"
            text = QVBoxLayout()
            text.setSpacing(2)
            text.addWidget(label(f'<b>{msg}</b>', rich=True, wrap=False))
            text.addWidget(label(f'{pill(state, color)}&nbsp;&nbsp;<span style="color:{SUBTEXT}">#{run["run_number"]}  ·  '
                                 f'{fmt_duration((end - started).total_seconds())}  ·  {fmt_ago(started)}</span>', rich=True, wrap=False))
            g.addLayout(text, 1)
            if state == "Passed":
                dl = button("Download ISO", slot=lambda _=False, r=run: self.download(r))
                dl.setMinimumWidth(dl.sizeHint().width())
                g.addWidget(dl)
            g.addWidget(button("Log", slot=lambda _=False, r=run: self.show_log(r, failed_only=run_state(r)[0] == "Failed")))
            self.hist.insertWidget(self.hist.count() - 1, row)

    # ---- actions

    def start_build(self):
        if self.current and self.current["status"] != "completed":
            if QMessageBox.question(self, "DeckOS Builder", "A build is already running. Start another one too?") != QMessageBox.Yes:
                return
        self.build_btn.setEnabled(False)
        self.say("Starting a new ISO build on GitHub…")

        def done(_, err):
            self.build_btn.setEnabled(True)
            if err:
                self.say(f"Couldn't start the build: {err}")
                return
            self.say("Build started")
            QTimer.singleShot(6000, self.refresh)

        self.bg(lambda _: gh("workflow", "run", WORKFLOW, "--repo", self.repo, "--ref", "main"), done)

    def cancel_build(self):
        run = self.current
        if not run or QMessageBox.question(self, "DeckOS Builder", f"Cancel build #{run['run_number']}?") != QMessageBox.Yes:
            return
        self.bg(lambda _: gh("run", "cancel", str(run["id"]), "--repo", self.repo),
                lambda _, e: (self.say(f"Cancel failed: {e}" if e else "Cancel requested"), QTimer.singleShot(5000, self.refresh)))

    def show_log(self, run, failed_only=False):
        self.say(f"Fetching log for #{run['run_number']}…", log=False)

        def work(_):
            args = ["run", "view", str(run["id"]), "--repo", self.repo, "--log-failed" if failed_only else "--log"]
            text = gh(*args, check=False)
            lines = []
            for line in text.splitlines():
                parts = line.split("\t", 2)
                body = parts[-1]
                if len(body) > 29 and body[4] == "-" and body[28] == "Z":
                    body = body[29:]
                lines.append(f"{parts[0]:>8} │ {body}" if len(parts) == 3 else body)
            return lines[-1500:]

        def done(lines, err):
            if err:
                self.say(f"Log: {err}")
                return
            self.log.clear()
            self.append_log(f"── #{run['run_number']} {'failed steps' if failed_only else 'full log'} ──")
            for l in lines:
                self.log.appendPlainText(l)
            self.log.moveCursor(QTextCursor.End)
            self.say(f"Log for #{run['run_number']} loaded ({len(lines)} lines)", log=False)

        self.bg(work, done)

    def download(self, run):
        out = self.out_dir()
        self.dl_meter.show()
        self.dl_meter.set(0)
        repo = self.repo

        def work(progress):
            arts = gh_json(f"repos/{repo}/actions/runs/{run['id']}/artifacts")["artifacts"]
            art = next((a for a in arts if a["name"] == ARTIFACT and not a["expired"]), None)
            if not art:
                raise RuntimeError("this build has no ISO (or it expired after 14 days)")
            token = gh("auth", "token").strip()
            req = urllib.request.Request(art["archive_download_url"])
            req.add_unredirected_header("Authorization", f"Bearer {token}")  # not sent on to the storage host
            zpath = out / f"deckos-run{run['run_number']}.zip"
            total, done_b, t0 = art["size_in_bytes"], 0, time.time()
            with urllib.request.urlopen(req, timeout=60) as r, open(zpath, "wb") as f:
                while chunk := r.read(4 << 20):
                    f.write(chunk)
                    done_b += len(chunk)
                    rate = done_b / max(time.time() - t0, 0.1) / 1e6
                    progress(0.9 * done_b / max(total, 1), f"Downloading #{run['run_number']}: "
                             f"{done_b / 1e9:.2f} / {total / 1e9:.2f} GB  ·  {rate:.0f} MB/s")
            with zipfile.ZipFile(zpath) as z:
                iso_name = next(n for n in z.namelist() if n.endswith(".iso"))
                target = out / iso_name
                with z.open(iso_name) as src, open(target, "wb") as dst:
                    size, copied = z.getinfo(iso_name).file_size, 0
                    while chunk := src.read(8 << 20):
                        dst.write(chunk)
                        copied += len(chunk)
                        progress(0.9 + 0.1 * copied / size, f"Unpacking {iso_name}")
            zpath.unlink()
            return target

        def done(path, err):
            if err:
                self.dl_label.setText(f'<span style="color:{DANGER}">Download failed: {err}</span>')
                self.say(f"Download failed: {err}")
                return
            self.dl_meter.set(1)
            self.dl_label.setText(f"Saved {path.name} ({path.stat().st_size / 1e9:.2f} GB) in {path.parent}")
            self.say(f"ISO ready: {path}")
            self.settings.setValue("last_iso", str(path))

        self.bg(work, done, lambda f, t: (self.dl_meter.set(f), self.dl_label.setText(t)))

    def newest_iso(self):
        last = self.settings.value("last_iso", "")
        if last and Path(last).exists():
            return Path(last)
        isos = sorted(self.out_dir().glob("*.iso"), key=lambda p: p.stat().st_mtime, reverse=True)
        return isos[0] if isos else None

    def scan_usb(self):
        def done(drives, err):
            self.usb_combo.clear()
            if err or not drives:
                self.usb_combo.addItem("No Ventoy USB found")
                self.usb_info.setText("Plug in your Ventoy USB and press Rescan.")
                self.usb_btn.setEnabled(False)
                return
            for path, lab, free in drives:
                self.usb_combo.addItem(f"{path}  ({lab}, {free / 1e9:.1f} GB free)", path)
            self.usb_btn.setEnabled(True)
            path = drives[0][0]
            isos = sorted(Path(path).glob("deckos-*.iso"))
            self.usb_info.setText("On the USB: " + (", ".join(p.name for p in isos) if isos else "no DeckOS ISOs yet"))

        self.bg(lambda _: ventoy_drives(), done)

    def copy_to_usb(self):
        iso = self.newest_iso()
        dest_root = self.usb_combo.currentData()
        if not iso or not dest_root:
            self.say("Nothing to copy: download an ISO first" if not iso else "No USB selected")
            return
        remove_old = self.remove_old.isChecked()
        self.usb_meter.show()
        self.usb_btn.setEnabled(False)

        def work(progress):
            dest = Path(dest_root) / iso.name
            if shutil.disk_usage(dest_root).free < iso.stat().st_size and not dest.exists():
                raise RuntimeError("not enough space on the USB")
            total, done_b = iso.stat().st_size, 0
            with open(iso, "rb") as src, open(dest, "wb") as dst:
                while chunk := src.read(8 << 20):
                    dst.write(chunk)
                    done_b += len(chunk)
                    progress(0.6 * done_b / total, f"Copying {done_b / 1e9:.2f} / {total / 1e9:.2f} GB")
                dst.flush()
                os.fsync(dst.fileno())  # make sure it's really on the stick before saying so
            a = sha256(iso, progress, "Checking (PC)", 0.6, 0.2)
            b = sha256(dest, progress, "Checking (USB)", 0.8, 0.2)
            if a != b:
                raise RuntimeError("the copy on the USB doesn't match — try again or use another USB port")
            removed = []
            if remove_old:
                for old in Path(dest_root).glob("deckos-*.iso"):
                    if old.name != iso.name:
                        old.unlink()
                        removed.append(old.name)
            return dest, a, removed

        def done(res, err):
            self.usb_btn.setEnabled(True)
            if err:
                self.usb_info.setText(f'<span style="color:{DANGER}">Copy failed: {err}</span>')
                self.say(f"USB copy failed: {err}")
                return
            dest, digest, removed = res
            self.usb_meter.set(1)
            self.say(f"Copied and verified {dest.name} (SHA256 {digest[:12]}…)"
                     + (f"; removed {', '.join(removed)}" if removed else ""))
            self.usb_info.setText(f'<span style="color:{SUCCESS}">✓</span> {dest.name} is on the USB and verified. '
                                  "Eject the USB before unplugging it.")

        self.bg(work, done, lambda f, t: (self.usb_meter.set(f), self.usb_info.setText(t)))

    def open_out(self):
        path = str(self.out_dir())
        if IS_WINDOWS:
            os.startfile(path)
        else:
            QProcess.startDetached("xdg-open", [path])

    def build_local(self):
        """Linux (Arch/DeckOS): run build.sh here, streaming its output into the log panel."""
        if self.local_proc and self.local_proc.state() != QProcess.NotRunning:
            self.say("A local build is already running")
            return
        if QMessageBox.question(self, "DeckOS Builder", "Build the ISO on this PC? It needs about 30 GB free and asks for your password.") != QMessageBox.Yes:
            return
        self.log.clear()
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.setWorkingDirectory(str(REPO_DIR))
        p.readyReadStandardOutput.connect(lambda: self.append_log(bytes(p.readAllStandardOutput()).decode("utf-8", "replace").rstrip()))
        p.finished.connect(lambda code, _s: self.say("Local build finished" if code == 0 else f"Local build failed (exit {code})"))
        env = p.processEnvironment()
        env.insert("OUT", str(self.out_dir()))
        p.setProcessEnvironment(env)
        p.start("pkexec", ["env", f"OUT={self.out_dir()}", "bash", str(REPO_DIR / "build.sh")])
        self.local_proc = p
        self.say("Local build started")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DeckOS Builder")
    app.setDesktopFileName("deckos-builder")
    for f in FONTS.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(f))
    app.setStyleSheet(QSS)
    app.setFont(QFont("Inter Display" if IS_WINDOWS else "Inter", 10))
    w = Builder()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
