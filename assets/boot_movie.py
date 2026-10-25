"""Renders Steam's startup movie for Gaming Mode: the login splash (wordmark, thumbstick cap turning
once, as in Splash.qml) fading in from and out to the slate, so the switch from the desktop's cover
(usr/lib/deckos/transition) carries straight on. Needs PySide6 and ffmpeg; the output is committed:
    python assets/boot_movie.py
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1] / "pkg/deckos-settings/rootfs/usr/share/deckos/branding"
OUT = ROOT / "deckos-startup.webm"
W, H, FPS = 1920, 1080, 30
SECONDS = 3.0
TURN = 2.5  # Splash.qml: 360 → 0 every 2.5 s
FADE_IN, FADE_OUT = 0.35, 0.45
BG = QColor("#0F1115")


def frame(word, stick, t):
    img = QImage(W, H, QImage.Format_RGB888)
    img.fill(BG)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(min(1.0, t / FADE_IN, (SECONDS - t) / FADE_OUT))
    s = min(W * 0.4, 1008) / 1008  # same scale as Splash.qml
    wx, wy = (W - 1008 * s) / 2, (H - 194 * s) / 2
    word.render(p, QRectF(wx, wy, 1008 * s, 194 * s))
    p.translate(wx + 625.5 * s, wy + 117.4 * s)
    p.rotate(-360 * (t % TURN) / TURN)
    stick.render(p, QRectF(-54.5 * s, -54.5 * s, 109 * s, 109 * s))
    p.end()
    return img


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841 (QPainter on images needs the app for fonts)
    word, stick = QSvgRenderer(str(ROOT / "wordmark-bare.svg")), QSvgRenderer(str(ROOT / "stick.svg"))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libvpx-vp9", "-b:v", "0",
                           "-crf", "32", "-row-mt", "1", "-pix_fmt", "yuv420p", "-an", str(OUT)],
                          stdin=subprocess.PIPE)
    for i in range(int(SECONDS * FPS)):
        img = frame(word, stick, i / FPS)
        ff.stdin.write(bytes(img.constBits())[:W * H * 3] if img.bytesPerLine() == W * 3 else
                       b"".join(bytes(img.constScanLine(y))[:W * 3] for y in range(H)))
    ff.stdin.close()
    sys.exit(ff.wait())


if __name__ == "__main__":
    main()
