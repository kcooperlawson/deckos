"""DecKoOS Disks: every disk and partition, and whether the drives meant to mount at start-up actually will.

The start-up check looks at each fstab entry and each data partition: is the drive there, does fstab name the right
file system, does the mount point exist, did it mount at this start-up (and if not, why: marked dirty, Windows
hibernated, a wrong option), will start-up wait for it if it's unplugged. Adding a drive to start-up test-mounts it
before the entry is kept, so DecKoOS never writes an entry that wouldn't mount.

Reading needs no root (lsblk, /etc/fstab, findmnt, systemd, the kernel log). Changes do: `deckos disks startup add|
remove`, `repair`, `health` run as root (pkexec from the app). Entries DecKoOS adds go in the same managed block of
/etc/fstab as `deckos drives`; entries outside it (the installer's /, /home, EFI) are shown but never changed.
No Qt.

Partition editing (format, create, delete, resize) runs as root too, under the installer's safety rules: never a
partition that's mounted, in fstab, the system, EFI, Windows' own, BitLocker/LUKS/RAID/LVM; never a table change on
the disk DecKoOS runs from; every change names the partition (--confirm, its label or name) and the disk as the app
saw it (--layout, its fingerprint), and is refused if either doesn't match. The table is saved before it's changed.

    disks.py list [--json] | verify
    disks.py startup add UUID | startup remove UUID | repair UUID | health     (as root)
    disks.py format PATH FS LABEL | delete PATH | resize PATH BYTES  --confirm NAME --layout FP     (as root)
    disks.py create DISK START BYTES FS LABEL --layout FP     (as root)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

FSTAB = Path(os.environ.get("DECKOS_FSTAB") or "/etc/fstab")
BEGIN = "# >>> DeckOS drives (managed by 'deckos drives rescan') >>>"
END = "# <<< DeckOS drives <<<"
HEALTH = Path(os.environ.get("DECKOS_DISKS_HEALTH") or "/var/lib/deckos/disks/health.json")
MNT = Path(os.environ.get("DECKOS_MNT") or "/mnt")
GOOD, WARN, BAD, INFO = "good", "warn", "bad", "info"
# File systems DecKoOS can set up to mount at start-up, and the type fstab names them by
MOUNTABLE = {"ntfs": "ntfs3", "exfat": "exfat", "vfat": "vfat", "ext4": "ext4", "ext3": "ext3", "btrfs": "btrfs",
             "xfs": "xfs", "f2fs": "f2fs"}
SAME_FS = {"ntfs3": "ntfs", "ntfs-3g": "ntfs", "ntfs": "ntfs", "fuseblk": "ntfs"}
SYSTEM_TARGETS = ("/", "/home", "/boot", "/boot/efi", "/efi", "/var", "/var/log", "/.snapshots", "/var/cache/pacman/pkg")
TABLES = Path(os.environ.get("DECKOS_DISKS_TABLES") or "/var/lib/deckos/disks/tables")  # partition tables before a change
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
try:
    import pulse  # the DecKoOS timeline (absent in an old checkout: then changes just aren't recorded)
except ImportError:
    pulse = None


def run(cmd, timeout=20, input=None):
    """(exit code, stdout + stderr when it fails). Missing programs and timeouts are failures, never exceptions
    (tests replace this). `input` goes to its stdin (sfdisk scripts, ntfsresize's "are you sure")."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input)
        return r.returncode, r.stdout if r.returncode == 0 else r.stdout + r.stderr
    except (OSError, subprocess.SubprocessError):
        return 127, ""


# ------------------------------------------------------------------ what's there

@dataclass
class Part:
    name: str
    path: str
    size: int
    start: int  # bytes from the start of the disk
    fstype: str = ""
    label: str = ""
    uuid: str = ""
    partuuid: str = ""
    ptype: str = ""  # the partition type's name ("Microsoft basic data", "EFI System")
    mountpoints: list = field(default_factory=list)
    used: int = 0
    avail: int = 0
    number: int = 0  # its number in the table (sdb2: 2)
    guid: str = ""  # the partition type itself: a GUID on GPT, "0x7" on MBR

    @property
    def role(self):
        """What it's for, in a word: system, efi, swap, windows, recovery, reserved or data."""
        mps = set(self.mountpoints)
        if mps & {"/", "/home"}:
            return "system"
        if "EFI" in self.ptype or self.guid in (ESP, "0xef") or mps & {"/boot/efi", "/efi", "/boot"}:  # also Ventoy's and other USB sticks' boot part
            return "efi"
        if self.fstype == "swap" or "[SWAP]" in mps:
            return "swap"
        if "recovery" in self.ptype.lower() or self.guid in (RECOVERY, "0x27"):
            return "recovery"
        if ("reserved" in self.ptype.lower() or self.guid == MSR) and not self.fstype:
            return "reserved"
        if self.fstype == "ntfs" and any((Path(m) / "Windows/System32").is_dir() for m in self.mountpoints):
            return "windows"
        return "data"

    @property
    def mountable(self):
        # Under 100 MB is a boot or tool partition, not somewhere to keep files
        return self.fstype in MOUNTABLE and self.role in ("data", "windows") and self.size >= 100e6


@dataclass
class Disk:
    name: str
    path: str
    size: int
    model: str = ""
    tran: str = ""  # nvme, sata, usb
    rotational: bool = False
    removable: bool = False
    table: str = ""  # gpt, dos
    parts: list = field(default_factory=list)
    temp: float = 0.0
    sector: int = 512  # logical sector size: the unit of partition tables
    fstype: str = ""  # a file system straight on the disk, without a table

    @property
    def kind(self):
        if self.tran == "usb" or self.removable:
            return "usb"
        return "hdd" if self.rotational else "nvme" if self.tran == "nvme" else "ssd"

    def layout(self):
        """The disk from start to end: ("part", Part) and ("free", Free) in order. Gaps under 16 MiB are alignment.
        Free space starts and ends on a MiB, past the table at the start and GPT's backup copy at the end."""
        out, pos = [], MiB
        for p in sorted(self.parts, key=lambda p: p.start):
            gap = Free(-(-pos // MiB) * MiB, 0)
            gap.size = (p.start - gap.start) // MiB * MiB
            if gap.size >= 16 << 20:
                out.append(("free", gap))
            out.append(("part", p))
            pos = max(pos, p.start + p.size)
        gap = Free(-(-pos // MiB) * MiB, 0)
        gap.size = (self.size - 33 * self.sector - gap.start) // MiB * MiB
        if gap.size >= 16 << 20:
            out.append(("free", gap))
        return out

    def room_after(self, part):
        """Bytes of free space straight after a partition: what it can grow into."""
        layout = self.layout()
        for i, (kind, item) in enumerate(layout):
            if item is part:
                nxt = layout[i + 1] if i + 1 < len(layout) else None
                if nxt and nxt[0] == "free":
                    return nxt[1].start + nxt[1].size - (part.start + part.size)
        return 0


@dataclass
class Free:
    start: int  # bytes from the start of the disk
    size: int


MiB = 1 << 20
ESP, MSR = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "e3c9e316-0b5c-4db8-817d-f92df00215ae"
RECOVERY = "de94bba4-06d1-4d40-a16a-bfd50179d6ac"
LSBLK = "NAME,PATH,TYPE,SIZE,START,LOG-SEC,FSTYPE,LABEL,UUID,PARTUUID,PARTTYPENAME,MOUNTPOINTS,MODEL,TRAN,RM,ROTA," \
        "FSAVAIL,FSUSED,PTTYPE,PARTN,PARTTYPE"


def inventory(text=None):
    """The disks (not loop, zram or optical ones) with their partitions. NAME is a column on purpose: without it
    util-linux 2.42's lsblk doesn't nest partitions under their disk."""
    if text is None:
        _, text = run(["lsblk", "-J", "-b", "-o", LSBLK])
    try:
        devices = json.loads(text or "{}").get("blockdevices", [])
    except ValueError:
        return []
    disks = []
    for d in devices:
        if d.get("type") != "disk" or re.match(r"(zram|loop|sr|ram)", d.get("name", "")):
            continue
        sector = int(d.get("log-sec") or 512)
        disk = Disk(d["name"], d.get("path") or f"/dev/{d['name']}", int(d.get("size") or 0),
                    (d.get("model") or "").strip(), d.get("tran") or "", bool(d.get("rota")), bool(d.get("rm")),
                    d.get("pttype") or "", temp=_temp(d["name"]), sector=sector, fstype=d.get("fstype") or "")
        for c in d.get("children") or []:
            if c.get("type") != "part":
                continue
            disk.parts.append(Part(c["name"], c.get("path") or f"/dev/{c['name']}", int(c.get("size") or 0),
                                   int(c.get("start") or 0) * sector, c.get("fstype") or "", c.get("label") or "",
                                   c.get("uuid") or "", c.get("partuuid") or "", c.get("parttypename") or "",
                                   [m for m in (c.get("mountpoints") or []) if m], int(c.get("fsused") or 0),
                                   int(c.get("fsavail") or 0), int(c.get("partn") or 0),
                                   (c.get("parttype") or "").lower()))
        disks.append(disk)
    return disks


def _temp(name):
    """°C from the kernel's own sensors (NVMe always; SATA when the drivetemp module is loaded), else 0."""
    for pattern in (f"/sys/block/{name}/device/hwmon/hwmon*/temp1_input",
                    f"/sys/class/nvme/{re.sub(r'n\d+$', '', name)}/hwmon*/temp1_input"):
        for f in sorted(Path("/").glob(pattern.lstrip("/"))):
            try:
                return int(f.read_text()) / 1000
            except (OSError, ValueError):
                pass
    return 0.0


# ------------------------------------------------------------------ fstab

@dataclass
class Entry:
    spec: str  # UUID=…, LABEL=…, PARTUUID=…, /dev/…
    target: str
    fstype: str
    options: list
    line: int
    managed: bool  # inside DecKoOS's block: DecKoOS may change it

    @property
    def nofail(self):
        return "nofail" in self.options

    @property
    def automount(self):
        return "x-systemd.automount" in self.options


def fstab(text=None):
    if text is None:
        try:
            text = FSTAB.read_text()
        except OSError:
            return []
    out, inside = [], False
    for i, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if line == BEGIN:
            inside = True
        elif line == END:
            inside = False
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if len(f) < 4:
            continue
        out.append(Entry(f[0], f[1].replace("\\040", " "), f[2], f[3].split(","), i, inside))
    return out


def resolve(entry, disks):
    """The partition an entry names, or None (not connected, or not a disk at all)."""
    key, _, value = entry.spec.partition("=")
    for d in disks:
        for p in d.parts:
            if (key == "UUID" and p.uuid == value) or (key == "PARTUUID" and p.partuuid == value) \
                    or (key == "LABEL" and p.label == value) or entry.spec == p.path:
                return p
    return None


# ------------------------------------------------------------------ will it mount at start-up?

@dataclass
class Check:
    target: str  # the mount point (or the partition's path when it has none)
    part: str  # the partition's path, or ""
    state: str  # good, warn, bad, info
    title: str
    text: str
    fix: str = ""  # an action id the app offers: repair, add, remove, edit
    managed: bool = False


def context():
    """What this boot says: mounted targets, failed mount units, automounts waiting, and the kernel's NTFS complaints."""
    _, mounts = run(["findmnt", "-rn", "-o", "TARGET,OPTIONS"])
    mounted = {}
    for line in mounts.splitlines():
        t, _, o = line.partition(" ")
        mounted[t.replace("\\x20", " ")] = o.split(",")
    _, failed = run(["systemctl", "--failed", "--plain", "--no-legend", "--type=mount,automount"])
    _, kernel = run(["journalctl", "-k", "-b", "--no-pager", "-o", "cat"])
    return {"mounted": mounted, "failed": {line.split()[0] for line in failed.splitlines() if line.split()},
            "kernel": [l for l in kernel.splitlines() if l.startswith("ntfs3(")]}


def unit(target):
    """mnt-BIG.mount for /mnt/BIG (systemd's path escaping)."""
    t = target.strip("/")
    if not t:
        return "-.mount"  # the root file system
    t = re.sub(r"[^A-Za-z0-9:_./]", lambda m: "".join(f"\\x{b:02x}" for b in m.group().encode()), t)  # "-" too
    return t.replace("/", "-") + ".mount"


def startup(disks, entries, ctx):
    """[Check] for every fstab entry on a disk, and every data partition that isn't in fstab. Worst first."""
    checks = []
    in_fstab = set()
    for e in entries:
        if e.fstype in ("swap", "tmpfs", "proc", "none") or e.target in ("none", "swap"):
            continue
        p = resolve(e, disks)
        if p:
            in_fstab.add(p.path)
        name = e.target
        mounted = ctx["mounted"].get(e.target)
        u = unit(e.target)
        failed = u in ctx["failed"] or u.replace(".mount", ".automount") in ctx["failed"]
        if p is None:
            if e.nofail:
                checks.append(Check(name, "", INFO, f"{name}: not connected",
                                    "Its drive isn't plugged in. Start-up skips it (nofail) and it mounts when it's back.",
                                    "remove" if e.managed else "", e.managed))
            else:
                checks.append(Check(name, "", BAD, f"{name}: start-up waits for a drive that isn't there",
                                    "Its drive isn't connected and the entry has no nofail, so start-up waits 90 seconds "
                                    "for it, then may stop in emergency mode.", "remove" if e.managed else "", e.managed))
            continue
        want = SAME_FS.get(e.fstype, e.fstype)
        have = SAME_FS.get(p.fstype, p.fstype)
        kname = Path(p.path).name
        if e.fstype != "auto" and want != have:
            checks.append(Check(name, p.path, BAD, f"{name}: fstab names the wrong file system",
                                f"fstab says {e.fstype}, but the drive is {p.fstype or 'not formatted'}: it can't mount.",
                                "edit" if e.managed else "", e.managed))
        elif any(l.startswith(f"ntfs3({kname}):") and "hiber" in l.lower() for l in ctx["kernel"]) and not mounted:
            checks.append(Check(name, p.path, WARN, f"{name}: held by Windows",
                                "Windows saved its session on it (Fast Startup or hibernation). Start Windows, run "
                                "powercfg /h off as Administrator, then Shut Down.", "", e.managed))
        elif any(l.startswith(f"ntfs3({kname}): volume is dirty") for l in ctx["kernel"]) and not mounted:
            checks.append(Check(name, p.path, BAD, f"{name}: marked dirty, so it won't mount",
                                "The PC was cut off while it was in use. Until the mark is cleared it fails at every "
                                "start. Repair clears it; run chkdsk /f on it in Windows when you can.", "repair", e.managed))
        elif failed and not mounted:
            _, why = run(["journalctl", "-b", "-u", u, "-n", "3", "--no-pager", "-o", "cat"])
            checks.append(Check(name, p.path, BAD, f"{name} didn't mount at this start-up",
                                (why.strip().splitlines() or ["systemd gave no reason"])[-1], "repair", e.managed))
        elif not mounted and not e.automount and "noauto" not in e.options and not Path(e.target).is_dir():
            checks.append(Check(name, p.path, BAD, f"{name}: its folder is missing",
                                f"{e.target} doesn't exist, so there's nowhere to mount it.", "repair", e.managed))
        elif mounted and "ro" in mounted and "ro" not in e.options:
            checks.append(Check(name, p.path, WARN, f"{name} is read-only",
                                "It mounted, but only for reading: usually Windows Fast Startup, or errors the file "
                                "system found. Files can't be saved there.", "", e.managed))
        elif p and not e.nofail and e.target not in SYSTEM_TARGETS and _external(p, disks):
            checks.append(Check(name, p.path, WARN, f"{name}: start-up waits for it when it's unplugged",
                                "It's an external drive without nofail: unplugged, start-up waits 90 seconds for it.",
                                "edit" if e.managed else "", e.managed))
        elif mounted or e.automount:
            checks.append(Check(name, p.path, GOOD, f"{name} mounts at start-up",
                                "Mounted now." if mounted and "autofs" not in ",".join(mounted)
                                else "Mounts the first time something opens it.", "remove" if e.managed else "", e.managed))
        else:
            checks.append(Check(name, p.path, WARN, f"{name} isn't mounted",
                                "It's in fstab but isn't mounted now (noauto, or unmounted since start-up).", "", e.managed))
    for d in disks:
        for p in d.parts:
            if p.mountable and p.path not in in_fstab and p.role == "data":
                where = f" (mounted at {p.mountpoints[0]} for now)" if p.mountpoints else ""
                checks.append(Check(p.mountpoints[0] if p.mountpoints else p.path, p.path, INFO,
                                    f"{p.label or p.name}: not set to mount at start-up",
                                    f"{p.fstype} · {size(p.size)}{where}. Mount at start-up makes it appear in the same "
                                    "place after every restart.", "add"))
    order = {BAD: 0, WARN: 1, INFO: 2, GOOD: 3}
    return sorted(checks, key=lambda c: order[c.state])


def _external(part, disks):
    return any(part in d.parts and d.kind == "usb" for d in disks)


# ------------------------------------------------------------------ health (SMART, read by root, kept for everyone)

def health_cache():
    try:
        return json.loads(HEALTH.read_text())
    except (OSError, ValueError):
        return {}


def health_of(report):
    """{"state", "text", "hours", "temp", "wear"} from smartctl -j -a, in plain words."""
    passed = (report.get("smart_status") or {}).get("passed")
    attrs = {a.get("id"): (a.get("raw") or {}).get("value", 0)
             for a in (report.get("ata_smart_attributes") or {}).get("table", [])}
    nvme = report.get("nvme_smart_health_information_log") or {}
    worn = nvme.get("percentage_used")
    bad_sectors = attrs.get(5, 0) + attrs.get(197, 0) + attrs.get(198, 0)
    out = {"hours": (report.get("power_on_time") or {}).get("hours"),
           "temp": (report.get("temperature") or {}).get("current"), "wear": worn}
    if passed is False:
        out.update(state=BAD, text="The drive reports it's failing: copy what matters off it now")
    elif bad_sectors:
        out.update(state=WARN, text=f"{bad_sectors} damaged or waiting sectors: keep a backup, watch if it grows")
    elif worn is not None and worn >= 90:
        out.update(state=WARN, text=f"{worn}% of its rated writes used")
    elif passed:
        out.update(state=GOOD, text="Healthy")
    else:
        out.update(state=INFO, text="No health report (USB enclosures often hide it)")
    return out


def refresh_health(disks):
    """As root: smartctl on every disk into HEALTH, which anyone can read (System Doctor, the app)."""
    out = {}
    for d in disks:
        code, text = run(["smartctl", "-j", "-a", d.path], timeout=60)
        try:
            out[d.path] = dict(health_of(json.loads(text)), checked=int(time.time()))
        except ValueError:
            out[d.path] = {"state": INFO, "text": "No health report", "checked": int(time.time())}
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH.write_text(json.dumps(out, indent=1))
    HEALTH.chmod(0o644)
    return out


# ------------------------------------------------------------------ changes (root)

class Refused(Exception):
    pass


def size(n):
    for unit_, step in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6)):
        if n >= step:
            return f"{n / step:.1f} {unit_}".replace(".0 ", " ")
    return f"{n} bytes"


def options_for(part, disk, uid=1000, gid=1000):
    """fstab options that mount it at every start, and never hold start-up up if it's gone."""
    base = ["nofail", "x-systemd.device-timeout=5s", "x-gvfs-show", "noatime"]
    fs = part.fstype
    if fs == "ntfs":
        opts = [f"uid={uid}", f"gid={gid}", "umask=022", "windows_names", "prealloc"] + base
    elif fs in ("exfat", "vfat"):
        opts = [f"uid={uid}", f"gid={gid}", "umask=022"] + (["utf8"] if fs == "vfat" else []) + base
    else:
        opts = ["defaults"] + base
    if disk.kind == "usb":
        opts += ["noauto", "x-systemd.automount", "x-systemd.idle-timeout=0"]
    return opts


def mount_point(part, entries):
    used = {e.target for e in entries}
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", part.label or part.name).strip("-") or part.name
    target, n = str(MNT / name), 1
    while target in used or (Path(target).exists() and any(Path(target).iterdir())):
        n += 1
        target = str(MNT / f"{name}-{n}")
    return target


def _write(text):
    shutil.copy(FSTAB, FSTAB.with_name(FSTAB.name + ".deckos-bak"))
    tmp = FSTAB.with_name(FSTAB.name + ".deckos-tmp")
    tmp.write_text(text)
    os.replace(tmp, FSTAB)


def with_entry(text, line):
    """fstab text with a line added at the end of DecKoOS's block (the block is made if there's none)."""
    lines = text.rstrip("\n").splitlines()
    if END in lines:
        lines.insert(lines.index(END), line)
    else:
        lines += ["", BEGIN, line, END]
    return "\n".join(lines) + "\n"


def without_entry(text, target):
    """fstab text without the managed entry for target (and the comment line just above it, if it has one)."""
    lines, out, inside = text.splitlines(), [], False
    for i, line in enumerate(lines):
        s = line.strip()
        inside = True if s == BEGIN else False if s == END else inside
        f = s.split()
        if inside and len(f) >= 2 and not s.startswith("#") and f[1].replace("\\040", " ") == target:
            if out and out[-1].strip().startswith("#") and out[-1].strip() != BEGIN:
                out.pop()
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def add(uuid, uid=1000, gid=1000):
    """Mount at start-up: a managed fstab entry, kept only once a test mount works. Returns the mount point."""
    disks, entries = inventory(), fstab()
    part = next((p for d in disks for p in d.parts if p.uuid == uuid), None)
    if part is None:
        raise Refused("no connected partition has that UUID")
    disk = next(d for d in disks if part in d.parts)
    if not part.mountable:
        raise Refused(f"{part.path} ({part.fstype or 'no file system'}, {part.role}) isn't a drive DecKoOS mounts")
    if any(resolve(e, disks) is part for e in entries):
        raise Refused(f"{part.path} is already in /etc/fstab")
    target = mount_point(part, entries)
    created = not Path(target).exists()
    Path(target).mkdir(parents=True, exist_ok=True)
    before = FSTAB.read_text()
    line = f"UUID={uuid}  {target.replace(' ', chr(92) + '040')}  {MOUNTABLE[part.fstype]}  " \
           f"{','.join(options_for(part, disk, uid, gid))}  0 0"
    _write(with_entry(before, f"# {part.path} ({size(part.size)}{', ' + disk.tran if disk.tran else ''})\n{line}"))
    run(["systemctl", "daemon-reload"])
    if part.mountpoints:  # mounted somewhere else (Files, udisks): moved to its place
        run(["umount", part.path])
    code, _ = run(["mount", target], timeout=60)
    if code != 0:
        _, why = run(["journalctl", "-k", "-n", "5", "--no-pager", "-o", "cat"])
        _write(before)
        run(["systemctl", "daemon-reload"])
        if created:
            try:
                Path(target).rmdir()
            except OSError:
                pass
        raise Refused("it didn't mount, so nothing was saved: " +
                      next((l for l in reversed(why.splitlines()) if Path(part.path).name in l), "the mount failed"))
    if disk.kind == "usb":  # externals wait to be opened, so being unplugged never holds start-up up
        run(["umount", target])
        run(["systemctl", "start", unit(target).replace(".mount", ".automount")])
    return target


def remove(uuid):
    disks, entries = inventory(), fstab()
    entry = next((e for e in entries if e.spec == f"UUID={uuid}"), None)
    if entry is None:
        raise Refused("that drive isn't set to mount at start-up")
    if not entry.managed:
        raise Refused(f"{entry.target} was set up outside DecKoOS (the installer or by hand): it's left as it is")
    if entry.target in SYSTEM_TARGETS:
        raise Refused(f"{entry.target} is part of the system")
    u = unit(entry.target)
    run(["systemctl", "stop", u.replace(".mount", ".automount")])
    code, _ = run(["umount", entry.target])
    if code != 0 and entry.target in context()["mounted"]:
        raise Refused(f"{entry.target} is in use: close what's open on it first")
    _write(without_entry(FSTAB.read_text(), entry.target))
    run(["systemctl", "daemon-reload"])
    try:
        Path(entry.target).rmdir()  # only if empty
    except OSError:
        pass
    return entry.target


def repair(uuid):
    """Whatever stops it mounting that DecKoOS can safely fix: NTFS's dirty mark (deckos drives repair), a missing
    folder, or a file system check of an unmounted Linux, exFAT or FAT drive."""
    disks, entries = inventory(), fstab()
    part = next((p for d in disks for p in d.parts if p.uuid == uuid), None)
    if part is None:
        raise Refused("no connected partition has that UUID")
    entry = next((e for e in entries if resolve(e, disks) is part), None)
    done = []
    if entry and not Path(entry.target).exists():
        Path(entry.target).mkdir(parents=True)
        done.append(f"made {entry.target}")
    if part.fstype == "ntfs":
        code, _ = run(["deckos", "drives", "repair"], timeout=300)
        done.append("cleared the dirty mark" if code == 0 else "deckos drives repair couldn't finish")
    elif not part.mountpoints and part.fstype in ("ext4", "ext3", "exfat", "vfat"):
        tool = {"ext4": ["e2fsck", "-p"], "ext3": ["e2fsck", "-p"], "exfat": ["fsck.exfat", "-p"],
                "vfat": ["fsck.vfat", "-a"]}[part.fstype]
        code, _ = run(tool + [part.path], timeout=1800)
        done.append("checked and repaired the file system" if code in (0, 1) else f"{tool[0]} found errors it couldn't fix")
    if entry:
        u = unit(entry.target)
        run(["systemctl", "reset-failed", u, u.replace(".mount", ".automount")])
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "restart", u.replace(".mount", ".automount")] if entry.automount else ["mount", entry.target])
    return done or ["nothing to repair"]


# ------------------------------------------------------------------ partition editing (root)

# What DecKoOS formats with: the tool, the longest label it takes, and the partition type it gets (GPT, MBR)
BASIC_DATA, LINUX_FS = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", "0fc63daf-8483-4772-8e79-3d69d8477de4"
FORMATS = {
    "ext4": ("Linux (ext4)", 16, LINUX_FS, "83"),
    "btrfs": ("Linux (btrfs)", 64, LINUX_FS, "83"),
    "ntfs": ("Windows and Linux (NTFS)", 32, BASIC_DATA, "7"),
    "exfat": ("Any computer (exFAT)", 15, BASIC_DATA, "7"),
    "vfat": ("Old devices (FAT32)", 11, BASIC_DATA, "c"),
}
RESIZABLE = ("ext4", "ext3", "ntfs")  # resized unmounted with their own tools; btrfs and XFS only resize mounted
MIN_PART = 64 * MiB
LONG = 6 * 3600  # an NTFS resize on a full hard drive takes a while


def mkfs(path, fs, label):
    return {"ext4": ["mkfs.ext4", "-F", "-q"] + (["-L", label] if label else []),
            "btrfs": ["mkfs.btrfs", "-f", "-q"] + (["-L", label] if label else []),
            "ntfs": ["mkfs.ntfs", "-Q", "-F", "-q"] + (["-L", label] if label else []),
            "exfat": ["mkfs.exfat"] + (["-L", label] if label else []),
            "vfat": ["mkfs.fat", "-F", "32"] + (["-n", label.upper()] if label else [])}[fs] + [path]


def check_label(fs, label):
    if fs not in FORMATS:
        raise Refused(f"DecKoOS formats as {', '.join(FORMATS)}, not {fs}. Nothing was changed.")
    if label and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]*", label):
        raise Refused("a name can have letters, numbers, spaces, dots, dashes and underscores. Nothing was changed.")
    if len(label) > FORMATS[fs][1]:
        raise Refused(f"{fs} names are {FORMATS[fs][1]} characters at most. Nothing was changed.")
    return label.upper() if fs == "vfat" else label


def fingerprint(disk):
    """The disk as the app saw it: a change refuses unless the disk is still exactly this."""
    import hashlib
    parts = sorted((p.name, p.start, p.size, p.fstype, p.uuid, p.label) for p in disk.parts)
    return hashlib.sha256(repr((disk.path, disk.size, disk.table, disk.fstype, parts)).encode()).hexdigest()[:16]


def confirm_word(part):
    """What a person types to confirm a change to it."""
    return part.label or part.name


def runs_system(disk):
    return any(set(p.mountpoints) & set(SYSTEM_TARGETS) for p in disk.parts)


def why_not(part, disk, entries, action):
    """Why DecKoOS won't format, delete or resize this partition, in a sentence; "" when it may.
    The root command asks again on a fresh read, and then also looks inside NTFS for Windows."""
    fs, mps = part.fstype, part.mountpoints
    if fs == "BitLocker":
        return "BitLocker-encrypted, so DecKoOS can't see what's on it. Turn BitLocker off in Windows first."
    if fs == "crypto_LUKS":
        return "Encrypted (LUKS), so DecKoOS can't see what's on it: it's left as it is."
    if fs.endswith("_member"):
        return "Part of a RAID, LVM or ZFS set: changing it would break the whole set."
    reason = {"system": "It holds DecKoOS itself.", "efi": "The boot (EFI) partition: the PC starts from it.",
              "reserved": "Windows keeps this space for itself.", "recovery": "Windows keeps its repair tools here.",
              "windows": "It holds Windows.", "swap": "It's swap: overflow for memory."}.get(part.role)
    if reason:
        return reason
    if mps:
        return f"It's mounted at {mps[0]}: unmount it first."
    entry = next((e for e in entries if resolve(e, [disk]) is part), None)
    if entry:
        return (f"It's set to mount at start-up ({entry.target}): choose Don't mount at start-up first." if entry.managed
                else f"/etc/fstab mounts it at {entry.target} (set up outside DecKoOS): take it out of fstab first.")
    if any(p.label == "Ventoy" for p in disk.parts):
        return "It's a Ventoy stick: change it with Ventoy."
    if part.guid in ("0x5", "0xf", "0x85") or (disk.table == "dos" and part.number > 4):
        return "It's an extended or logical partition: DecKoOS only changes primary ones."
    if action in ("delete", "resize"):
        if runs_system(disk):
            return "This disk holds the running DecKoOS: its partition table isn't changed while DecKoOS runs from it."
        if disk.table not in ("gpt", "dos") or not part.number:
            return "DecKoOS can't read this disk's partition table."
    if action == "resize" and fs not in RESIZABLE:
        return (f"{fs or 'An empty partition'} can't be resized here: DecKoOS resizes ext4 and NTFS. "
                "Copy the files off, delete it and make a bigger one.")
    return ""


def why_not_create(disk):
    if runs_system(disk):
        return "This disk holds the running DecKoOS: its partition table isn't changed while DecKoOS runs from it."
    if any(p.label == "Ventoy" for p in disk.parts):
        return "It's a Ventoy stick: change it with Ventoy."
    if disk.table == "dos":
        return "This disk uses the older MBR layout: DecKoOS only adds partitions to GPT disks."
    if not disk.table and (disk.parts or disk.fstype):
        return f"It holds a file system ({disk.fstype or 'unknown'}) with no partition table: DecKoOS leaves it as it is."
    if disk.table not in ("gpt", ""):
        return "DecKoOS can't read this disk's partition table."
    return ""


def _fresh(path, layout):
    """The partition (or disk) at path and its disk, read again now, and refused if the disk changed."""
    disks = inventory()
    for d in disks:
        part = next((p for p in d.parts if p.path == path), None)
        if part or d.path == path:
            if layout != fingerprint(d):
                raise Refused(f"{d.path} changed since you looked at it: refresh and try again. Nothing was changed.")
            return part, d
    raise Refused(f"{path} isn't connected. Nothing was changed.")


def _checked(path, action, confirm, layout):
    part, disk = _fresh(path, layout)
    if part is None:
        raise Refused(f"{path} is a disk, not a partition. Nothing was changed.")
    if confirm != confirm_word(part):
        raise Refused(f"type {confirm_word(part)} to confirm. Nothing was changed.")
    why = why_not(part, disk, fstab(), action)
    if not why and part.fstype == "ntfs":
        why = _windows_inside(part)
    if why:
        raise Refused(f"{why} Nothing was changed.")
    return part, disk


def _windows_inside(part):
    """Mounts an NTFS partition read-only to see whether it holds Windows (or its boot files). One that won't mount
    can't be checked, so it's refused, like the installer does."""
    where = tempfile.mkdtemp(prefix="deckos-disks-")
    try:
        if run(["mount", "-t", "ntfs3", "-o", "ro", part.path, where], timeout=60)[0] != 0:
            return ("It won't mount, so DecKoOS can't check that it isn't Windows (Windows hibernated or it needs "
                    "chkdsk /f): start Windows and shut it down fully, or Repair it.")
        try:
            inside = {x.lower() for x in os.listdir(where)}
            if "windows" in inside and (Path(where) / "Windows/System32").is_dir():
                return "It holds Windows."
            if "bootmgr" in inside:
                return "It holds Windows' boot files."
        finally:
            run(["umount", where])
        return ""
    finally:
        try:
            os.rmdir(where)
        except OSError:
            pass


def _sectors_free(disk):
    """sfdisk -F: the unused ranges now, as (first, last) sectors."""
    code, out = run(["sfdisk", "-F", disk.path])
    if code != 0:
        raise Refused(f"couldn't read {disk.path}'s free space. Nothing was changed.")
    return [(int(f[0]), int(f[1])) for f in (line.split() for line in out.splitlines())
            if len(f) >= 2 and f[0].isdigit() and f[1].isdigit()]


def _save_table(disk):
    """sfdisk --dump into TABLES before every table change: `sfdisk DISK < FILE` puts it back."""
    code, out = run(["sfdisk", "--dump", disk.path])
    if code != 0 or not out.strip():
        raise Refused(f"couldn't save {disk.path}'s partition table first, so it wasn't changed.")
    TABLES.mkdir(parents=True, exist_ok=True)
    saved = TABLES / f"{disk.name}-{time.strftime('%Y%m%d-%H%M%S')}.sfdisk"
    saved.write_text(out)
    return saved


def _settle(*cmd):
    """Tells the kernel about one partition (the disk's others may be in use) and waits for udev."""
    code, _ = run(list(cmd))
    run(["udevadm", "settle"], timeout=60)
    return code == 0


def _record(title):
    if pulse:
        try:
            pulse.emit("drives", title, app="Disks", system=True)
        except (OSError, ValueError):
            pass


def _block(path):
    return Path(path).exists()


def _uuid(path):
    return run(["blkid", "-s", "UUID", "-o", "value", path])[1].strip()


def _make_fs(path, fs, label):
    """wipefs first (an old file system's leftovers confuse blkid), then mkfs. (ok, why)"""
    run(["wipefs", "-a", path], timeout=120)
    code, out = run(mkfs(path, fs, label), timeout=1800)
    return code == 0, _last(out)


def _set_type(disk, part, fs):
    if disk.table in ("gpt", "dos") and part.number:
        run(["sfdisk", "--no-reread", "--part-type", disk.path, str(part.number),
             FORMATS[fs][2 if disk.table == "gpt" else 3]])


def _last(out):
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return lines[-1] if lines else "no reason given"


def format_part(path, fs, label, confirm, layout):
    """Erases one partition and makes a new file system on it. Returns its new UUID."""
    label = check_label(fs, label)
    part, disk = _checked(path, "format", confirm, layout)
    ok, why = _make_fs(part.path, fs, label)
    if not ok:
        raise Refused(f"formatting {part.path} as {fs} failed ({why}). It's empty now: its old files were erased "
                      "first. The partition itself is unchanged; format it again or pick another file system.")
    if not runs_system(disk):  # Windows then sees an NTFS/exFAT partition as its own, Linux ones as Linux
        _set_type(disk, part, fs)
    _settle("udevadm", "trigger", "--action=change", part.path)
    _record(f"Formatted {part.path} as {fs}" + (f" ({label})" if label else ""))
    return _uuid(part.path)


def create(disk_path, start, nbytes, fs, label, layout):
    """One new partition in free space (GPT first on an empty disk), formatted. Returns (path, UUID)."""
    label = check_label(fs, label)
    _, disk = _fresh(disk_path, layout)
    why = why_not_create(disk)
    if why:
        raise Refused(f"{why} Nothing was changed.")
    sec = disk.sector
    first = -(-int(start) // MiB) * MiB // sec  # MiB-aligned, like every partition tool
    count = (int(start) + int(nbytes) - first * sec) // MiB * MiB // sec
    if count * sec < MIN_PART:
        raise Refused(f"a new partition needs at least {size(MIN_PART)}. Nothing was changed.")
    fresh = not disk.table
    if fresh:  # nothing on it at all (no table, no file system): it gets GPT
        code, out = run(["sfdisk", "-q", "--no-reread", disk.path], input="label: gpt\n")
        if code != 0:
            raise Refused(f"couldn't write a partition table on {disk.path} ({_last(out)}). It was empty before, so "
                          "nothing was lost.")
    if not any(a <= first and first + count - 1 <= b for a, b in _sectors_free(disk)):
        raise Refused(f"that space on {disk.path} isn't free any more. "
                      + ("It has an empty partition table now; nothing else changed." if fresh else "Nothing was changed."))
    saved = _save_table(disk)
    code, out = run(["sfdisk", "-q", "--append", "--no-reread", disk.path],
                    input=f"start={first}, size={count}, type={FORMATS[fs][2]}\n")
    if code != 0:
        raise Refused(f"couldn't add the partition ({_last(out)}). " +
                      ("It has an empty partition table now; nothing else changed." if fresh else "Nothing was changed."))
    code, out = run(["sfdisk", "-J", disk.path])
    try:
        new = next(p for p in json.loads(out)["partitiontable"]["partitions"] if int(p["start"]) == first)
        node, number = new["node"], int(re.search(r"(\d+)$", new["node"]).group(1))
    except (ValueError, KeyError, StopIteration, AttributeError):
        raise Refused(f"the new partition was added to {disk.path}'s table, but DecKoOS couldn't find it again. "
                      f"Restart, then look in Disks. (The table before: {saved})")
    _settle("partx", "-a", "--nr", str(number), disk.path)
    if not _block(node):
        raise Refused(f"{node} was added to the table, but the system hasn't picked it up yet. Unplug the drive and "
                      "plug it back in (or restart), then format it in Disks.")
    ok, why = _make_fs(node, fs, label)
    if not ok:
        raise Refused(f"{node} was made, but formatting it as {fs} failed ({why}). It's an empty partition now: "
                      "format it again or delete it.")
    _settle("udevadm", "trigger", "--action=change", node)
    _record(f"New partition {node}: {size(count * sec)} {fs}" + (f" ({label})" if label else ""))
    return node, _uuid(node)


def delete(path, confirm, layout):
    """Takes one partition out of the table. Its data isn't wiped, but nothing in DecKoOS brings it back."""
    part, disk = _checked(path, "delete", confirm, layout)
    saved = _save_table(disk)
    code, out = run(["sfdisk", "-q", "--no-reread", "--delete", disk.path, str(part.number)])
    if code != 0:
        raise Refused(f"couldn't delete {part.path} ({_last(out)}). The partition table wasn't written: nothing was "
                      "changed.")
    note = "" if _settle("partx", "-d", "--nr", str(part.number), disk.path) else \
        " The system still lists it until you unplug the drive or restart."
    _record(f"Deleted {part.path} ({part.label or part.fstype or 'empty'}, {size(part.size)})")
    return f"deleted {part.path} (its table was saved in {saved}).{note}"


def _fs_min(part):
    """The smallest an ext file system can shrink to, in bytes (resize2fs -P, in its blocks), or 0 if unknown."""
    _, est = run(["resize2fs", "-P", part.path], timeout=600)
    _, head = run(["dumpe2fs", "-h", part.path])
    blocks = re.search(r"minimum size of the filesystem:\s*(\d+)", est)
    bs = re.search(r"Block size:\s*(\d+)", head)
    return int(blocks.group(1)) * int(bs.group(1)) if blocks and bs else 0


def _fs_resize(part, nbytes=None, again=False):
    """Resizes the file system to nbytes (None: fill the partition). (ok, why)"""
    if part.fstype == "ntfs":
        cmd = ["ntfsresize"] + (["-f"] if again else []) + (["-s", str(nbytes)] if nbytes else []) + [part.path]
        code, out = run(cmd, timeout=LONG, input="y\n")
    else:
        code, out = run(["resize2fs", part.path] + ([f"{nbytes // 1024}K"] if nbytes else []), timeout=LONG)
    return code == 0, _last(out)


def _table_size(disk, part, count):
    """Writes the partition's new size (same start). (written, the kernel has it too, why not)"""
    code, out = run(["sfdisk", "-q", "--no-reread", "-N", str(part.number), disk.path],
                    input=f"start={part.start // disk.sector}, size={count}\n")
    if code != 0:
        return False, False, _last(out)
    return True, _settle("partx", "-u", "--nr", str(part.number), disk.path), "the system didn't take the new size"


def resize(path, nbytes, confirm, layout):
    """Grows or shrinks one partition. Its start never moves. Shrinking: the file system first, then the table;
    growing: the table first, then the file system. A failed step undoes the one before it."""
    part, disk = _checked(path, "resize", confirm, layout)
    sec = disk.sector
    old, new = part.size // sec, int(nbytes) // MiB * MiB // sec
    if abs(new - old) * sec < MiB:
        raise Refused("that's the size it is already. Nothing was changed.")
    if new * sec < MIN_PART:
        raise Refused(f"a partition needs at least {size(MIN_PART)}. Nothing was changed.")
    first = part.start // sec
    if new > old and not any(a <= first + old and first + new - 1 <= b for a, b in _sectors_free(disk)):
        raise Refused(f"there isn't that much free space straight after {part.path}. Nothing was changed.")
    # Is the file system healthy, and will it fit? Asked before anything changes.
    if part.fstype == "ntfs":
        if new < old:
            code, out = run(["ntfsresize", "--no-action", "-s", str(new * sec), part.path], timeout=LONG)
            if code != 0:
                raise Refused(f"ntfsresize's trial run says no: {_last(out)} Nothing was changed.")
    else:
        code, out = run(["e2fsck", "-f", "-p", part.path], timeout=LONG)
        if code not in (0, 1):
            raise Refused(f"the file system has errors e2fsck can't fix by itself ({_last(out)}): Repair it first. "
                          "Nothing was changed.")
        smallest = _fs_min(part)
        if new < old and (not smallest or new * sec < smallest * 1.05 + 16 * MiB):
            raise Refused(f"it holds too much to be that small: the smallest it can be is "
                          f"{size(smallest * 1.05 + 16 * MiB) if smallest else 'unknown'}. Nothing was changed.")
    saved = _save_table(disk)
    ntfs_note = (" Windows checks it the next time it starts. Without Windows, Repair clears that mark so it mounts "
                 "here.") if part.fstype == "ntfs" else ""
    if new < old:
        ok, why = _fs_resize(part, new * sec)
        if not ok:
            raise Refused(f"shrinking the file system failed ({why}). The partition table wasn't touched; run Repair "
                          "to check the file system.")
        written, known, why = _table_size(disk, part, new)
        if written and not known:  # the file system already fits the smaller partition: safe as it is
            raise Refused(f"{part.path}'s file system and partition are {size(new * sec)} now, but the system still "
                          "sees the old size until you unplug the drive or restart. Nothing is lost.")
        if not written:  # the kernel still has the old size, so growing back fills exactly that
            back, _ = _fs_resize(part, again=True)
            raise Refused(f"couldn't change the partition table ({why}), so " +
                          ("the file system was grown back: the disk is as it was." if back else
                           f"the file system is {size(new * sec)} in a {size(part.size)} partition. Nothing is lost; "
                           "resizing it to its full size again fixes it."))
    else:
        written, known, why = _table_size(disk, part, new)
        if not written:
            raise Refused(f"couldn't change the partition table ({why}). Nothing was changed.")
        if not known:  # growing the file system now would only fill the old size: put the table back
            ok = _table_size(disk, part, old)[0]  # the kernel never left the old size
            raise Refused(f"{why}, so " + ("the partition was put back: the disk is as it was." if ok else
                                          f"the table says {size(new * sec)} but the file system is still "
                                          f"{size(part.size)}. Nothing is lost; restart and resize it again."))
        if part.fstype == "ntfs":
            code, out = run(["ntfsresize", "--no-action", part.path], timeout=LONG)
            if code != 0:
                ok = all(_table_size(disk, part, old)[:2])
                raise Refused(f"ntfsresize's trial run says no ({_last(out)}), so " +
                              ("the partition was put back: the disk is as it was." if ok else
                               f"the partition is {size(new * sec)} with a {size(part.size)} file system. Nothing is "
                               f"lost. (The table before: {saved})"))
        ok, why = _fs_resize(part)
        if not ok:
            raise Refused(f"the partition is {size(new * sec)} now, but the file system kept its old size ({why}). "
                          "Your files are fine; try again after Repair.")
    _settle("udevadm", "trigger", "--action=change", part.path)
    _record(f"Resized {part.path} from {size(part.size)} to {size(new * sec)}")
    return f"{part.path} is {size(new * sec)} now.{ntfs_note}"


# ------------------------------------------------------------------ command line

def report():
    disks, entries = inventory(), fstab()
    checks = startup(disks, entries, context())
    health = health_cache()
    return {"disks": [dict(asdict(d), kind=d.kind, health=health.get(d.path),
                           parts=[dict(asdict(p), role=p.role, mountable=p.mountable) for p in d.parts]) for d in disks],
            "checks": [asdict(c) for c in checks]}


def main(argv):
    try:
        if argv[:1] in ([], ["list"]):
            r = report()
            if "--json" in argv:
                print(json.dumps(r))
                return 0
            for d in r["disks"]:
                print(f"{d['path']}  {d['model'] or d['name']}  {size(d['size'])}  {d['kind']}")
                for p in d["parts"]:
                    print(f"    {p['path']:16} {p['fstype'] or '—':6} {size(p['size']):>9}  {p['label'] or ''}  "
                          f"{', '.join(p['mountpoints'])}")
            print()
            for c in r["checks"]:
                print(f"  [{c['state']}] {c['title']}")
            return 0
        if argv[:1] == ["verify"]:  # one line per problem: state, mount point, title (System Doctor reads it)
            for c in startup(inventory(), fstab(), context()):
                if c.state in (BAD, WARN):
                    print(f"{c.state}\t{c.target}\t{c.part}\t{c.title}\t{c.text}\t{c.fix}")
            return 0
        if os.geteuid() != 0:
            raise Refused(f"this needs root: sudo deckos disks {' '.join(argv)}")
        if argv[:2] == ["startup", "add"] and len(argv) == 3:
            uid = int(os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID") or 1000)
            import pwd
            gid = pwd.getpwuid(uid).pw_gid
            print(f"mounts at start-up: {add(argv[2], uid, gid)}")
            return 0
        if argv[:2] == ["startup", "remove"] and len(argv) == 3:
            print(f"no longer mounts at start-up: {remove(argv[2])}")
            return 0
        if argv[:1] == ["repair"] and len(argv) == 2:
            print("; ".join(repair(argv[1])))
            return 0
        opts = {}
        for flag in ("--confirm", "--layout"):  # the partition's name and the disk as the app saw it
            if flag in argv[:-1]:
                i = argv.index(flag)
                opts[flag] = argv[i + 1]
                argv = argv[:i] + argv[i + 2:]
        confirm, layout = opts.get("--confirm", ""), opts.get("--layout", "")
        if argv[:1] == ["format"] and len(argv) in (3, 4):
            uuid = format_part(argv[1], argv[2], (argv[3:] or [""])[0], confirm, layout)
            print(f"formatted {argv[1]} as {argv[2]}\nuuid {uuid}\nfs {argv[2]}")
            return 0
        if argv[:1] == ["create"] and len(argv) in (5, 6) and argv[2].isdigit() and argv[3].isdigit():
            node, uuid = create(argv[1], int(argv[2]), int(argv[3]), argv[4], (argv[5:] or [""])[0], layout)
            print(f"made {node} ({argv[4]})\nuuid {uuid}\nfs {argv[4]}")
            return 0
        if argv[:1] == ["delete"] and len(argv) == 2:
            print(delete(argv[1], confirm, layout))
            return 0
        if argv[:1] == ["resize"] and len(argv) == 3 and argv[2].isdigit():
            print(resize(argv[1], int(argv[2]), confirm, layout))
            return 0
        if argv[:1] == ["health"]:
            for path, h in refresh_health(inventory()).items():
                print(f"{path}: {h['text']}")
            return 0
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
