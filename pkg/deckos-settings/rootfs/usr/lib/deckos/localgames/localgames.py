"""Games on my drives: PC games that live in plain folders (no Steam, Heroic or Lutris), found, understood and
started. No Qt: the Hub's Games page and `deckos-play` use it; tests/test_localgames.py checks it on fake folders.

For each folder under a games root (a "Games" folder on any drive, ~/Games) it works out, from the files alone:
which program starts the game (not the uninstaller, crash reporter or redistributables), the engine, whether it's a
Windows game (Proton, through umu) or a Linux one (run as it is), what the .exe needs (read from its import table),
and what will stop it (anti-cheat without Linux support, a publisher's launcher). Nothing is guessed silently: an
unsure pick says so, and the person's own pick always wins.

Each game gets its own Wine prefix. With the game's Steam id (steam_appid.txt, else a close title match from Steam's
store search) umu applies Proton's known fixes for it (GAMEID=umu-ID), and the Hub shows its cover and ProtonDB rating.
DecKoOS launches games as they are on disk: it never changes DRM or anti-cheat.

    localgames.py scan [ROOT…] | play FOLDER | install FOLDER | roots [set PATH…] | steam | look-up TITLE | pick FOLDER exe|name|appid|hidden VALUE
"""
import difflib
import fnmatch
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config/deckos/localgames.json"  # roots, and the person's picks per game
IDS = HOME / ".cache/deckos/localgames-ids.json"  # title -> Steam id lookups, so the store is asked once
COVERS = HOME / ".cache/deckos/covers"
PREFIXES = HOME / ".local/share/deckos/prefixes"
LOGS = HOME / ".local/state/deckos/localgames"  # each game's last run
PROTON_DIRS = [Path("/usr/share/steam/compatibilitytools.d"), HOME / ".local/share/Steam/compatibilitytools.d",
               HOME / ".steam/root/compatibilitytools.d"]
STEAM_TAG = "DecKoOS Games"

# Folders in a games root that aren't games
NOT_A_GAME = re.compile(r"^(_|\$|\.)|^(Prefixes|Retro|Emulation|umu|Steam|SteamLibrary|CommonRedist|Redist|"
                        r"System Volume Information|found\.\d+)$", re.I)
# Programs that ship with a game but aren't it
NOT_THE_GAME = re.compile(r"unins|setup|install|redist|vc_?redist|vcredist|dxsetup|dxwebsetup|directx|dotnet|"
                          r"ndp\d|crash|report|unitycrashhandler|ue4prereq|ueprereq|prereq|easyanticheat|"
                          r"start_protected_game|beservice|battleye|cefprocess|cefsharp|webhelper|quicksfv|"
                          r"touchup|cleanup|updater?$|patcher|activation|register|benchmark|dedicated|server|"
                          r"editor|modmanager|config(urator)?$|settings$|helper$|7z|unrar|winrar", re.I)
# A game's own installer (GOG's setup_*.exe, a plain setup.exe), never redistributables
INSTALLER = re.compile(r"^(setup|install)(_|-|$)|^setup.*\d|^install(er)?$", re.I)
ENGINES = [  # (engine, a file or folder that gives it away)
    ("Unity", "UnityPlayer.dll"), ("Unity", "*_Data/Managed"), ("Unreal Engine", "Engine/Binaries"),
    ("Unreal Engine", "*/Binaries/Win64"), ("Godot", "*.pck"), ("Ren'Py", "renpy"), ("RPG Maker", "RPG_RT.exe"),
    ("RPG Maker", "www/js/rpg_core.js"), ("RPG Maker", "js/rmmz_core.js"), ("GameMaker", "data.win"),
    ("XNA / FNA", "Microsoft.Xna.Framework.dll"), ("NW.js", "nw.pak"), ("Source", "bin/engine.dll"),
]
ANTICHEAT = [("EasyAntiCheat", "EasyAntiCheat"), ("BattlEye", "BattlEye"), ("BattlEye", "BEService*.exe"),
             ("Denuvo Anti-Cheat", "denuvo-anti-cheat*"), ("nProtect GameGuard", "GameGuard"),
             ("Ricochet", "randgrid.sys"), ("Vanguard", "vgc.exe")]
LAUNCHERS = [("Ubisoft Connect", "uplay_r1_loader*.dll"), ("Ubisoft Connect", "upc_r2_loader*.dll"),
             ("EA app", "Link2EA*"), ("EA app", "EAAntiCheat*"), ("Rockstar Games Launcher", "PlayGTAV.exe"),
             ("Rockstar Games Launcher", "socialclub*.dll"), ("Battle.net", "*Launcher.db")]
# What an .exe's imports say it needs, in plain words; Proton brings all of these but .NET Framework and XNA
NEEDS = [(re.compile(r"^d3d12\.dll$"), "DirectX 12"), (re.compile(r"^(d3d11|dxgi)\.dll$"), "DirectX 11"),
         (re.compile(r"^d3d10"), "DirectX 10"), (re.compile(r"^d3d9\.dll$"), "DirectX 9"),
         (re.compile(r"^d3d8\.dll$"), "DirectX 8"), (re.compile(r"^(opengl32)\.dll$"), "OpenGL"),
         (re.compile(r"^vulkan-1\.dll$"), "Vulkan"), (re.compile(r"^(msvcp|vcruntime)1[0-4]\d"), "Visual C++ runtime"),
         (re.compile(r"^mscoree\.dll$"), ".NET Framework"), (re.compile(r"^xinput"), "Controller (XInput)")]


@dataclass
class Game:
    name: str
    folder: str
    exe: str = ""  # relative to folder; "" when nothing could start it
    runner: str = "proton"  # proton | native | none
    engine: str = ""
    arch: str = ""  # 64-bit | 32-bit
    needs: list = field(default_factory=list)
    blockers: list = field(default_factory=list)  # what will stop it, said plainly
    notes: list = field(default_factory=list)
    candidates: list = field(default_factory=list)  # other programs it could be, best first
    sure: bool = True  # False: the pick is a guess between programs; the Hub asks
    installer: str = ""  # relative: a setup program, when the game still needs installing
    appid: str = ""  # Steam id: fixes, art and ProtonDB
    picked: bool = False  # the person chose the program


# ------------------------------------------------------------------ reading .exe files

def pe_info(path):
    """(arch, [imported dll names, lower case]) from a Windows .exe, or None when it isn't one. Reads the headers
    and import table only."""
    try:
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                return None
            f.seek(0x3C)
            pe = struct.unpack("<I", f.read(4))[0]
            f.seek(pe)
            if f.read(4) != b"PE\0\0":
                return None
            machine, nsec, _, _, _, optsize, _ = struct.unpack("<HHIIIHH", f.read(20))
            opt = f.read(optsize)
            magic = struct.unpack("<H", opt[:2])[0]
            arch = {0x8664: "64-bit", 0x14C: "32-bit", 0xAA64: "ARM"}.get(machine, "")
            dirs = 96 if magic == 0x10B else 112  # data directories start here in PE32 / PE32+
            if len(opt) < dirs + 16:
                return arch, []
            imp_rva = struct.unpack("<I", opt[dirs + 8:dirs + 12])[0]
            sections = [struct.unpack("<8sIIII", f.read(40)[:24]) for _ in range(min(nsec, 96))]

            def off(rva):
                for _n, vsize, vaddr, rsize, raw in sections:
                    if vaddr <= rva < vaddr + max(vsize, rsize):
                        return rva - vaddr + raw
                return None

            def cstr(rva):
                o = off(rva)
                if o is None:
                    return ""
                f.seek(o)
                return f.read(128).split(b"\0", 1)[0].decode("ascii", "replace")

            dlls, o = [], off(imp_rva) if imp_rva else None
            while o is not None and len(dlls) < 256:
                f.seek(o)
                entry = f.read(20)
                if len(entry) < 20 or entry == b"\0" * 20:
                    break
                name = cstr(struct.unpack("<IIIII", entry)[3])
                if name:
                    dlls.append(name.lower())
                o += 20
            return arch, dlls
    except (OSError, struct.error):
        return None


def is_elf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


# ------------------------------------------------------------------ finding the game in a folder

def words(text):
    return set(re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower()))


def _files(folder, depth=4, limit=4000):
    """Files under folder, shallow first, to a depth: enough to find a game's programs without walking a 100 GB tree."""
    out, todo = [], [(Path(folder), 0)]
    while todo and len(out) < limit:
        d, lvl = todo.pop(0)
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name.lower())
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if lvl < depth and not e.name.startswith(".") and e.name.lower() not in ("_commonredist", "redist",
                                                                                            "directx", "dotnet"):
                        todo.append((Path(e.path), lvl + 1))
                elif e.is_file(follow_symlinks=False):
                    out.append(Path(e.path))
            except OSError:
                continue
    return out


def _has(folder, files, pattern):
    """Whether a pattern (a file name, a glob, or a path under folder) is present."""
    if "/" in pattern:
        return any(Path(folder).glob(pattern))
    pat = pattern.lower()
    return any(fnmatch.fnmatch(p.name.lower(), pat) for p in files) or \
        any(fnmatch.fnmatch(d.name.lower(), pat) for d in _dirs(folder))


def _dirs(folder, depth=3):
    out, todo = [], [(Path(folder), 0)]
    while todo:
        d, lvl = todo.pop()
        try:
            for e in os.scandir(d):
                if e.is_dir(follow_symlinks=False):
                    out.append(Path(e.path))
                    if lvl < depth:
                        todo.append((Path(e.path), lvl + 1))
        except OSError:
            continue
    return out


def score(exe, folder, name):
    """How likely a program is the one that starts the game: named like the game, near the top, not a helper."""
    rel = exe.relative_to(folder)
    stem = exe.stem
    s = 0.0
    s -= 2.0 * (len(rel.parts) - 1)
    overlap = words(stem) & words(name)
    s += 4.0 * len(overlap) / max(1, len(words(name)))
    s += 3.0 * difflib.SequenceMatcher(None, re.sub(r"\W", "", stem.lower()), re.sub(r"\W", "", name.lower())).ratio()
    if re.search(r"-Win64-Shipping$|-WinGDK-Shipping$", stem):
        s += 2.5  # Unreal's game program; the stub at the top only starts it
    if re.search(r"launcher", stem, re.I):
        s -= 1.5
    if re.search(r"_x64|64$", stem):
        s += 0.3
    try:
        s += min(exe.stat().st_size / 50e6, 1.5)  # the game is usually the biggest program
    except OSError:
        pass
    return s


def inspect(folder, name=None):
    """A Game from one folder's files."""
    folder = Path(folder)
    name = name or clean_name(folder.name)
    g = Game(name=name, folder=str(folder))
    files = _files(folder)
    for engine, pat in ENGINES:
        if _has(folder, files, pat):
            g.engine = engine
            break
    g.blockers += [f"{ac}: its anti-cheat may refuse to run on Linux unless the game turned on Proton support"
                   for ac in dict.fromkeys(a for a, p in ANTICHEAT if _has(folder, files, p))]
    g.blockers += [f"{ln}: it has to be installed and signed in inside this game's prefix first"
                   for ln in dict.fromkeys(n for n, p in LAUNCHERS if _has(folder, files, p))]
    appid = folder / "steam_appid.txt"
    if appid.is_file():
        try:
            g.appid = re.sub(r"\D", "", appid.read_text(errors="replace"))[:10]
        except OSError:
            pass

    exes = [p for p in files if p.suffix.lower() == ".exe" and not NOT_THE_GAME.search(p.stem)]
    native = [p for p in files if p.suffix.lower() in ("", ".x86_64", ".x86", ".sh") and os.access(p, os.X_OK)
              and not NOT_THE_GAME.search(p.stem) and (p.suffix == ".sh" or is_elf(p))]
    if native and not exes:
        g.runner = "native"
        ranked = sorted(native, key=lambda p: -score(p, folder, name))
    elif exes:
        ranked = sorted(exes, key=lambda p: -score(p, folder, name))
    else:
        g.runner, g.sure = "none", False
        setup = sorted((p for p in files if p.suffix.lower() == ".exe" and INSTALLER.search(p.stem)),
                       key=lambda p: (len(p.relative_to(folder).parts), p.name.lower()))
        if setup:
            g.installer = str(setup[0].relative_to(folder))
            g.notes.append(f"Needs installing first: {g.installer} sets it up in the game's own prefix.")
        else:
            g.notes.append("No program to start it was found: it may still need unpacking (an archive).")
        return g
    g.exe = str(ranked[0].relative_to(folder))
    g.candidates = [str(p.relative_to(folder)) for p in ranked[:8]]
    if len(ranked) > 1:
        top, second = score(ranked[0], folder, name), score(ranked[1], folder, name)
        g.sure = top - second >= 1.5
    if g.runner == "proton":
        info = pe_info(ranked[0])
        if info:
            g.arch, dlls = info
            for rx, what in NEEDS:
                if any(rx.search(d) for d in dlls) and what not in g.needs:
                    g.needs.append(what)
        if g.engine == "XNA / FNA":
            g.notes.append("XNA games need Microsoft XNA 4.0 in the prefix (DecKoOS installs it the first time).")
        if ".NET Framework" in g.needs and g.engine not in ("Unity",):
            g.notes.append("Uses .NET Framework: Proton's Mono usually runs it; some games need the real one.")
    return g


def clean_name(folder_name):
    """A title from a folder name: no version tags, release-group brackets or underscores."""
    n = re.sub(r"[\[(][^\])]*[\])]", " ", folder_name).replace("_", " ")
    n = re.sub(r"\bv?\d+(\.\d+){1,3}[a-z]?\b", " ", n, flags=re.I)
    n = re.sub(r"\.+(?=\w)", " ", n) if " " not in n.strip() else n  # Some.Game, but not S.T.A.L.K.E.R. 2
    return re.sub(r"\s+", " ", n).strip(" -_") or folder_name


# ------------------------------------------------------------------ roots, picks, scanning

def default_roots():
    """"Games" folders at the top of mounted drives, and ~/Games (DecKoOS Retro's own folder is left out)."""
    out = []
    for base in (Path("/mnt"), Path("/media"), Path("/run/media") / os.environ.get("USER", "")):
        try:
            drives = [d for d in base.iterdir() if d.is_dir()]
        except OSError:
            continue
        for d in drives:
            for name in ("Games", "games", "PC Games"):
                if (d / name).is_dir():
                    out.append(d / name)
    if (HOME / "Games").is_dir():
        out.append(HOME / "Games")
    return out


def load():
    try:
        data = json.loads(CONFIG.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(CONFIG)


def roots():
    data = load()
    return [Path(r) for r in data.get("roots", [])] or default_roots()


def set_roots(paths):
    """The folders to look in; an empty list goes back to finding them (Games folders on every drive)."""
    data = load()
    data["roots"] = [str(Path(p)) for p in dict.fromkeys(paths)]
    save(data)


def log_of(name):
    path = LOGS / f"{slug(name)}.log"
    return path if path.is_file() else None


# ------------------------------------------------------------------ installing

def new_programs(prefix, since, name):
    """Programs an installer put in a prefix (Program Files, GOG Games…) after `since`, best match first."""
    drive = Path(prefix) / "drive_c"
    found = []
    for base in [drive / d for d in ("Program Files", "Program Files (x86)", "GOG Games", "Games")]:
        for p in _files(base, depth=4) if base.is_dir() else []:
            try:
                if p.suffix.lower() == ".exe" and not NOT_THE_GAME.search(p.stem) and p.stat().st_mtime >= since - 5:
                    found.append(p)
            except OSError:
                continue
    return sorted(found, key=lambda p: -score(p, p.parent, name))


def install(folder):
    """Runs a game's installer in the game's own prefix, then remembers the program it installed. Returns the
    program's path, or None."""
    folder = Path(folder)
    g = inspect(folder, load().get("games", {}).get(str(folder), {}).get("name"))
    if not g.installer:
        raise RuntimeError("no installer in that folder")
    if not shutil.which("umu-run"):
        raise RuntimeError("Windows installers need umu-launcher: sudo pacman -S umu-launcher")
    exe_game = Game(**{**asdict(g), "exe": g.installer, "runner": "proton"})
    argv, env, cwd = command(exe_game)
    Path(env["WINEPREFIX"]).mkdir(parents=True, exist_ok=True)
    since = time.time()
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{slug(g.name)}-install.log", "w") as log:
        subprocess.call(argv, cwd=cwd, env={**os.environ, **env}, stdout=log, stderr=subprocess.STDOUT)
    found = new_programs(env["WINEPREFIX"], since, g.name)
    if found:
        pick(folder, exe=str(found[0]))  # an absolute path: the game now lives in its prefix
        return found[0]
    return None


def looks_like_junk(name):
    """Download leftovers: long runs of letters and digits with no spaces (temp folders, hashes)."""
    return " " not in name and len(name) > 40


def scan(paths=None):
    """Every game folder under the roots, with the person's picks applied. Hidden ones are left out."""
    picks = load().get("games", {})
    games, seen = [], set()
    for root in paths or roots():
        try:
            folders = sorted((d for d in Path(root).iterdir() if d.is_dir()), key=lambda d: d.name.lower())
        except OSError:
            continue
        for d in folders:
            if NOT_A_GAME.search(d.name) or looks_like_junk(d.name):
                continue
            mine = picks.get(str(d), {})
            if mine.get("hidden"):
                continue
            g = inspect(d, mine.get("name"))
            if mine.get("exe") and (d / mine["exe"]).is_file():  # relative, or absolute once installed in a prefix
                g.exe, g.sure, g.picked, g.installer = mine["exe"], True, True, ""
                g.notes = [n for n in g.notes if "installing" not in n and "unpacking" not in n]
                g.runner = "proton" if g.exe.lower().endswith(".exe") else "native"
            if mine.get("appid"):
                g.appid = mine["appid"]
            key = (g.name.lower(), g.exe.lower())
            if key in seen:  # the same game on two drives: both are listed, with the drive in the name
                g.name = f"{g.name} ({Path(root).parent.name})"
            seen.add(key)
            games.append(g)
    return games


def pick(folder, **changes):
    """The person's choice for a game: exe, name, appid or hidden."""
    data = load()
    data.setdefault("games", {}).setdefault(str(folder), {}).update(changes)
    save(data)


# ------------------------------------------------------------------ Steam ids (fixes, art, ProtonDB)

def _norm(title):
    return re.sub(r"[^a-z0-9]", "", title.lower().replace("&", "and"))


def match_title(title, results):
    """The Steam id for a title among store search results [(id, name)], or "" when none is close enough: an exact
    match, or the store's name with its subtitle ("S.T.A.L.K.E.R. 2: Heart of Chornobyl") matching."""
    want = _norm(title)
    for appid, name in results:
        base = re.split(r"[:–—]| - ", name)[0]
        if _norm(name) == want or _norm(base) == want:
            return str(appid)
    for appid, name in results[:1]:
        if difflib.SequenceMatcher(None, _norm(name), want).ratio() >= 0.9:
            return str(appid)
    return ""


def steam_id(title, fetch=None):
    """A Steam id for a title, asked of Steam's store search once and remembered (also when there's none)."""
    try:
        cache = json.loads(IDS.read_text())
    except (OSError, ValueError):
        cache = {}
    if title in cache:
        return cache[title]
    url = "https://store.steampowered.com/api/storesearch/?" + urllib.parse.urlencode({"term": title, "cc": "us", "l": "en"})
    try:
        if fetch:
            body = fetch(url)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "DecKoOS"})
            with urllib.request.urlopen(req, timeout=8) as r:
                body = r.read().decode()
        items = json.loads(body).get("items", [])
    except (OSError, ValueError):
        return ""  # offline: ask again next time
    found = match_title(title, [(i.get("id"), i.get("name", "")) for i in items])
    cache[title] = found
    IDS.parent.mkdir(parents=True, exist_ok=True)
    IDS.write_text(json.dumps(cache))
    return found


def cover_url(appid):
    return f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900.jpg"


def cover(appid, fetch=None):
    """The game's cover from Steam, downloaded once into the cache: its path, or None."""
    if not re.fullmatch(r"\d{1,10}", str(appid or "")):
        return None
    path = COVERS / f"{appid}.jpg"
    if path.is_file():
        return path
    try:
        if fetch:
            data = fetch(cover_url(appid))
        else:
            req = urllib.request.Request(cover_url(appid), headers={"User-Agent": "DecKoOS"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read(5_000_000)
    except OSError:
        return None
    if not data.startswith(b"\xff\xd8"):  # a JPEG, not an error page
        return None
    COVERS.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# ------------------------------------------------------------------ starting a game

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "game"


def proton_path():
    """The newest Proton installed: CachyOS's first, then any other. None lets umu use its own UMU-Proton."""
    found = []
    for d in PROTON_DIRS:
        try:
            found += [p for p in d.iterdir() if (p / "proton").is_file()]
        except OSError:
            continue
    found.sort(key=lambda p: ("cachyos" not in p.name.lower(), -p.stat().st_mtime))
    return found[0] if found else None


def command(g):
    """(argv, env additions, working folder) that start a game."""
    exe = Path(g.folder) / g.exe
    if g.runner == "native":
        return ([str(exe)] if os.access(exe, os.X_OK) else ["sh", str(exe)]), {}, str(exe.parent)
    env = {"WINEPREFIX": str(PREFIXES / slug(g.name)), "GAMEID": f"umu-{g.appid}" if g.appid else "umu-default",
           "STORE": "none", "PROTON_VERB": "waitforexitandrun"}
    proton = proton_path()
    if proton:
        env["PROTONPATH"] = str(proton)
    return ["umu-run", str(exe)], env, str(exe.parent)


def play(folder):
    """Starts the game in folder (what Steam shortcuts and the Hub run). Returns its exit code."""
    folder = Path(folder)
    g = next((x for x in scan([folder.parent]) if Path(x.folder) == folder), None) or inspect(folder)
    if not g.exe:
        print(f"Nothing in {folder} starts a game.", file=sys.stderr)
        return 1
    if g.runner == "proton" and not shutil.which("umu-run"):
        print("Windows games need umu-launcher: sudo pacman -S umu-launcher", file=sys.stderr)
        return 1
    if g.runner == "proton" and not g.appid:
        g.appid = steam_id(g.name)  # Proton's fixes for it, when Steam knows the game
    argv, env, cwd = command(g)
    Path(env.get("WINEPREFIX", cwd)).mkdir(parents=True, exist_ok=True)
    # The game's own output, for Game Doctor and for whoever helps when it won't start
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{slug(g.name)}.log", "w") as log:
        return subprocess.call(argv, cwd=cwd, env={**os.environ, **env}, stdout=log, stderr=subprocess.STDOUT)


# ------------------------------------------------------------------ Steam library

def steam_entry(g):
    """A non-Steam game for Steam's library that starts through deckos-play."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gamedoctor"))
    import steamfiles
    exe = '"/usr/bin/deckos-play"'
    return {
        "appid": steamfiles.shortcut_appid(exe, g.name), "AppName": g.name, "Exe": exe, "StartDir": '"/usr/bin/"',
        "icon": "", "ShortcutPath": "", "LaunchOptions": f'"{g.folder}"', "IsHidden": 0, "AllowDesktopConfig": 1,
        "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "", "DevkitOverrideAppID": 0, "LastPlayTime": 0,
        "FlatpakAppID": "", "tags": {"0": STEAM_TAG},
    }


def sync_steam(games, user=None):
    """Adds games to Steam's library as non-Steam games and takes out ours whose folder is gone; other shortcuts are
    left exactly as they are. Steam must be closed. Returns (added, removed)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gamedoctor"))
    import steamfiles
    if steamfiles.steam_running():
        raise RuntimeError("Steam is running")
    added = removed = 0
    for u in [user] if user else steamfiles.users():
        entries = steamfiles.read_shortcuts(u)
        ours = {e.get("LaunchOptions", ""): e for e in entries if STEAM_TAG in (e.get("tags") or {}).values()}
        keep = [e for e in entries if STEAM_TAG not in (e.get("tags") or {}).values()]
        wanted = {}
        for g in games:
            if g.exe:
                e = steam_entry(g)
                wanted[e["LaunchOptions"]] = ours.get(e["LaunchOptions"], e)  # keeps Steam's own fields
        for opts, e in ours.items():
            if opts not in wanted:
                if Path(opts.strip('"')).is_dir():
                    wanted[opts] = e  # its drive's root was taken out of the list, but the game is still there
                else:
                    removed += 1
        added += sum(1 for o in wanted if o not in ours)
        steamfiles.write_shortcuts(u, keep + list(wanted.values()))
    return added, removed


def main(argv):
    if argv[:1] == ["scan"]:
        print(json.dumps([asdict(g) for g in scan([Path(p) for p in argv[1:]] or None)], indent=1))
        return 0
    if argv[:1] == ["look-up"] and len(argv) == 2:
        # The Hub's background lookup for one game: its Steam id and cover, both cached
        appid = steam_id(argv[1])
        art = cover(appid) if appid else None
        print(json.dumps({"appid": appid, "art": str(art) if art else ""}))
        return 0
    if argv[:1] == ["pick"] and len(argv) == 4 and argv[2] in ("exe", "name", "appid", "hidden"):
        pick(argv[1], **{argv[2]: argv[3] == "1" if argv[2] == "hidden" else argv[3]})
        return 0
    if argv[:1] == ["install"] and len(argv) == 2:
        try:
            exe = install(argv[1])
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(exe or "", end="")
        return 0 if exe else 3  # 3: the installer ran but nothing new to start was found
    if argv[:1] == ["roots"]:
        if argv[1:2] == ["set"]:
            set_roots(argv[2:])
        print("\n".join(str(r) for r in roots()))
        return 0
    if argv[:1] == ["play"] and len(argv) == 2:
        return play(argv[1])
    if argv[:1] == ["steam"]:
        try:
            added, removed = sync_steam(scan())
        except RuntimeError as e:
            print(f"Close Steam first ({e}).", file=sys.stderr)
            return 1
        print(f"Steam: {added} added, {removed} removed")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
