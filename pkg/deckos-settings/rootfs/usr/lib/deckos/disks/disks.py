"""DecKoOS Disks: every disk and partition, and whether the drives meant to mount at start-up actually will.

The start-up check looks at each fstab entry and each data partition: is the drive there, does fstab name the right
file system, does the mount point exist, did it mount at this start-up (and if not, why: marked dirty, Windows
hibernated, a wrong option), will start-up wait for it if it's unplugged. Adding a drive to start-up test-mounts it
before the entry is kept, so DecKoOS never writes an entry that wouldn't mount.

Reading needs no root (lsblk, /etc/fstab, findmnt, systemd, the kernel log). Changes do: `deckos disks startup add|
remove`, `repair`, `health` run as root (pkexec from the app). Entries DecKoOS adds go in the same managed block of
/etc/fstab as `deckos drives`; entries outside it (the installer's /, /home, EFI) are shown but never changed.
No Qt. Partition editing (create, delete, resize, format) is not here yet.

    disks.py list [--json] | verify
    disks.py startup add UUID | startup remove UUID | repair UUID | health     (as root)
"""
import json
import os
import re
import shutil
import subprocess
import sys
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


def run(cmd, timeout=20):
    """(exit code, stdout). Missing programs and timeouts are failures, never exceptions (tests replace this)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
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

    @property
    def role(self):
        """What it's for, in a word: system, efi, swap, windows, recovery, reserved or data."""
        mps = set(self.mountpoints)
        if mps & {"/", "/home"}:
            return "system"
        if "EFI" in self.ptype or mps & {"/boot/efi", "/efi", "/boot"}:  # also Ventoy's and other USB sticks' boot part
            return "efi"
        if self.fstype == "swap" or "[SWAP]" in mps:
            return "swap"
        if "recovery" in self.ptype.lower():
            return "recovery"
        if "reserved" in self.ptype.lower() and not self.fstype:
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

    @property
    def kind(self):
        if self.tran == "usb" or self.removable:
            return "usb"
        return "hdd" if self.rotational else "nvme" if self.tran == "nvme" else "ssd"

    def layout(self):
        """The disk from start to end: ("part", Part) and ("free", bytes) in order. Gaps under 16 MiB are alignment."""
        out, pos = [], 0
        for p in sorted(self.parts, key=lambda p: p.start):
            if p.start - pos >= 16 << 20:
                out.append(("free", p.start - pos))
            out.append(("part", p))
            pos = max(pos, p.start + p.size)
        if self.size - pos >= 16 << 20:
            out.append(("free", self.size - pos))
        return out


LSBLK = "NAME,PATH,TYPE,SIZE,START,LOG-SEC,FSTYPE,LABEL,UUID,PARTUUID,PARTTYPENAME,MOUNTPOINTS,MODEL,TRAN,RM,ROTA," \
        "FSAVAIL,FSUSED,PTTYPE"


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
                    d.get("pttype") or "", temp=_temp(d["name"]))
        for c in d.get("children") or []:
            if c.get("type") != "part":
                continue
            disk.parts.append(Part(c["name"], c.get("path") or f"/dev/{c['name']}", int(c.get("size") or 0),
                                   int(c.get("start") or 0) * sector, c.get("fstype") or "", c.get("label") or "",
                                   c.get("uuid") or "", c.get("partuuid") or "", c.get("parttypename") or "",
                                   [m for m in (c.get("mountpoints") or []) if m], int(c.get("fsused") or 0),
                                   int(c.get("fsavail") or 0)))
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
