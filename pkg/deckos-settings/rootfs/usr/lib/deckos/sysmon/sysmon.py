"""DecKoOS System Monitor's data: processes, processor, memory, graphics card, disks and network, read
straight from /proc and /sys (no psutil, no Qt). Rates and CPU shares come from the difference between
two samples, so the first sample has none. DECKOS_PROC / DECKOS_SYS point it at a fake tree for tests.
"""
import os
import pwd
import re
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

PROC = Path(os.environ.get("DECKOS_PROC", "/proc"))
SYS = Path(os.environ.get("DECKOS_SYS", "/sys"))
PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096

# Kernel threads and the like: not apps anyone would look for
HIDDEN_PARENTS = {2}  # kthreadd


def read(path):
    try:
        return Path(path).read_text()
    except (OSError, UnicodeDecodeError):
        return ""


@dataclass
class Proc:
    pid: int
    ppid: int
    name: str
    command: str
    user: str
    uid: int
    state: str
    threads: int
    rss: int  # bytes
    ticks: int  # utime + stime, clock ticks
    cpu: float = 0.0  # share of the whole processor, 0..100
    io: int = 0  # bytes read + written since start, when readable
    io_rate: float = 0.0  # bytes per second


@dataclass
class Gpu:
    card: str
    name: str
    busy: float  # 0..100
    vram_used: int
    vram_total: int
    temp: float | None  # °C
    power: float | None  # W


@dataclass
class Snapshot:
    when: float
    cpu: float = 0.0  # 0..100
    cores: list = field(default_factory=list)  # 0..100 each
    cpu_temp: float | None = None
    cpu_mhz: float | None = None
    mem_used: int = 0
    mem_total: int = 0
    swap_used: int = 0
    swap_total: int = 0
    gpus: list = field(default_factory=list)
    disks: dict = field(default_factory=dict)  # name: (read B/s, write B/s)
    net: tuple = (0.0, 0.0)  # down, up B/s
    procs: list = field(default_factory=list)
    uptime: float = 0.0


def _users():
    cache = {}

    def name(uid):
        if uid not in cache:
            try:
                cache[uid] = pwd.getpwuid(uid).pw_name
            except KeyError:
                cache[uid] = str(uid)
        return cache[uid]
    return name


def _cpu_times():
    """[(busy, total)] for 'cpu' then each core."""
    out = []
    for line in read(PROC / "stat").splitlines():
        if not line.startswith("cpu"):
            break
        f = list(map(int, line.split()[1:9]))
        idle = f[3] + f[4]
        out.append((sum(f) - idle, sum(f)))
    return out


def _proc(pid, user_name):
    stat = read(PROC / str(pid) / "stat")
    if not stat:
        return None
    # comm can hold spaces and brackets: split around the last ')'
    head, _, rest = stat.rpartition(")")
    comm = head.partition("(")[2]
    f = rest.split()
    if len(f) < 22:
        return None
    ppid = int(f[1])
    if ppid in HIDDEN_PARENTS or int(pid) == 2:
        return None
    cmd = read(PROC / str(pid) / "cmdline").replace("\0", " ").strip()
    status = read(PROC / str(pid) / "status")
    uid = int(re.search(r"^Uid:\s+(\d+)", status, re.M).group(1)) if "Uid:" in status else 0
    io_text = read(PROC / str(pid) / "io")
    io = sum(int(v) for k, v in re.findall(r"^(read_bytes|write_bytes):\s+(\d+)", io_text, re.M))
    return Proc(pid=int(pid), ppid=ppid, name=app_name(comm, cmd), command=cmd or f"[{comm}]",
                user=user_name(uid), uid=uid, state=f[0], threads=int(f[17]),
                rss=int(f[21]) * PAGE, ticks=int(f[11]) + int(f[12]), io=io)


def app_name(comm, cmd):
    """What people call the program: its app name from the .desktop files, else the script for
    interpreters, else the program file. Grouping by the program (not comm) keeps Firefox's tabs
    ("Isolated Web Co") and Electron helpers with their app."""
    words = cmd.split()
    if not words:
        return comm
    exe = Path(words[0]).name
    if re.fullmatch(r"python[\d.]*|bash|sh|node|java|perl|ruby", exe) and len(words) > 1:
        script = next((w for w in words[1:] if not w.startswith("-")), "")
        if script:
            exe = Path(script).name
    return apps().get(exe, (exe or comm,))[0]


_APPS = None


def apps():
    """{program file name: (app name, icon)} from the installed .desktop files."""
    global _APPS
    if _APPS is None:
        _APPS = {}
        dirs = [Path.home() / ".local/share/applications", Path("/usr/share/applications"),
                Path("/var/lib/flatpak/exports/share/applications")]
        for d in dirs:
            for f in sorted(d.glob("*.desktop")) if d.is_dir() else []:
                text = read(f)
                if re.search(r"^NoDisplay=true", text, re.M):
                    continue
                name = re.search(r"^Name=(.+)$", text, re.M)
                exe = re.search(r"^Exec=(\S+)", text, re.M)
                icon = re.search(r"^Icon=(.+)$", text, re.M)
                if name and exe:
                    key = Path(exe.group(1).strip('"')).name
                    if key not in ("env", "sh", "bash", "flatpak", "python3") and key not in _APPS:
                        _APPS[key] = (name.group(1).strip(), icon.group(1).strip() if icon else "")
    return _APPS


def pci_name(vendor, device):
    """Marketing name from the PCI ID database (the same lookup as hub_system.pci_name)."""
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


def _gpus():
    out = []
    for dev in sorted((SYS / "class/drm").glob("card[0-9]")):
        d = dev / "device"
        busy = read(d / "gpu_busy_percent").strip()
        if not busy:
            continue  # not amdgpu (or no busy counter): nothing honest to show
        hw = next(iter(sorted((d / "hwmon").glob("hwmon*"))), None)
        temp = read(hw / "temp1_input").strip() if hw else ""
        power = (read(hw / "power1_average") or read(hw / "power1_input")).strip() if hw else ""
        name = (read(d / "product_name").strip() or pci_name(read(d / "vendor").strip(), read(d / "device").strip())
                or "Graphics card")
        out.append(Gpu(card=dev.name, name=name, busy=float(busy),
                       vram_used=int(read(d / "mem_info_vram_used") or 0),
                       vram_total=int(read(d / "mem_info_vram_total") or 0),
                       temp=int(temp) / 1000 if temp else None,
                       power=int(power) / 1e6 if power else None))
    # NVIDIA's driver has no such sysfs files: its cards come from NVML (gpu/nvml.py)
    for i, d in enumerate(_nvidia()):
        out.append(Gpu(card=f"nvidia{i}", name=d["name"], busy=d["busy"] or 0.0, vram_used=d["vram_used"],
                       vram_total=d["vram_total"], temp=d["temp"], power=d["power"]))
    # The real card first: the one with the most video memory
    return sorted(out, key=lambda g: -g.vram_total)


def _nvidia():
    if os.environ.get("DECKOS_SYS"):  # a test's fake tree: no real driver
        return []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gpu"))
        import nvml
        return nvml.devices()
    except ImportError:
        return []


def _cpu_temp():
    for hw in sorted((SYS / "class/hwmon").glob("hwmon*")):
        if read(hw / "name").strip() in ("k10temp", "coretemp", "zenpower"):
            t = read(hw / "temp1_input").strip()
            return int(t) / 1000 if t else None
    return None


def _disks():
    out = {}
    for line in read(PROC / "diskstats").splitlines():
        f = line.split()
        if len(f) < 10:
            continue
        name = f[2]
        # whole disks only (nvme0n1, sda), not partitions, loops or zram
        if re.fullmatch(r"nvme\d+n\d+|sd[a-z]+|vd[a-z]+|mmcblk\d+", name):
            out[name] = (int(f[5]) * 512, int(f[9]) * 512)
    return out


def _net():
    down = up = 0
    for line in read(PROC / "net/dev").splitlines()[2:]:
        name, _, data = line.partition(":")
        if name.strip() == "lo":
            continue
        f = data.split()
        if len(f) >= 9:
            down += int(f[0])
            up += int(f[8])
    return down, up


class Sampler:
    """Call sample() about once a second; each Snapshot carries rates since the previous one."""

    def __init__(self):
        self.prev = None
        self.prev_procs = {}
        self.prev_disks = {}
        self.prev_net = None
        self.user_name = _users()

    def sample(self, with_procs=True):
        now = time.monotonic()
        snap = Snapshot(when=now)
        cpu = _cpu_times()
        if self.prev and cpu:
            pct = []
            for (b, t), (pb, pt) in zip(cpu, self.prev[1]):
                pct.append(100 * (b - pb) / (t - pt) if t > pt else 0.0)
            snap.cpu, snap.cores = pct[0], pct[1:]
        total_delta = (cpu[0][1] - self.prev[1][0][1]) if self.prev and cpu else 0

        mem = dict((k, int(v) * 1024) for k, v in re.findall(r"^(\w+):\s+(\d+) kB", read(PROC / "meminfo"), re.M))
        snap.mem_total = mem.get("MemTotal", 0)
        snap.mem_used = snap.mem_total - mem.get("MemAvailable", 0)
        snap.swap_total = mem.get("SwapTotal", 0)
        snap.swap_used = snap.swap_total - mem.get("SwapFree", 0)
        snap.cpu_temp = _cpu_temp()
        mhz = re.findall(r"^cpu MHz\s*:\s*([\d.]+)", read(PROC / "cpuinfo"), re.M)
        snap.cpu_mhz = sum(map(float, mhz)) / len(mhz) if mhz else None
        snap.gpus = _gpus()
        up = read(PROC / "uptime").split()
        snap.uptime = float(up[0]) if up else 0.0

        dt = now - self.prev[0] if self.prev else 0
        disks = _disks()
        if dt > 0:
            snap.disks = {n: ((r - self.prev_disks[n][0]) / dt, (w - self.prev_disks[n][1]) / dt)
                          for n, (r, w) in disks.items() if n in self.prev_disks}
        self.prev_disks = disks
        net = _net()
        if dt > 0 and self.prev_net:
            snap.net = ((net[0] - self.prev_net[0]) / dt, (net[1] - self.prev_net[1]) / dt)
        self.prev_net = net

        if with_procs:
            procs = {}
            for entry in PROC.iterdir():
                if entry.name.isdigit():
                    p = _proc(entry.name, self.user_name)
                    if p:
                        old = self.prev_procs.get(p.pid)
                        if old and total_delta > 0:
                            p.cpu = 100 * max(0, p.ticks - old.ticks) / total_delta
                            p.io_rate = max(0, p.io - old.io) / dt if dt > 0 else 0.0
                        procs[p.pid] = p
            self.prev_procs = procs
            snap.procs = list(procs.values())
        self.prev = (now, cpu)
        return snap


def group(procs):
    """{app name: [Proc]} for the Processes list: one row per app, its processes inside."""
    out = {}
    for p in procs:
        out.setdefault(p.name, []).append(p)
    return out


def stop(pid, force=False):
    """Ends a process of this user. Returns '' or why it couldn't. Other users' go through pkexec
    (the window does that, so the password prompt is the system's own)."""
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        return ""
    except ProcessLookupError:
        return "It had already closed."
    except PermissionError:
        return "permission"


def size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") or n >= 100 else f"{n:.1f} {unit}"
        n /= 1000
    return ""


def gib(n):
    return f"{n / 1073741824:.1f} GB"


def mode(path=None):
    """DecKoOS's workload mode (deckos mode writes it): {"mode": "gaming", "game": ..., "vram": bytes freed, ...} while
    a game runs, {"mode": "normal"} otherwise."""
    f = Path(path or os.environ.get("DECKOS_MODE_FILE") or
             Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "deckos-mode")
    out = {"mode": "normal"}
    try:
        for line in f.read_text().splitlines():
            k, sep, v = line.partition("=")
            if sep:
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out
