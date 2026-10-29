"""The pictures in DecKoOS's tour (deckos-tour): real screenshots from docs/screenshots and renders of the Hub, the
Vibes and Vibe mode from their --demo modes, resized to 1600 px JPEGs in usr/share/deckos/tour/ (committed).

    QT_QPA_PLATFORM=offscreen python3 assets/tour_images.py

Re-run after retaking docs/screenshots or changing a page the tour shows, and commit the pictures with it. Needs
PySide6. Each picture's source is in SOURCES; the tour's slides (usr/lib/deckos/welcome/deckos_tour.py) name them.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parent.parent
RFS = ROOT / "pkg/deckos-settings/rootfs"
OUT = RFS / "usr/share/deckos/tour"
SHOTS = ROOT / "docs/screenshots"
WIDTH = 1600

# picture name: where it comes from ("shot:FILE" from docs/screenshots, "hub:PAGE", "vibe:SCENE", "music")
SOURCES = {
    "desktop": "shot:desktop.png",
    "menu": "shot:menu.png",
    "quicksettings": "shot:quicksettings.png",
    "hub": "hub:home",
    "vibes": "vibe:neon",
    "music": "music",
    "games": "hub:games",
    "timeline": "hub:timeline",
    "assistant": "shot:assistant.png",
    "sysmon": "shot:sysmon.png",
    "files": "shot:files.png",
    "backup": "hub:system",
}


def render(tmp):
    """Runs the previewers once; returns {kind: folder or file} of what they wrote."""
    env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    subprocess.run([sys.executable, str(ROOT / "assets/preview_hub.py"), "--all"], env=env, check=True,
                   capture_output=True)
    subprocess.run([sys.executable, str(ROOT / "assets/preview_vibes.py")], env=env, check=True, capture_output=True)
    music = RFS / "usr/lib/deckos/music/deckos_music.py"
    subprocess.run([sys.executable, str(music), "--demo", "--screenshot", str(tmp)], env=env, capture_output=True,
                   timeout=120)


def source(spec, tmp):
    kind, _, name = spec.partition(":")
    if kind == "shot":
        return SHOTS / name
    if kind == "hub":
        return ROOT / "assets" / ("hub-preview.png" if name == "home" else f"hub-preview-{name}.png")
    if kind == "vibe":
        return ROOT / "assets" / f"vibe-preview-{name}.png"
    pics = sorted(Path(tmp).glob("*.png"))
    return pics[0] if pics else None


def main():
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        render(tmp)
        missing = []
        for name, spec in SOURCES.items():
            path = source(spec, tmp)
            img = QImage(str(path)) if path else QImage()
            if img.isNull():
                missing.append(f"{name} ({spec})")
                continue
            if img.width() > WIDTH:
                img = img.scaledToWidth(WIDTH, Qt.SmoothTransformation)
            img.convertToFormat(QImage.Format_RGB32).save(str(OUT / f"{name}.jpg"), "JPG", 86)
            print("wrote", OUT / f"{name}.jpg")
    # the previewers' own outputs aren't committed
    for f in list(ROOT.glob("assets/hub-preview*.png")) + list(ROOT.glob("assets/vibe-preview-*.png")):
        f.unlink()
    if missing:
        print("missing:", ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
