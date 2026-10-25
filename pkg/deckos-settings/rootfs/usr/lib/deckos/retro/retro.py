"""DecKoOS Retro's engine (no Qt): which consoles there are, which of your files are games for which console,
what each needs to run (an emulator from the Arch repos or Flathub, sometimes a BIOS you dump from your own
console), how to start a game, and adding games to Steam so they're in Gaming Mode.

DecKoOS Retro never downloads games or BIOS files: it works with the ones you have.
DECKOS_RETRO_HOME / DECKOS_STEAM_ROOT point it at test folders.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gamedoctor"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
import steamfiles  # noqa: E402

HOME = Path(os.environ.get("DECKOS_RETRO_HOME") or Path.home())
LIBRARY = HOME / "Games/Retro"  # one folder per console, made by setup_folders()
RETROARCH_SYSTEM = HOME / ".config/retroarch/system"  # where RetroArch cores look for BIOS files
PCSX2_BIOS = HOME / ".var/app/net.pcsx2.PCSX2/config/PCSX2/bios"
CORES = Path("/usr/lib/libretro")
STEAM_TAG = "DecKoOS Retro"


@dataclass(frozen=True)
class Bios:
    name: str  # the file name the emulator looks for
    md5: tuple  # known-good dumps (any of them)
    required: bool = True
    note: str = ""


@dataclass(frozen=True)
class System:
    id: str
    name: str
    exts: tuple  # extensions that can only be this console's
    folders: tuple  # folder names people use for it (the first is the one setup_folders makes)
    package: str  # what to install: a libretro core package, or a Flathub app id
    core: str = ""  # libretro core file stem; empty for a standalone emulator
    bios: tuple = ()
    disc: bool = False  # games come as disc images (.iso/.cue/.chd...): told apart by their headers


SYSTEMS = [
    System("nes", "Nintendo (NES)", (".nes", ".fds", ".unf", ".unif"), ("nes", "famicom", "fds"),
           "libretro-nestopia", "nestopia"),
    System("snes", "Super Nintendo", (".sfc", ".smc", ".swc", ".fig"), ("snes", "sfc", "superfamicom"),
           "libretro-snes9x", "snes9x"),
    System("n64", "Nintendo 64", (".n64", ".z64", ".v64"), ("n64", "nintendo64"),
           "libretro-mupen64plus-next", "mupen64plus_next"),
    System("gb", "Game Boy", (".gb",), ("gb", "gameboy"), "libretro-gambatte", "gambatte"),
    System("gbc", "Game Boy Color", (".gbc",), ("gbc", "gameboycolor"), "libretro-gambatte", "gambatte"),
    System("gba", "Game Boy Advance", (".gba",), ("gba", "gameboyadvance"), "libretro-mgba", "mgba",
           (Bios("gba_bios.bin", ("a860e8c0b6d573d191e4ec7db1b1e4f6",), False, "Games run without it"),)),
    System("nds", "Nintendo DS", (".nds", ".dsi"), ("nds", "ds"), "libretro-melonds", "melonds",
           (Bios("bios7.bin", ("df692a80a5b1bc90728bc3dfc76cd948",), False, "Games run without it"),
            Bios("bios9.bin", ("a392174eb3e572fed6447e956bde4b25",), False, "Games run without it"))),
    System("gamecube", "GameCube", (".gcm", ".gcz"), ("gamecube", "gc", "ngc"), "libretro-dolphin", "dolphin",
           disc=True),
    System("wii", "Wii", (".wbfs", ".wad"), ("wii",), "libretro-dolphin", "dolphin", disc=True),
    System("genesis", "Mega Drive / Genesis", (".md", ".gen", ".smd", ".68k"), ("genesis", "megadrive", "md"),
           "libretro-genesis-plus-gx", "genesis_plus_gx"),
    System("sms", "Master System", (".sms",), ("mastersystem", "sms"), "libretro-genesis-plus-gx", "genesis_plus_gx"),
    System("gamegear", "Game Gear", (".gg",), ("gamegear", "gg"), "libretro-genesis-plus-gx", "genesis_plus_gx"),
    System("segacd", "Mega-CD / Sega CD", (), ("segacd", "megacd"), "libretro-genesis-plus-gx", "genesis_plus_gx",
           (Bios("bios_CD_U.bin", ("2efd74e3232ff260e371b99f84024f7f",), True, "for American games"),
            Bios("bios_CD_E.bin", ("e66fa1dc5820d254611fdcdba0662372",), False, "for European games"),
            Bios("bios_CD_J.bin", ("278a9397d192149e84e820ac621a8edd",), False, "for Japanese games")), True),
    System("saturn", "Saturn", (), ("saturn", "segasaturn"), "libretro-kronos", "kronos",
           (Bios("saturn_bios.bin", ("af5828fdff51384f99b3c4926be27762",), True),), True),
    System("dreamcast", "Dreamcast", (".gdi", ".cdi"), ("dreamcast", "dc"), "libretro-flycast", "flycast",
           (Bios("dc_boot.bin", ("e10c53c2f8b90bab96ead2d368858623",), False, "Most games run without it"),), True),
    System("pce", "PC Engine / TurboGrafx-16", (".pce", ".sgx"), ("pce", "pcengine", "tg16", "turbografx16"),
           "libretro-beetle-pce-fast", "mednafen_pce_fast"),
    System("psx", "PlayStation", (".pbp",), ("psx", "ps1", "playstation"), "libretro-beetle-psx-hw",
           "mednafen_psx_hw",
           (Bios("scph5501.bin", ("490f666e1afb15b7362b406ed1cea246",), True, "for American games"),
            Bios("scph5500.bin", ("8dd7d5296a650fac7319bce665a6a53c",), False, "for Japanese games"),
            Bios("scph5502.bin", ("32736f17079d0b2b7024407c39bd3050",), False, "for European games")), True),
    System("ps2", "PlayStation 2", (), ("ps2", "playstation2"), "net.pcsx2.PCSX2", "",
           (Bios("PS2 BIOS (any region)", (), True, "PCSX2 asks for it the first time"),), True),
    System("psp", "PSP", (".cso",), ("psp",), "libretro-ppsspp", "ppsspp", disc=True),
    System("arcade", "Arcade", (), ("arcade", "fbneo", "mame"), "libretro-mame", "mame"),
]
BY_ID = {s.id: s for s in SYSTEMS}
DISC_EXTS = (".iso", ".bin", ".cue", ".chd", ".img", ".rvz", ".m3u", ".ciso")
ARCHIVE_EXTS = (".zip", ".7z")


@dataclass
class Game:
    path: Path  # what the emulator opens (the .m3u or .cue for multi-file games)
    system: str
    title: str
    region: str = ""
    discs: int = 1
    files: list = field(default_factory=list)  # every file that belongs to it


# ------------------------------------------------------------------ telling consoles apart

def folder_hint(path, roots):
    """The console a folder name says (…/psx/game.chd), from the folder the game is in up to the root."""
    for parent in path.parents:
        if any(parent == r for r in roots):
            break
        name = re.sub(r"[^a-z0-9]", "", parent.name.lower())
        for s in SYSTEMS:
            if name in s.folders:
                return s.id
    return None


def read_head(path, size=4 << 20):
    try:
        with open(path, "rb") as f:
            return f.read(size)
    except OSError:
        return b""


def sniff_disc(path):
    """Which console a disc image is for, from the bytes where each console puts its signature."""
    if path.suffix.lower() == ".cue":
        target = cue_tracks(path)
        if not target:
            return None
        path = target[0]
    head = read_head(path)
    if len(head) < 0x40:
        return None
    if head[0x1C:0x20] == b"\xC2\x33\x9F\x3D":
        return "gamecube"
    if head[0x18:0x1C] == b"\x5D\x1C\x9E\xA3":
        return "wii"
    if b"SEGADISCSYSTEM" in head[:0x200]:
        return "segacd"
    if b"SEGA SEGASATURN" in head[:0x200]:
        return "saturn"
    # ISO 9660 discs: the PlayStations and the PSP say so in the volume descriptor
    if b"PSP GAME" in head[0x8000:0x8100] or b"UMD_DATA.BIN" in head:
        return "psp"
    if b"BOOT2" in head and b"cdrom0:" in head:
        return "ps2"
    if b"PLAYSTATION" in head[:0x10000]:
        return "psx"
    return None


def cue_tracks(cue):
    """The files a .cue sheet names, in order."""
    out = []
    try:
        for line in cue.read_text(errors="replace").splitlines():
            m = re.match(r'\s*FILE\s+"?(.+?)"?\s+\w+\s*$', line, re.I)
            if m:
                out.append(cue.parent / m.group(1))
    except OSError:
        pass
    return out


TAGS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
DISC = re.compile(r"\s*[\(\[]?\s*dis[ck]\s*(\d+)(?:\s*of\s*\d+)?\s*[\)\]]?", re.I)
REGIONS = ("USA", "Europe", "Japan", "World", "Germany", "France", "Spain", "Italy", "Korea", "Australia", "Brazil")


def title_of(path):
    """'Chrono Trigger (USA) [!].sfc' -> ('Chrono Trigger', 'USA')."""
    stem = path.stem
    region = next((r for r in REGIONS if re.search(rf"[\(,\s]{r}[\),]", stem)), "")
    title = DISC.sub("", TAGS.sub("", stem)).replace("_", " ").strip(" -")
    # "Legend of Zelda, The" -> "The Legend of Zelda"
    m = re.match(r"(.+), (The|A|An)$", title)
    if m:
        title = f"{m.group(2)} {m.group(1)}"
    return title or stem, region


def scan(roots):
    """Every game under `roots`, one Game per game (a three-disc game is one Game)."""
    roots = [Path(r) for r in roots if Path(r).is_dir()]
    files = []
    for r in roots:
        for p in r.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.relative_to(r).parts):
                files.append((r, p))
    claimed = set()
    games = []
    # Playlists and cue sheets first: the files they name aren't games of their own
    for root, p in files:
        ext = p.suffix.lower()
        if ext == ".m3u":
            discs = [p.parent / line.strip() for line in p.read_text(errors="replace").splitlines()
                     if line.strip() and not line.startswith("#")]
            claimed.update(discs)
            for d in discs:
                if d.suffix.lower() == ".cue":
                    claimed.update(cue_tracks(d))
        elif ext in (".cue", ".gdi"):
            claimed.update(cue_tracks(p) if ext == ".cue" else
                           [p.parent / f.split()[4].strip('"') for f in p.read_text(errors="replace").splitlines()[1:]
                            if len(f.split()) >= 5])
    for root, p in files:
        if p in claimed:
            continue
        ext = p.suffix.lower()
        system = folder_hint(p, roots)
        if system is None:
            system = next((s.id for s in SYSTEMS if ext in s.exts), None)
        if system is None and ext in DISC_EXTS:
            if ext == ".m3u":
                first = next((p.parent / line.strip() for line in p.read_text(errors="replace").splitlines()
                              if line.strip() and not line.startswith("#")), None)
                system = sniff_disc(first) if first else None
            elif ext not in (".chd", ".rvz"):  # compressed: only the folder can say
                system = sniff_disc(p)
            elif ext == ".rvz":
                system = "gamecube"  # Dolphin opens GameCube and Wii alike
        if system is None:
            continue  # not a game, or a console we can't tell: never guessed
        if ext in ARCHIVE_EXTS and system != "arcade" and not folder_hint(p, roots):
            continue
        if ext in (".bin", ".img") and not BY_ID[system].disc and system not in ("genesis",):
            continue
        title, region = title_of(p)
        games.append(Game(path=p, system=system, title=title, region=region, files=[p]))
    # Discs of one game without a playlist: "X (Disc 1).cue", "X (Disc 2).cue" become one Game
    merged = {}
    for g in games:
        key = (g.system, g.title, g.region, g.path.parent)
        if key in merged and DISC.search(g.path.stem):
            first = merged[key]
            first.discs += 1
            first.files += g.files
            if DISC.search(g.path.stem).group(1) < DISC.search(first.path.stem).group(1):
                first.path = g.path
        else:
            merged[key] = g
    return sorted(merged.values(), key=lambda g: (BY_ID[g.system].name, g.title.lower()))


# ------------------------------------------------------------------ what each console needs

def installed(system):
    s = BY_ID[system]
    if s.core:
        return (CORES / f"{s.core}_libretro.so").exists() and shutil.which("retroarch") is not None
    return subprocess.run(["flatpak", "info", s.package], capture_output=True).returncode == 0 \
        if shutil.which("flatpak") else False


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def bios_status(system):
    """[(Bios, state)] with state 'ok', 'unknown dump' (a file, but not a dump we know), or 'missing'."""
    out = []
    for b in BY_ID[system].bios:
        if system == "ps2":
            found = any(PCSX2_BIOS.glob("*.bin")) if PCSX2_BIOS.is_dir() else False
            out.append((b, "ok" if found else "missing"))
            continue
        path = RETROARCH_SYSTEM / b.name
        if not path.exists():
            out.append((b, "missing"))
        else:
            out.append((b, "ok" if not b.md5 or md5(path) in b.md5 else "unknown dump"))
    return out


def ready(system):
    """'' when games for it can start, else what's in the way."""
    if not installed(system):
        return "emulator"
    if any(b.required and state == "missing" for b, state in bios_status(system)):
        return "bios"
    return ""


def import_bios(folder):
    """Copies the BIOS files found in `folder` (a backup of your own console's) to where the emulators look,
    under the names they expect: recognised by checksum, whatever they're called. Returns [(file, as name)]."""
    known = {m: b.name for s in SYSTEMS for b in s.bios for m in b.md5}
    done = []
    RETROARCH_SYSTEM.mkdir(parents=True, exist_ok=True)
    for p in Path(folder).rglob("*"):
        if not p.is_file() or p.stat().st_size > 64 << 20:
            continue
        name = known.get(md5(p))
        if name:
            shutil.copy2(p, RETROARCH_SYSTEM / name)
            done.append((p, name))
        elif re.fullmatch(r"scph[-_]?\d+.*\.bin|ps2.*bios.*\.bin", p.name, re.I) and p.stat().st_size >= 4 << 20:
            PCSX2_BIOS.mkdir(parents=True, exist_ok=True)  # PS2 BIOS dumps vary too much to list
            shutil.copy2(p, PCSX2_BIOS / p.name)
            done.append((p, f"PS2 BIOS ({p.name})"))
    return done


def packages_for(systems):
    """What to install for these consoles: (pacman packages, flatpak ids)."""
    pac, flat = {"retroarch", "libretro-core-info"}, set()
    for sid in systems:
        s = BY_ID[sid]
        (pac if s.core else flat).add(s.package)
    return sorted(pac), sorted(flat)


def setup_folders(root=LIBRARY):
    """~/Games/Retro/<console>/ for each console, so there's an obvious place for every game."""
    for s in SYSTEMS:
        (root / s.folders[0]).mkdir(parents=True, exist_ok=True)
    return root


# ------------------------------------------------------------------ playing

def command(game, fullscreen=True):
    s = BY_ID[game.system]
    if s.core:
        return (["retroarch"] + (["-f"] if fullscreen else []) +
                ["-L", str(CORES / f"{s.core}_libretro.so"), str(game.path)])
    return ["flatpak", "run", s.package] + (["-fullscreen"] if fullscreen else []) + ["-batch", "--", str(game.path)]


# ------------------------------------------------------------------ Steam

def steam_entry(game):
    """A non-Steam game for Steam's library: it starts through deckos-retro, which picks the emulator."""
    exe = '"/usr/bin/deckos-retro"'
    name = game.title
    return {
        "appid": steamfiles.shortcut_appid(exe, name), "AppName": name, "Exe": exe, "StartDir": '"/usr/bin/"',
        "icon": "", "ShortcutPath": "", "LaunchOptions": f'--play "{game.path}"', "IsHidden": 0,
        "AllowDesktopConfig": 1, "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "",
        "DevkitOverrideAppID": 0, "LastPlayTime": 0, "FlatpakAppID": "",
        "tags": {"0": STEAM_TAG, "1": BY_ID[game.system].name},
    }


def sync_steam(games, user=None):
    """Adds `games` to every Steam user's library (or `user`'s), and takes out DecKoOS Retro games whose file
    is gone. Other non-Steam games are left exactly as they are. Steam must be closed (it rewrites the file
    when it exits). Returns (added, removed)."""
    if steamfiles.steam_running():
        raise RuntimeError("Steam is running")
    added = removed = 0
    for u in [user] if user else steamfiles.users():
        entries = steamfiles.read_shortcuts(u)
        ours = {e.get("LaunchOptions", ""): e for e in entries if STEAM_TAG in (e.get("tags") or {}).values()}
        keep = [e for e in entries if STEAM_TAG not in (e.get("tags") or {}).values()]
        wanted = {}
        for g in games:
            e = steam_entry(g)
            wanted[e["LaunchOptions"]] = ours.get(e["LaunchOptions"], e)  # keep Steam's own fields (play time)
        for opts, e in ours.items():
            if opts not in wanted:
                path = re.search(r'--play "(.+)"', opts)
                if path and Path(path.group(1)).exists():
                    wanted[opts] = e  # removed from the scan roots, but the game is still there: keep it
                else:
                    removed += 1
        added += sum(1 for o in wanted if o not in ours)
        steamfiles.write_shortcuts(u, keep + list(wanted.values()))
    if added or removed:
        try:
            import pulse
            pulse.emit("retro", f"Steam: {added} retro game{'s' if added != 1 else ''} added"
                       + (f", {removed} removed" if removed else ""), app="DecKoOS Retro")
        except (ImportError, OSError, ValueError):
            pass
    return added, removed
