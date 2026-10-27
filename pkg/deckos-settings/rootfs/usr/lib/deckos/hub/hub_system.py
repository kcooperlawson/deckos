"""What DecKoOS Hub shows: hardware, live stats, drives, updates, snapshots, firewall, themes.

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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gpu"))
import nvml  # noqa: E402  NVIDIA cards' numbers (gpu/nvml.py)

DEMO = "--demo" in sys.argv
# --demo-gpu=nvidia|intel: the demo on a non-AMD card, to check those layouts.
DEMO_VENDOR = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--demo-gpu=")), "amd")
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
        try:
            out = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        except RuntimeError:  # the window closed while it ran: nobody to tell
            return
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
    return f"DecKoOS {v}" if v and v != "rolling" else "DecKoOS"


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
                if line.startswith("#") or not line.strip():
                    continue  # comments sit inside vendor blocks too
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
    """The main graphics card: an AMD card with the most VRAM, else the boot display card.

    A Ryzen's built-in graphics (well under 2 GB of VRAM) only counts when it drives the screens, so
    a PC with an NVIDIA or Intel card next to it reports that card."""

    def __init__(self):
        self.dev = self.hwmon = None
        self.name, self.vendor = "No graphics card found", ""
        if DEMO:
            self.name, self.vendor = {"nvidia": ("GeForce RTX 4070", "0x10de"),
                                      "intel": ("Arc A770", "0x8086")}.get(DEMO_VENDOR, ("Radeon RX 9070 XT", "0x1002"))
            self.amd, self.nvidia = self.vendor == "0x1002", self.vendor == "0x10de"
            return
        best, best_vram = None, -1
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
            if "-" in card.name:
                continue
            dev = card / "device"
            vendor = read(dev / "vendor")
            vram = int(read(dev / "mem_info_vram_total") or 0)
            score = (vram if vendor == "0x1002" and vram >= 2 << 30
                     else 0 if read(dev / "boot_vga") == "1" else -1)
            if score > best_vram:
                best, best_vram = dev, score
        if best:
            self.dev, self.vendor = best, read(best / "vendor")
            self.name = pci_name(self.vendor, read(best / "device")) or "Graphics card"
            self.hwmon = next(iter(sorted((best / "hwmon").glob("hwmon*"))), None)
        self.amd, self.nvidia = self.vendor == "0x1002", self.vendor == "0x10de"


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
        if self.gpu.nvidia and nvml.devices():
            self.nvidia_sample(out)
        dev, hw = self.gpu.dev, self.gpu.hwmon
        t = read(hw / "temp1_input") if hw else ""
        out.setdefault("gpu_temp", (f"{int(t) / 1000:.0f}°C", int(t) / 100000) if t else ("—", None))
        pw = (read(hw / "power1_average") or read(hw / "power1_input")) if hw else ""
        cap = int(read(hw / "power1_cap") or 0) if hw else 0
        out.setdefault("gpu_power", (f"{int(pw) / 1e6:.0f} W", int(pw) / (cap or 300e6)) if pw else ("—", None))
        lines = read(dev / "pp_dpm_mclk").splitlines() if dev else []
        cur = next((ln for ln in lines if "*" in ln), "")
        mhz = re.search(r"(\d+)\s*Mhz", cur, re.I)
        top = re.search(r"(\d+)\s*Mhz", lines[-1], re.I) if lines else None
        out.setdefault("vram", (f"{mhz.group(1)} MHz", int(mhz.group(1)) / int(top.group(1))) if mhz and top
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

    def nvidia_sample(self, out):
        """An NVIDIA card's tiles from NVML (its driver has no amdgpu sysfs files to read)."""
        d = nvml.devices()[0]
        if d["temp"] is not None:
            out["gpu_temp"] = (f"{d['temp']:.0f}°C", d["temp"] / 100)
        if d["power"] is not None:
            out["gpu_power"] = (f"{d['power']:.0f} W", d["power"] / (d["power_limit"] or 300))
        if d["mem_clock"]:
            out["vram"] = (f"{d['mem_clock']} MHz", d["mem_clock"] / (d["mem_clock_max"] or d["mem_clock"]))

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
    ("ai", "Local AI", "Ollama, for running models on a Radeon RX 7000 / 9000 (ROCm) or an NVIDIA card (CUDA)", "ai",
     "ollama"),
    ("dev", "Development", "Claude Code, VS Code, JetBrains Toolbox, Docker, Node, Python, .NET, Java", "code",
     "docker"),
]

TOOLS = [  # AI & Dev page: name, command, what it is
    ("Claude Code", "claude", "AI coding agent in your terminal"),
    ("Ollama", "ollama", "Local models on your GPU"),
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
    {"number": 1, "date": "2026-10-24 19:02:11", "description": "Fresh DecKoOS install", "userdata": {"important": "yes"}},
    {"number": 14, "date": "2026-10-26 21:40:03", "description": "pacman -Syu", "userdata": None},
    {"number": 15, "date": "2026-10-26 21:43:57", "description": "pacman -Syu", "userdata": None},
    {"number": 16, "date": "2026-10-28 18:12:30", "description": "pacman -S lutris", "userdata": None},
]})


DEMO_HOME_SNAPSHOTS = json.dumps({"home": [{"number": 0, "description": "current"}] + [
    {"number": n, "date": f"2026-10-28 {h:02d}:00:01", "description": "timeline", "userdata": None}
    for n, h in zip(range(31, 43), range(8, 20))]})


def parse_undoable(out):
    """[(pre_number, date, what)] newest first, from `deckos undo --tsv`."""
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            rows.append((int(parts[0]), parts[1], parts[2]))
    return rows


def sound_theme():
    """deckos, ocean or another sound theme from kdeglobals (the user's, then the system default); off when muted."""
    if DEMO:
        return "deckos"
    theme, enabled = "", "true"
    for path in (Path("/etc/xdg/kdeglobals"), Path.home() / ".config/kdeglobals"):  # the user's file wins
        try:
            text = path.read_text()
        except OSError:
            continue
        m = re.search(r"^\[Sounds\]\n((?:[^\[].*\n?)*)", text, re.M)
        if m:
            theme = (re.search(r"^Theme=(.*)$", m.group(1), re.M) or [None, theme])[1] or theme
            enabled = (re.search(r"^Enable=(.*)$", m.group(1), re.M) or [None, enabled])[1] or enabled
    return "off" if enabled.strip().lower() == "false" else (theme.strip() or "ocean")


def set_sound_theme(theme):
    """Plasma's own setting (kdeglobals [Sounds]), as System Settings writes it: no root, applies to new sounds."""
    if theme == "off":
        subprocess.run(["kwriteconfig6", "--file", "kdeglobals", "--group", "Sounds", "--key", "Enable", "false"])
        return
    subprocess.run(["kwriteconfig6", "--file", "kdeglobals", "--group", "Sounds", "--key", "Enable", "true"])
    subprocess.run(["kwriteconfig6", "--file", "kdeglobals", "--group", "Sounds", "--key", "Theme", theme])


def booted_snapshot():
    """The snapshot GRUB's snapshots menu started, or None (grub-btrfs runs it read-only under an overlay)."""
    if DEMO:
        return 42 if "--demo-snapshot" in sys.argv else None
    try:
        m = re.search(r'rootflags=\S*subvol="?/?@snapshots/(\d+)/snapshot', Path("/proc/cmdline").read_text())
    except OSError:
        return None
    return int(m.group(1)) if m else None


DEMO_UNDOABLE = ("42\t2026-10-28 18:12\tlutris python-moddb\n"
                 "38\t2026-10-26 21:40\tlinux-cachyos mesa vulkan-radeon steam and 41 more\n"
                 "30\t2026-10-24 19:02\tdeckos-settings\n")


def last_undo():
    """What `deckos undo` last went back to: {snapshot, date, what, kept, cleaned?}, or None."""
    text = read(Path("/var/lib/deckos/undo")) if not DEMO else ""
    info = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    return info if info.get("snapshot") else None


def ask_assistant(question):
    """DecKoOS Assistant's chat box, asked about something that went wrong (it runs on the local model)."""
    if not DEMO:
        from PySide6.QtCore import QProcess
        QProcess.startDetached("deckos-assistant", ["--ask", question[-6000:]])


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


# DecKoOS's own packages, from the signed DecKoOS repo; everything else comes from Arch and CachyOS.
DECKOS_PKGS = ("deckos-settings", "deckos-files", "deckos-terminal", "deckos-editor", "deckos-theme-tmpikes")
# Updates that only take effect after a restart: the kernel and what boots with it.
REBOOT_RE = re.compile(r"linux(-cachyos[\w-]*|-zen|-lts)?(-headers)?$|linux-firmware.*|amd-ucode|systemd|mesa|"
                       r"vulkan-radeon|nvidia.*")
# Updates the running desktop keeps the old copy of until it restarts (the panel, Menu, Quick Settings).
DESKTOP_RE = re.compile(r"deckos-settings|plasma-workspace|plasma-desktop|libplasma|kwin|qt6-declarative")

DEMO_UPDATES = "\n".join([
    "deckos-settings 0.12.2-1 -> 0.12.3-1", "deckos-files 0.12.2-1 -> 0.12.3-1",
    "linux-cachyos 6.17.4-1 -> 6.17.5-1", "mesa 1:25.2.5-1 -> 1:25.2.6-1", "firefox 144.0-1 -> 144.0.1-1",
    "plasma-workspace 6.5.0-1 -> 6.5.1-1", "kwin 6.5.0-1 -> 6.5.1-1", "pipewire 1:1.4.9-1 -> 1:1.4.9-2",
    "steam 1.0.0.84-1 -> 1.0.0.85-1", "python 3.13.7-1 -> 3.13.8-1", "curl 8.16.0-1 -> 8.16.0-2"])


def parse_updates(text):
    """checkupdates / paru -Qua lines ("name old -> new") to [(name, old, new)]."""
    out = []
    for ln in text.splitlines():
        p = ln.split()
        if len(p) >= 4 and p[2] == "->" and "[ignored]" not in ln:
            out.append((p[0], p[1], p[3]))
    return out


def plain_version(v):
    """'1:25.2.6-1' -> '25.2.6': no epoch or package release, for showing people."""
    return v.split(":", 1)[-1].rsplit("-", 1)[0]


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
    """[(id, name, description, preview image)] for DecKoOS global themes."""
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
        src = {"DeckOS": "deckos/branding/wallpaper.svg", "TMpikes": "deckos/themes/tmpikes/wallpaper.svg"}.get(
            name, f"deckos/wallpapers/{name}.svg")
        if src and _repo_share(src).exists():
            yield _repo_share(src)


def wallpapers():
    """[(package dir, name, preview)] for installed wallpaper packages, DecKoOS ones first."""
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
            if d.name not in [o[0].name for o in out]:  # the user's copy, or demo mode's repo copy, once
                out.append((d, name, preview))
    return sorted(out, key=lambda w: (w[0].name not in ("DeckOS", "TMpikes"), w[1].lower()))


def vibes():
    """[(key, name, summary, preview)]: the Vibes (vibes.py), then "DecKoOS" to turn them off."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vibes"))
    import vibes as v
    out = []
    for key, x in v.VIBES.items():
        preview = next((b / f"plasma/wallpapers/org.deckos.vibe/contents/previews/{key}.jpg" for b in _dirs("")
                        if (b / f"plasma/wallpapers/org.deckos.vibe/contents/previews/{key}.jpg").exists()), None)
        out.append((key, x["name"], x["summary"], preview))
    home = next((p for tid, _n, _d, p in look_and_feels() if tid == "org.deckos.desktop"), None)
    out.append(("off", "DecKoOS", "No Vibe: the DecKoOS look", home))
    return out


def taskbar_settings():
    """{"height", "colorMode", "motion", "screens"} of the first DecKoOS taskbar, from Plasma's own files."""
    if DEMO:
        return {"height": 48, "colorMode": "vibe", "motion": True, "screens": "all"}
    cfg = Path.home() / ".config"
    out = {"height": 0, "colorMode": "accent", "motion": True,
           "screens": "all" if read(cfg / "deckos/taskbar-screens").strip() == "all" else "one"}
    try:
        text = (cfg / "plasma-org.kde.plasma.desktop-appletsrc").read_text()
        m = re.search(r"^\[Containments\]\[(\d+)\]\[Applets\]\[(\d+)\]\n(?:[^\[].*\n)*?plugin=org\.deckos\.taskbar", text, re.M)
        if m:
            grp = re.escape(f"[Containments][{m.group(1)}][Applets][{m.group(2)}][Configuration][General]")
            body = re.search(rf"^{grp}\n((?:[^\[].*\n?)*)", text, re.M)
            if body:
                mode = re.search(r"^colorMode=(\w+)", body.group(1), re.M)
                motion = re.search(r"^motion=(\w+)", body.group(1), re.M)
                out["colorMode"] = mode.group(1) if mode else "accent"
                out["motion"] = not (motion and motion.group(1) == "false")
        thick = re.search(r"^thickness=(\d+)", (cfg / "plasmashellrc").read_text(), re.M)
        out["height"] = int(thick.group(1)) if thick else 0
    except OSError:
        pass
    return out


def ai_setting(key, default=""):
    """An Assistant setting: the person's ~/.config/deckos/ai.conf, then /etc/deckos/ai.conf."""
    for path in (Path.home() / ".config/deckos/ai.conf", Path("/etc/deckos/ai.conf")):
        m = re.search(rf"^{key}=(.*)$", read(path), re.M)
        if m:
            return m.group(1).strip()
    return default


def desktop_widgets():
    """Which DecKoOS desktop widgets are on the desktop (from Plasma's own file)."""
    if DEMO:
        return {"org.deckos.bigclock", "org.deckos.nowplaying"}
    try:
        text = (Path.home() / ".config/plasma-org.kde.plasma.desktop-appletsrc").read_text()
    except OSError:
        return set()
    return set(re.findall(r"^plugin=(org\.deckos\.(?:bigclock|nowplaying|weather|focus|note))$", text, re.M))


def weather_place():
    try:
        return (Path.home() / ".config/deckos/weather-place").read_text().strip()
    except OSError:
        return ""


def visualizer_style():
    """bars, wave, ring or none: what `deckos vibe` last set (~/.config/deckos/visualizer)."""
    if DEMO:
        return "bars"
    try:
        return (Path.home() / ".config/deckos/visualizer").read_text().strip() or "none"
    except OSError:
        return "none"


def current_vibe():
    if DEMO:
        return "lofi"
    try:
        return (Path.home() / ".config/deckos/vibe").read_text().strip() or "off"
    except OSError:
        return "off"


def desktop_layouts():
    """[(key, name, description, preview)] for the DecKoOS panel layouts (deckos layout set KEY)."""
    out = []
    for base in _dirs("plasma/layout-templates"):
        for d in sorted(base.glob("org.deckos.layout.*")):
            try:
                meta = json.loads(read(d / "metadata.json")).get("KPlugin", {})
            except ValueError:
                continue
            key = d.name.rsplit(".", 1)[1]
            if key == "kids":  # Kid mode's own panel, set in a child's account; not a layout for grown-ups
                continue
            preview = next((b / f"deckos/layouts/{key}.svg" for b in _dirs("") if (b / f"deckos/layouts/{key}.svg").exists()), None)
            if key not in [o[0] for o in out]:
                out.append((key, meta.get("Name", key).replace("DecKoOS: ", ""), meta.get("Description", ""), preview))
    order = ["dock", "classic", "topbar", "minimal", "big"]
    return sorted(out, key=lambda o: order.index(o[0]) if o[0] in order else 99)


def current_look():
    return kconfig("kdeglobals", "KDE", "LookAndFeelPackage", "org.deckos.desktop")


def current_wallpaper():
    """The first desktop's wallpaper, as a package dir or image path (None when unknown)."""
    for line in read(Path.home() / ".config/plasma-org.kde.plasma.desktop-appletsrc").splitlines():
        if line.startswith("Image="):
            return Path(line.split("=", 1)[1].removeprefix("file://").rstrip("/"))
    return None


def current_icons():
    return kconfig("kdeglobals", "Icons", "Theme", "DeckOS")


def current_cursor():
    return kconfig("kcminputrc", "Mouse", "cursorTheme", "DeckOS-cursors")


def current_plasma_style():
    return kconfig("plasmarc", "Theme", "name", "deckos")


# ------------------------------------------------------------------ gaming tuning

GAMING_ENV = Path.home() / ".config/environment.d/90-deckos-gaming.conf"
DEMO_SCHEDULER = "state=enabled\nrunning=lavd\nsched=lavd\nmode=Gaming"
DEMO_GPU = ("card=card1\ncap=304\ncap_default=304\ncap_min=213\ncap_max=334\nod=0\nfan_curve=1\n"
            "power_percent=100\nvoltage_offset=0\nfan=stock\nlact=0")
DEMO_AUTO_UPDATE = "enabled=1\nwhen=1793163600\nresult=ok\ncount=14\nwhy="


def kv(text):
    """key=value lines (deckos status commands) to a dict."""
    return dict(ln.split("=", 1) for ln in text.splitlines() if "=" in ln)


def gaming_env():
    """The desktop + Gaming Mode environment DecKoOS Hub manages (FSR 4 upgrade and friends)."""
    return conf(GAMING_ENV)


def write_gaming_env(values):
    """Merges values into GAMING_ENV; None removes a key. Steam picks it up after logging in again."""
    env = {k: v for k, v in {**gaming_env(), **values}.items() if v is not None}
    if DEMO:
        return
    GAMING_ENV.parent.mkdir(parents=True, exist_ok=True)
    GAMING_ENV.write_text("# Written by DecKoOS Hub (Gaming > Performance). Gaming Mode reads it too.\n" +
                          "".join(f"{k}={v}\n" for k, v in env.items()))


def ntsync():
    return DEMO or Path("/dev/ntsync").exists()


def shader_cache_size():
    return "10G" if DEMO else conf("/usr/lib/environment.d/60-deckos-gaming.conf").get("MESA_SHADER_CACHE_MAX_SIZE", "")


def battery_devices():
    """[(name, percent or None, status)] for controllers and other wireless devices with a battery."""
    if DEMO:
        return [("Xbox Wireless Controller", 80, "Discharging"), ("DualSense Wireless Controller", 35, "Charging")]
    out = []
    for ps in sorted(Path("/sys/class/power_supply").glob("*")):
        if read(ps / "scope") != "Device":  # the PC's own battery/UPS has scope System
            continue
        cap = read(ps / "capacity")
        out.append((read(ps / "model_name") or ps.name, int(cap) if cap.isdigit() else None,
                    read(ps / "status") or read(ps / "capacity_level")))
    return out


def xone_dongle():
    """An Xbox wireless dongle (xone) is plugged in."""
    return DEMO or any(Path("/sys/bus/usb/drivers/xone-dongle").glob("*/pairing"))


def decky_installed():
    return (Path.home() / "homebrew/services/PluginLoader").exists() and not DEMO


def outputs():
    """[(name, vrr_policy, hdr_on, can_vrr, can_hdr)] for enabled screens, from kscreen-doctor.
    vrr_policy: 0 never, 1 always, 2 automatic."""
    if DEMO:
        return [("DP-1", 0, False, True, True)]
    try:
        data = json.loads(run(["kscreen-doctor", "-j"]) or "{}")
    except ValueError:
        return []
    out = []
    for o in data.get("outputs", []):
        if not (o.get("connected") and o.get("enabled")):
            continue
        caps = o.get("capabilities", 0)
        out.append((o["name"], o.get("vrrPolicy", 0), bool(o.get("hdr")), bool(caps & 0x2), bool(caps & 0x8)))
    return out
