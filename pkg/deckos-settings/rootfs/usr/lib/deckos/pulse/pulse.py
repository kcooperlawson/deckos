"""DecKoOS Pulse: what happened on this PC, in one place, and how to take it back.

Every part of DecKoOS records the things a person would want to know about (an update, a snapshot, a game
fix, a theme, a drive, a game starting) as one line in a timeline, and other parts react to it: the files
are watched (no polling), and a user's events also go out as a D-Bus signal (org.deckos.Pulse.Event).

Two timelines, merged when read:
- ~/.local/state/deckos/timeline.jsonl: this user's events (themes, game fixes, Retro...).
- /var/lib/deckos/timeline.jsonl: the system's (updates, snapshots, drives), written as root.

An event can carry an undo: a `deckos ...` command from UNDOABLE. A user file can't ask for root: only
entries in the root-owned system timeline undo through pkexec.

    python3 pulse.py emit KIND TITLE [--detail TEXT] [--app NAME] [--undo deckos ARGS...]
    python3 pulse.py list [--json] [--limit N]
    python3 pulse.py undo ID
"""
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path

def user_file():
    # read each time, so tests (DECKOS_PULSE_USER) never touch a real timeline
    return Path(os.environ.get("DECKOS_PULSE_USER") or
                Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "deckos/timeline.jsonl")


def system_file():
    return Path(os.environ.get("DECKOS_PULSE_SYSTEM") or "/var/lib/deckos/timeline.jsonl")
MAX_BYTES = 1 << 20  # then the oldest half goes

# deckos subcommands an undo may run (each one already knows how to put its change back)
UNDOABLE = {"theme", "accent", "layout", "undo", "restore", "drives", "mode", "profile", "retro", "gamedoctor", "setup"}

# What each kind of event looks like where it's shown: (DecKoOS line icon, group)
KINDS = {
    "update": ("update", "System"), "snapshot": ("snapshot", "System"), "undo": ("undo", "System"),
    "drives": ("drives", "System"), "install": ("package", "Apps"), "remove": ("trash", "Apps"),
    "theme": ("appearance", "Look"), "accent": ("drop", "Look"), "layout": ("panel-right", "Look"),
    "game-start": ("play", "Games"), "game-stop": ("stop", "Games"), "gamedoctor": ("check", "Games"),
    "profile": ("sliders", "Games"), "retro": ("gaming", "Games"), "mode": ("gauge", "Games"),
    "crash": ("alert", "Health"), "care": ("shield", "Health"), "setup": ("download", "System"),
    "kids": ("user", "System"),
}


def _now():
    return time.time()


def _target(system=None):
    """Root writes the system timeline; everyone else their own."""
    if system is None:
        system = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    return system_file() if system else user_file()


def _append(path, entry):
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        if path.stat().st_size > MAX_BYTES:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(True)
            path.write_text("".join(lines[len(lines) // 2:]), encoding="utf-8")
    except FileNotFoundError:
        pass
    try:  # a line cut short by a crash: start a fresh one, or this event would be glued onto it
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                line = "\n" + line
    except OSError:
        pass  # a new (or empty) file
    with open(path, "a", encoding="utf-8") as f:  # one write per line: concurrent writers don't interleave
        f.write(line)
    if path == system_file():
        try:
            os.chmod(path, 0o644)  # everyone reads the system timeline; only root writes it
        except OSError:
            pass


def emit(kind, title, detail="", app="", undo=None, data=None, system=None):
    """Records an event and returns it. `undo` is a deckos command as a list (["deckos", "theme", ...])."""
    if undo is not None and not undoable(undo):
        raise ValueError(f"not an undo DecKoOS runs: {undo}")
    entry = {"id": uuid.uuid4().hex[:12], "time": round(_now(), 3), "kind": kind, "title": title}
    if detail:
        entry["detail"] = detail
    if app:
        entry["app"] = app
    if undo:
        entry["undo"] = list(undo)
    if data:
        entry["data"] = data
    path = _target(system)
    _append(path, entry)
    if path == user_file() and not os.environ.get("DECKOS_PULSE_USER"):
        # Live listeners on this user's session bus; harmless when there's no session (a service, ssh)
        subprocess.run(["busctl", "--user", "emit", "/org/deckos/Pulse", "org.deckos.Pulse", "Event", "ss",
                        kind, json.dumps(entry, ensure_ascii=False)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=False)
    return entry


def undoable(argv):
    return (isinstance(argv, (list, tuple)) and len(argv) >= 2 and argv[0] == "deckos" and argv[1] in UNDOABLE
            and all(isinstance(a, str) and "\n" not in a for a in argv))


def _read(path, source):
    out = []
    n = 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue  # a half-written line from a crash: skip it, keep the rest
        if isinstance(e, dict) and e.get("id") and e.get("kind"):
            e["source"] = source
            e["_order"] = n  # same-millisecond events keep the order they were written in
            n += 1
            out.append(e)
    return out


def entries(limit=200, kinds=None):
    """Newest first, both timelines merged. Undone events carry undone=True; the undo events themselves
    are kept (they say what was put back)."""
    all_ = _read(system_file(), "system") + _read(user_file(), "user")
    undone = {e.get("data", {}).get("target") for e in all_ if e["kind"] == "undo"}
    for e in all_:
        e["undone"] = e["id"] in undone
        e["can_undo"] = bool(e.get("undo")) and not e["undone"] and undoable(e["undo"])
    all_.sort(key=lambda e: (e.get("time", 0), e["_order"]), reverse=True)
    if kinds:
        all_ = [e for e in all_ if e["kind"] in kinds]
    return all_[:limit]


def find(entry_id):
    return next((e for e in entries(limit=100000) if e["id"] == entry_id), None)


def undo(entry_id, runner=subprocess.run):
    """Runs an event's undo. Returns (ok, message)."""
    e = find(entry_id)
    if e is None:
        return False, "That event isn't in the timeline any more."
    if not e["can_undo"]:
        return False, "That can't be undone (or it already was)."
    argv = list(e["undo"])
    if e["source"] == "system":
        argv = ["pkexec", *argv]  # the system's own changes go back through the password prompt
    r = runner(argv, capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "it didn't work").strip().splitlines()[-1]
    emit("undo", f"Undid: {e['title']}", app="Timeline", data={"target": e["id"]},
         system=e["source"] == "system" and os.geteuid() == 0)
    return True, f"Undid: {e['title']}"


def when(ts, now=None):
    """'just now', '5 min ago', 'today 14:02', 'yesterday 09:10', 'Tue 18 Oct'."""
    now = now or _now()
    d = now - ts
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)} min ago"
    t, n = time.localtime(ts), time.localtime(now)
    clock = time.strftime("%H:%M", t)
    if t.tm_yday == n.tm_yday and t.tm_year == n.tm_year:
        return f"today {clock}"
    if d < 2 * 86400 and (n.tm_yday - t.tm_yday) % 366 == 1:
        return f"yesterday {clock}"
    return time.strftime("%a %d %b", t)


def last_pre_snapshot(run=subprocess.run):
    """The newest 'before' snapshot snap-pac took (what `deckos undo N` goes back to), or None."""
    try:
        r = run(["snapper", "--jsonout", "-c", "root", "list"], capture_output=True, text=True, timeout=20)
        snaps = json.loads(r.stdout).get("root", [])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    pres = [s["number"] for s in snaps if s.get("type") == "pre"]
    return max(pres) if pres else None


def pacman_event(operation, targets, version="", pre=None):
    """(kind, title, detail, undo) for a pacman transaction (the hooks in /usr/share/libalpm/hooks)."""
    names = sorted({t.strip() for t in targets if t.strip()})
    n = len(names)
    shown = ", ".join(names[:3]) + (f" and {n - 3} more" if n > 3 else "")
    if operation == "upgrade":
        kind = "update"
        title = (f"Updated to DecKoOS {version}" if "deckos-settings" in names and version else
                 f"Updated {n} package{'s' if n != 1 else ''}")
    elif operation == "remove":
        kind, title = "remove", f"Removed {shown}"
    else:
        kind, title = "install", f"Installed {shown}"
    undo = ["deckos", "undo", str(pre)] if pre else None
    return kind, title, shown if operation == "upgrade" else "", undo


def main(argv):
    if argv[:1] == ["pacman"] and len(argv) > 1:  # a pacman hook: targets on stdin, run as root
        try:
            version = Path("/usr/share/deckos/version").read_text().strip()
        except OSError:
            version = ""
        kind, title, detail, undo_argv = pacman_event(argv[1], sys.stdin.read().split(), version, last_pre_snapshot())
        emit(kind, title, detail, app="pacman", undo=undo_argv, system=True)
        return 0
    if not argv or argv[0] not in ("emit", "list", "undo"):
        print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
        return 2
    if argv[0] == "emit":
        if len(argv) < 3:
            print("usage: pulse.py emit KIND TITLE [--detail T] [--app A] [--undo deckos ...]", file=sys.stderr)
            return 2
        kind, title, rest = argv[1], argv[2], argv[3:]
        opts, undo_argv = {}, None
        while rest:
            if rest[0] == "--undo":
                undo_argv = rest[1:]
                break
            if rest[0] in ("--detail", "--app") and len(rest) > 1:
                opts[rest[0][2:]] = rest[1]
                rest = rest[2:]
            else:
                rest = rest[1:]
        try:
            emit(kind, title, undo=undo_argv, **opts)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        return 0
    if argv[0] == "list":
        limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv[:-1] else 30
        rows = entries(limit)
        if "--json" in argv:
            print(json.dumps(rows, ensure_ascii=False))
        else:
            for e in rows:
                mark = " (undone)" if e["undone"] else (f"  [undo: {shlex.join(e['undo'])}]" if e["can_undo"] else "")
                print(f"{when(e['time']):>16}  {e['id']}  {e['title']}{mark}")
        return 0
    ok, msg = undo(argv[1]) if len(argv) > 1 else (False, "usage: pulse.py undo ID")
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
