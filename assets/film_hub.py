"""Films DecKoOS Hub for the website from its --demo data (no one's real files or apps): the pages unfolding in, the
Timeline's day strip, Made for you, and the plates flaring on a steady beat (a stand-in for React to music, 120 a
minute). Frames from the window itself, so no screen recording or permission is needed. Needs PySide6 and ffmpeg.

    python assets/film_hub.py OUT.mp4
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.argv.append("--demo")
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/hub"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

app = QApplication(sys.argv)
import hub_style as S  # noqa: E402
import deckos_hub  # noqa: E402

app.setStyleSheet(S.qss())


class Beat:
    """React to music's beat without music: a kick every half second, fading like the real one."""

    def __init__(self):
        import weakref
        self.watch, self.pulse, self.t0 = weakref.WeakSet(), 0.0, time.monotonic()


beat = Beat()
S._react.append(beat)  # hub_style asks _react[0] for the pulse and registers what to repaint

w = deckos_hub.Hub()
w.resize(1280, 800)
w.show()

# (seconds from the start, what to do)
SHOTS = [(0.0, lambda: w.navigate("home")), (3.5, lambda: w.navigate("timeline")), (7.0, lambda: w.navigate("health")),
         (10.0, lambda: w.navigate("appearance")), (13.5, lambda: w.navigate("home")),
         (14.5, lambda: w.page("home").findChild(QScrollArea).verticalScrollBar().setValue(600))]
LENGTH = 18.0


def main():
    out = Path(sys.argv[1])
    frames = Path(tempfile.mkdtemp(prefix="hub-film-"))
    start, n, todo = time.monotonic(), 0, list(SHOTS)
    while (now := time.monotonic() - start) < LENGTH:
        while todo and todo[0][0] <= now:
            todo.pop(0)[1]()
        beat.pulse = max(0.0, 1 - ((now % 0.5) / 0.5) * 2.2) * 0.9  # the kick, then its fade
        for x in list(beat.watch):
            if x.isVisible():
                x.update()
        app.processEvents()
        w.grab().save(str(frames / f"{n:05d}.jpg"), "JPG", 93)
        n += 1
    fps = n / LENGTH
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:.2f}", "-i", str(frames / "%05d.jpg"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                    "-r", "30", str(out)], check=True)
    print(f"{n} frames, {fps:.1f} a second -> {out}")
    app.exit(0)


QTimer.singleShot(800, main)
app.exec()
