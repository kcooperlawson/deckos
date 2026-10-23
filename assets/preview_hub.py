"""Renders DeckOS Hub to assets/hub-preview.png on any OS (sample sensor values, no system calls).

    python -m pip install PySide6-Essentials && python assets/preview_hub.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "pkg/deckos-settings/rootfs"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DECKOS_BRANDING"] = str(ROOT / "usr/share/deckos/branding")
sys.path.insert(0, str(ROOT / "usr/lib/deckos/hub"))

import deckos_hub as hub  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

hub.run = lambda cmd, timeout=6: {"systemctl": "active"}.get(cmd[0], "")
hub.shutil.which = lambda name: f"/usr/bin/{name}"


def fake_live(self):
    sample = {"gpu_temp": ("47°C", 0.47), "vram": ("2518 MHz", 1.0), "gpu_power": ("38 W", 0.11),
              "cpu_temp": ("52°C", 0.55), "ram": ("9.4 / 31 GB", 0.30)}
    for key, (text, frac) in sample.items():
        val, bar = self.stats[key]
        val.setText(text)
        bar.set(frac)
    self.display_live.setText("RX 9070 XT   VRAM 2518 MHz   mode manual   47°C")
    self.ai_live.setText("Claude Code ✓   Ollama (ROCm) ✓   VS Code ✓   Docker ✓")


hub.Hub.refresh_live = fake_live
hub.Hub.refresh_drives = lambda self: [self.drive_list.addWidget(hub.label(t)) for t in (
    f'<span style="color:{hub.SUCCESS}">●</span>&nbsp; <b>/mnt/Windows</b>&nbsp; <span style="color:{hub.SUBTEXT}">189 / 476 GB</span>',
    f'<span style="color:{hub.SUCCESS}">●</span>&nbsp; <b>/mnt/SSD</b>&nbsp; <span style="color:{hub.SUBTEXT}">684 / 932 GB</span>',
    f'<span style="color:{hub.SUCCESS}">●</span>&nbsp; <b>/mnt/BIG</b>&nbsp; <span style="color:{hub.SUBTEXT}">2.29 / 7.45 TB</span>')]

app = QApplication(sys.argv)
for f in (ROOT / "usr/share/fonts/deckos").glob("*.otf"):
    QFontDatabase.addApplicationFont(str(f))
app.setStyleSheet(hub.QSS.replace('"Inter", "Noto Sans"', '"Inter Display", "Segoe UI"'))
app.setFont(QFont("Inter Display", 10))
w = hub.Hub()
w.resize(1060, 820)
w.show()
app.processEvents()
out = HERE / "hub-preview.png"
w.grab().save(str(out))
print("wrote", out)
