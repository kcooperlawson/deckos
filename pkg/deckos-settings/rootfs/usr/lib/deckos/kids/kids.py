"""Kid mode: each child gets their own account (no password, no admin rights), a desktop of big tiles with only
the apps a parent approved, a family-filtered Firefox and, if the parent sets one, a daily time limit or bedtime.
The parent's session stays locked underneath: Linux keeps accounts apart, so a child can't touch the parent's
files, apps or settings.

Settings per child are in /etc/deckos/kids/NAME.conf (root-owned: a child can't change their own limits). Root
work (accounts, settings) goes through `deckos kids`, which calls this file. No Qt.

    kids.py list [--json] | show NAME | apps | seed NAME HOME | check NAME | watch
"""
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

CONF = Path(os.environ.get("DECKOS_KIDS_DIR") or "/etc/deckos/kids")
# Minutes used per child and day: written by the root service (deckos-kids-time), read by the child's launcher
STATE = Path(os.environ.get("DECKOS_KIDS_STATE") or "/var/lib/deckos/kids")
# Retro games a parent shared (Hub > System > Kids > Games): copies, since a child can't read the parent's home
GAMES = Path(os.environ.get("DECKOS_KIDS_GAMES") or "/srv/deckos-kids/games")
GRACE = 1.0  # minutes between "time's up" and the session ending, to save a drawing
APPS_DIRS = [Path(p) for p in os.environ.get("DECKOS_APPS_DIRS", "/usr/share/applications:/var/lib/flatpak/exports/share"
                                             "/applications").split(":")]
GROUP = "deckos-kids"
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
# Filtered DNS over HTTPS for the child's Firefox: CleanBrowsing's free family filter (adult sites, proxies and
# mixed-content search blocked; safe search forced).
FAMILY_DOH = "https://doh.cleanbrowsing.org/doh/family-filter/"

# Approved by default when installed: made for children, offline, nothing to buy
SUGGESTED = ["org.kde.kolourpaint", "tuxpaint", "org.kde.gcompris", "org.kde.ktuberling", "org.kde.kblocks",
             "org.kde.kpat", "org.kde.blinken", "org.kde.klettres", "org.kde.kgeography", "supertux", "supertuxkart",
             "deckos-kids-browser"]

DEFAULTS = {"display": "", "apps": "", "minutes": "0", "bedtime": "", "web": "filtered", "games": "on", "volume": "100",
            "theme": "space", "builtin": "on"}  # theme: kids_themes.THEMES; builtin: DecKoOS's own games on the home

# Hub > Kids > Limits presets: (minutes a day, bedtime, max volume %)
PRESETS = {"4–6": (45, "19:00", 60), "7–9": (60, "19:30", 70), "10+": (90, "20:30", 80)}


def valid_name(name):
    return bool(NAME_RE.match(name or "")) and name not in ("root", "deckos")


def read_conf(name):
    conf = dict(DEFAULTS)
    try:
        for line in (CONF / f"{name}.conf").read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() in conf:
                conf[k.strip()] = v.strip()
    except OSError:
        return None
    return conf


def write_conf(name, conf):
    CONF.mkdir(parents=True, exist_ok=True)
    text = "# Kid mode settings (DecKoOS Hub > System > Kids, or deckos kids)\n"
    text += "".join(f"{k}={conf.get(k, v)}\n" for k, v in DEFAULTS.items())
    (CONF / f"{name}.conf").write_text(text)


def kids():
    """Every child set up for Kid mode, in name order."""
    out = []
    for f in sorted(CONF.glob("*.conf")):
        conf = read_conf(f.stem)
        if conf is not None and valid_name(f.stem):
            out.append({"name": f.stem, **conf})
    return out


def desktop_entry(path):
    """Name, icon and exec of a .desktop file, or None for one that isn't an app to show."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    m = re.search(r"^\[Desktop Entry\]\n((?:[^\[].*\n?)*)", text, re.M)
    if not m:
        return None
    body = m.group(1)

    def key(k):
        hit = re.search(rf"^{k}=(.*)$", body, re.M)
        return hit.group(1).strip() if hit else ""
    if key("Type") != "Application" or key("NoDisplay").lower() == "true" or not key("Exec"):
        return None
    return {"id": path.name.removesuffix(".desktop"), "name": key("Name"), "icon": key("Icon"),
            "exec": re.sub(r"\s*%[fFuUdDnNickvm]", "", key("Exec")), "comment": key("Comment")}


def installed_apps():
    """Every app that could be approved, by desktop id (first directory wins, like the menu)."""
    apps = {}
    for d in APPS_DIRS:
        for f in sorted(d.glob("*.desktop")) if d.is_dir() else []:
            e = desktop_entry(f)
            if e and e["id"] not in apps:
                apps[e["id"]] = e
    # The web, as a tile: Firefox in the child's own profile (the family filter is set there, see seed())
    if "firefox" in apps:
        apps["deckos-kids-browser"] = {"id": "deckos-kids-browser", "name": "The web", "icon": "firefox",
                                       "exec": "firefox", "comment": "Websites, with the family filter"}
    return apps


def _retro():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "retro"))
    import retro
    return retro


def shared_games(root=None):
    """The shared retro games as tiles: each starts its emulator straight into the game (no menus)."""
    root = Path(root or GAMES)
    if not root.is_dir():
        return []
    try:
        retro = _retro()
        games = retro.scan([root])
    except Exception:  # a broken game file mustn't take the child's whole desktop with it
        return []
    return [{"id": f"game:{g.path.relative_to(root)}", "name": g.title, "icon": "applications-games",
             "argv": retro.command(g), "exec": "", "comment": retro.BY_ID[g.system].name} for g in games]


def sync_games(paths, root=None):
    """Makes the shared folder hold exactly these games (paths of games in a parent's Retro library), copying
    each game's files into a folder per console. Run as root by `deckos kids games`."""
    import shutil
    retro = _retro()
    root = Path(root or GAMES)
    wanted = {}
    for p in paths:
        p = Path(p)
        for g in retro.scan([p.parent]):
            if g.path == p:
                folder = root / retro.BY_ID[g.system].folders[0]
                for f in g.files:
                    wanted[folder / Path(f).name] = Path(f)
    root.mkdir(parents=True, exist_ok=True)
    for dest, src in wanted.items():
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    for f in [f for f in root.rglob("*") if f.is_file() and f not in wanted]:
        f.unlink()
    for d in sorted((d for d in root.rglob("*") if d.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    return len(wanted)


def approved(name, apps=None):
    """The child's tiles: the approved ids that are installed, in the parent's order. No web tile when the
    parent turned the web off."""
    conf = read_conf(name) or DEFAULTS
    apps = installed_apps() if apps is None else apps
    ids = [i for i in conf["apps"].split(",") if i and not (i == "deckos-kids-browser" and conf["web"] == "off")]
    tiles = [apps[i] for i in ids if i in apps]
    return tiles + (shared_games() if conf.get("games", "on") != "off" else [])


def suggested(apps=None):
    apps = installed_apps() if apps is None else apps
    return [i for i in SUGGESTED if i in apps]


# ------------------------------------------------------------------ the child's desktop

MARK = "X-DeckOS-Kids=true"  # entries Kid mode wrote, so it only ever removes its own
GAMES_ENTRY = "deckos-kids-games"


def quote_exec(argv):
    """argv as a desktop entry's Exec, quoted the desktop-entry way, so paths with spaces work."""
    def q(a):
        return a if re.fullmatch(r"[A-Za-z0-9_./:=+-]+", a) else '"' + re.sub(r'(["`$\\])', r"\\\1", a) + '"'
    return " ".join(q(a) for a in argv)


def entry_text(name, icon, exec_line, comment=""):
    """A launcher for one of the child's tiles."""
    return ("[Desktop Entry]\nType=Application\n" f"Name={name}\n" f"Icon={icon or 'applications-games'}\n"
            f"Exec={exec_line}\n" + (f"Comment={comment}\n" if comment else "") +
            "Categories=Game;\n" f"{MARK}\n")


def desktop_entries(tiles, games_on=True):
    """{file name: entry} for the child's desktop and taskbar: their games first, then each approved tile."""
    out = {}
    if games_on:
        out[f"{GAMES_ENTRY}.desktop"] = entry_text("My games", "applications-games", "deckos-kids --games",
                                                   "Bubble pop, Memory match and your apps")
    for t in tiles:
        # An app's own Exec as it is, without its file placeholders (%U, %f…); a game's command quoted
        line = quote_exec(t["argv"]) if t.get("argv") else re.sub(r"\s*%[a-zA-Z]", "", t.get("exec") or "").strip()
        if not line:
            continue
        slug = re.sub(r"[^A-Za-z0-9]+", "-", t["id"]).strip("-").lower()
        out[f"deckos-kid-{slug}.desktop"] = entry_text(t["name"], t.get("icon"), line, t.get("comment", ""))
    return out


def sync_desktop(home, entries):
    """Writes the entries to the child's desktop and app list, takes away Kid mode's own that are gone (an app the
    parent removed); the child's other files stay. Returns the taskbar pins, in order."""
    places = [Path(home) / "Desktop", Path(home) / ".local/share/applications"]
    for d in places:
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.desktop"):
            if f.name not in entries:
                try:
                    if MARK in f.read_text(errors="replace"):
                        f.unlink()
                except OSError:
                    pass
        for fname, text in entries.items():
            f = d / fname
            try:
                if not f.exists() or f.read_text() != text:
                    f.write_text(text)
                f.chmod(0o755)  # a launcher on the desktop starts without asking only when it's executable
            except OSError:
                pass
    return [f"applications:{fname}" for fname in entries]


# ------------------------------------------------------------------ the child's Plasma layout, written before Plasma starts
#
# A child's desktop is locked (KIOSK: no editing panels), and that lock also stops Plasma's scripting, so Kid mode
# can't change a running desktop: their panels were left as Plasma first made them, with the full DecKoOS panel and
# its menu. Instead deckos-kids-prepare.service writes the whole layout at each login, before plasmashell reads it:
# one kid panel (their apps pinned, the time left, volume, the clock) and their theme on every screen's desktop.

KID_PANEL = ["org.deckos.taskbar", "org.deckos.kidtime", "org.kde.plasma.volume", "org.kde.plasma.digitalclock"]
SCREENS = 4  # desktops written for screens 0..3; Plasma makes any further ones itself


def activity_id(home):
    """The child's Plasma activity (desktops belong to one), made and saved when they have none yet."""
    rc = Path(home) / ".config/kactivitymanagerdrc"
    try:
        m = re.search(r"^\[activities\]\n([0-9a-f-]{36})=", rc.read_text(), re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    import uuid
    act = str(uuid.uuid4())
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text(f"[activities]\n{act}=Default\n\n[main]\ncurrentActivity={act}\n")
    return act


def plasma_layout(pins, wallpaper, activity, screens=SCREENS):
    """plasma-org.kde.plasma.desktop-appletsrc for a child: the kid panel on the first screen, and a desktop on
    each screen with their theme and big icons. Containments are locked (immutability=2)."""
    out = ["[Containments][1]", "activityId=", "formfactor=2", "immutability=2", "lastScreen=0", "location=4",
           "plugin=org.kde.panel", "wallpaperplugin=org.kde.image", ""]
    for n, plugin in enumerate(KID_PANEL, start=2):
        out += [f"[Containments][1][Applets][{n}]", "immutability=2", f"plugin={plugin}", ""]
    out += ["[Containments][1][Applets][2][Configuration][General]", "launchers=" + ",".join(pins), "lockedPins=true",
            "showLabels=false", "",
            f"[Containments][1][Applets][{1 + len(KID_PANEL)}][Configuration][Appearance]", "showDate=false", "",
            "[Containments][1][General]", "AppletOrder=" + ";".join(str(n) for n in range(2, 2 + len(KID_PANEL))), ""]
    for s in range(screens):
        c = 20 + s
        out += [f"[Containments][{c}]", f"activityId={activity}", "formfactor=0", "immutability=2", f"lastScreen={s}",
                "location=0", "plugin=org.kde.plasma.folder", "wallpaperplugin=org.kde.image", "",
                f"[Containments][{c}][General]", "iconSize=5", "",
                f"[Containments][{c}][Wallpaper][org.kde.image][General]", f"Image=file://{wallpaper}", ""]
    return "\n".join(out)


def panel_view(old=""):
    """plasmashellrc with the kid panel's size and place (centred, floating, as wide as its icons); the file's
    other groups are kept."""
    keep = re.sub(r"(?ms)^\[PlasmaViews\].*?(?=^\[(?!PlasmaViews)|\Z)", "", old).strip()
    ours = ("[PlasmaViews][Panel 1]\nalignment=132\nfloating=1\npanelLengthMode=1\n\n"
            "[PlasmaViews][Panel 1][Defaults]\nthickness=56\n")
    return (keep + "\n\n" if keep else "") + ours


def write_plasma(home, pins, wallpaper):
    """Writes the child's Plasma layout (before plasmashell starts). The first time, what was there is kept as
    .deckos-bak."""
    cfg = Path(home) / ".config"
    cfg.mkdir(parents=True, exist_ok=True)
    applets = cfg / "plasma-org.kde.plasma.desktop-appletsrc"
    if applets.exists() and not applets.with_name(applets.name + ".deckos-bak").exists():
        applets.with_name(applets.name + ".deckos-bak").write_bytes(applets.read_bytes())
    applets.write_text(plasma_layout(pins, wallpaper, activity_id(home)))
    shellrc = cfg / "plasmashellrc"
    shellrc.write_text(panel_view(shellrc.read_text() if shellrc.exists() else ""))


# ------------------------------------------------------------------ time

def state_file(name):
    return STATE / f"{name}.json"


def minutes_used(path, today=None):
    today = today or time.strftime("%Y-%m-%d")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return 0.0
    return float(data.get(today, 0)) if isinstance(data, dict) else 0.0


def add_minutes(path, minutes, today=None):
    today = today or time.strftime("%Y-%m-%d")
    try:
        data = json.loads(path.read_text())
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    data = {k: v for k, v in data.items() if k >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))}
    data[today] = round(float(data.get(today, 0)) + minutes, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def week(name, today=None):
    """[(day, minutes)] for the last 7 days, oldest first (the time service's count; 0 for days without any)."""
    today = today or time.time()
    days = [time.strftime("%Y-%m-%d", time.localtime(today - n * 86400)) for n in range(6, -1, -1)]
    f = state_file(name)
    return [(d, minutes_used(f, today=d)) for d in days]


def fmt_minutes(m):
    m = int(round(m))
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def time_left(conf, used, now=None):
    """Minutes left today (None when there's no limit at all): the daily limit and bedtime, whichever is sooner."""
    now = now or time.localtime()
    left = None
    limit = int(conf.get("minutes") or 0)
    if limit > 0:
        left = max(0.0, limit - used)
    bed = conf.get("bedtime") or ""
    m = re.match(r"^(\d{1,2}):(\d{2})$", bed)
    if m:
        bed_min = int(m.group(1)) * 60 + int(m.group(2))
        now_min = now.tm_hour * 60 + now.tm_min
        # Before 5 in the morning still counts as after bedtime
        until = 0.0 if now_min >= bed_min or now_min < 5 * 60 else float(bed_min - now_min)
        left = until if left is None else min(left, until)
    return left


def active_children(run=None):
    """Children whose session is the one on screen now (switched away or locked doesn't count)."""
    import subprocess
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout)
    names = {k["name"] for k in kids()}
    out = set()
    for line in run(["loginctl", "list-sessions", "--no-legend"]).splitlines():
        cols = line.split()
        if len(cols) >= 3 and cols[2] in names:
            props = run(["loginctl", "show-session", cols[0], "-p", "Active", "-p", "Type", "-p", "LockedHint"])
            if "Active=yes" in props and "LockedHint=yes" not in props and re.search(r"Type=(wayland|x11)", props):
                out.add(cols[2])
    return out


def step(minutes=1.0, now=None, run=None, end=None):
    """One minute of the time service: count it for children on screen, end the sessions whose time is up.
    `end(name)` logs a child out (loginctl terminate-user); returns what it did, for the log and tests."""
    import subprocess
    end = end or (lambda n: subprocess.run(["loginctl", "terminate-user", n], timeout=30))
    done = []
    for name in sorted(active_children(run)):
        conf = read_conf(name)
        f = state_file(name)
        add_minutes(f, minutes)
        left = time_left(conf, minutes_used(f), now)
        if left is not None and left <= 0:
            # Time's up: the child sees it, and after the grace minute(s) on screen the session ends
            today = time.strftime("%Y-%m-%d", now) if now else None
            key = f"{today or time.strftime('%Y-%m-%d')}:over"
            add_minutes(f, minutes, today=key)
            if minutes_used(f, today=key) > GRACE:
                end(name)
                done.append(f"{name}: time's up, logged out")
                continue
        if left is not None:
            done.append(f"{name}: {left:.0f} min left")
    return done


def watch():
    """The time service (deckos-kids-time.service, as root): once a minute, while there are children set up."""
    while True:
        time.sleep(60)
        if kids():
            for line in step():
                print(line, flush=True)


# ------------------------------------------------------------------ the child's home

KIOSK = """# Kid mode (DecKoOS): no terminal, no running commands, nothing that changes the system
[KDE]
LookAndFeelPackage=org.deckos.kids

[KDE Action Restrictions][$i]
shell_access=false
run_command=false
action/run_command=false
action/options_configure=false
lock_screen=false
logout=true
plasma/allow_configure_when_locked=false
plasma-desktop/add_activities=false
plasma/plasmashell/unlockedDesktop=false

[KDE Control Module Restrictions][$i]
kcm_users.desktop=false
kcm_kscreen.desktop=false
kcm_sddm.desktop=false
"""


def firefox_prefs(web):
    lines = ['// Kid mode (DecKoOS): set by the parent', 'user_pref("browser.shell.checkDefaultBrowser", false);',
             'user_pref("datareporting.policy.dataSubmissionEnabled", false);',
             'user_pref("browser.aboutConfig.showWarning", true);']
    if web == "filtered":
        # Firefox resolves every name through the family filter; mode 3 means never around it
        lines += [f'user_pref("network.trr.uri", "{FAMILY_DOH}");', 'user_pref("network.trr.mode", 3);',
                  f'user_pref("network.trr.custom_uri", "{FAMILY_DOH}");']
    return "\n".join(lines) + "\n"


def seed(home, name, web="filtered"):
    """Writes the child's desktop settings into their home (as root, from `deckos kids add`; chowned after)."""
    cfg = home / ".config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "kdeglobals").write_text(KIOSK)
    # The logout screen offers only logging out (polkit refuses the rest for children anyway)
    (cfg / "ksmserverrc").write_text("[General]\nofferShutdown=false\n")
    # The Kid mode desktop: the big-tile launcher at login, a taskbar without a menu, Welcome not shown
    (cfg / "deckos").mkdir(exist_ok=True)
    (cfg / "deckos/welcome-done").touch()
    auto = cfg / "autostart"
    auto.mkdir(exist_ok=True)
    (auto / "deckos-kids.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Kid mode\nExec=deckos-kids --session\nIcon=deckos\n"
        "X-KDE-autostart-phase=2\n")
    profile = home / ".mozilla/firefox/kidmode.default"
    profile.mkdir(parents=True, exist_ok=True)
    (home / ".mozilla/firefox/profiles.ini").write_text(
        "[Profile0]\nName=Kid mode\nIsRelative=1\nPath=kidmode.default\nDefault=1\n\n[General]\nStartWithLastProfile=1\n"
        "Version=2\n")
    (profile / "user.js").write_text(firefox_prefs(web))


def main(argv):
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        rows = kids()
        if "--json" in argv:
            print(json.dumps(rows))
        else:
            for k in rows:
                limit = f"{k['minutes']} min a day" if k["minutes"] != "0" else "no daily limit"
                bed = f", bedtime {k['bedtime']}" if k["bedtime"] else ""
                print(f"  {k['name']:<12} {k['display'] or k['name']}: {len([a for a in k['apps'].split(',') if a])} "
                      f"apps, {limit}{bed}, web {k['web']}")
        return 0
    if cmd == "sync-games":
        print(f"{sync_games(argv[1:])} files shared")
        return 0
    if cmd == "watch":
        watch()
        return 0
    if cmd == "apps":
        print(json.dumps({"installed": installed_apps(), "suggested": suggested()}))
        return 0
    if cmd == "suggested":
        print(",".join(suggested()))
        return 0
    if cmd in ("show", "check", "seed") and len(argv) > 1 and valid_name(argv[1]):
        name = argv[1]
        conf = read_conf(name)
        if conf is None:
            print(f"{name} isn't set up for Kid mode", file=sys.stderr)
            return 1
        if cmd == "show":
            print(json.dumps({"name": name, **conf, "tiles": approved(name)}))
        elif cmd == "seed":
            seed(Path(argv[2]), name, conf["web"])
        else:
            left = time_left(conf, minutes_used(state_file(name)))
            print("unlimited" if left is None else f"{left:.0f}")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
