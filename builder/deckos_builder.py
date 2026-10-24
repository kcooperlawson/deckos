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
import re
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
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QTextCursor
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
                               QLineEdit, QMessageBox, QPlainTextEdit, QScrollArea, QSplitter, QVBoxLayout, QWidget)

HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parent
HUB = REPO_DIR / "pkg/deckos-settings/rootfs/usr/lib/deckos/hub"
sys.path.insert(0, str(HUB))  # same look as DeckOS Hub: its palette, QSS, line icons and widgets

import hub_style as S  # noqa: E402
from hub_widgets import Card, Meter, RowItem, StatusTile, Toast, button, label, row  # noqa: E402

BRANDING = REPO_DIR / "pkg/deckos-settings/rootfs/usr/share/deckos/branding"
FONTS = REPO_DIR / "pkg/deckos-settings/rootfs/usr/share/fonts/deckos"
WORKFLOW = "build-iso.yml"
ARTIFACT = "deckos-iso"
IS_WINDOWS = platform.system() == "Windows"
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0  # CREATE_NO_WINDOW: no console flashes on Windows

SURFACE, BORDER, TEXT, SUBTEXT, MUTED = S.SURFACE, S.BORDER, S.TEXT, S.SUBTEXT, S.MUTED
SUCCESS, WARNING, DANGER, ACCENT = S.SUCCESS, S.WARNING, S.DANGER, S.P.accent
PKG_RE = re.compile(r"^(.+)-([^-]+)-([^-]+)-([^-]+)\.pkg\.tar\.zst$")  # name-ver-rel-arch


def git(*args, check=True):
    r = subprocess.run(["git", "-C", str(REPO_DIR), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NO_WINDOW)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f"git {' '.join(args)} failed")
    return r.stdout.strip()


def read_version():
    return (REPO_DIR / "VERSION").read_text().strip()


def next_version(v):
    parts = v.split(".")
    parts[-1] = str(int(parts[-1]) + 1) if parts[-1].isdigit() else parts[-1]
    return ".".join(parts)


def vkey(v):
    return [int(x) if x.isdigit() else 0 for x in v.split(".")]


# ------------------------------------------------------------------ GitHub (via gh)

def gh_path():
    found = shutil.which("gh")
    if found:
        return found
    for p in (r"C:\Program Files\GitHub CLI\gh.exe", "/usr/bin/gh", "/usr/local/bin/gh"):
        if Path(p).exists():
            return p
    return None


WSL_DISTRO = "archlinux"  # Windows: local builds run build.sh in WSL's Arch Linux


def wsl_distros():
    """Installed WSL distributions, lower-case; [] when WSL isn't set up."""
    try:
        r = subprocess.run(["wsl", "-l", "-q"], capture_output=True, creationflags=NO_WINDOW, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode:
        return []
    text = r.stdout.decode("utf-16-le", "ignore") if b"\x00" in r.stdout else r.stdout.decode("utf-8", "ignore")
    return [ln.strip().lower() for ln in text.splitlines() if ln.strip()]


def wsl_path(path):
    """C:/Users/me/x (or with backslashes) -> /mnt/c/Users/me/x"""
    p = Path(path).resolve()
    return f"/mnt/{p.drive[0].lower()}{p.as_posix()[2:]}"


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


def _job_state(job):
    if not job:
        return None
    if job["status"] != "completed":
        return "waiting" if job["status"] in ("queued", "waiting", "pending", "requested") else "running"
    return job["conclusion"]


def phases(run, jobs):
    """A run's two results, each (text, colour): the update (packages in the pacman repo, which
    installed systems get from `deckos update`) and the ISO. A version tag publishes the update
    ~10 minutes in; the ISO takes ~35 more, so the update is usually live long before the ISO."""
    by = {j["name"]: j for j in jobs}
    pub = _job_state(by.get("publish"))
    if not (run.get("event") == "push" and (run.get("head_branch") or "").startswith("v")):
        update = ("No update (not a version tag)", MUTED)
    elif pub == "success":
        update = ("Live: deckos update installs it", SUCCESS)
    elif pub == "running":
        update = ("Publishing…", ACCENT)
    elif pub in ("failure", "cancelled", "timed_out") or "failure" in (_job_state(by.get("lint")), _job_state(by.get("package"))):
        update = ("Not published", DANGER)
    else:
        update = ("Building packages…", WARNING)
    iso = {"success": ("ISO ready", SUCCESS), "running": ("ISO building", ACCENT), "waiting": ("ISO waiting", WARNING),
           None: ("ISO waiting", WARNING), "skipped": ("No ISO", MUTED)}.get(_job_state(by.get("iso")), ("ISO failed", DANGER))
    return update, iso


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

def pill(text, color):
    return (f'<span style="color:{color}; font-weight:600">●</span>&nbsp;'
            f'<span style="color:{color}; font-weight:600">{text}</span>')


def local_state():
    """VERSION, the newest tag, and how many commits are past it / not pushed yet."""
    st = {"version": read_version()}
    try:
        st["tag"] = git("describe", "--tags", "--abbrev=0", check=False)
        st["ahead"] = int(git("rev-list", "--count", f"{st['tag']}..HEAD") or 0) if st["tag"] else 0
        st["unpushed"] = int(git("rev-list", "--count", "@{u}..HEAD", check=False) or 0)
        st["branch"] = git("rev-parse", "--abbrev-ref", "HEAD")
    except (OSError, RuntimeError, ValueError):
        pass
    return st


class ReleaseDialog(QDialog):
    """Version + summary for a release; lists the commits it will publish."""

    def __init__(self, parent, version, commits):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("Release DeckOS")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(10)
        v.addWidget(label("Release DeckOS", "title"))
        v.addWidget(label(f"Now {version}. Tags and pushes main; CI signs the packages and installed systems "
                          "get the update about 5 minutes later. An ISO is only built when the installer or live "
                          "USB changed since the last release.", "sub"))
        self.version = QLineEdit(next_version(version))
        self.summary = QLineEdit()
        self.summary.setPlaceholderText("What changed, e.g. Hub opens again; thumbstick login splash")
        v.addWidget(label("VERSION", "kicker"))
        v.addWidget(self.version)
        v.addWidget(label("SUMMARY", "kicker"))
        v.addWidget(self.summary)
        v.addWidget(label(f"{len(commits)} commit(s) since the last release" if commits else
                          "No new commits since the last release", "kicker"))
        log = QPlainTextEdit("\n".join(commits))
        log.setReadOnly(True)
        log.setFixedHeight(120)
        v.addWidget(log)
        self.iso = QCheckBox("Build an ISO too, even if the installer and live USB didn't change")
        v.addWidget(self.iso)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok = bb.button(QDialogButtonBox.Ok)
        ok.setText("Release")
        ok.setObjectName("primary")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)


# ------------------------------------------------------------------ main window

class Builder(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("DeckOS Builder")
        self.setWindowIcon(QIcon(str(BRANDING / "logo.svg")))
        self.resize(1180, 920)
        self.setMinimumSize(760, 560)
        self.settings = QSettings("DeckOS", "Builder")
        self.pool = QThreadPool.globalInstance()
        self.runs, self.jobs, self.current, self.busy = [], [], None, False
        self.assets, self.local = None, {}
        self._tasks = set()
        self.typical = self.settings.value("typical_iso_seconds", 1800, type=int)
        self.iso_runs = {}  # finished run id -> seconds to a built ISO, or 0 when it built none
        self.local_proc = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(16)
        outer.addLayout(self.header())
        outer.addWidget(self.tiles())

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
        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self.history_card(), 3)
        right.addWidget(self.repo_card(), 2)
        cols.addLayout(right, 6)
        split.addWidget(top)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Build logs and messages appear here.")
        self.log.setMaximumBlockCount(5000)
        split.addWidget(self.log)
        split.setSizes([740, 110])
        outer.addWidget(split, 1)
        self.status = label("", "sub")
        outer.addWidget(self.status)

        self.toast = Toast(self)
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
        self.repo_box.setFixedWidth(200)
        self.repo_box.editingFinished.connect(self.repo_changed)
        h.addWidget(self.repo_box)
        if IS_WINDOWS or shutil.which("pacman") or Path("/etc/arch-release").exists():
            self.local_btn = button("Build on this PC", slot=self.build_local, icon="terminal",
                                    tip="Builds the ISO with this PC's CPU (in WSL on Windows): minutes, not a GitHub queue")
            h.addWidget(self.local_btn)
        self.release_btn = button("Release…", slot=self.release, icon="arrow-up",
                                  tip="Bump VERSION, tag and push: installed systems get it about 10 minutes later")
        h.addWidget(self.release_btn)
        self.build_btn = button("Build ISO", "primary", self.start_build, "play", "Starts the 'Build DeckOS ISO' workflow on GitHub")
        h.addWidget(self.build_btn)
        return h

    def tiles(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)
        self.t_version = StatusTile("package", "This checkout")
        self.t_repo = StatusTile("download", "Update repo")
        self.t_build = StatusTile("snapshot", "Last build")
        self.t_usb = StatusTile("drives", "Ventoy USB")
        self.t_version.clicked.connect(self.release)
        self.t_repo.clicked.connect(lambda: webbrowser.open(f"https://github.com/{self.repo}/releases/tag/repo"))
        self.t_build.clicked.connect(lambda: self.current and webbrowser.open(self.current["html_url"]))
        self.t_usb.clicked.connect(self.scan_usb)
        for t in (self.t_version, self.t_repo, self.t_build, self.t_usb):
            h.addWidget(t, 1)
        return w

    def repo_card(self):
        c = Card("Packages", "pacman repo (the \"repo\" release)", "package")
        self.repo_open = button("Open", slot=lambda: webbrowser.open(f"https://github.com/{self.repo}/releases/tag/repo"),
                                icon="external")
        c.actions.addWidget(self.repo_open)
        holder = QWidget()
        self.pkgs = QVBoxLayout(holder)
        self.pkgs.setContentsMargins(0, 0, 0, 0)
        self.pkgs.setSpacing(6)
        self.pkgs.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(holder)
        scroll.setStyleSheet(f"QScrollArea, QScrollArea > QWidget > QWidget {{ background: {SURFACE}; }}")
        c.body.addWidget(scroll, 1)
        return c

    def current_card(self):
        c = Card("Current build", None, "snapshot")
        self.cur_state = label("")
        self.cur_phases = label("", wrap=False)
        self.cur_title = label("No builds yet", "big")
        self.cur_meta = label("", "sub")
        self.cur_meter = Meter(8)
        self.cur_steps = label("", wrap=False)
        self.cur_steps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.cancel_btn = button("Cancel", slot=self.cancel_build)
        self.open_btn = button("Open on GitHub", slot=lambda: self.current and webbrowser.open(self.current["html_url"]))
        self.cur_log_btn = button("Show log", slot=lambda: self.current and self.show_log(self.current))
        for w in (self.cur_state, self.cur_title, self.cur_meta, self.cur_phases):
            c.body.addWidget(w)
        c.body.addSpacing(4)
        c.body.addWidget(self.cur_meter)
        c.body.addSpacing(4)
        c.body.addWidget(self.cur_steps)
        c.body.addWidget(row(self.cancel_btn, self.cur_log_btn, self.open_btn))
        return c

    def usb_card(self):
        c = Card("USB", "Ventoy drive", "drives")
        self.usb_combo = QComboBox()
        self.usb_combo.setMinimumWidth(280)
        self.usb_info = label("", "sub")
        self.remove_old = QCheckBox("Remove older DeckOS ISOs from the USB")
        self.remove_old.setChecked(self.settings.value("remove_old", False, type=bool))
        self.remove_old.toggled.connect(lambda v: self.settings.setValue("remove_old", v))
        self.usb_meter = Meter(6)
        self.usb_meter.hide()
        self.usb_btn = button("Copy newest ISO to USB", "primary", self.copy_to_usb)
        c.body.addWidget(row(self.usb_combo, button("Rescan", slot=self.scan_usb)))
        c.body.addWidget(self.usb_info)
        c.body.addWidget(self.remove_old)
        c.body.addWidget(self.usb_meter)
        c.body.addWidget(row(self.usb_btn, button("Open ISO folder", slot=self.open_out)))
        return c

    def history_card(self):
        c = Card("Builds", "Recent builds", "list")
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
        known = dict(self.iso_runs)

        def work(_):
            runs = gh_json(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?per_page=12")["workflow_runs"]
            cur = runs[0] if runs else None
            jobs = gh_json(f"repos/{repo}/actions/runs/{cur['id']}/jobs")["jobs"] if cur else []
            # Which finished runs built an ISO (update-only tags don't): asked once per run, then remembered.
            for r in runs:
                if r["status"] == "completed" and r["id"] not in known:
                    rj = jobs if r is cur else gh_json(f"repos/{repo}/actions/runs/{r['id']}/jobs")["jobs"]
                    j = next((x for x in rj if x["name"] == "iso"), None)
                    known[r["id"]] = (parse_ts(j["completed_at"]) - parse_ts(r["run_started_at"])).total_seconds()                         if j and j["conclusion"] == "success" and j["completed_at"] else 0
            # Typical ISO build time = the newest run that built one.
            typical = next((known[r["id"]] for r in runs if known.get(r["id"])), None)
            try:
                assets = gh_json(f"repos/{repo}/releases/tags/repo")["assets"]
            except RuntimeError:
                assets = None  # no repo release yet
            return runs, cur, jobs, typical, assets, local_state(), known

        def done(res, err):
            self.busy = False
            if err:
                self.say(f"GitHub: {err}")
                self.timer.start(60000)
                return
            prev, prev_jobs = self.current, self.jobs
            self.runs, self.current, self.jobs, typical, self.assets, self.local, self.iso_runs = res
            # The update goes live ~35 minutes before the ISO is done: say so the moment it does.
            if prev and self.current and prev["id"] == self.current["id"]:
                was, now = phases(prev, prev_jobs)[0][1], phases(self.current, self.jobs)[0][1]
                if now == SUCCESS and was != SUCCESS:
                    QApplication.alert(self)
                    tag = self.current.get("head_branch", "")
                    iso = phases(self.current, self.jobs)[1][0]
                    self.say(f"Update {tag} is live: deckos update installs it" +
                             (" (no ISO needed this time)" if iso == "No ISO" else " (the ISO is still building)"))
                    self.toast.show_message(f"Update {tag} is live: run deckos update", "ok", 9000)
            if typical:
                self.typical = int(typical)
                self.settings.setValue("typical_iso_seconds", self.typical)
            self.render_current()
            self.render_history()
            self.render_repo()
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
        self.toast.show_message(f"Build #{run['run_number']} {state.lower()}",
                                {"Passed": "ok", "Failed": "bad"}.get(state, "info"))
        if state == "Failed":
            self.show_log(run, failed_only=True)
        elif state == "Passed" and self.settings.value("auto_download", True, type=bool)                 and phases(run, self.jobs)[1][0] == "ISO ready":  # update-only tags have no ISO to fetch
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
        (u_text, u_col), (i_text, i_col) = phases(run, self.jobs)
        self.cur_phases.setText(f'<span style="color:{SUBTEXT}">Update</span>&nbsp; {pill(u_text, u_col)}'
                                f'&nbsp;&nbsp;&nbsp;<span style="color:{SUBTEXT}">ISO</span>&nbsp; {pill(i_text, i_col)}')
        msg = (run.get("head_commit") or {}).get("message", run["display_title"]).splitlines()[0]
        self.cur_title.setText(msg)
        active = run["status"] != "completed"
        if active and i_text == "No ISO":
            self.cur_meta.setText(f"Running {fmt_duration(elapsed)}  ·  update only, no ISO this time")
            self.cur_meter.set(min(0.97, elapsed / 400))
        elif active:
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
            lines.append("&nbsp;&nbsp;".join(
                f'<span style="color:{SUCCESS}">✓</span> <span style="color:{SUBTEXT}">{j["name"]}</span>'
                if j["conclusion"] == "success" else
                f'<span style="color:{MUTED}">– {j["name"]} skipped</span>' for j in done_jobs))
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

    def render_tiles(self):
        lo = self.local
        if lo:
            v = lo["version"]
            if lo.get("ahead"):
                self.t_version.set(v, f"{lo['ahead']} commit(s) not released yet: click to release", "warn")
            elif lo.get("unpushed"):
                self.t_version.set(v, f"{lo['unpushed']} commit(s) not pushed", "warn")
            else:
                self.t_version.set(v, f"Released as {lo.get('tag') or 'v' + v}", "ok")
        if self.assets is None:
            self.t_repo.set("No repo yet", "Push a version tag to publish packages", "off")
        else:
            vers = {m.group(1): m.group(2) for a in self.assets if (m := PKG_RE.match(a["name"]))}
            pub = vers.get("deckos-settings", "?")
            newest = max((parse_ts(a["updated_at"]) for a in self.assets), default=None)
            when = f"published {fmt_ago(newest)}" if newest else ""
            if lo and pub != lo["version"] and vkey(lo["version"]) > vkey(pub) and not lo.get("ahead"):
                self.t_repo.set(pub, f"{lo['version']} is on its way · {when}", "info")
            else:
                self.t_repo.set(pub, f"deckos-settings · {when}", "ok")
        if self.current:
            state, _ = run_state(self.current)
            (u_text, u_col), (i_text, _) = phases(self.current, self.jobs)
            if u_col == SUCCESS and self.current["status"] != "completed":
                # Tag build half done: the update is installable, the ISO isn't yet.
                self.t_build.set("Update live", f"{i_text} · {self.current.get('head_branch', '')}", "ok")
            elif state == "Passed" and i_text == "No ISO":
                self.t_build.set("Update only", f"No ISO needed · {self.current.get('head_branch', '')}", "ok")
            else:
                self.t_build.set(f"#{self.current['run_number']} {state.lower()}", self.current["display_title"][:48],
                                 {"Passed": "ok", "Failed": "bad", "Cancelled": "off"}.get(state, "info"))

    def render_repo(self):
        self.render_tiles()
        while self.pkgs.count() > 1:
            w = self.pkgs.takeAt(0).widget()
            if w:
                w.deleteLater()
        pkgs = sorted((a for a in self.assets or [] if PKG_RE.match(a["name"])), key=lambda a: a["name"])
        if not pkgs:
            self.pkgs.insertWidget(0, label("No packages published yet.", "sub"))
        for a in pkgs:
            name, ver, rel, _ = PKG_RE.match(a["name"]).groups()
            self.pkgs.insertWidget(self.pkgs.count() - 1, RowItem(
                "package", name, f"{ver}-{rel}  ·  {a['size'] / 1e6:.1f} MB  ·  {fmt_ago(parse_ts(a['updated_at']))}",
                S.P.accent))

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
            text.addWidget(label(f'<b>{msg}</b>', wrap=False))
            text.addWidget(label(f'{pill(state, color)}&nbsp;&nbsp;<span style="color:{SUBTEXT}">#{run["run_number"]}  ·  '
                                 f'{fmt_duration((end - started).total_seconds())}  ·  {fmt_ago(started)}</span>', wrap=False))
            g.addLayout(text, 1)
            if state == "Passed" and self.iso_runs.get(run["id"]):
                dl = button("Download ISO", slot=lambda _=False, r=run: self.download(r))
                dl.setMinimumWidth(dl.sizeHint().width())
                g.addWidget(dl)
            elif state == "Passed" and run["id"] in self.iso_runs:
                g.addWidget(label(f'<span style="color:{MUTED}">update only</span>', wrap=False))
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

    def release(self):
        lo = local_state()
        if lo.get("branch") not in (None, "main"):
            QMessageBox.warning(self, "DeckOS Builder", f"Releases go out from main; this checkout is on {lo['branch']}.")
            return
        tag = lo.get("tag")
        commits = git("log", "--oneline", f"{tag}..HEAD" if tag else "-20", check=False).splitlines()
        dlg = ReleaseDialog(self, lo["version"], commits)
        if dlg.exec() != QDialog.Accepted:
            return
        ver, summary, want_iso = dlg.version.text().strip(), dlg.summary.text().strip(), dlg.iso.isChecked()
        if not re.fullmatch(r"\d+(\.\d+)+", ver) or vkey(ver) <= vkey(lo["version"]):
            self.toast.show_message(f"Version must be newer than {lo['version']}", "bad")
            return
        if not summary:
            self.toast.show_message("Add a short summary first", "bad")
            return
        self.release_btn.setEnabled(False)
        self.say(f"Releasing DeckOS {ver}…")

        def work(_):
            if git("tag", "-l", f"v{ver}"):
                raise RuntimeError(f"tag v{ver} already exists")
            (REPO_DIR / "VERSION").write_text(ver + "\n")
            msg = f"DeckOS {ver}: {summary}"
            git("commit", "-m", msg, "--", "VERSION")
            git("tag", "-a", f"v{ver}", "-m", msg + (" [iso]" if want_iso else ""))  # [iso]: CI's plan job builds one
            git("push", "origin", "HEAD:main")
            git("push", "origin", f"v{ver}")

        def done(_, err):
            self.release_btn.setEnabled(True)
            if err:
                self.say(f"Release failed: {err}")
                self.toast.show_message("Release failed: see the log", "bad", 8000)
                return
            self.say(f"Released DeckOS {ver}: installed systems get it in about 5 minutes")
            self.toast.show_message(f"DeckOS {ver} is on its way", "ok")
            QTimer.singleShot(8000, self.refresh)

        self.bg(work, done)

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
        """The most recently made ISO: downloaded or built on this PC, whichever came last."""
        isos = list(self.out_dir().glob("*.iso"))
        last = Path(self.settings.value("last_iso", "") or "")
        if last.name and last.exists():
            isos.append(last)  # a download kept outside the ISO folder
        return max(isos, key=lambda p: p.stat().st_mtime, default=None)

    def scan_usb(self):
        def done(drives, err):
            self.usb_combo.clear()
            if err or not drives:
                self.usb_combo.addItem("No Ventoy USB found")
                self.usb_info.setText("Plug in your Ventoy USB and press Rescan.")
                self.usb_btn.setEnabled(False)
                self.t_usb.set("Not plugged in", "Click to scan again", "off")
                return
            for path, lab, free in drives:
                self.usb_combo.addItem(f"{path}  ({lab}, {free / 1e9:.1f} GB free)", path)
            self.usb_btn.setEnabled(True)
            self.t_usb.set(drives[0][0], f"{drives[0][2] / 1e9:.1f} GB free", "ok")
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
        """Run build.sh on this PC: directly on Arch/DeckOS, in WSL's Arch Linux on Windows. Output streams
        into the log panel; the ISO lands in the ISO folder, ready for Copy newest ISO to USB."""
        if self.local_proc and self.local_proc.state() != QProcess.NotRunning:
            self.stop_local()
            return
        out = self.out_dir()
        out.mkdir(parents=True, exist_ok=True)
        if IS_WINDOWS:
            distros = wsl_distros()
            if WSL_DISTRO not in distros:
                self.setup_wsl(bool(distros))
                return
            ask = ("Build the ISO on this PC?\n\nIt runs in WSL (Arch Linux) on all your CPU cores, needs about 30 GB "
                   "free on C: while it works and takes roughly 10 minutes. Nothing is published.")
            cmd = ["wsl", "-d", WSL_DISTRO, "-u", "root", "--exec", "env", f"OUT={wsl_path(out)}",
                   "WORK=/var/tmp/deckos-build", "bash", wsl_path(REPO_DIR / "build.sh")]
        else:
            ask = "Build the ISO on this PC? It needs about 30 GB free and asks for your password."
            cmd = ["pkexec", "env", f"OUT={out}", "bash", str(REPO_DIR / "build.sh")]
        if QMessageBox.question(self, "DeckOS Builder", ask) != QMessageBox.Yes:
            return
        self.log.clear()
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.setWorkingDirectory(str(REPO_DIR))
        ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        p.readyReadStandardOutput.connect(lambda: self.append_log(
            ansi.sub("", bytes(p.readAllStandardOutput()).decode("utf-8", "replace")).rstrip()))
        started = time.time()

        def finished(code, _status):
            took = fmt_duration(time.time() - started)
            self.local_btn.setText("Build on this PC")
            QApplication.alert(self)
            if code == 0:
                iso = self.newest_iso()
                if iso:
                    self.settings.setValue("last_iso", str(iso))
                self.say(f"Local build finished in {took}" + (f": {iso.name}" if iso else ""))
                self.toast.show_message(f"ISO built on this PC in {took}", "ok", 8000)
            else:
                self.say(f"Local build stopped (exit {code}) after {took}: see the log")
                self.toast.show_message("Local build failed: see the log", "bad", 8000)

        p.finished.connect(finished)
        p.start(cmd[0], cmd[1:])
        self.local_proc = p
        self.local_btn.setText("Stop local build")
        self.say("Local build started" + (" in WSL" if IS_WINDOWS else ""))

    def stop_local(self):
        if QMessageBox.question(self, "DeckOS Builder", "Stop the local build?") != QMessageBox.Yes:
            return
        if IS_WINDOWS:
            # Ending wsl.exe leaves build.sh running inside; shutting the distro down stops all of it.
            subprocess.run(["wsl", "--terminate", WSL_DISTRO], creationflags=NO_WINDOW)
        else:
            self.local_proc.terminate()

    def setup_wsl(self, have_wsl):
        """One-time: WSL (if missing) and its Arch Linux, which local builds on Windows run in."""
        box = QMessageBox(self)
        box.setWindowTitle("DeckOS Builder")
        box.setText("Building on Windows needs WSL with Arch Linux")
        box.setInformativeText(
            ("WSL is set up; this adds Arch Linux to it (a few minutes). " if have_wsl else
             "Windows installs WSL and Arch Linux (a few minutes; asks for admin, and may need a restart). ") +
            "When the Arch Linux window finishes and shows a prompt, close it and click Build on this PC again.")
        go = box.addButton("Set up WSL", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is not go:
            return
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          f"Start-Process powershell -Verb RunAs -ArgumentList '-NoExit','-Command','wsl --install {WSL_DISTRO}'"],
                         creationflags=NO_WINDOW)
        self.say("Setting up WSL with Arch Linux in a new window…")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DeckOS Builder")
    app.setDesktopFileName("deckos-builder")
    for f in FONTS.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(f))
    app.setStyleSheet(S.qss() + f"""
QLineEdit {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 10px; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
#row {{ background: transparent; border-top: 1px solid {BORDER}; }}
""")
    app.setFont(QFont("Inter Display" if IS_WINDOWS else "Inter", 10))
    w = Builder()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
