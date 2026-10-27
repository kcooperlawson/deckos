"""DecKoOS's daily self-test: the things DecKoOS itself relies on, each tried for real, so a part that breaks says so the
day it breaks, with the real cause, instead of failing quietly for weeks. (Update checks once failed for days with
"No connection" while the cause was a signature check; nothing said so.)

No Qt, read-only. The user unit deckos-selftest.timer runs it daily; a desktop notification only when a check that
passed starts failing (never the same news twice). System Doctor and `deckos selftest` show the latest results.
Tests feed `run` canned output: tests/test_selftest.py.

    selftest.py [run|show|watch|updates]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "deckos/selftest.json"


@dataclass
class Result:
    id: str
    ok: bool
    title: str  # what was checked, in plain words
    cause: str = ""  # when it failed: what actually happened
    fix: str = ""  # a command that fixes it, when there is one
    skipped: bool = False  # not on this PC (no scheduler installed, say)


def run(cmd, timeout=60):
    """(exit code, stdout, stderr); a missing program is 127, never an exception."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} isn't installed"
    except (OSError, subprocess.TimeoutExpired) as e:
        return 124, "", str(e)


def update_cause(stderr):
    """checkupdates' failure in plain words: the line pacman printed, not a guess."""
    text = stderr.strip()
    if re.search(r"missing required signature|signature from .* is (invalid|unknown trust)", text):
        repo = re.search(r"error: (\S+): (missing required signature|signature)", text)
        return (f"The {repo.group(1) if repo else 'a'} repo's signature couldn't be checked, so no updates are "
                "found. Run deckos update (it checks as root) and tell the DecKoOS maintainer.")
    if re.search(r"Could not resolve host|Failed to connect|Connection timed out|failed retrieving file", text):
        return "No connection to the package mirrors (or they're down)."
    lines = [ln for ln in text.splitlines() if "error" in ln.lower()] or text.splitlines()
    return lines[-1][:200] if lines else "checkupdates failed without saying why."


def check_updates():
    if not shutil.which("checkupdates"):
        return Result("updates", False, "Checking for updates", "checkupdates isn't installed (pacman-contrib).",
                      "pkexec pacman -S --needed pacman-contrib")
    code, _out, err = run(["checkupdates"], 180)
    if code in (0, 2):  # 2: nothing to update
        return Result("updates", True, "Checking for updates")
    return Result("updates", False, "Checking for updates", update_cause(err), "deckos update")


def check_sound():
    code, out, _ = run(["pw-metadata", "-n", "settings"], 15)
    if code == 127:
        return Result("sound", True, "Sound", skipped=True)
    if code != 0:
        return Result("sound", False, "Sound", "PipeWire (the sound server) isn't answering.",
                      "systemctl --user restart pipewire pipewire-pulse wireplumber")
    m = re.search(r"key:'clock\.min-quantum' value:'(\d+)'", out)
    if m and int(m.group(1)) < 128:
        return Result("sound", False, "Sound", f"The sound buffer floor is {m.group(1)} samples: games and music "
                      "together may crackle.", "deckos sound buffer balanced")
    return Result("sound", True, "Sound")


def check_unit(rid, title, unit, user=False, why=""):
    base = ["systemctl"] + (["--user"] if user else [])
    code, out, _ = run(base + ["is-enabled", unit], 15)
    if out.strip() in ("", "not-found") or code == 127:
        return Result(rid, True, title, skipped=True)
    if out.strip() in ("disabled", "masked"):
        return Result(rid, True, title, skipped=True)  # turned off on purpose
    code, out, _ = run(base + ["is-active", unit], 15)
    if out.strip() == "active":
        return Result(rid, True, title)
    return Result(rid, False, title, f"{unit} isn't running{': ' + why if why else ''}.",
                  " ".join(base[:1] + (["--user"] if user else []) + ["restart", unit]) if user else
                  f"pkexec systemctl restart {unit}")


def check_space():
    try:
        st = os.statvfs("/")
    except OSError:
        return Result("space", True, "Room for updates", skipped=True)
    free = st.f_bavail * st.f_frsize
    if free < 8e9:
        return Result("space", False, "Room for updates", f"Only {free / 1e9:.1f} GB free on the system drive: "
                      "updates and snapshots start failing below a few GB.", "deckos-hub --page system")
    return Result("space", True, "Room for updates")


def check_failed_units():
    code, out, _ = run(["systemctl", "--failed", "--no-legend", "--plain"], 15)
    names = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    if code == 0 and names:
        return Result("failed", False, "System services", f"{len(names)} failed: {', '.join(names[:4])}"
                      + (" and more" if len(names) > 4 else ""), "deckos-sysdoctor")
    return Result("failed", True, "System services")


def checks():
    return [check_updates(), check_sound(), check_space(), check_failed_units(),
            check_unit("scheduler", "Game scheduler", "scx_loader.service", why="games lose the tuned CPU scheduler"),
            check_unit("modes", "Workload modes", "deckos-modes.service", user=True,
                       why="AI and Docker aren't paused while you play"),
            check_unit("care", "DecKoOS Care", "deckos-care.service", user=True,
                       why="crash reports and fixes aren't offered")]


def load():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save(results, notified):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"at": time.time(), "results": [asdict(r) for r in results], "notified": notified}))
    tmp.replace(STATE)


def news(results, before):
    """Failures to tell the person about: ones that weren't failing (or were failing for another reason) last time."""
    old = {r["id"]: r for r in before.get("results", []) if not r.get("ok")}
    told = set(before.get("notified", []))
    return [r for r in results if not r.ok and not (r.id in old and old[r.id].get("cause") == r.cause and r.id in told)]


def notify(fails):
    if not fails or not shutil.which("notify-send"):
        return
    title = fails[0].title + (" stopped working" if len(fails) == 1 else f" and {len(fails) - 1} more need a look")
    body = fails[0].cause + (f"\nFix: {fails[0].fix}" if fails[0].fix else "")
    subprocess.Popen(["notify-send", "--app-name=DecKoOS", "--icon=deckos", "--urgency=normal", f"DecKoOS: {title}",
                      body], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_all(tell=True):
    before = load()
    results = checks()
    new = news(results, before)
    if tell:
        notify(new)
    still = [r.id for r in results if not r.ok and r.id in set(before.get("notified", []))]
    save(results, sorted(set(still) | {r.id for r in new}))
    return results


def show(results):
    for r in results:
        mark = "–" if r.skipped else "✔" if r.ok else "✘"
        print(f"{mark} {r.title}" + ("" if r.ok else f": {r.cause}" + (f"\n    fix: {r.fix}" if r.fix else "")))


def main(argv):
    cmd = argv[0] if argv else "run"
    if cmd == "run":
        results = run_all(tell=False)  # from a terminal: shown here, not as a notification
        show(results)
        return 0 if all(r.ok for r in results) else 1
    if cmd == "watch":  # the timer's run
        run_all(tell=True)
        return 0
    if cmd == "updates":  # the Hub's "Couldn't check for updates": why, in plain words
        r = check_updates()
        print("" if r.ok else r.cause)
        return 0
    if cmd == "show":
        data = load()
        if not data:
            print("No self-test yet: deckos selftest")
            return 0
        show([Result(**r) for r in data.get("results", [])])
        print(f"(checked {time.strftime('%b %d %H:%M', time.localtime(data.get('at', 0)))})")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
