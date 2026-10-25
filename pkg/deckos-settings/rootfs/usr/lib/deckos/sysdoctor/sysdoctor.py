"""DecKoOS System Doctor: what's wrong with this PC right now, in plain words, with fixes.

Plain Python, no Qt (deckos_sysdoctor.py is the window). It only reads: the journal, systemd, disks.
Fixes are commands the window runs when the person presses them (pkexec for root ones). Every check
goes through run(), so tests feed it canned output.

checkup() -> [Finding], worst first. Each Finding has the evidence it's based on, so the window can
show it, and the local model (deckos-local's summarize) can explain it on request.
"""
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

BAD, WARN, INFO = "bad", "warn", "info"


@dataclass
class Fix:
    title: str
    cmd: list  # run as is; root fixes start with pkexec
    detail: str = ""


@dataclass
class Finding:
    key: str
    level: str  # bad, warn, info
    title: str
    text: str
    evidence: list = field(default_factory=list)  # log lines it's based on
    fixes: list = field(default_factory=list)
    open: list = field(default_factory=list)  # a DecKoOS app that handles it: [cmd, args...]


def run(cmd, timeout=30):
    """(exit code, stdout). Missing commands and timeouts count as failures, never exceptions."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 127, ""


# ------------------------------------------------------------------ checks

def failed_units():
    out = []
    for scope in ("system", "user"):
        user = ["--user"] if scope == "user" else []
        _, text = run(["systemctl", *user, "--failed", "--plain", "--no-legend"])
        for line in text.splitlines():
            unit = line.split()[0] if line.split() else ""
            if not unit or unit.startswith("●"):
                unit = line.split()[1] if len(line.split()) > 1 else ""
            if not unit:
                continue
            _, log = run(["journalctl", *user, "-b", "-u", unit, "-n", "15", "--no-pager", "-o", "cat"])
            restart = ["systemctl", *user, "restart", unit] if scope == "user" else ["pkexec", "systemctl", "restart", unit]
            clear = ["systemctl", *user, "reset-failed", unit] if scope == "user" else ["pkexec", "systemctl", "reset-failed", unit]
            out.append(Finding(f"unit:{scope}:{unit}", BAD, f"{describe_unit(unit)} failed",
                               f"The {'background service' if scope == 'system' else 'service in your session'} "
                               f"{unit} stopped with an error. The lines below are what it said last.",
                               evidence=log.splitlines()[-15:],
                               fixes=[Fix("Try again", restart, "Starts it again"),
                                      Fix("Forget it", clear, "Clears the failure; it runs again at the next start")]))
    return out


UNIT_NAMES = {"drkonqi-coredump-pickup": "KDE's crash reporter", "NetworkManager": "Networking",
              "bluetooth": "Bluetooth", "sddm": "The login screen", "ollama": "Local AI (Ollama)",
              "deckos-gpu": "DecKoOS's graphics card tuning", "deckos-display": "DecKoOS's display fix",
              "snapper-timeline": "Hourly home snapshots", "docker": "Docker", "plasma-plasmashell": "The desktop panel"}


def describe_unit(unit):
    base = re.sub(r"(@.*)?\.(service|timer|socket|mount)$", "", unit)
    return UNIT_NAMES.get(base, unit)


# A crashed program, by what ran (python3 alone says nothing): the first match names it.
PROGRAMS = [
    (r"plasmashell", "The desktop (plasmashell)", "desktop"),
    (r"kwin_wayland|kwin_x11", "The window manager (KWin)", "desktop"),
    (r"ksplashqml|plasma-fallback|ksecretd|kdeconnectd|drkonqi|kded6|xdg-desktop-portal", "A desktop service", "desktop"),
    (r"gamescope", "Gaming Mode (gamescope)", "gaming"),
    (r"steamwebhelper|steam\b|/Steam/", "Steam", "steam"),
    (r"\.exe\b|proton|wine", "A game", "game"),
    (r"deckos_movein", "DecKoOS Move In", "deckos"),
    (r"deckos_hub|hub_pages", "DecKoOS Hub", "deckos"),
    (r"deckos_store", "DecKoOS Store", "deckos"),
    (r"deckos_assistant", "DecKoOS Assistant", "deckos"),
    (r"work_app", "DecKoOS Work", "deckos"),
    (r"bench_app|deckos_bench", "DecKoOS Bench", "deckos"),
    (r"deckos-terminal", "DecKoOS Terminal", "deckos"),
    (r"deckos-editor", "DecKoOS Editor", "deckos"),
    (r"deckos-files", "DecKoOS Files", "deckos"),
    (r"firefox", "Firefox", "app"),
    (r"spotify", "Spotify", "app"),
    (r"discord", "Discord", "app"),
]


def name_program(comm, cmdline):
    text = f"{comm} {cmdline}"
    for pattern, name, kind in PROGRAMS:
        if re.search(pattern, text, re.I):
            return name, kind
    script = next((w for w in cmdline.split()[1:] if w.endswith(".py")), "")
    if script:  # python3 alone says nothing: the script does
        return f"{script.rsplit('/', 1)[-1]} (Python)", "app"
    return (cmdline.split()[0].rsplit("/", 1)[-1] if cmdline else comm) or "A program", "app"


def coredumps(since="-24h"):
    """[{when, comm, cmdline, signal, name, kind}] from systemd-coredump's journal entries."""
    _, text = run(["journalctl", "--since", since, "-t", "systemd-coredump", "-o", "json", "--no-pager",
                   "--output-fields=COREDUMP_COMM,COREDUMP_CMDLINE,COREDUMP_SIGNAL_NAME,COREDUMP_TIMESTAMP,MESSAGE"], 60)
    dumps = []
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not e.get("COREDUMP_COMM"):
            continue
        comm, cmd = str(e.get("COREDUMP_COMM", "")), str(e.get("COREDUMP_CMDLINE", ""))
        when = int(str(e.get("COREDUMP_TIMESTAMP") or 0)) / 1e6
        name, kind = name_program(comm, cmd)
        dumps.append({"when": when, "comm": comm, "cmdline": cmd, "signal": e.get("COREDUMP_SIGNAL_NAME", ""),
                      "name": name, "kind": kind})
    return dumps


def crashes():
    dumps = coredumps()
    if not dumps:
        return []
    out = []
    # Many desktop programs dying within seconds of each other: the session underneath went away (Gaming
    # Mode's exit on 0.3.x did exactly this), not each of them on its own.
    desktop = sorted((d for d in dumps if d["kind"] == "desktop"), key=lambda d: d["when"])
    clusters = []  # crashes each within 15 s of the one before
    for d in desktop:
        if clusters and d["when"] - clusters[-1][-1]["when"] <= 15:
            clusters[-1].append(d)
        else:
            clusters.append([d])
    burst = max(clusters, key=lambda c: len({b["comm"] for b in c}), default=[])
    if len({b["comm"] for b in burst}) >= 4:
        at = time.strftime("%H:%M", time.localtime(burst[0]["when"]))
        out.append(Finding("crash:desktop-burst", BAD, "The desktop crashed and restarted",
                           f"At {at}, {len({b['comm'] for b in burst})} desktop programs stopped at the same moment. "
                           "That usually means the display they ran on went away (switching from Gaming Mode, a "
                           "graphics driver reset), not a fault in each of them. If it keeps happening, the "
                           "evidence below helps a bug report.",
                           evidence=[f"{time.strftime('%H:%M:%S', time.localtime(b['when']))} {b['comm']} ({b['signal']})"
                                     for b in burst],
                           fixes=[Fix("Restart the desktop panel", ["systemctl", "--user", "restart",
                                                                     "plasma-plasmashell.service"])]))
        shown = {b["comm"] for b in burst}
        dumps = [d for d in dumps if not (d["kind"] == "desktop" and d["comm"] in shown)]
    groups = {}
    for d in dumps:
        groups.setdefault(d["name"], []).append(d)
    # Programs of no particular kind that crashed once: one finding, not a card each
    once = {name: ds for name, ds in groups.items() if len(ds) == 1 and ds[0]["kind"] == "app"}
    if len(once) >= 2:
        for name in once:
            del groups[name]
        ds = sorted((d[0] for d in once.values()), key=lambda d: d["when"])
        out.append(Finding("crash:others", INFO, f"{len(ds)} other programs crashed once",
                           f"{', '.join(sorted(once)[:6])}{' and more' if len(once) > 6 else ''}. Once is usually "
                           "nothing to worry about; if one keeps crashing it gets a finding of its own.",
                           evidence=[f"{time.strftime('%H:%M:%S', time.localtime(d['when']))} {d['cmdline'] or d['comm']} "
                                     f"({d['signal']})" for d in ds[-8:]]))
    for name, ds in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        kind = ds[0]["kind"]
        last = time.strftime("%a %H:%M", time.localtime(max(d["when"] for d in ds)))
        n = len(ds)
        times = f"{n} times" if n > 1 else "once"
        level = BAD if kind in ("desktop", "gaming") or n >= 3 else WARN
        f = Finding(f"crash:{name}", level, f"{name} crashed {times}", f"Last at {last}.",
                    evidence=[f"{time.strftime('%H:%M:%S', time.localtime(d['when']))} {d['cmdline'] or d['comm']} "
                              f"({d['signal']})" for d in ds[-6:]])
        if kind == "game":
            f.text += " Game Doctor reads what the game printed and has fixes for the common causes."
            f.open = ["deckos-gamedoctor"]
        elif kind == "gaming":
            f.text += " Gaming Mode's log (~/.local/state/deckos/gaming-session.log) says what happened around it."
        elif kind == "deckos":
            f.text += " That's a DecKoOS app: please report it with the evidence below (the line shows how it was run)."
        elif kind == "desktop":
            f.fixes.append(Fix("Restart the desktop panel", ["systemctl", "--user", "restart", "plasma-plasmashell.service"]))
        out.append(f)
    return out


FSTAB = Path("/etc/fstab")


def network_mounts():
    """fstab lines that mount over the network (they need the network up at start)."""
    try:
        lines = FSTAB.read_text().splitlines()
    except OSError:
        return []
    return [l for l in lines if not l.lstrip().startswith("#")
            and re.search(r"\s(nfs4?|cifs|smb3|sshfs|fuse\.sshfs|davfs)\s|_netdev", l)]


def slow_boot():
    code, text = run(["systemd-analyze"])
    m = re.search(r"\+ ([\d.]+)s \(userspace\)", text)
    if code != 0 or not m:
        return []
    userspace = float(m.group(1))
    _, blame = run(["systemd-analyze", "blame", "--no-pager"])
    slow = []
    for line in blame.splitlines()[:5]:
        mm = re.match(r"\s*(?:(\d+)min )?([\d.]+)(ms|s) (\S+)", line)
        if mm:
            secs = int(mm.group(1) or 0) * 60 + float(mm.group(2)) / (1000 if mm.group(3) == "ms" else 1)
            if secs >= 3:
                slow.append((mm.group(4), secs))
    out = []
    for unit, secs in slow:
        if unit == "NetworkManager-wait-online.service":
            if network_mounts():  # those do need the network up before they mount
                continue
            out.append(Finding("boot:wait-online", WARN, f"Starting up waits {secs:.0f} s for the network",
                               "NetworkManager-wait-online holds the start until the network is up. Only network "
                               "drives in /etc/fstab need that, and this PC has none, so it can go.",
                               evidence=[f"{unit}: {secs:.1f} s of {userspace:.1f} s"],
                               fixes=[Fix("Don't wait for the network", ["pkexec", "systemctl", "disable",
                                                                          "NetworkManager-wait-online.service"])]))
        elif secs >= 10:
            out.append(Finding(f"boot:{unit}", INFO, f"{describe_unit(unit)} takes {secs:.0f} s at start-up",
                               "It's the slowest part of starting up; often a service waiting for a device or "
                               "the network.", evidence=[f"{unit}: {secs:.1f} s of {userspace:.1f} s"]))
    return out


def missing_programs():
    """A rule or service that runs a program which isn't installed (udev's 'callout binary')."""
    _, text = run(["journalctl", "-b", "-p", "err", "--no-pager", "-o", "cat"], 60)
    missing = {}
    for line in text.splitlines():
        m = re.search(r'Failed to find and pin callout binary "([^"]+)"|(/usr/s?bin/\S+): (?:not found|No such file)', line)
        if m:
            path = m.group(1) or m.group(2)
            missing.setdefault(path, []).append(line)
    out = []
    for path, lines in missing.items():
        _, owner = run(["pacman", "-F", "-q", path], 60)
        pkg = owner.split("\n")[0].split("/")[-1].strip() if owner.strip() else ""
        if not pkg and run(["pacman", "-Si", Path(path).name])[0] == 0:
            pkg = Path(path).name  # pacman -F needs its file list downloaded; most programs' package has their name
        f = Finding(f"missing:{path}", WARN, f"{Path(path).name} is needed but not installed",
                    f"Something on this PC runs {path} ({len(lines)} times this start-up) and it isn't there, so "
                    "what it's for doesn't happen" + (f". It comes with the {pkg} package." if pkg else "."),
                    evidence=lines[:5])
        if pkg:
            f.fixes.append(Fix(f"Install {pkg}", ["pkexec", "pacman", "-S", "--needed", "--noconfirm", pkg]))
        out.append(f)
    return out


def disk_space():
    out, seen = [], set()
    for mount in ("/", "/home"):
        try:
            st = os.statvfs(mount)
        except OSError:
            continue
        key = (st.f_fsid, st.f_blocks)
        if key in seen:
            continue
        seen.add(key)
        free, total = st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize
        if total and (free < 15e9 or free / total < 0.08):
            f = Finding(f"disk:{mount}", BAD if free < 5e9 else WARN, f"Only {free / 1e9:.0f} GB free",
                        f"The drive with {mount} is {100 - free * 100 // total}% full. Updates, snapshots and games "
                        "need room; below a few GB things start failing.",
                        evidence=[f"{mount}: {free / 1e9:.1f} GB free of {total / 1e9:.0f} GB"])
            if shutil.which("paccache"):
                f.fixes.append(Fix("Clear old package downloads", ["pkexec", "paccache", "-rk1"],
                                   "Keeps the newest copy of each package"))
            f.fixes.append(Fix("Delete systems kept by Undo", ["pkexec", "deckos", "undo", "clean"]))
            if shutil.which("filelight"):
                f.open = ["filelight", mount]
            out.append(f)
    return out


def gpu_resets():
    _, text = run(["journalctl", "-b", "-k", "--no-pager", "-o", "short-precise", "--grep",
                   r"amdgpu.*(GPU reset|ring .* timeout|hang)"], 60)
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("--")]
    if not lines:
        return []
    return [Finding("gpu:reset", BAD, "The graphics card reset itself",
                    f"{len(lines)} times this start-up the graphics driver gave up on the card and restarted it; the "
                    "screen goes black for a moment and programs on it can crash. Undervolting or overclocking is the "
                    "usual cause; on Radeon cards, DecKoOS's display fix levels help with blackouts.",
                    evidence=lines[:6], open=["deckos-hub", "--page", "display"])]


SYS, PROC = Path("/sys"), Path("/proc")  # tests point these at a fake tree


def read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeDecodeError):
        return ""
# RTX 50 (Blackwell: GB202-GB207) PCI device IDs; NVIDIA's closed kernel module doesn't drive these cards
BLACKWELL = range(0x2B00, 0x3000)


def nvidia_driver():
    """An NVIDIA card that isn't on NVIDIA's driver: on nouveau or none (Secure Boot, a failed install), or an RTX 50
    on the closed module, which doesn't support it."""
    out = []
    for dev in sorted((SYS / "bus/pci/devices").glob("*")):
        if not (dev / "class").exists() or not read(dev / "class").startswith("0x03") or read(dev / "vendor") != "0x10de":
            continue
        drv = (dev / "driver").resolve().name if (dev / "driver").exists() else ""
        try:
            device = int(read(dev / "device"), 16)
        except ValueError:
            device = 0
        fix = [Fix("Set up the NVIDIA driver",
                   ["pkexec", "sh", "-c", "pacman -S --needed --noconfirm chwd && chwd -a"],
                   "CachyOS's hardware setup picks the right NVIDIA driver for this card; restart afterwards")]
        if drv != "nvidia":
            out.append(Finding(f"nvidia:{dev.name}", BAD, "The NVIDIA card isn't using NVIDIA's driver",
                               ("It's on the basic nouveau driver: games and Gaming Mode run badly or not at all."
                                if drv == "nouveau" else "No driver has taken it, so it can't be used.")
                               + " Secure Boot on is a common cause (turn it off in the BIOS); otherwise set up "
                               "the driver.", evidence=[f"{dev.name}: driver {drv or 'none'}"], fixes=fix))
        elif device in BLACKWELL:
            version = read(PROC / "driver/nvidia/version")
            if version and "Open Kernel Module" not in version:
                out.append(Finding(f"nvidia-open:{dev.name}", BAD, "This RTX 50 card needs NVIDIA's open driver",
                                   "The closed NVIDIA driver doesn't support RTX 50 cards. Switching to the open one "
                                   "(the same driver, open kernel module) makes it work.",
                                   evidence=[version.splitlines()[0][:160]], fixes=fix))
    return out


def intel_microcode():
    """13th and 14th gen Intel desktop processors (Raptor Lake) degrade on old microcode; Intel's fix is 0x12B."""
    text = read(PROC / "cpuinfo")
    if "GenuineIntel" not in text:
        return []
    model = re.search(r"^model\s*:\s*(\d+)", text, re.M)
    family = re.search(r"^cpu family\s*:\s*(\d+)", text, re.M)
    micro = re.search(r"^microcode\s*:\s*(0x[0-9a-f]+)", text, re.M)
    name = re.search(r"^model name\s*:\s*(.+)$", text, re.M)
    if not (model and family and micro) or family.group(1) != "6" or int(model.group(1)) not in (0xB7, 0xBA, 0xBF):
        return []
    if int(micro.group(1), 16) >= 0x12B:
        return []
    return [Finding("intel-microcode", WARN, "Your Intel processor is missing Intel's stability update",
                    "13th and 14th gen Intel processors can become unstable over time without Intel's microcode "
                    "fix (0x12B or newer). DecKoOS loads it at start-up from the intel-ucode package; a BIOS update "
                    "from your motherboard maker brings it too.",
                    evidence=[f"{name.group(1).strip() if name else 'Intel CPU'}: microcode {micro.group(1)}"],
                    fixes=[Fix("Install Intel's microcode", ["pkexec", "pacman", "-S", "--needed", "--noconfirm",
                                                             "intel-ucode"], "Takes effect after a restart")])]


def restart_pending():
    running = os.uname().release
    if Path(f"/usr/lib/modules/{running}").is_dir():
        return []
    return [Finding("restart", WARN, "Restart to finish an update",
                    f"An update replaced the running kernel ({running}); until a restart, new USB devices, drives and "
                    "some drivers can't load.", fixes=[Fix("Restart now", ["systemctl", "reboot"])])]


def journal_errors(known):
    """What the system flagged as errors this start-up and nothing above explains: the most repeated."""
    _, text = run(["journalctl", "-b", "-p", "err", "--no-pager", "-o", "cat"], 60)
    counts = {}
    for line in text.splitlines():
        line = line.strip()
        # crash reports and missing programs have findings of their own
        if (not line or line.startswith(("#", "Module ", "Stack trace")) or "ELF object" in line
                or "callout binary" in line or "dumped core" in line or "terminated abnormally" in line):
            continue
        line = re.sub(r"\b\d+\b", "N", line)[:200]
        counts[line] = counts.get(line, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:8]
    top = [(l, n) for l, n in top if not any(k in l for k in known)]
    if not top:
        return []
    return [Finding("journal", INFO, "Other errors in the system log",
                    "Lines the system marked as errors this start-up. Many are harmless; Explain asks the local AI "
                    "what they mean for you.", evidence=[f"{n}×  {l}" for l, n in top])]


CHECKS = [failed_units, crashes, gpu_resets, nvidia_driver, intel_microcode, missing_programs, disk_space,
          restart_pending, slow_boot]
ORDER = {BAD: 0, WARN: 1, INFO: 2}


def checkup():
    findings = []
    for check in CHECKS:
        try:
            findings += check()
        except Exception as e:  # one broken check mustn't hide the others
            findings.append(Finding(f"check:{check.__name__}", INFO, f"Couldn't check {check.__name__}", str(e)))
    known = [f.key.split(":", 2)[-1] for f in findings if f.key.startswith(("unit:", "missing:"))]
    findings += journal_errors(known)
    return sorted(findings, key=lambda f: ORDER[f.level])


def explain(finding, model=None):
    """The local model's plain-words reading of one finding's evidence (deckos-local's summarize)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assistant"))
    from assistant import pick_model, summarize
    model = model or pick_model()
    if not model:
        return "No local model to ask (sudo deckos ai setup). The finding above comes from known patterns."
    text = "\n".join(finding.evidence) or finding.text
    return summarize(text, f"On a DecKoOS (Arch Linux, KDE Plasma) PC: {finding.title}. {finding.text} In 2-4 plain "
                     "sentences for a non-expert: what this means, whether it matters, and the most likely cause. "
                     "Quote the one line that shows it. Don't suggest commands.", model)
