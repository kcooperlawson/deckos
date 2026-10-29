"""DecKoOS Game Doctor: why a game closed right after starting, and one-click fixes that can be undone.

Steam logs every game launch and exit ("Game process added/removed" in logs/console_log.txt) and the
game's own Proton and Wine output (logs/console-linux.txt). A game that's gone within QUICK seconds
didn't really start: the doctor reads what it printed in that window, matches it against known
problems, and offers the fixes that help with them. Every fix is recorded per game and can be undone.
"""
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import steamfiles as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
try:
    import pulse  # the DecKoOS timeline (absent in an old checkout's tests: then fixes just aren't recorded)
except ImportError:
    pulse = None

QUICK = 45  # seconds: a game gone sooner than this didn't really start
LOGS = sf.STEAM / "logs"
STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "deckos/gamedoctor"
# Where a library on a Windows (NTFS) drive keeps its Proton prefixes instead ("prefix-home")
PREFIXES = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "deckos/proton-prefixes"

EVENT = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Game process (added|removed)\s*: AppID (\d+)")
STAMP = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]")


def stamp(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").timestamp()


# ------------------------------------------------------------------ what happened

def sessions(log=LOGS / "console_log.txt"):
    """[{appid, start, end, seconds}] for every finished launch in Steam's log, oldest first."""
    out, open_ = [], {}
    try:
        lines = Path(log).read_text(errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        m = EVENT.match(line)
        if not m:
            continue
        when, kind, appid = stamp(m.group(1)), m.group(2), m.group(3)
        if kind == "added":
            open_.setdefault(appid, when)
        elif appid in open_:
            start = open_.pop(appid)
            out.append({"appid": appid, "start": start, "end": when, "seconds": when - start})
    return out


def last_failure(appid=None):
    """The most recent quick exit (of one game, or any)."""
    for s in reversed(sessions()):
        if (appid is None or s["appid"] == str(appid)) and s["seconds"] < QUICK:
            return s
    return None


NOISE = re.compile(r"fixme:|ProtonFixes.*(INFO|Skipping)|radv is not a conformant|^\s*$|steamwebhelper|"
                   r"\[(minidump|tid)|cef_|chromium|CAppInfoCache|BuildCompleteAppOverviewChange")


def game_output(start, end, log=LOGS / "console-linux.txt", limit=400):
    """What Steam's console caught between a launch and its exit: the game's Proton/Wine output."""
    out, inside = [], False
    try:
        with open(log, errors="replace") as f:
            for line in f:
                m = STAMP.match(line)
                if m:
                    t = stamp(m.group(1))
                    inside = start - 1 <= t <= end + 3
                if inside and not NOISE.search(line):
                    out.append(line.rstrip())
    except OSError:
        pass
    return out[-limit:]


# ------------------------------------------------------------------ what it means

# (id, pattern, title, explanation, fixes in the order to try them)
RULES = [
    # first: the drive itself, which no Proton setting gets round
    ("ntfs-prefix", r"dosdevices/c:|Errno 22\] Invalid argument.*(compatdata|pfx)",
     "Proton can't set up on this drive",
     "The game is on a Windows (NTFS) drive. Proton builds a small Windows setup for each game (its prefix) next "
     "to it, and that needs names Windows drives refuse, like c:. Keeping the prefixes on your Linux drive fixes "
     "it for every game in that library; the games stay where they are.", ["prefix-home"]),
    ("anticheat", r"EasyAntiCheat|BattlEye|BEService|EAC.*(error|fail)|anti-?cheat",
     "Anti-cheat stopped the game",
     "The game's anti-cheat doesn't allow Linux, or needs its Proton support switched on by the developer. "
     "No setting on this PC changes that; check areweanticheatyet.com for this game.", []),
    ("missing-dll", r"err:module:import_dll.*Library (\S+)|Library (\S+\.dll) .*not found",
     "A Windows library is missing",
     "The game needs a Windows DLL its Proton prefix doesn't have. A fresh prefix, or another Proton "
     "version, usually brings it.", ["proton-other", "prefix-reset"]),
    ("vulkan", r"VK_ERROR_\w+|DXVK: .*(failed|error)|vkd3d.*(err|fail)|vkCreateDevice failed|No Vulkan",
     "The graphics layer failed to start",
     "DXVK or VKD3D (which turn DirectX into Vulkan) couldn't start. The OpenGL path (WineD3D) is slower but "
     "often starts when they don't; another Proton version may carry a fixed DXVK.",
     ["wined3d", "proton-other"]),
    ("crash", r"Unhandled (page fault|exception)|wine: Unhandled|segfault|SIGSEGV|EXCEPTION_ACCESS_VIOLATION",
     "The game crashed while starting",
     "Something in the game or its Proton prefix crashed early. Another Proton version, a clean prefix or "
     "checking the game files fixes most of these.", ["proton-other", "verify", "prefix-reset"]),
    # whole words, and a failure: "esync" is in game names ("Resynced") and "fsync: up and running" is fine
    ("sync", r"\b[ef]sync\b.*\b(fail\w*|error|not supported|unavailable)|\bntsync\b.*\b(fail\w*|error)|"
             r"futex_waitv.*(not supported|ENOSYS)",
     "Proton's sync method misbehaved",
     "Proton's fast synchronisation (NTSync/fsync) didn't work for this game. Turning it off costs a little "
     "speed but often fixes start-up hangs and crashes.", ["no-fsync", "proton-other"]),
    ("dotnet", r"mscoree|mono-?\d|\.NET Framework|clr\.dll",
     "The game needs .NET",
     "It wants Microsoft .NET, which Wine replaces with Mono. A fresh prefix or another Proton version "
     "usually sets that up properly.", ["prefix-reset", "proton-other"]),
    ("memory", r"out of memory|Cannot allocate memory|ERROR_NOT_ENOUGH_MEMORY",
     "It ran out of memory",
     "The game couldn't get the memory it asked for. Closing other apps (or letting workload modes pause "
     "them) helps.", []),
]
FALLBACK = ("unknown", None, "No clear cause in the log",
            "The game didn't say why it closed. These fix most early exits; try them one at a time.",
            ["proton-other", "verify", "prefix-reset"])


def diagnose(lines):
    """Findings, most specific first: {id, title, text, evidence (the lines), fixes}."""
    text = "\n".join(lines)
    found = []
    for rid, pattern, title, explanation, fixes in RULES:
        hits = [l for l in lines if re.search(pattern, l, re.I)]
        if hits:
            found.append({"id": rid, "title": title, "text": explanation, "evidence": hits[-5:], "fixes": fixes})
    if not found:
        rid, _p, title, explanation, fixes = FALLBACK
        found.append({"id": rid, "title": title, "text": explanation, "evidence": [], "fixes": fixes})
    if not text.strip():
        found[0]["text"] += " (Steam's log caught no output from it at all.)"
    return found


# ------------------------------------------------------------------ fixes (each one undoable)

def _state_file(appid):
    return STATE / f"{appid}.json"


def applied(appid):
    try:
        return json.loads(_state_file(appid).read_text())
    except (OSError, ValueError):
        return []


def _record(appid, entry):
    STATE.mkdir(parents=True, exist_ok=True)
    entries = applied(appid) + [dict(entry, when=time.time())]
    _state_file(appid).write_text(json.dumps(entries, indent=1))


def _forget(appid, fix_id):
    entries = [e for e in applied(appid) if e["fix"] != fix_id]
    if entries:
        _state_file(appid).write_text(json.dumps(entries, indent=1))
    else:
        _state_file(appid).unlink(missing_ok=True)


def pretty_tool(name):
    """'proton-cachyos-11.0-20261015 (steam linux runtime)' -> 'Proton-CachyOS 11.0'."""
    m = re.match(r"proton[-_ ]cachyos[-_ ]?(\d+(?:\.\d+)?)", name, re.I)
    if m:
        return f"Proton-CachyOS {m.group(1)}"
    m = re.match(r"GE-Proton[-_ ]?(\S+)", name, re.I)
    if m:
        return f"GE-Proton {m.group(1)}"
    return name


def other_proton(appid):
    """The compatibility tool to try instead of the current one: DecKoOS's Proton-CachyOS, else Experimental."""
    current = sf.compat_tool(appid)
    tools = sf.compat_tools()
    for t in [t for t in tools if "cachyos" in t] + ["proton_experimental"] + list(tools):
        if t and t != current:
            return t, pretty_tool(tools.get(t, "Proton Experimental" if t == "proton_experimental" else t))
    return None, None


def describe_fix(fix, appid):
    """(title, what it does) for the window's button."""
    if fix == "proton-other":
        tool, name = other_proton(appid)
        return (f"Try {name}" if tool else "Try another Proton version",
                "Runs the game with another Proton version. Steam closes and reopens to change it.")
    return {
        "wined3d": ("Use the OpenGL path (WineD3D)", "Adds PROTON_USE_WINED3D=1 to the game's launch options."),
        "no-fsync": ("Turn off fast sync", "Adds PROTON_NO_FSYNC=1 PROTON_NO_NTSYNC=1 to the launch options."),
        "prefix-home": ("Keep Proton's files on your Linux drive",
                        "Moves this library's Proton prefixes to your home drive and links them back; "
                        "the games stay on the Windows drive."),
        "prefix-reset": ("Start the Proton prefix fresh",
                         "Moves the game's Windows folder aside (kept, so this can be undone); Proton makes a "
                         "new one at the next start. Saves stored in Steam Cloud come back by themselves."),
        "verify": ("Check the game files", "Steam checks every file of the game and re-downloads damaged ones."),
    }[fix]


LAUNCH_ENV = {"wined3d": "PROTON_USE_WINED3D=1", "no-fsync": "PROTON_NO_FSYNC=1 PROTON_NO_NTSYNC=1"}


def _remove_launch_env(appid, env):
    """Takes just this fix's variables out, so undoing one fix leaves the others (and yours) alone."""
    words = [w for w in sf.launch_options(appid).split() if w not in env.split()]
    sf.set_launch_options(appid, "" if words == ["%command%"] else " ".join(words))


def _add_launch_env(appid, env):
    options = sf.launch_options(appid)
    if env in options:
        return options
    if "%command%" in options:
        new = f"{env} {options}"
    else:
        new = f"{env} %command% {options}".strip()
    sf.set_launch_options(appid, new)
    return options


def apply(fix, appid, confirm_steam_restart=lambda: True):
    """Applies a fix; returns a sentence for the window. Raises with a reason if it can't. The fix goes in the
    DecKoOS timeline, with an undo unless it's one that can't be (checking files)."""
    done = _apply(fix, appid, confirm_steam_restart)
    if pulse:
        game = (sf.game(appid) or {}).get("name", f"App {appid}")
        title = describe_fix(fix, appid)[0]
        try:
            pulse.emit("gamedoctor", f"{game}: {title}", app="Game Doctor",
                       undo=None if fix == "verify" else ["deckos", "gamedoctor", "undo", str(appid), fix])
        except (OSError, ValueError):
            pass
    return done


def _apply(fix, appid, confirm_steam_restart=lambda: True):
    g = sf.game(appid)
    if fix == "verify":
        sf.start_steam(f"steam://validate/{appid}")
        return "Steam is checking the game files now."
    if fix == "prefix-home":
        if not g:
            raise RuntimeError("this game isn't installed")
        return _prefixes_home(appid, g["compatdata"].parent)
    if fix == "prefix-reset":
        if not g or not g["compatdata"].exists():
            raise RuntimeError("this game has no Proton prefix yet")
        aside = g["compatdata"].with_name(f"{appid}.deckos-{time.strftime('%Y%m%d-%H%M%S')}")
        g["compatdata"].rename(aside)
        _record(appid, {"fix": fix, "aside": str(aside)})
        return "The prefix is set aside; Proton makes a fresh one when the game starts."
    # the rest edit Steam's config files, which Steam overwrites when it closes
    if sf.steam_running():
        if not confirm_steam_restart():
            raise RuntimeError("Steam has to close for this; nothing was changed")
        if not sf.close_steam():
            raise RuntimeError("Steam didn't close; nothing was changed")
        reopen = True
    else:
        reopen = False
    try:
        if fix == "proton-other":
            tool, name = other_proton(appid)
            if not tool:
                raise RuntimeError("no other Proton version is installed")
            before = sf.compat_tool(appid)
            sf.set_compat_tool(appid, tool)
            _record(appid, {"fix": fix, "before": before, "after": tool})
            done = f"{g['name'] if g else 'The game'} now runs with {name}."
        elif fix in LAUNCH_ENV:
            before = _add_launch_env(appid, LAUNCH_ENV[fix])
            _record(appid, {"fix": fix, "before": before})
            done = f"Launch options: {sf.launch_options(appid)}"
        else:
            raise ValueError(f"unknown fix {fix}")
    finally:
        if reopen:
            sf.start_steam()
    return done


def _prefixes_home(appid, compat):
    """A library's compatdata folder moved to PREFIXES (a Linux filesystem) and linked back in its place."""
    if compat.is_symlink():
        raise RuntimeError("this library's Proton files are already on another drive")
    target = PREFIXES / (re.sub(r"[^A-Za-z0-9]+", "-", str(compat.parent.parent)).strip("-") or "library")
    target.mkdir(parents=True, exist_ok=True)
    if compat.exists():
        for child in compat.iterdir():  # a prefix that failed half way is moved too: Proton finishes it there
            shutil.move(str(child), str(target / child.name))
        compat.rmdir()
    compat.symlink_to(target, target_is_directory=True)
    _record(appid, {"fix": "prefix-home", "library": str(compat), "target": str(target)})
    return "This library's Proton files are on your Linux drive now; start the game again."


def _prefixes_back(entry):
    compat, target = Path(entry["library"]), Path(entry["target"])
    if compat.is_symlink():
        compat.unlink()
    compat.mkdir(exist_ok=True)
    for child in target.iterdir():
        shutil.move(str(child), str(compat / child.name))
    target.rmdir()


def undo(fix, appid, confirm_steam_restart=lambda: True):
    entry = next((e for e in reversed(applied(appid)) if e["fix"] == fix), None)
    if entry is None:
        raise RuntimeError("that fix isn't applied")
    if fix == "prefix-home":
        _prefixes_back(entry)
        _forget(appid, fix)
        return "The Proton files are back on the game's drive."
    if fix == "prefix-reset":
        g = sf.game(appid)
        aside = Path(entry["aside"])
        if g and g["compatdata"].exists():  # the fresh one Proton made, set aside in turn
            g["compatdata"].rename(g["compatdata"].with_name(f"{appid}.deckos-fresh-{time.strftime('%Y%m%d-%H%M%S')}"))
        aside.rename(g["compatdata"] if g else aside.with_name(str(appid)))
        _forget(appid, fix)
        return "The old prefix is back."
    if sf.steam_running():
        if not confirm_steam_restart():
            raise RuntimeError("Steam has to close for this; nothing was changed")
        if not sf.close_steam():
            raise RuntimeError("Steam didn't close; nothing was changed")
        reopen = True
    else:
        reopen = False
    try:
        if fix == "proton-other":
            sf.set_compat_tool(appid, entry.get("before", ""))
        else:
            _remove_launch_env(appid, LAUNCH_ENV[fix])
    finally:
        if reopen:
            sf.start_steam()
    _forget(appid, fix)
    return "Undone."


def cleanup_old_prefixes(appid, keep_days=30):
    """Prefixes set aside more than keep_days ago, removed once the game has run fine since."""
    g = sf.game(appid)
    if not g:
        return
    for d in g["compatdata"].parent.glob(f"{appid}.deckos-*"):
        if time.time() - d.stat().st_mtime > keep_days * 86400:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    # The timeline's Undo: gamedoctor.py undo APPID FIX (through `deckos gamedoctor undo`)
    if len(sys.argv) == 4 and sys.argv[1] == "undo":
        try:
            print(undo(sys.argv[3], sys.argv[2]))
        except (OSError, RuntimeError, ValueError) as e:
            sys.exit(str(e))
        sys.exit(0)
    sys.exit("usage: gamedoctor.py undo APPID FIX")
