"""Preview of the DeckOS Plasma style without Plasma: draws the theme's 9-slice frames the way
Plasma does (corners at their own size, edges and centre stretched, shadows outside) on the
DeckOS wallpaper, as a dock, a popup and a tooltip.
    python assets/preview_plasma.py [out.png]
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "pkg/deckos-settings/rootfs/usr/share"
THEME = SHARE / "plasma/desktoptheme/deckos"
SIDES = ("top", "bottom", "left", "right")


def svg(path, color=None):
    data = path.read_text()
    if color:
        data = data.replace("#000", color)
    return QSvgRenderer(data.encode())


def size(r, el):
    b = r.boundsOnElement(el)
    return b.width(), b.height()


def draw_frame(p, r, rect, shadow=True):
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    if shadow and r.elementExists("shadow-top"):
        st, sb = size(r, "shadow-top")[1], size(r, "shadow-bottom")[1]
        sl, sr = size(r, "shadow-left")[0], size(r, "shadow-right")[0]
        for el, rr in (("shadow-topleft", (x - sl, y - st, sl, st)), ("shadow-top", (x, y - st, w, st)),
                       ("shadow-topright", (x + w, y - st, sr, st)), ("shadow-left", (x - sl, y, sl, h)),
                       ("shadow-right", (x + w, y, sr, h)), ("shadow-bottomleft", (x - sl, y + h, sl, sb)),
                       ("shadow-bottom", (x, y + h, w, sb)), ("shadow-bottomright", (x + w, y + h, sr, sb))):
            r.render(p, el, QRectF(*rr))
    cw, ch = size(r, "topleft")
    for el, rr in (("topleft", (x, y, cw, ch)), ("top", (x + cw, y, w - 2 * cw, ch)), ("topright", (x + w - cw, y, cw, ch)),
                   ("left", (x, y + ch, cw, h - 2 * ch)), ("center", (x + cw, y + ch, w - 2 * cw, h - 2 * ch)),
                   ("right", (x + w - cw, y + ch, cw, h - 2 * ch)), ("bottomleft", (x, y + h - ch, cw, ch)),
                   ("bottom", (x + cw, y + h - ch, w - 2 * cw, ch)), ("bottomright", (x + w - cw, y + h - ch, cw, ch))):
        r.render(p, el, QRectF(*rr))
    t, b, l, rt = (size(r, f"hint-{s}-margin")[1 if s in ("top", "bottom") else 0] for s in SIDES)
    return rect.adjusted(l, t, -rt, -b)  # the content area


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "assets/plasma-preview.png")
    app = QGuiApplication(sys.argv)  # noqa: F841 (fonts need it)
    img = QImage(1600, 900, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    svg(SHARE / "deckos/branding/wallpaper.svg").render(p, QRectF(0, 0, 1600, 900))
    panel, dialog, tip = (svg(THEME / f) for f in ("widgets/panel-background.svg", "dialogs/background.svg",
                                                   "widgets/tooltip.svg"))
    icons = SHARE / "deckos/icons"
    font = QFont("Segoe UI", 10)
    p.setFont(font)

    # dock
    dock = QRectF(520, 820, 560, 56)
    inner = draw_frame(p, panel, dock)
    names = ["home", "folder", "terminal", "external", "gaming", "code", "system"]
    for i, n in enumerate(names):
        svg(icons / f"{n}.svg", "#E8EAF0").render(p, QRectF(inner.x() + 6 + i * 44, inner.y() + 10, 24, 24))
    p.setPen(QColor("#E8EAF0"))
    p.drawText(QRectF(inner.right() - 120, inner.y(), 110, inner.height()), Qt.AlignVCenter | Qt.AlignRight,
               "2026-10-28  19:42")

    # launcher popup
    pop = QRectF(520, 380, 380, 420)
    c = draw_frame(p, dialog, pop)
    p.setPen(QColor("#8C94A6"))
    p.drawText(QRectF(c.x() + 6, c.y() + 4, 300, 20), "APPLICATIONS")
    for i, (n, t) in enumerate((("gaming", "Steam"), ("ai", "DeckOS Hub"), ("terminal", "Konsole"),
                                ("folder", "Dolphin"), ("code", "VS Code"), ("display", "System Settings"))):
        yy = c.y() + 36 + i * 50
        if i == 1:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(76, 141, 255, 50))
            p.drawRoundedRect(QRectF(c.x(), yy - 6, c.width(), 42), 8, 8)
        svg(icons / f"{n}.svg", "#4C8DFF" if i == 1 else "#C9CEDA").render(p, QRectF(c.x() + 10, yy + 3, 24, 24))
        p.setPen(QColor("#E8EAF0"))
        p.drawText(QRectF(c.x() + 46, yy, 260, 30), Qt.AlignVCenter, t)

    # tooltip over the dock
    tt = QRectF(830, 760, 150, 40)
    tc = draw_frame(p, tip, tt)
    p.setPen(QColor("#E8EAF0"))
    p.drawText(tc, Qt.AlignCenter, "DeckOS Hub")
    p.end()
    img.save(out)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
