"""What DeckOS Hub shows: hardware, live stats, drives, updates, snapshots, firewall, themes.

Everything here reads the system and never changes it; changes go through `deckos` (with
pkexec where root is needed) or Plasma's own tools. `--demo` swaps in canned data, for working
on the UI anywhere, Windows included.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess

DEMO = "--demo" in sys.argv
DECKOS = "/usr/bin/deckos"


def read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def run(cmd, timeout=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def have(cmd):
    return DEMO or shutil.which(cmd) is not None


class Job(QObject):
    """Runs a command without blocking the window; calls done(output, exit_code)."""

    def __init__(self, parent, cmd, done, demo=None):
        super().__init__(parent)
        self.done = done
        if DEMO:
            out, code = demo if demo is not None else ("", 0)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, lambda: (done(out, code), self.deleteLater()))
            return
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.SeparateChannels)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(lambda _e: self._finished(-1, None))
        self.proc.start(cmd[0], cmd[1:])

    def _finished(self, code, _status):
        out = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        self.done(out, code)
        self.deleteLater()


def kconfig(file, group, key, default=""):
    """A value from a KDE config file in ~/.config (falling back to /etc/xdg)."""
    for base in (Path.home() / ".config", Path("/etc/xdg")):
        cur = None
        for line in read(base / file).splitlines():
            if line.startswith("["):
                cur = line.strip("[]")
            elif cur == group and line.split("=", 1)[0] == key:
                return line.split("=", 1)[1]
    return default


def conf(path):
    """KEY=value pairs from a shell-style config file."""
    out = {}
    for line in read(path).splitlines():
        m = re.match(r"\s*([A-Z_]+)=(.*)", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def deckos_version():
    v = read("/usr/share/deckos/version") or (read(Path(__file__).resolve().parents[7] / "VERSION") if DEMO else "")
    return f"DeckOS {v}" if v and v != "rolling" else "DeckOS"


# ------------------------------------------------------------------ hardware

def cpu_name():
    if DEMO:
        return "Ryzen 7 7800X3D"
    m = re.search(r"model name\s*:\s*(.+)", read("/proc/cpuinfo"))
    name = m.group(1) if m else "CPU"
    name = re.sub(r"\s+\d+-Core Processor|\(R\)|\(TM\)|CPU|Processor|@.*", "", name)
    return re.sub(r"^(AMD|Intel)\s+", "", re.sub(r"\s+", " ", name)).strip()


def pci_name(vendor, device):
    """Marketing name from the PCI ID database, e.g. "Radeon RX 9070/9070 XT/9070 GRE"."""
    vendor, device = vendor.removeprefix("0x").lower(), device.removeprefix("0x").lower()
    in_vendor = False
    try:
        with open("/usr/share/hwdata/pci.ids", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.startswith("\t"):
                    in_vendor = line.startswith(vendor + "  ")
                elif in_vendor and line.startswith(f"\t{device}  "):
                    name = line.split("  ", 1)[1].strip()
                    m = re.search(r"\[(.+)\]", name)
                    return m.group(1) if m else name
    except OSError:
        pass
    return ""


class Gpu:
    """The main graphics card: an AMD card with the most VRAM, else the boot display card."""

    def __init__(self):
        self.dev = self.hwmon = None
        self.name, self.vendor, self.amd = "No graphics card found", "", False
        if DEMO:
            self.name, self.vendor, self.amd = "Radeon RX 9070 XT", "0x1002", True
            return
        best, best_vram = None, -1
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
            if "-" in card.name:
                continue
            dev = card / "device"
            vendor = read(dev / "vendor")
            vram = int(read(dev / "mem_info_vram_total") or 0)
            score = vram if vendor == "0x1002" else (0 if read(dev / "boot_vga") == "1" else -1)
            if score > best_vram:
                best, best_vram = dev, score
        if best:
            self.dev, self.vendor = best, read(best / "vendor")
            self.name = pci_name(self.vendor, read(best / "device")) or "Graphics card"
            self.hwmon = next(iter(sorted((best / "hwmon").glob("hwmon*"))), None)
        self.amd = self.vendor == "0x1002"


class Stats:
    """Samples GPU temperature, power and VRAM clock, CPU temperature and load, and memory."""

    def __init__(self, gpu):
        self.gpu = gpu
        self._cpu_prev = None
        self._tick = 0
        self.cpu_hwmon = None
        for hw in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
            if read(hw / "name") in ("k10temp", "coretemp", "zenpower"):
                self.cpu_hwmon = hw
                break

    def sample(self):
        """{key: (text, fraction 0..1 or None)}"""
        if DEMO:
            import math
            self._tick += 1
            t = self._tick
            w = lambda base, amp, per: base + amp * math.sin(t / per) + amp * 0.4 * math.sin(t / 2.3)
            return {"gpu_temp": (f"{w(52, 6, 5):.0f}°C", w(52, 6, 5) / 100),
                    "gpu_power": (f"{w(64, 28, 4):.0f} W", w(64, 28, 4) / 340),
                    "vram": (f"{1258 if t % 9 else 96} MHz", (1258 if t % 9 else 96) / 1258),
                    "cpu_temp": (f"{w(58, 7, 6):.0f}°C", w(58, 7, 6) / 95),
                    "cpu_load": (f"{w(18, 12, 3):.0f}%", w(18, 12, 3) / 100),
                    "ram": ("9.4 / 31 GB", 9.4 / 31)}
        out = {}
        dev, hw = self.gpu.dev, self.gpu.hwmon
        t = read(hw / "temp1_input") if hw else ""
        out["gpu_temp"] = (f"{int(t) / 1000:.0f}°C", int(t) / 100000) if t else ("—", None)
        pw = (read(hw / "power1_average") or read(hw / "power1_input")) if hw else ""
        cap = int(read(hw / "power1_cap") or 0) if hw else 0
        out["gpu_power"] = (f"{int(pw) / 1e6:.0f} W", int(pw) / (cap or 300e6)) if pw else ("—", None)
        lines = read(dev / "pp_dpm_mclk").splitlines() if dev else []
        cur = next((ln for ln in lines if "*" in ln), "")
        mhz = re.search(r"(\d+)\s*Mhz", cur, re.I)
        top = re.search(r"(\d+)\s*Mhz", lines[-1], re.I) if lines else None
        out["vram"] = ((f"{mhz.group(1)} MHz", int(mhz.group(1)) / int(top.group(1))) if mhz and top
                       else ("—", None))
        ct = read(self.cpu_hwmon / "temp1_input") if self.cpu_hwmon else ""
        out["cpu_temp"] = (f"{int(ct) / 1000:.0f}°C", int(ct) / 95000) if ct else ("—", None)
        fields = read("/proc/stat").splitlines()[0].split()[1:] if read("/proc/stat") else []
        if fields:
            nums = list(map(int, fields))
            idle, total = nums[3] + nums[4], sum(nums)
            if self._cpu_prev:
                d_idle, d_total = idle - self._cpu_prev[0], total - self._cpu_prev[1]
                load = 1 - d_idle / d_total if d_total else 0
                out["cpu_load"] = (f"{load * 100:.0f}%", load)
            self._cpu_prev = (idle, total)
        out.setdefault("cpu_load", ("—", None))
        mem = dict(re.findall(r"(\w+):\s+(\d+)", read("/proc/meminfo")))
        if "MemTotal" in mem:
            total = int(mem["MemTotal"]) / 1048576
            used = total - int(mem.get("MemAvailable", 0)) / 1048576
            out["ram"] = (f"{used:.1f} / {total:.0f} GB", used / total)
        else:
            out["ram"] = ("—", None)
        return out

    def vram_mode(self):
        dev = self.gpu.dev
        return read(dev / "power_dpm_force_performance_level") if dev else ""


# ------------------------------------------------------------------ display

LEVELS = [
    ("Stock", "AMD defaults, no workarounds.", "—"),
    ("No FAMS", "Turns off firmware-assisted memory-clock switching, the usual cause of 1–2 s blackouts.",
     "small idle power"),
    ("Pinned VRAM clock", "Level 1, plus the VRAM clock locked to max at boot.", "~15–30 W idle"),
    ("No multi-monitor switching", "Level 2, plus no multi-monitor clock switching, PSR or Panel Replay.",
     "~15–30 W idle"),
    ("Locked high", "Every GPU clock forced high. Last resort.", "most idle power and heat"),
]


def display_level():
    level = conf("/etc/deckos/display.conf").get("LEVEL", "0")
    return int(level) if level.isdigit() and int(level) < len(LEVELS) else 0


def display_recommend():
    """(level, reason) from `deckos display recommend`."""
    out = "1\tRX 9070-series card + Samsung Odyssey" if DEMO else run([DECKOS, "display", "recommend"])
    lvl, _, why = out.partition("\t")
    return (int(lvl), why) if lvl.isdigit() else (0, "")


def monitors():
    """[(connector, name)] on the main graphics card."""
    out = "DP-1\tOdyssey G70B\nDP-2\tLG ULTRAGEAR" if DEMO else run([DECKOS, "display", "monitors"])
    return [tuple((ln.split("\t") + [""])[:2]) for ln in out.splitlines() if ln.strip()]


# ------------------------------------------------------------------ drives

def drives():
    """[(mountpoint, used_bytes, total_bytes, read_only, fstype)] for Windows-style drives."""
    if DEMO:
        return [("/mnt/Windows", 412e9, 1000e9, False, "ntfs3"), ("/mnt/SSD", 1.21e12, 2e12, False, "ntfs3"),
                ("/mnt/BIG", 3.1e12, 4e12, True, "ntfs3")]
    data = run(["findmnt", "-J", "-t", "ntfs3,fuseblk,exfat,vfat", "-o", "TARGET,FSTYPE,OPTIONS"])
    try:
        mounts = json.loads(data or "{}").get("filesystems", [])
    except ValueError:
        mounts = []
    out = []
    for m in mounts:
        if not m["target"].startswith(("/mnt", "/run/media")):
            continue
        try:
            u = shutil.disk_usage(m["target"])
            used, total = u.used, u.total
        except OSError:
            used = total = 0
        out.append((m["target"], used, total, ",ro," in f",{m['options']},", m["fstype"]))
    return out


def size(n):
    return f"{n / 1e12:.2f} TB" if n >= 1e12 else f"{n / 1e9:.0f} GB"


# ------------------------------------------------------------------ software

# key, title, description, icon, a command that exists once it's installed
GROUPS = [
    ("gaming", "Gaming", "Steam with Gaming Mode, Proton, Lutris, Heroic, MangoHud, Discord, OBS", "gaming",
     "gamescope-session-plus"),
    ("ai", "Local AI", "Ollama with ROCm, for running models on a Radeon RX 7000 / 9000", "ai", "ollama"),
    ("dev", "Development", "Claude Code, VS Code, JetBrains Toolbox, Docker, Node, Python, .NET, Java", "code",
     "docker"),
]

TOOLS = [  # AI & Dev page: name, command, what it is
    ("Claude Code", "claude", "AI coding agent in your terminal"),
    ("Ollama", "ollama", "Local models (ROCm)"),
    ("VS Code", "code", "Editor"),
    ("JetBrains Toolbox", "jetbrains-toolbox", "IDE manager"),
    ("Docker", "docker", "Containers"),
    ("Node.js", "node", "JavaScript runtime"),
    ("Python + uv", "uv", "Python tooling"),
    (".NET", "dotnet", "C# / .NET SDK"),
    ("Java", "java", "OpenJDK"),
    ("GitHub CLI", "gh", "gh"),
]


def installed(cmd):
    if DEMO:
        return cmd not in ("jetbrains-toolbox",)
    return shutil.which(cmd) is not None or (cmd == "claude" and (Path.home() / ".local/bin/claude").exists())


def service_active(name):
    return DEMO or run(["systemctl", "is-active", name]) == "active"


# ------------------------------------------------------------------ now playing (MPRIS)

PLAYERCTL_FORMAT = ("{{playerName}}\t{{status}}\t{{xesam:title}}\t{{xesam:artist}}\t{{xesam:album}}\t"
                    "{{mpris:artUrl}}\t{{position}}\t{{mpris:length}}")


def parse_players(out):
    """Players from `playerctl -a metadata --format PLAYERCTL_FORMAT`: playing first, then paused."""
    rows = []
    for line in out.splitlines():
        f = line.split("\t")
        if len(f) < 8 or f[1] not in ("Playing", "Paused"):
            continue
        art = f[5].replace("https://open.spotify.com/image/", "https://i.scdn.co/image/")  # Spotify's dead art links
        rows.append({"player": f[0], "status": f[1], "title": f[2] or "Unknown title", "artist": f[3],
                     "album": f[4], "art": art, "position": int(f[6]) / 1e6 if f[6].isdigit() else 0.0,
                     "length": int(f[7]) / 1e6 if f[7].isdigit() else 0.0})
    return sorted(rows, key=lambda r: r["status"] != "Playing")


def player_label(name):
    base = name.split(".")[0]
    return {"spotify": "Spotify", "firefox": "Firefox", "chromium": "Chromium", "vlc": "VLC", "elisa": "Elisa",
            "mpv": "mpv", "brave": "Brave", "strawberry": "Strawberry"}.get(base, base.capitalize())


def demo_playing():
    """Now-playing output for --demo, advancing with the clock."""
    import time
    pos = time.time() % 214
    art = (_PKG / "deckos-settings/rootfs/usr/share/deckos/branding/store-logo.svg").as_uri()
    return (f"spotify\tPlaying\tMidnight City\tM83\tHurry Up, We're Dreaming\t{art}\t{int(pos * 1e6)}\t214000000", 0)


# ------------------------------------------------------------------ updates, snapshots, firewall

def parse_snapshots(out):
    """[(number, date, description, important)] newest first, from `snapper --jsonout list`."""
    try:
        data = json.loads(out)
    except ValueError:
        return None
    rows = next((v for v in data.values() if isinstance(v, list)), []) if isinstance(data, dict) else []
    snaps = []
    for s in rows:
        if s.get("number", 0) == 0:
            continue
        important = (s.get("userdata") or {}).get("important") == "yes"
        snaps.append((s["number"], (s.get("date") or "")[:16], s.get("description") or "", important))
    return sorted(snaps, reverse=True)


DEMO_SNAPSHOTS = json.dumps({"root": [
    {"number": 0, "description": "current"},
    {"number": 1, "date": "2026-10-24 19:02:11", "description": "Fresh DeckOS install", "userdata": {"important": "yes"}},
    {"number": 14, "date": "2026-10-26 21:40:03", "description": "pacman -Syu", "userdata": None},
    {"number": 15, "date": "2026-10-26 21:43:57", "description": "pacman -Syu", "userdata": None},
    {"number": 16, "date": "2026-10-28 18:12:30", "description": "pacman -S lutris", "userdata": None},
]})


DEMO_HOME_SNAPSHOTS = json.dumps({"home": [{"number": 0, "description": "current"}] + [
    {"number": n, "date": f"2026-10-28 {h:02d}:00:01", "description": "timeline", "userdata": None}
    for n, h in zip(range(31, 43), range(8, 20))]})


def home_snapshots_on():
    return DEMO or Path("/etc/snapper/configs/home").exists()


def backup_info():
    """(destination folder, last backup time) from ~/.config/deckos/backup.conf, or ("", "")."""
    if DEMO:
        return "/mnt/BIG", "2026-10-27 22:15"
    c = conf(Path.home() / ".config/deckos/backup.conf")
    return c.get("DEST", ""), c.get("LAST", "")


def update_channel_on():
    return DEMO or "Include = /etc/pacman.d/deckos-repo" in read("/etc/pacman.conf")


# ------------------------------------------------------------------ appearance

_HERE = Path(__file__).resolve()
_PKG = _HERE.parents[6] if len(_HERE.parents) > 6 else Path("/nonexistent")  # pkg/ in the repo; absent once installed
REPO_SHARES = [_PKG / "deckos-settings/rootfs/usr/share", _PKG / "deckos-theme-tmpikes/rootfs/usr/share"]


def _dirs(sub):
    """Where to look for themes: the system, the user, and (for --demo) the repo's packages."""
    return [Path("/usr/share") / sub, Path.home() / ".local/share" / sub] + (
        [s / sub for s in REPO_SHARES] if DEMO else [])


def _repo_share(sub):
    """First repo package file at `sub`, for --demo runs (PNG previews only exist once built)."""
    return next((s / sub for s in REPO_SHARES if (s / sub).exists()), REPO_SHARES[0] / sub)


def look_and_feels():
    """[(id, name, description, preview image)] for DeckOS global themes."""
    out = []
    dirs = _dirs("plasma/look-and-feel")
    for base in dirs:
        for d in sorted(base.glob("org.deckos.*")):
            try:
                meta = json.loads(read(d / "metadata.json")).get("KPlugin", {})
            except ValueError:
                continue
            wall = re.search(r"^Image=(.+)$", read(d / "contents/defaults"), re.M)
            preview = next((p for w in ([wall.group(1)] if wall else []) for p in wallpaper_previews(w)), None)
            if d.name not in [o[0] for o in out]:
                out.append((d.name, meta.get("Name", d.name), meta.get("Description", ""), preview))
    return out


def wallpaper_previews(name):
    dirs = _dirs("wallpapers")
    for base in dirs:
        for f in ("contents/screenshot.png", "contents/images/1920x1080.png"):
            if (base / name / f).exists():
                yield base / name / f
    if DEMO:  # the PNGs are made when the package builds; the repo only has the SVG sources
        src = {"DeckOS": "deckos/branding/wallpaper.svg", "TMpikes": "deckos/themes/tmpikes/wallpaper.svg"}.get(name)
        if src and _repo_share(src).exists():
            yield _repo_share(src)


def wallpapers():
    """[(package dir, name, preview)] for installed wallpaper packages, DeckOS ones first."""
    out = []
    dirs = _dirs("wallpapers")
    for base in dirs:
        for d in sorted(base.iterdir()) if base.is_dir() else []:
            preview = next(wallpaper_previews(d.name), None)
            if not preview and not DEMO:
                continue
            try:
                name = json.loads(read(d / "metadata.json")).get("KPlugin", {}).get("Name", d.name)
            except ValueError:
                name = d.name
            out.append((d, name, preview))
    return sorted(out, key=lambda w: (w[0].name not in ("DeckOS", "TMpikes"), w[1].lower()))


def current_look():
    return kconfig("kdeglobals", "KDE", "LookAndFeelPackage", "org.deckos.desktop")


def current_icons():
    return kconfig("kdeglobals", "Icons", "Theme", "DeckOS")


def current_plasma_style():
    return kconfig("plasmarc", "Theme", "name", "deckos")
