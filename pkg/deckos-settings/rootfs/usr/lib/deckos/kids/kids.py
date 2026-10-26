"""Kid mode: each child gets their own account (no password, no admin rights), a desktop of big tiles with only
the apps a parent approved, a family-filtered Firefox and, if the parent sets one, a daily time limit or bedtime.
The parent's session stays locked underneath: Linux keeps accounts apart, so a child can't touch the parent's
files, apps or settings.

Settings per child are in /etc/deckos/kids/NAME.conf (root-owned: a child can't change their own limits). Root
work (accounts, settings) goes through `deckos kids`, which calls this file. No Qt.

    kids.py list [--json] | show NAME | apps | seed NAME | used NAME | check NAME
"""
import json
import os
import re
import sys
import time
from pathlib import Path

CONF = Path(os.environ.get("DECKOS_KIDS_DIR") or "/etc/deckos/kids")
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

DEFAULTS = {"display": "", "apps": "", "minutes": "0", "bedtime": "", "web": "filtered"}


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


def approved(name, apps=None):
    """The child's tiles: the approved ids that are installed, in the parent's order. No web tile when the
    parent turned the web off."""
    conf = read_conf(name) or DEFAULTS
    apps = installed_apps() if apps is None else apps
    ids = [i for i in conf["apps"].split(",") if i and not (i == "deckos-kids-browser" and conf["web"] == "off")]
    return [apps[i] for i in ids if i in apps]


def suggested(apps=None):
    apps = installed_apps() if apps is None else apps
    return [i for i in SUGGESTED if i in apps]


# ------------------------------------------------------------------ time

def state_file(name):
    return Path.home() / ".local/state/deckos/kids-time.json"


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


# ------------------------------------------------------------------ the child's home

KIOSK = """# Kid mode (DecKoOS): no terminal, no running commands, nothing that changes the system
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
