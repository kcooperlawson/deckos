"""DecKoOS Care: System Doctor's checks, run when something happens instead of when someone remembers to open
it. A user service (deckos-care.service) that follows three streams and never polls:

- the journal's crash reports: a program of yours crashed -> one calm notification, with "Why?" opening
  System Doctor, and a line in the timeline. Games are Game Doctor's (it watches Steam itself); code being worked
  on (a DecKoOS checkout, a test run) is the developer's, who sees it in their terminal.
- the system timeline (DecKoOS Pulse): after an update, install or removal -> "restart to finish", a service
  that failed, a drive filling up.
- this user's timeline: a game stopped -> is the drive filling up?

Each thing is said once in a while, not every time (KEEP_QUIET), and the timeline keeps the record.
"""
import json
import os
import selectors
import subprocess
import sys
import threading
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(LIB / "sysdoctor"), str(LIB / "pulse")]
import pulse  # noqa: E402
import sysdoctor as sd  # noqa: E402

STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "deckos/care.json"
KEEP_QUIET = {"crash": 3600, "finding": 6 * 3600}  # seconds before the same thing is said again
AFTER_CHANGES = (sd.restart_pending, sd.failed_units, sd.disk_space)  # quick checks, after a system change
CRASH_FIELDS = "COREDUMP_COMM,COREDUMP_CMDLINE,COREDUMP_UID,COREDUMP_SIGNAL_NAME"
# Crashes of code being worked on, not of the system: DecKoOS run from a checkout, and test runners. Left out, or
# a morning of development fills the timeline (26 "crashes" in four minutes once) and buries a real one.
DEVELOPMENT = ("/pkg/deckos-settings/rootfs/", "/tests/", "-m unittest", "-m pytest", "/pytest", "check.sh")


def development(cmd):
    """True for a command line that's code being developed or tested rather than the installed system."""
    return any(mark in cmd for mark in DEVELOPMENT) or any(Path(a).name.startswith(("test_", "zz_test"))
                                                          for a in cmd.split())


class Care:
    """What to say about each event; `notify(title, body, button, cmd)` says it, `checks` are System Doctor's."""

    def __init__(self, notify, checks=AFTER_CHANGES, uid=None, now=time.time, record=pulse.emit):
        self.notify, self.checks, self.now, self.record = notify, checks, now, record
        self.uid = os.getuid() if uid is None else uid
        self.said = self.load()

    def load(self):
        try:
            return json.loads(STATE.read_text())
        except (OSError, ValueError):
            return {}

    def save(self):
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(self.said))
        except OSError:
            pass

    def quiet(self, key, kind):
        """True if this was said recently; otherwise remembers saying it now."""
        if key in self.said and self.now() - self.said[key] < KEEP_QUIET[kind]:
            return True
        self.said[key] = self.now()
        self.save()
        return False

    # ---- the three streams

    def crash(self, line):
        try:
            e = json.loads(line)
        except ValueError:
            return
        comm, cmd = str(e.get("COREDUMP_COMM", "")), str(e.get("COREDUMP_CMDLINE", ""))
        if not comm or str(e.get("COREDUMP_UID", "")) != str(self.uid):
            return  # someone else's, or the system's: System Doctor's checkup lists those
        if development(cmd):
            return
        name, kind = sd.name_program(comm, cmd)
        if kind == "game":
            return  # Game Doctor's job
        self.record("crash", f"{name} crashed", detail=str(e.get("COREDUMP_SIGNAL_NAME", "")), app="DecKoOS Care")
        if not self.quiet(f"crash:{name}", "crash"):
            self.notify(f"{name} closed unexpectedly", "System Doctor can show why, and what to do about it.",
                        "Why?", ["deckos-sysdoctor"])

    def timeline(self, line, source):
        try:
            e = json.loads(line)
        except ValueError:
            return
        kind = e.get("kind")
        if source == "system" and kind in ("update", "install", "remove"):
            self.check(self.checks)
        elif source == "user" and kind == "game-stop":
            self.check([sd.disk_space])

    def check(self, checks):
        for check in checks:
            try:
                findings = check()
            except Exception:  # a broken check never stops the others (as in sysdoctor.checkup)
                continue
            for f in findings:
                if f.level in (sd.BAD, sd.WARN) and not self.quiet(f"finding:{f.key}", "finding"):
                    self.record("care", f.title, detail=f.text, app="DecKoOS Care")
                    fix = f.fixes[0] if f.fixes and f.key == "restart" else None
                    # A vetted recipe (heal.py) is offered in the notification itself, if the person allows suggestions;
                    # anything else, or with suggestions off, opens System Doctor to show what's wrong
                    if fix is None and f.fixes and "heal" in f.fixes[0].cmd and suggestions_on():
                        fix = f.fixes[0]
                    self.notify(f.title, f.text, fix.title if fix else "Show me",
                                fix.cmd if fix else ["deckos-sysdoctor"])


def suggestions_on():
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heal"))
        import heal
        return heal.is_on("suggest")
    except Exception:
        return False


def notify(title, body, button, cmd):
    """A desktop notification with one button; clicking it runs cmd. Doesn't block the watcher."""
    def wait():
        try:
            r = subprocess.run(["notify-send", "--app-name=DecKoOS", "--icon=deckos", "--expire-time=20000",
                                f"--action=go={button}", title, body], capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            return
        if r.stdout.strip() != "go":
            return
        if "heal" in cmd and "apply" in cmd:  # a vetted recipe: run it, then "Did that fix it?"
            done = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if done.returncode == 0:
                i = cmd.index("apply")
                finding = next((a.split("=", 1)[1] for a in cmd if a.startswith("--finding=")), "")
                subprocess.Popen(["deckos", "heal", "ask", cmd[i + 1], finding], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Thread(target=wait, daemon=True).start()


def follow():
    """Runs until stopped: the journal's crash reports and both timelines, line by line."""
    care = Care(notify)
    sel = selectors.DefaultSelector()
    streams = {
        "crash": ["journalctl", "--follow", "--lines=0", "--output=json", "--identifier=systemd-coredump",
                  f"--output-fields={CRASH_FIELDS}"],
        "system": ["tail", "-F", "-n0", str(pulse.system_file())],
        "user": ["tail", "-F", "-n0", str(pulse.user_file())],
    }
    procs = []
    for name, cmd in streams.items():
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        procs.append(p)
        sel.register(p.stdout, selectors.EVENT_READ, name)
    # Once, a little after login: a drive that filled up, or a restart still owed
    started, first_done = time.monotonic(), False
    try:
        while True:
            timeout = None if first_done else max(0.0, 120 - (time.monotonic() - started))
            for key, _ in sel.select(timeout):
                line = key.fileobj.readline()
                if not line:
                    sel.unregister(key.fileobj)
                    continue
                if key.data == "crash":
                    care.crash(line)
                else:
                    care.timeline(line, key.data)
            if not first_done and time.monotonic() - started >= 120:
                care.check([sd.disk_space, sd.restart_pending])
                first_done = True
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    follow()
