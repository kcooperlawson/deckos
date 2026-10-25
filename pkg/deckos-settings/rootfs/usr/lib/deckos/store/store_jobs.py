"""Installs and removals, one at a time, with progress read from each tool's output.

Repo packages: pacman through pkexec (asks for your password). Flathub: flatpak, which Arch lets
wheel users run without a password. AUR: paru, with pkexec instead of sudo, so its password prompt
is a window too.
"""
import re
import sys

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

DEMO = "--demo" in sys.argv
FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def command(action, source, ident):
    """The argv for installing or removing `ident` from `source`."""
    if action == "install":
        return {"repo": ["pkexec", "pacman", "-S", "--noconfirm", "--needed", ident],
                "flathub": ["flatpak", "install", "-y", "--noninteractive", "flathub", ident],
                "aur": ["paru", "-S", "--noconfirm", "--needed", "--skipreview", "--sudo", "pkexec", ident]}[source]
    if action == "remove":
        return {"repo": ["pkexec", "pacman", "-Rns", "--noconfirm", ident],
                "aur": ["pkexec", "pacman", "-Rns", "--noconfirm", ident],
                "flathub": ["flatpak", "uninstall", "-y", "--noninteractive", ident]}[source]
    if action == "setup-flathub":
        return ["pkexec", "flatpak", "remote-add", "--if-not-exists", "flathub", FLATHUB_URL]
    if action == "refresh-flathub":
        return ["flatpak", "update", "--appstream", "-y", "--noninteractive"]
    raise ValueError(action)


class Job:
    def __init__(self, key, action, source, ident, title):
        self.key, self.action, self.source, self.ident, self.title = key, action, source, ident, title
        self.progress, self.text, self.log, self.ok = 0.0, "Waiting…", [], None


class Jobs(QObject):
    """A queue of jobs. `changed(key)` fires on any progress; `done(key, ok, message)` at the end."""

    changed = Signal(str)
    done = Signal(str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue, self.current, self.proc = [], None, None
        self.by_key = {}

    def busy(self, key):
        j = self.by_key.get(key)
        return j if j and j.ok is None else None

    def add(self, key, action, source, ident, title):
        job = Job(key, action, source, ident, title)
        self.by_key[key] = job
        self.queue.append(job)
        self.changed.emit(key)
        if not self.current:
            self._next()
        return job

    def _next(self):
        if not self.queue:
            self.current = None
            return
        job = self.current = self.queue.pop(0)
        job.text = {"install": "Installing…", "remove": "Removing…"}.get(job.action, "Working…")
        self.changed.emit(job.key)
        if DEMO:
            self._demo(job)
            return
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._output)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(lambda e: self._finished(-1, None) if e == QProcess.FailedToStart else None)
        argv = command(job.action, job.source, job.ident)
        job.log.append("$ " + " ".join(argv))
        self.proc.start(argv[0], argv[1:])

    def _output(self):
        job = self.current
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        for line in re.split(r"[\r\n]+", text):
            line = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", line).strip()
            if not line:
                continue
            job.log.append(line)
            step = re.search(r"\(\s*(\d+)/(\d+)\)\s+(installing|upgrading|removing|reinstalling)\s+(\S+)", line)
            pct = re.search(r"(\d{1,3})%", line)
            if step:
                n, total = int(step.group(1)), int(step.group(2))
                job.progress = 0.5 + 0.5 * n / total
                job.text = f"{step.group(3).capitalize()} {step.group(4)} ({n}/{total})"
            elif "downloading" in line.lower() or "retrieving" in line.lower():
                job.text = "Downloading…"
                job.progress = max(job.progress, 0.1)
            elif job.source == "aur" and line.startswith("==>"):
                job.text = line[3:].strip()[:60] + "…"
            elif pct and job.source == "flathub":
                job.progress = int(pct.group(1)) / 100
                job.text = f"Installing… {pct.group(1)}%" if job.action == "install" else f"Removing… {pct.group(1)}%"
        self.changed.emit(job.key)

    def _finished(self, code, _status):
        job = self.current
        if job is None or job.ok is not None:
            return
        job.ok = code == 0
        job.progress = 1.0 if job.ok else job.progress
        if job.ok:
            msg = f"{job.title} {'installed' if job.action == 'install' else 'removed' if job.action == 'remove' else 'done'}."
        elif code in (126, 127):
            msg = "Cancelled."
        else:
            tail = " ".join(job.log[-6:]).lower()
            if "failed retrieving file" in tail or "404" in tail:
                msg = "The package files moved on the mirrors: update DecKoOS first, then try again."
            elif "conflict" in tail:
                msg = f"{job.title} conflicts with something installed; see details."
            else:
                msg = f"Something went wrong with {job.title}; see details."
        job.text = msg
        self.changed.emit(job.key)
        self.done.emit(job.key, job.ok, msg)
        self.proc = None
        QTimer.singleShot(0, self._next)

    def _demo(self, job):
        steps = iter([(0.15, "Downloading…"), (0.45, "Downloading…"), (0.7, "Installing… 70%"), (0.9, "Installing… 90%")])

        def tick():
            s = next(steps, None)
            if s is None:
                timer.stop()
                job.log.append("demo: done")
                self._finished(0, None)
                return
            job.progress, job.text = s
            job.log.append(s[1])
            self.changed.emit(job.key)
        timer = QTimer(self, interval=350, timeout=tick)
        timer.start()
