"""`deckos report`: one text file that says what a PC is and how DecKoOS runs on it, for someone helping from
elsewhere (a bug report, a first install on hardware DecKoOS hasn't been tested on). Read-only, no root.

Personal details are taken out before anything is written: the user and computer names, home paths, serial
numbers, UUIDs, network addresses. The file is shown before it goes anywhere: DecKoOS never sends it.

    deckos_report.py [--out FILE] [--print]
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent
PROC = Path(os.environ.get("DECKOS_PROC") or "/proc")


def run(cmd, timeout=20):
    """stdout (or what went wrong): a missing command or a slow one never stops the report."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr).rstrip() or f"(no output, exit {r.returncode})"
    except FileNotFoundError:
        return f"({cmd[0]} isn't installed)"
    except subprocess.TimeoutExpired:
        return f"({cmd[0]} took longer than {timeout} s)"
    except OSError as e:
        return f"({e})"


def read(path, limit=None):
    try:
        text = Path(path).read_text(errors="replace").rstrip()
    except OSError:
        return f"({path} unreadable)"
    return "\n".join(text.splitlines()[-limit:]) if limit else text


def cpu():
    info = read(PROC / "cpuinfo")
    out = []
    for key in ("model name", "vendor_id", "cpu family", "model", "microcode"):
        m = re.search(rf"^{key}\s*:\s*(.*)$", info, re.M)
        if m:
            out.append(f"{key}: {m.group(1).strip()}")
    out.append(f"threads: {len(re.findall(r'^processor', info, re.M))}")
    return "\n".join(out)


def nvidia():
    version = read("/proc/driver/nvidia/version")
    if "unreadable" in version:
        return "no NVIDIA driver loaded"
    sys.path.insert(0, str(LIB / "gpu"))
    try:
        import nvml
        cards = [f"{d['name']}: {d['vram_total'] / 2**30:.1f} GiB, {d['temp']} °C, {d['power']} / {d['power_limit']} W"
                 for d in nvml.devices()]
    except Exception as e:  # the report must still come out
        cards = [f"(NVML: {e})"]
    return "\n".join([version, *cards])


def ai():
    sys.path.insert(0, str(LIB / "assistant"))
    try:
        import models
        hw = models.hardware()
        confs = [read(p) for p in (Path.home() / ".config/deckos/ai.conf", "/etc/deckos/ai.conf") if Path(p).exists()]
        return "\n".join([models.describe(hw), f"recommended model: {models.recommend(hw)}", *confs])
    except Exception as e:
        return f"({e})"


def doctor():
    sys.path.insert(0, str(LIB / "sysdoctor"))
    try:
        import sysdoctor
        findings = sysdoctor.checkup()
    except Exception as e:
        return f"(System Doctor: {e})"
    if not findings:
        return "nothing found"
    return "\n".join(f"[{f.level}] {f.title}: {f.text}" + "".join(f"\n    {e}" for e in f.evidence[:5])
                     for f in findings)


def sections():
    deckos = os.environ.get("DECKOS_TOOL") or "deckos"
    return [
        ("DecKoOS", lambda: read("/usr/share/deckos/version") + "\n" + run(["pacman", "-Q", "deckos-settings"])),
        ("Update channel", lambda: run([deckos, "channel"])),
        ("Kernel", lambda: run(["uname", "-a"]) + "\n" + read(PROC / "cmdline")),
        ("Processor", cpu),
        ("Memory", lambda: "\n".join(read(PROC / "meminfo").splitlines()[:3])),
        ("Graphics and drivers", lambda: "\n".join(  # VGA, 3D and display controllers (NVIDIA cards can be 0302)
            t for c in ("0300", "0302", "0380") if not (t := run(["lspci", "-nnk", "-d", f"::{c}"])).startswith("(no"))),
        ("NVIDIA", nvidia),
        ("Vulkan", lambda: run(["vulkaninfo", "--summary"], 30)),
        ("Display fix", lambda: run([deckos, "display", "status"])),
        ("Monitors", lambda: run(["kscreen-doctor", "-o"])),
        ("Disks", lambda: run(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,PARTTYPENAME,MOUNTPOINTS"])),
        ("Drives", lambda: run([deckos, "drives"])),
        ("Local AI", ai),
        ("System Doctor", doctor),
        ("Failed services", lambda: run(["systemctl", "--failed", "--no-legend"]) + "\n" +
         run(["systemctl", "--user", "--failed", "--no-legend"])),
        ("Errors this start-up (last 80)", lambda: run(["journalctl", "-b", "-p", "err", "-o", "short-monotonic",
                                                       "--no-pager", "-n", "80"], 40)),
        ("Graphics driver messages", lambda: "\n".join(
            line for line in run(["journalctl", "-k", "-b", "--no-pager", "-o", "cat"], 40).splitlines()
            if re.search(r"amdgpu|nvidia|nouveau|i915|xe |drm", line, re.I))[-6000:]),
        ("Gaming Mode (last attempt)", lambda: read(Path.home() / ".local/state/deckos/gaming-session.log", 60)),
        ("Installed DecKoOS packages", lambda: run(["sh", "-c", "pacman -Q | grep -E '^(deckos|linux-cachyos|mesa|"
                                                    "vulkan-|nvidia|lib32-nvidia|ollama|steam|gamescope|intel-ucode|"
                                                    "amd-ucode|chwd)'"])),
        ("Install log (last 60 lines)", lambda: read("/var/log/deckos-install.log", 60)),
    ]


def scrub(text, user=None, host=None):
    """Takes personal details out: user and computer names, home paths, serials, UUIDs, network addresses."""
    user = user if user is not None else os.environ.get("USER") or Path.home().name
    host = host if host is not None else socket.gethostname()
    text = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<uuid>", text)
    text = re.sub(r"(UUID=)[0-9A-Fa-f-]{8,}", r"\1<uuid>", text)
    text = re.sub(r"\b[0-9a-f]{32}\b", "<id>", text)  # machine and boot ids (in crash file names, among others)
    text = re.sub(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b", "<mac>", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>", text)
    text = re.sub(r"\b[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*::(?:[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*)?", "<ip>", text)
    text = re.sub(r"\b(?:[0-9a-fA-F]{1,4}:){5,7}[0-9a-fA-F]{1,4}\b", "<ip>", text)  # not 20:13:43 (times)
    text = re.sub(r"(?i)(serial(?:[ _]?(?:number|no))?\s*[:=]\s*)\S+", r"\1<serial>", text)
    for name, mark in ((user, "<user>"), (host, "<computer>")):
        if name and len(name) > 2 and name not in ("root", "localhost", "deckos"):
            text = re.sub(rf"\b{re.escape(name)}\b", mark, text)
    return text


def build(progress=None):
    parts = [f"DecKoOS report, {time.strftime('%Y-%m-%d %H:%M')}",
             "Personal details (names, serials, UUIDs, addresses) are replaced with <...>.", ""]
    for title, fn in sections():
        if progress:
            progress(title)
        try:
            body = fn()
        except Exception as e:
            body = f"({e})"
        parts += [f"===== {title} =====", body.strip() or "(nothing)", ""]
    return scrub("\n".join(parts))


def main(argv):
    out = None
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])
    text = build(lambda t: print(f"  {t}…", file=sys.stderr))
    if "--print" in argv:
        print(text)
        return 0
    out = out or Path.home() / f"deckos-report-{time.strftime('%Y%m%d-%H%M')}.txt"
    out.write_text(text + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
