"""How long each DecKoOS app takes from launch to its first window: imports, building the window, everything before
the person sees something. Runs each app in --demo (no system calls) offscreen, several times, and prints the median.

    python3 assets/startup_times.py [APP…] [--runs N] [--real]

--real runs without --demo (reads the real system, changes nothing); still offscreen.
"""
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos"
APPS = {
    "hub": "hub/deckos_hub.py", "store": "store/deckos_store.py", "welcome": "welcome/deckos_welcome.py",
    "assistant": "assistant/deckos_assistant.py", "sysmon": "sysmon/deckos_sysmon.py",
    "gamedoctor": "gamedoctor/deckos_gamedoctor.py",
    "retro": "retro/deckos_retro.py", "movein": "movein/deckos_movein.py", "disks": "disks/deckos_disks.py",
    "bench": "bench/bench_app.py", "work": "work/work_app.py", "builder": "builder/deckos_builder.py",
    "kids": "kids/deckos_kids.py", "whatsnew": "whatsnew/deckos_whatsnew.py",
}
# Runs inside the app's process: notes the moment the first window is shown, then leaves at once
PROBE = r"""
import os, runpy, sys, time
t0 = float(os.environ["DECKOS_T0"])
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer
_show = QWidget.show
def show(self, *a, **k):
    _show(self, *a, **k)
    if self.isWindow() and not os.environ.get("DECKOS_SHOWN"):
        os.environ["DECKOS_SHOWN"] = "1"
        def done():
            print(f"STARTUP {time.time() - t0:.3f}", flush=True)
            os._exit(0)
        QTimer.singleShot(0, done)  # after this turn of the event loop: the window is really there
QWidget.show = show
sys.argv = [sys.argv[1]] + sys.argv[2:]
sys.path.insert(0, os.path.dirname(sys.argv[0]))  # as when the script runs itself
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def once(script, real):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "DECKOS_T0": str(time.time())}
    args = [sys.executable, "-c", PROBE, str(script)] + ([] if real else ["--demo"])
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60, env=env).stdout
    except subprocess.TimeoutExpired:
        return None
    line = next((ln for ln in out.splitlines() if ln.startswith("STARTUP ")), None)
    return float(line.split()[1]) if line else None


def main(argv):
    runs = int(argv[argv.index("--runs") + 1]) if "--runs" in argv else 3
    real = "--real" in argv
    names = [a for a in argv if a in APPS] or list(APPS)
    for name in names:
        times = [t for t in (once(LIB / APPS[name], real) for _ in range(runs)) if t is not None]
        print(f"{name:12} {statistics.median(times) * 1000:6.0f} ms" if times else f"{name:12}   didn't show a window")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
