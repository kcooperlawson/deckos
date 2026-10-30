"""DecKoOS Made for you: the PC getting better at being yours, from what it already keeps about how you use it.

It collects nothing new and sends nothing anywhere. It reads, on this PC, what's already here: KDE's app usage
(kactivitymanagerd's scores: which apps you open, how often, when last), Steam's own records (your games, their size,
when you last played and for how long) and DecKoOS's timeline (when you play). From those it says what it has noticed
(so you can see exactly what it knows) and suggests small changes, each one yours to take or leave:

  pin     an app you open a lot that isn't on the taskbar
  unpin   a pinned app you haven't opened in a month
  space   a big game you haven't played in months: uninstalling it frees that much (Steam can reinstall it)

The only thing it keeps is which suggestions you said no to (~/.local/state/deckos/learn.json), so they don't come
back; `forget` clears that. `deckos learn off` turns it all off. No Qt; tests/test_learn.py checks it.

    learn.py [noticed|suggest|dismiss KEY|forget]       JSON for noticed and suggest
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(LIB / "pulse"), str(LIB / "gamedoctor"), str(LIB / "shelf")]

STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "deckos/learn.json"
CONF = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "deckos/learn.conf"
USAGE = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "kactivitymanagerd/resources/database"
DAY = 86400
PIN_SCORE = 5.0      # kactivitymanagerd's score (it decays): an app opened most days
UNUSED_DAYS = 30     # a pin not opened for this long
GAME_GB = 15         # a game this big
GAME_IDLE_DAYS = 120  # not played for this long


def enabled(conf=None):
    try:
        return "on=no" not in Path(conf or CONF).read_text()
    except OSError:
        return True


def dismissed(state=None):
    try:
        return set(json.loads(Path(state or STATE).read_text()).get("dismissed", []))
    except (OSError, ValueError):
        return set()


def dismiss(key, state=None):
    path = Path(state or STATE)
    keys = dismissed(path) | {key}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"dismissed": sorted(keys)}))


def forget(state=None):
    Path(state or STATE).unlink(missing_ok=True)


# ------------------------------------------------------------------ what's already on the PC

def app_usage(db=None):
    """{app id (NAME.desktop): (score, last used epoch)} and since when KDE has been counting (epoch, 0 if unknown)."""
    try:
        con = sqlite3.connect(f"file:{db or USAGE}?mode=ro", uri=True, timeout=2)
        rows = con.execute("SELECT targettedResource, cachedScore, lastUpdate, firstUpdate FROM ResourceScoreCache "
                           "WHERE targettedResource LIKE 'applications:%'").fetchall()
        con.close()
    except sqlite3.Error:
        return {}, 0
    apps = {}
    for res, score, last, _first in rows:
        app = res.split(":", 1)[1]
        was = apps.get(app, (0.0, 0))
        apps[app] = (max(was[0], score or 0.0), max(was[1], last or 0))
    return apps, min((r[3] for r in rows if r[3]), default=0)


def pins():
    """The taskbar's pinned apps as NAME.desktop (`deckos taskbar pins`)."""
    try:
        out = subprocess.run(["deckos", "taskbar", "pins"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.split(":", 1)[1] for line in out.splitlines() if line.startswith("applications:")]


def app_name(app):
    """An app's name from its .desktop file, else its id without the dots."""
    for d in [Path(p) / "applications" for p in
              [os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share",
               *(os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"),
               "/var/lib/flatpak/exports/share", Path.home() / ".local/share/flatpak/exports/share"]]:
        try:
            for line in (d / app).read_text(errors="replace").splitlines():
                if line.startswith("Name="):
                    return line[5:].strip()
        except OSError:
            continue
    return app.removesuffix(".desktop").split(".")[-1].replace("-", " ").title()


def steam_games():
    """[{appid, name, bytes, last, minutes}] for installed Steam games (not tools and runtimes)."""
    try:
        import steamfiles as sf
        import shelf
    except ImportError:
        return []
    played = shelf.steam_played()
    out = []
    for lib in sf.libraries():
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                st = sf.read(acf).get("AppState", {})
            except (OSError, ValueError):
                continue
            name, appid = st.get("name", ""), str(st.get("appid", ""))
            if not appid or any(w in name for w in ("Proton", "Steam Linux Runtime", "Steamworks", "Redistributable")):
                continue
            last, mins = played.get(appid, (0, 0))
            out.append({"appid": appid, "name": name, "bytes": int(st.get("SizeOnDisk") or 0), "last": last,
                        "minutes": mins, "installed": acf.stat().st_mtime})
    return out


def play_hours(now=None, days=30):
    """{hour of day: game sessions started then} over the last `days`, from the timeline."""
    try:
        import pulse
        entries = pulse.entries(5000)
    except Exception:
        return {}
    since = (now or time.time()) - days * DAY
    hours = {}
    for e in entries:
        if e.get("kind") == "game-start" and e.get("time", 0) >= since:
            h = time.localtime(e["time"]).tm_hour
            hours[h] = hours.get(h, 0) + 1
    return hours


# ------------------------------------------------------------------ what it makes of it

def window(hours):
    """The stretch of the day you usually play, as (start hour, end hour), from session start times; None if too few."""
    if sum(hours.values()) < 3:
        return None
    best, best_n = None, -1
    for start in range(24):  # the busiest four hours (wrapping past midnight)
        n = sum(hours.get((start + i) % 24, 0) for i in range(4))
        if n > best_n:
            best, best_n = start, n
    return best, (best + 4) % 24


def hour_text(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def noticed(apps, games, hours, now=None):
    """What it has noticed, in plain words: shown so you can see everything it knows."""
    now = now or time.time()
    out = []
    top = sorted(apps.items(), key=lambda kv: kv[1][0], reverse=True)[:3]
    if top:
        out.append({"icon": "grid", "text": "Your most-used apps: " + ", ".join(app_name(a) for a, _ in top)})
    w = window(hours)
    if w:
        out.append({"icon": "gaming", "text": f"You usually play between {hour_text(w[0])} and {hour_text(w[1])}"})
    played = [g for g in games if g["minutes"]]
    if played:
        g = max(played, key=lambda g: g["minutes"])
        out.append({"icon": "star", "text": f"Your most-played game: {g['name']} ({g['minutes'] // 60} h)"})
    return out


def suggestions(apps, since, pinned, games, now=None, no=None):
    """[{key, kind, title, detail, run}] newest-first-worth-doing, without the ones you said no to."""
    now, no = now or time.time(), no or set()
    out = []
    for app, (score, _last) in sorted(apps.items(), key=lambda kv: kv[1][0], reverse=True):
        if score >= PIN_SCORE and app not in pinned and len([s for s in out if s["kind"] == "pin"]) < 2:
            out.append({"key": f"pin:{app}", "kind": "pin", "icon": "plus", "title": f"Pin {app_name(app)} to the taskbar",
                        "detail": "You open it most days, and it isn't on the taskbar.",
                        "run": ["deckos", "taskbar", "pin", app]})
    if since and now - since > UNUSED_DAYS * DAY:  # only once KDE has been counting long enough to know
        for app in pinned:
            last = apps.get(app, (0, 0))[1]
            if now - last > UNUSED_DAYS * DAY:
                out.append({"key": f"unpin:{app}", "kind": "unpin", "icon": "close",
                            "title": f"Take {app_name(app)} off the taskbar",
                            "detail": f"Pinned, but not opened in {UNUSED_DAYS} days or more.",
                            "run": ["deckos", "taskbar", "unpin", app]})
    for g in sorted(games, key=lambda g: g["bytes"], reverse=True):
        since_played = now - (g["last"] or g["installed"])
        if g["bytes"] >= GAME_GB * 1024 ** 3 and since_played > GAME_IDLE_DAYS * DAY:
            months = int(since_played // (30 * DAY))
            out.append({"key": f"space:{g['appid']}", "kind": "space", "icon": "drives",
                        "title": f"Free {g['bytes'] / 1024 ** 3:.0f} GB: uninstall {g['name']}",
                        "detail": (f"Last played {months} months ago." if g["last"] else
                                   f"Installed {months} months ago and not played.") + " Steam can reinstall it any time.",
                        "run": ["steam", f"steam://uninstall/{g['appid']}"]})
    return [s for s in out if s["key"] not in no]


def main(argv):
    cmd = argv[0] if argv else "suggest"
    if cmd == "dismiss" and len(argv) > 1:
        dismiss(argv[1])
        return 0
    if cmd == "forget":
        forget()
        return 0
    if not enabled():
        print("[]")
        return 0
    apps, since = app_usage()
    games = steam_games()
    if cmd == "noticed":
        print(json.dumps(noticed(apps, games, play_hours())))
        return 0
    if cmd == "suggest":
        print(json.dumps(suggestions(apps, since, pins(), games, no=dismissed())))
        return 0
    print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
