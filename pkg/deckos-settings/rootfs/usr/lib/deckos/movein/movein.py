"""DeckOS Move In: what a Windows install on this PC has that's worth bringing over, and bringing it.

Plain Python, no Qt (deckos_movein.py is the window). Windows is only ever read: nothing on its drives
is changed. On the Linux side every file changed keeps a NAME.deckos-bak first, and what was done is
recorded in ~/.local/state/deckos/movein.json.

scan() finds Windows system drives (Users/ and Windows/) and other NTFS drives among the mounted ones
(DECKOS_MOVEIN_ROOTS=a:b instead, for tests), and returns Items: the folders as sidebar places, the
wallpaper, Firefox profiles, Edge/Chrome bookmarks, Steam libraries, other launchers' games, apps with
a Linux equivalent, user fonts, and what can't come (Wi-Fi passwords). apply() does the chosen ones.
"""
import configparser
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gamedoctor"))
import steamfiles  # noqa: E402  (KeyValues read/write, Steam's own way)

HOME = Path.home()
STATE = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local/state") / "deckos/movein.json"
PLACES = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share") / "user-places.xbel"
FIREFOX = HOME / ".mozilla/firefox"
# Steam's own tools, listed among the games in a library
NOT_GAMES = re.compile(r"^(Steamworks |Steam Linux Runtime|Proton |Steam Controller|SteamVR|Driver Booster)", re.I)
NOT_USERS = {"public", "default", "default user", "all users", "defaultapppool", "wdagutilityaccount"}
FOLDERS = [("Documents", "folder-documents"), ("Pictures", "folder-pictures"), ("Music", "folder-music"),
           ("Videos", "folder-videos"), ("Downloads", "folder-downloads"), ("Desktop", "user-desktop"),
           ("OneDrive", "folder-cloud")]

# Start Menu name (lowercase, a substring) -> (what to get on DeckOS, Store search, command if installed)
APPS = [
    ("discord", "Discord", "discord", "discord"),
    ("spotify", "Spotify", "spotify", "spotify"),
    ("obs studio", "OBS Studio", "obs", "obs"),
    ("vlc", "VLC", "vlc", "vlc"),
    ("gimp", "GIMP", "gimp", "gimp"),
    ("visual studio code", "Visual Studio Code", "visual studio code", "code"),
    ("visual studio 20", "VS Code or JetBrains Rider (Visual Studio has no Linux version)", "visual studio code", "code"),
    ("google chrome", "Google Chrome", "chrome", "google-chrome-stable"),
    ("notepad++", "Kate (DeckOS's text editor)", "kate", "kate"),
    ("winrar", "Ark (opens RAR, ZIP and 7z; already installed)", "ark", "ark"),
    ("7-zip", "Ark (opens RAR, ZIP and 7z; already installed)", "ark", "ark"),
    ("microsoft office", "LibreOffice or OnlyOffice", "office", "libreoffice"),
    ("word", "LibreOffice or OnlyOffice", "office", "libreoffice"),
    ("excel", "LibreOffice or OnlyOffice", "office", "libreoffice"),
    ("zoom", "Zoom", "zoom", "zoom"),
    ("slack", "Slack", "slack", "slack"),
    ("telegram", "Telegram", "telegram", "telegram-desktop"),
    ("teams", "Microsoft Teams (web app) or Teams for Linux", "teams", "teams-for-linux"),
    ("epic games launcher", "Heroic (Epic, GOG and Amazon games)", "heroic", "heroic"),
    ("gog galaxy", "Heroic (Epic, GOG and Amazon games)", "heroic", "heroic"),
    ("ea app", "Lutris or Heroic (EA games)", "lutris", "lutris"),
    ("ubisoft connect", "Lutris (Ubisoft games)", "lutris", "lutris"),
    ("battle.net", "Lutris (Battle.net games)", "lutris", "lutris"),
    ("git", "Git (already installed)", "git", "git"),
    ("python", "Python (already installed)", "python", "python3"),
    ("powershell", "DeckOS Terminal (bash); PowerShell is in the Store too", "powershell", "pwsh"),
    ("steam", "Steam (Gaming in DeckOS Hub)", "steam", "steam"),
    ("firefox", "Firefox (already installed)", "firefox", "firefox"),
    ("microsoft edge", "Firefox, or Microsoft Edge from the Store", "edge", "microsoft-edge-stable"),
    ("msi afterburner", "DeckOS Hub > Gaming > Graphics card, and MangoHud for the overlay", "lact", "lact"),
    ("adrenalin", "DeckOS Hub > Gaming > Graphics card (power, fans, undervolt)", "lact", "lact"),
    ("blender", "Blender", "blender", "blender"),
    ("audacity", "Audacity", "audacity", "audacity"),
    ("krita", "Krita", "krita", "krita"),
    ("thunderbird", "Thunderbird", "thunderbird", "thunderbird"),
    ("signal", "Signal", "signal", "signal-desktop"),
    ("whatsapp", "WhatsApp (web app)", "whatsapp", ""),
    ("prism launcher", "Prism Launcher", "prism", "prismlauncher"),
    ("minecraft launcher", "Prism Launcher (Minecraft)", "prism", "prismlauncher"),
]


@dataclass
class Item:
    key: str
    kind: str  # folders, wallpaper, browser, games, apps, fonts, wifi, drives
    title: str
    detail: str
    ready: bool = True  # False: shown with why it can't come
    picked: bool = True  # chosen by default
    data: dict = field(default_factory=dict)


@dataclass
class Windows:
    root: Path  # the system drive's mount point
    users: list  # names of the user folders
    drives: list  # every NTFS mount point (system drive included)


# ------------------------------------------------------------------ finding Windows

def ntfs_mounts():
    if os.environ.get("DECKOS_MOVEIN_ROOTS") is not None:
        return [Path(p) for p in os.environ["DECKOS_MOVEIN_ROOTS"].split(":") if p]
    try:
        out = subprocess.run(["findmnt", "-rno", "TARGET,FSTYPE"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    mounts = []
    for line in out.splitlines():
        target, _, fstype = line.rpartition(" ")
        if fstype in ("ntfs3", "ntfs", "fuseblk"):
            mounts.append(Path(target.replace("\\x20", " ")))
    return mounts


def find_windows():
    drives = ntfs_mounts()
    systems = [d for d in drives if (d / "Users").is_dir() and (d / "Windows").is_dir()]
    if not systems:
        return None
    root = systems[0]
    users = sorted(u.name for u in (root / "Users").iterdir()
                   if u.is_dir() and not u.is_symlink() and u.name.lower() not in NOT_USERS
                   and (u / "AppData").is_dir())
    return Windows(root, users, drives)


def nonempty(path):
    try:
        return any(not p.name.startswith(("desktop.ini", ".")) for p in path.iterdir())
    except OSError:
        return False


def size_of(path, limit=20000):
    """Bytes under path, counting at most `limit` files (big folders: an estimate is enough)."""
    total = n = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
            n += 1
            if n >= limit:
                return total
    return total


def human(n):
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1000


# ------------------------------------------------------------------ what's there

def scan(user=None):
    """(Windows or None, [Item])."""
    win = find_windows()
    if not win or not win.users:
        return win, []
    user = user if user in win.users else win.users[0]
    home = win.root / "Users" / user
    items = []
    items += _folders(home)
    items += _wallpaper(home)
    items += _firefox(home)
    items += _chromium(home)
    items += _steam(win)
    items += _other_games(win)
    items += _apps(win, home)
    items += _fonts(home)
    items += _wifi(win)
    items += _drives(win)
    return win, items


def _folders(home):
    out = []
    for name, icon in FOLDERS:
        path = home / name
        if path.is_dir() and nonempty(path):
            out.append(Item(f"folder:{name}", "folders", f"Windows {name}",
                            "In DeckOS Files' sidebar, straight from the Windows drive: nothing is copied.",
                            data={"path": str(path), "icon": icon}))
    return out


def _wallpaper(home):
    path = home / "AppData/Roaming/Microsoft/Windows/Themes/TranscodedWallpaper"
    if not path.is_file() or path.stat().st_size < 1000:
        return []
    return [Item("wallpaper", "wallpaper", "Your Windows wallpaper", "Copied to Pictures and set as the desktop background.",
                 data={"path": str(path)})]


def _firefox(home):
    base = home / "AppData/Roaming/Mozilla/Firefox/Profiles"
    profiles = [p for p in base.glob("*") if (p / "places.sqlite").is_file()] if base.is_dir() else []
    profiles.sort(key=lambda p: (p / "places.sqlite").stat().st_mtime, reverse=True)
    out = []
    for i, p in enumerate(profiles):
        when = time.strftime("%d %b %Y", time.localtime((p / "places.sqlite").stat().st_mtime))
        item = Item(f"firefox:{p.name}", "browser", "Firefox: bookmarks, history, passwords, add-ons" + ("" if i == 0 else f" ({p.name})"),
                    f"Profile {p.name}, last used {when}, {human(size_of(p))}. Becomes Firefox's profile here; "
                    "the current one stays, in Firefox's profile manager.",
                    picked=i == 0, data={"path": str(p)})
        if _running("firefox"):
            item.ready, item.detail = False, "Close Firefox first, then look again."
        out.append(item)
    return out


def _chromium(home):
    out = []
    for name, rel in (("Microsoft Edge", "AppData/Local/Microsoft/Edge/User Data/Default/Bookmarks"),
                      ("Google Chrome", "AppData/Local/Google/Chrome/User Data/Default/Bookmarks")):
        path = home / rel
        if not path.is_file():
            continue
        try:
            count = len(list(_chromium_bookmarks(json.loads(path.read_text(errors="replace")))))
        except ValueError:
            continue
        if count:
            out.append(Item(f"bookmarks:{name}", "browser", f"{name} bookmarks",
                            f"{count} bookmarks, saved as a file Firefox imports (Bookmarks > Manage bookmarks > "
                            f"Import from HTML). Saved passwords are locked to Windows: export them in {name} "
                            "(Settings > Passwords > Export) and import that file in Firefox.",
                            data={"path": str(path), "browser": name, "count": count}))
    return out


def _chromium_bookmarks(data, folder=""):
    """(folder, title, url) for every bookmark in a Chrome/Edge Bookmarks file."""
    def walk(node, path):
        if node.get("type") == "url":
            yield path, node.get("name", ""), node.get("url", "")
        for child in node.get("children", []) or []:
            yield from walk(child, path + ([node["name"]] if node.get("type") == "folder" and node.get("name") else []))
    for root in (data.get("roots") or {}).values():
        if isinstance(root, dict):
            yield from walk(root, [])


def _steam_libraries(win):
    """steamapps folders with installed games on the Windows drives."""
    seen, libs = set(), []
    for drive in win.drives:
        for rel in ("SteamLibrary", "Steam", "Program Files (x86)/Steam", "Program Files/Steam", "Games/Steam",
                    "Games/SteamLibrary"):
            lib = drive / rel
            apps = lib / "steamapps"
            if apps.is_dir() and lib.resolve() not in seen and list(apps.glob("appmanifest_*.acf")):
                seen.add(lib.resolve())
                libs.append(lib)
    return libs


def _steam(win):
    libs = _steam_libraries(win)
    if not libs:
        return []
    linux_vdf = steamfiles.STEAM / "steamapps/libraryfolders.vdf"
    known = set()
    if linux_vdf.is_file():
        try:
            for entry in (steamfiles.read(linux_vdf).get("libraryfolders") or {}).values():
                if isinstance(entry, dict) and entry.get("path"):
                    known.add(Path(entry["path"]).resolve())
        except (OSError, ValueError):
            pass
    out = []
    for lib in libs:
        names = []
        for acf in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
            try:
                state = steamfiles.read(acf).get("AppState") or {}
            except (OSError, ValueError):
                continue
            if state.get("name") and not NOT_GAMES.match(state["name"]):
                names.append(state["name"])
        if not names:
            continue  # only Steam's tools: nothing to bring
        drive = next((d for d in win.drives if lib.is_relative_to(d)), lib.parent)
        where = "your Windows drive" if drive == win.root else drive.name
        shown = ", ".join(names[:4]) + (f" and {len(names) - 4} more" if len(names) > 4 else "")
        item = Item(f"steam:{lib}", "games", f"Steam games: {len(names)} on {where}",
                    f"{shown}. Added to Steam here as a library, so nothing downloads again; Proton's files for "
                    "them go on the Linux drive (deckos steam-ntfs).", data={"path": str(lib), "games": names})
        if lib.resolve() in known:
            item.ready, item.picked, item.detail = False, False, f"{shown}. Already in Steam here."
        elif not linux_vdf.is_file():
            item.ready, item.picked = False, False
            item.detail = f"{shown}. Install Steam first (DeckOS Hub > Gaming), open it once, then look again."
        elif steamfiles.steam_running():
            item.ready, item.detail = False, f"{shown}. Close Steam first, then look again."
        out.append(item)
    return out


def _other_games(win):
    found = []
    for drive in win.drives:
        for rel in ("Program Files/Epic Games", "Games", "GOG Games", "Program Files (x86)/GOG Galaxy/Games"):
            base = drive / rel
            if base.is_dir():
                found += [p.name for p in sorted(base.iterdir())
                          if p.is_dir() and p.name not in ("Steam", "SteamLibrary", "Launcher", "DirectXRedist")]
    if not found:
        return []
    shown = ", ".join(found[:5]) + (f" and {len(found) - 5} more" if len(found) > 5 else "")
    return [Item("other-games", "games", f"Other games: {len(found)} folders", f"{shown}. Epic and GOG games: "
                 "sign in to Heroic and use Import for each folder. Others: Lutris, or Steam's Add a Non-Steam Game.",
                 picked=False, data={"games": found})]


def _apps(win, home):
    names = {}  # lowercase -> as Windows shows it
    for base in (win.root / "ProgramData/Microsoft/Windows/Start Menu/Programs",
                 home / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"):
        if base.is_dir():
            for p in base.rglob("*"):
                if p.suffix.lower() in (".lnk", ".url") or p.is_dir():
                    names.setdefault(p.stem.lower(), p.stem)
    matches, done = [], set()
    for needle, what, search, command in APPS:
        found = sorted(n for n in names if needle in n)
        if what in done or not found:
            continue
        done.add(what)
        installed = bool(command and shutil.which(command))
        matches.append({"windows": needle, "name": names[min(found, key=len)], "linux": what, "search": search,
                        "installed": installed})
    if not matches:
        return []
    missing = [m for m in matches if not m["installed"]]
    return [Item("apps", "apps", f"Your apps: {len(matches)} with a DeckOS match",
                 f"{len(missing)} to get; the Store opens on each." if missing else "All of them are here already.",
                 picked=bool(missing), data={"apps": matches})]


def _fonts(home):
    base = home / "AppData/Local/Microsoft/Windows/Fonts"
    fonts = [p for p in base.glob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc")] if base.is_dir() else []
    if not fonts:
        return []
    return [Item("fonts", "fonts", f"Fonts you installed: {len(fonts)}", "Copied to your fonts folder "
                 "(~/.local/share/fonts/windows). Windows' own fonts stay on Windows (their license).",
                 data={"paths": [str(p) for p in fonts]})]


def _wifi(win):
    base = win.root / "ProgramData/Microsoft/Wlansvc/Profiles/Interfaces"
    names = []
    if base.is_dir():
        for xml in base.rglob("*.xml"):
            m = re.search(r"<name>([^<]+)</name>", xml.read_text(errors="replace"))
            if m:
                names.append(html.unescape(m.group(1)))
    if not names:
        return []
    return [Item("wifi", "wifi", f"Wi-Fi networks: {len(names)}", f"{', '.join(sorted(set(names))[:5])}. Their "
                 "passwords are encrypted by Windows, so connect once from the panel.", ready=False, picked=False)]


def _drives(win):
    """NTFS drives that are only mounted until the next restart (opened in a file manager)."""
    temporary = [d for d in win.drives if str(d).startswith(("/run/media/", "/media/"))]
    if not temporary:
        return []
    return [Item("drives", "drives", "Mount your Windows drives at every start",
                 f"{', '.join(str(d) for d in temporary)} only stay until you restart; games and folders on them "
                 "would vanish from Steam and the sidebar. This adds them to /mnt (deckos drives rescan; asks for "
                 "your password).", data={"drives": [str(d) for d in temporary]})]


def _running(name):
    try:
        return subprocess.run(["pgrep", "-x", name], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ------------------------------------------------------------------ bringing it over

def backup(path):
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".deckos-bak"))


def add_place(title, path, icon):
    """A bookmark in KDE's places (DeckOS Files' and Dolphin's sidebar). Inserted as text before </xbel>, so
    the rest of KDE's file stays exactly as it was."""
    url = "file://" + "/".join(html.escape(part, quote=True).replace(" ", "%20") for part in str(path).split("/"))
    text = PLACES.read_text() if PLACES.is_file() else ""
    if f'href="{url}"' in text:
        return False
    if "</xbel>" not in text:
        text = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xbel>\n<xbel xmlns:bookmark="http://www.freedesktop.org'
                '/standards/desktop-bookmarks" xmlns:kdepriv="http://www.kde.org/kdepriv" xmlns:mime="http://www.'
                'freedesktop.org/standards/shared-mime-info">\n</xbel>\n')
    entry = (f' <bookmark href="{url}">\n  <title>{html.escape(title)}</title>\n  <info>\n'
             f'   <metadata owner="http://freedesktop.org">\n    <bookmark:icon name="{icon}"/>\n   </metadata>\n'
             f'   <metadata owner="http://www.kde.org">\n    <ID>{int(time.time())}/{abs(hash(url)) % 10000}</ID>\n'
             '   </metadata>\n  </info>\n </bookmark>\n')
    backup(PLACES)
    PLACES.parent.mkdir(parents=True, exist_ok=True)
    i = text.rindex("</xbel>")
    PLACES.write_text(text[:i] + entry + text[i:])
    return True


def bookmarks_html(items, title):
    rows, folder = [], None
    for path, name, url in items:
        label = " / ".join(path)
        if label != folder:
            rows.append(f"    <DT><H3>{html.escape(label or title)}</H3>")
            folder = label
        rows.append(f'    <DT><A HREF="{html.escape(url, quote=True)}">{html.escape(name or url)}</A>')
    return ("<!DOCTYPE NETSCAPE-Bookmark-file-1>\n<META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; charset=UTF-8\">\n"
            f"<TITLE>{html.escape(title)}</TITLE>\n<H1>{html.escape(title)}</H1>\n<DL><p>\n" + "\n".join(rows) + "\n</DL><p>\n")


def import_firefox(src):
    """Copy a Windows Firefox profile in and make it the default, keeping the current one listed."""
    if _running("firefox"):
        raise RuntimeError("Firefox is open: close it and try again")
    FIREFOX.mkdir(parents=True, exist_ok=True)
    name = Path(src).name + ".from-windows"
    dest = FIREFOX / name
    if dest.exists():
        raise RuntimeError(f"already brought over ({dest})")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("parent.lock", "lock", ".parentlock", "cache2",
                                                             "startupCache", "crashes", "minidumps"))
    ini = FIREFOX / "profiles.ini"
    cp = configparser.RawConfigParser()
    cp.optionxform = str
    if ini.is_file():
        cp.read(ini)
    if not cp.has_section("General"):
        cp.add_section("General")
        cp.set("General", "StartWithLastProfile", "1")
        cp.set("General", "Version", "2")
    n = 0
    while cp.has_section(f"Profile{n}"):
        cp.remove_option(f"Profile{n}", "Default")
        n += 1
    sec = f"Profile{n}"
    cp.add_section(sec)
    for k, v in (("Name", "From Windows"), ("IsRelative", "1"), ("Path", name), ("Default", "1")):
        cp.set(sec, k, v)
    for s in cp.sections():  # [Install<hash>]: which profile each Firefox install opens
        if s.startswith("Install"):
            cp.set(s, "Default", name)
            cp.set(s, "Locked", "1")
    backup(ini)
    with ini.open("w") as f:
        cp.write(f, space_around_delimiters=False)
    installs = FIREFOX / "installs.ini"
    if installs.is_file():
        ic = configparser.RawConfigParser()
        ic.optionxform = str
        ic.read(installs)
        for s in ic.sections():
            ic.set(s, "Default", name)
        backup(installs)
        with installs.open("w") as f:
            ic.write(f, space_around_delimiters=False)
    return dest


def add_steam_library(path):
    vdf = steamfiles.STEAM / "steamapps/libraryfolders.vdf"
    if steamfiles.steam_running():
        raise RuntimeError("Steam is open: close it and try again")
    data = steamfiles.read(vdf)
    libs = data.setdefault("libraryfolders", {})
    if any(isinstance(e, dict) and Path(e.get("path", "")).resolve() == Path(path).resolve() for e in libs.values()):
        return False
    n = 0
    while str(n) in libs:
        n += 1
    libs[str(n)] = {"path": str(path), "label": "", "contentid": "", "totalsize": "0", "apps": {}}
    steamfiles.write(vdf, data)  # keeps libraryfolders.vdf.deckos-bak
    return True


def mount_source(path):
    try:
        out = subprocess.run(["findmnt", "-no", "SOURCE", "-T", str(path)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def mount_target(source):
    try:
        out = subprocess.run(["findmnt", "-rno", "TARGET", "-S", source], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    targets = [t.replace("\\x20", " ") for t in out.stdout.split("\n") if t]
    # right after the rescan a drive can be mounted twice: where it was opened, and its new /mnt place
    return next((t for t in targets if t.startswith("/mnt/")), targets[0] if targets else "")


def repoint(items, moved):
    """After the drives moved to /mnt: the other items' paths, from each drive's old mount to its new one.
    moved: {old mount: new mount}."""
    def fix(p):
        for old, new in moved.items():
            if p == old or p.startswith(old.rstrip("/") + "/"):
                return new + p[len(old):]
        return p
    for item in items:
        for key in ("path",):
            if key in item.data:
                item.data[key] = fix(item.data[key])
        if "paths" in item.data:
            item.data["paths"] = [fix(p) for p in item.data["paths"]]
        if item.key.startswith(("steam:", "firefox:")):
            item.key = item.key.split(":", 1)[0] + ":" + item.data["path"]


def apply(items, say=lambda text: None):
    """Bring the picked items over. [(key, ok, message)]. Drives first: everything else then points at
    where they're mounted from now on, not where they were until the restart."""
    results, log = [], []
    items = sorted(items, key=lambda i: i.kind != "drives")
    for item in items:
        if item.kind == "drives" and item.ready and item.picked:
            sources = {d: mount_source(d) for d in item.data["drives"]}
            say(item.title)
            try:
                results.append((item.key, True, _apply_one(item, log)))
            except Exception as e:
                results.append((item.key, False, str(e)))
                continue
            moved = {old: mount_target(src) for old, src in sources.items() if src and mount_target(src)}
            repoint(items, {o: n for o, n in moved.items() if n != o})
    for item in items:
        if item.kind == "drives":
            continue
        if not (item.ready and item.picked):
            continue
        say(item.title)
        try:
            msg = _apply_one(item, log)
            results.append((item.key, True, msg))
        except Exception as e:  # one item failing doesn't stop the rest
            results.append((item.key, False, str(e)))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(STATE.read_text()) if STATE.is_file() else []
    STATE.write_text(json.dumps(old + [{"when": int(time.time()), "done": log}], indent=1))
    return results


def _apply_one(item, log):
    d = item.data
    if item.kind == "folders":
        added = add_place(item.title, d["path"], d["icon"])
        log.append({"place": d["path"]})
        return "in the sidebar" if added else "was in the sidebar already"
    if item.kind == "wallpaper":
        src = Path(d["path"])
        ext = ".png" if src.read_bytes()[:4] == b"\x89PNG" else ".jpg"
        dest = HOME / "Pictures/Wallpapers" / f"From Windows{ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        log.append({"copied": str(dest)})
        if shutil.which("plasma-apply-wallpaperimage"):
            subprocess.run(["plasma-apply-wallpaperimage", str(dest)], capture_output=True, timeout=30)
        return f"set ({dest})"
    if item.key.startswith("firefox:"):
        dest = import_firefox(d["path"])
        log.append({"firefox": str(dest)})
        return "Firefox opens it from now on"
    if item.key.startswith("bookmarks:"):
        marks = list(_chromium_bookmarks(json.loads(Path(d["path"]).read_text(errors="replace"))))
        dest = HOME / "Documents" / f"Bookmarks from {d['browser']}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(bookmarks_html(marks, f"{d['browser']} bookmarks"))
        log.append({"copied": str(dest)})
        return f"saved to {dest}: import it in Firefox"
    if item.key.startswith("steam:"):
        added = add_steam_library(d["path"])
        log.append({"steam": d["path"]})
        deckos = shutil.which("deckos")
        if deckos:
            subprocess.run([deckos, "steam-ntfs"], capture_output=True, timeout=300)
        return "in Steam's libraries" if added else "was in Steam already"
    if item.kind == "apps":
        missing = [a for a in d["apps"] if not a["installed"]]
        if missing and shutil.which("deckos-store"):
            # one Store window, detached; the rest are listed in Move In with their own Get buttons
            subprocess.Popen(["deckos-store", "--search", missing[0]["search"]], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"the Store is open on {missing[0]['linux']}"
        return "nothing to get" if not missing else "get them from DeckOS Store"
    if item.kind == "fonts":
        dest = HOME / ".local/share/fonts/windows"
        dest.mkdir(parents=True, exist_ok=True)
        for p in d["paths"]:
            shutil.copy2(p, dest / Path(p).name)
        log.append({"fonts": str(dest)})
        if shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f", str(dest)], capture_output=True, timeout=120)
        return f"{len(d['paths'])} fonts installed"
    if item.kind == "drives":
        r = subprocess.run(["pkexec", "deckos", "drives", "rescan"], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError("deckos drives rescan didn't finish (see `sudo deckos drives rescan`)")
        return "mounted at every start, under /mnt"
    raise RuntimeError("nothing to do for this")
