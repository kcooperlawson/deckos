"""Renders DecKoOS Hub on any OS from its --demo data (no system calls): assets/hub-preview.png for
Home, plus one image per page with --all.

    python -m pip install PySide6-Essentials && python assets/preview_hub.py [--all]
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "pkg/deckos-settings/rootfs"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv.append("--demo")
sys.path.insert(0, str(ROOT / "usr/lib/deckos/hub"))

import deckos_hub as hub  # noqa: E402
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
app.setStyleSheet(hub.S.qss())
w = hub.Hub()
w.show()
for _ in range(30):  # some graph history
    w.tick()
pages = ([p[0] for p in hub.PAGES] if "--all" in sys.argv
         else [sys.argv[sys.argv.index("--page") + 1]] if "--page" in sys.argv else ["home"])
for key in pages:
    w.navigate(key)
    wait(800)
    out = HERE / ("hub-preview.png" if key == "home" else f"hub-preview-{key}.png")
    w.grab().save(str(out))
    print("wrote", out)
