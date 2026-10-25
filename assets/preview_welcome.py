"""Renders DecKoOS Welcome on any OS from its --demo data (no system calls): assets/welcome-preview.png
for the first step, plus one image per step with --all.

    python -m pip install PySide6-Essentials && python assets/preview_welcome.py [--all]
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "pkg/deckos-settings/rootfs"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv.append("--demo")
sys.path.insert(0, str(ROOT / "usr/lib/deckos/welcome"))

import deckos_welcome as welcome  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


app = QApplication(sys.argv)
for f in (ROOT / "usr/share/fonts/deckos").glob("*.otf"):
    QFontDatabase.addApplicationFont(str(f))
app.setFont(QFont("Inter", 10))
app.setStyleSheet(welcome.qss())
w = welcome.Welcome()
w.show()
steps = range(len(w.steps)) if "--all" in sys.argv else [0]
for i in steps:
    if i == len(w.steps) - 1:  # a few changes and a skipped step, so the summary has something to show
        w.note("look:accent", "Accent colour: Violet")
        w.note("display:level", "Display fix: level 1 (No FAMS)", "reboot")
        w.note("software:app-com.spotify.Client", "Spotify installed")
        w.state[4] = "skipped"
    w.go(i)
    wait(900)
    key = w.steps[i].key
    out = HERE / ("welcome-preview.png" if i == 0 else f"welcome-preview-{i + 1}-{key}.png")
    w.grab().save(str(out))
    print("wrote", out)
    w.leave("done")
