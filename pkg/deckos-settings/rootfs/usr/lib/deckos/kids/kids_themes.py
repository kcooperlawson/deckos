"""Kid mode's themes: a scene behind the tiles, painted here (no image files), its colours and a friend who says
hello. A parent picks one per child (Hub > Kids, or deckos kids theme NAME THEME); any theme suits any child.

The scene moves gently (a few frames a second) only while Kid mode's window is the one on screen.
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QRadialGradient

EMOJI = "Noto Color Emoji"

# id: name, a few words for the parent, sky (top, bottom), tile colours, text colour, the friend
THEMES = {
    "space": ("Space", "Stars, planets and a rocket", ("#0B1030", "#2A1B5C"),
              ["#FF7A59", "#4C8DFF", "#3DD68C", "#F5B84B", "#B36BFF", "#22C7B8"], "#FFFFFF", "🚀"),
    "ocean": ("Under the sea", "Bubbles, fish and waves", ("#0B5FA5", "#04294F"),
              ["#FF8A5B", "#FFC94B", "#3DD6C4", "#7AB8FF", "#FF6F91", "#9B7BFF"], "#FFFFFF", "🐠"),
    "dinos": ("Dinosaurs", "Volcanoes, jungle and dinosaurs", ("#7BC8F6", "#BFE8A8"),
              ["#3E9B4F", "#E07A2F", "#2F7FD0", "#C9483A", "#8A5CC9", "#D9A21E"], "#1E3A1E", "🦖"),
    "castle": ("Fairy castle", "A castle, sparkles and a unicorn", ("#FFC7E6", "#C7B8FF"),
               ["#FF5FA2", "#9B6BFF", "#FF9F5A", "#3FB8C8", "#E05FC9", "#6B8CFF"], "#3A1F4A", "🦄"),
    "rainbow": ("Rainbow", "A rainbow, clouds and sunshine", ("#8FD3FF", "#E8F6FF"),
                ["#FF6B6B", "#FFA94D", "#FFD43B", "#51CF66", "#4DABF7", "#9775FA"], "#23324A", "🌈"),
}
DEFAULT = "space"


def theme(tid):
    t = THEMES.get(tid) or THEMES[DEFAULT]
    return {"id": tid if tid in THEMES else DEFAULT, "name": t[0], "about": t[1], "sky": t[2], "tiles": t[3],
            "text": t[4], "friend": t[5]}


def emoji(p, ch, x, y, size):
    """A colour emoji centred on (x, y)."""
    f = QFont(EMOJI)
    f.setPixelSize(int(size))
    p.setFont(f)
    p.setPen(QColor("#000000"))  # a colour font ignores it, but with no pen at all nothing is drawn
    p.drawText(QRectF(x - size, y - size, size * 2, size * 2), Qt.AlignCenter, ch)


class Scene:
    """Everything that moves in a theme's background, made once for the window's size."""

    def __init__(self, tid, seed=7):
        self.t = theme(tid)
        self.rng = random.Random(seed)
        self.dots = [(self.rng.random(), self.rng.random(), self.rng.uniform(1.2, 3.2), self.rng.random() * 6.3)
                     for _ in range(70)]

    def paint(self, p, r, tick):
        """Paints the scene into rect r; tick counts frames (a few a second)."""
        t = self.t
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(t["sky"][0]))
        g.setColorAt(1, QColor(t["sky"][1]))
        p.fillRect(r, g)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = r.width(), r.height()
        getattr(self, "_" + t["id"])(p, r, w, h, tick)

    # ---- the scenes: shapes near the edges and corners, so the tiles in the middle stay easy to see

    def _space(self, p, r, w, h, tick):
        for x, y, size, phase in self.dots:  # twinkling stars
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(tick * 0.4 + phase))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(255 * a)))
            p.drawEllipse(QPointF(r.left() + x * w, r.top() + y * h), size, size)
        self._planet(p, QPointF(r.right() - 110, r.top() + h * 0.42), 64, "#FF9F5A", "#C2410C", ring=True)
        self._planet(p, QPointF(r.left() + 70, r.bottom() - 90), 46, "#7AB8FF", "#1E4FA0")
        emoji(p, "🚀", r.right() - 70 - 20 * math.sin(tick * 0.08), r.bottom() - 110 + 8 * math.sin(tick * 0.2), 46)

    def _planet(self, p, c, rad, light, dark, ring=False):
        g = QRadialGradient(c - QPointF(rad * 0.4, rad * 0.4), rad * 1.4)
        g.setColorAt(0, QColor(light))
        g.setColorAt(1, QColor(dark))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, rad, rad)
        if ring:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(255, 230, 200, 150))
            p.drawEllipse(c, rad * 1.6, rad * 0.45)

    def _ocean(self, p, r, w, h, tick):
        p.setPen(Qt.NoPen)
        for x, y, size, phase in self.dots[:40]:  # bubbles rising
            yy = (y - tick * 0.004 * size) % 1.0
            p.setBrush(QColor(255, 255, 255, 60))
            p.drawEllipse(QPointF(r.left() + x * w + 6 * math.sin(tick * 0.2 + phase), r.top() + yy * h),
                          size * 3, size * 3)
        sand = QPainterPath()
        sand.moveTo(r.left(), r.bottom())
        for i in range(0, int(w) + 40, 40):
            sand.lineTo(r.left() + i, r.bottom() - 46 - 10 * math.sin(i / 90))
        sand.lineTo(r.right(), r.bottom())
        p.setBrush(QColor("#E8C98A"))
        p.drawPath(sand)
        for i, (ch, size) in enumerate((("🐠", 42), ("🐟", 34), ("🐡", 38))):
            x = (tick * (3 + i) + i * 400) % (w + 120) - 60
            emoji(p, ch, r.left() + x, r.top() + 90 + i * 150 + 10 * math.sin(tick * 0.15 + i), size)
        emoji(p, "🐙", r.left() + 60, r.bottom() - 80, 52)
        emoji(p, "🪸", r.right() - 70, r.bottom() - 70, 50)

    def _dinos(self, p, r, w, h, tick):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8C6A4F"))
        peak = r.bottom() - min(230, h * 0.3)  # a small volcano in the corner, below the tiles' row of names
        hill = QPainterPath()
        hill.moveTo(r.right() - 300, r.bottom() - 40)
        hill.lineTo(r.right() - 190, peak)
        hill.lineTo(r.right() - 150, peak)
        hill.lineTo(r.right() - 40, r.bottom() - 40)
        p.drawPath(hill)
        p.setBrush(QColor(255, 140, 60, 140 + int(60 * math.sin(tick * 0.3))))
        p.drawEllipse(QPointF(r.right() - 170, peak - 6), 26, 12)  # the volcano glows
        p.setBrush(QColor("#5DAA4A"))
        p.drawRect(QRectF(r.left(), r.bottom() - 50, w, 50))
        emoji(p, "🦖", r.left() + 90, r.bottom() - 95 - abs(8 * math.sin(tick * 0.35)), 64)
        emoji(p, "🦕", r.right() - 120, r.bottom() - 95, 70)
        emoji(p, "🌴", r.left() + 220, r.bottom() - 100, 70)
        emoji(p, "☁️", r.left() + 120 + (tick % 400), r.top() + 80, 44)

    def _castle(self, p, r, w, h, tick):
        p.setPen(Qt.NoPen)
        for x, y, size, phase in self.dots[:45]:  # sparkles
            a = 0.5 + 0.5 * math.sin(tick * 0.5 + phase)
            p.setBrush(QColor(255, 255, 255, int(200 * a)))
            cx, cy = r.left() + x * w, r.top() + y * h
            p.drawEllipse(QPointF(cx, cy), size * 1.2, size * 0.4)
            p.drawEllipse(QPointF(cx, cy), size * 0.4, size * 1.2)
        emoji(p, "🏰", r.right() - 110, r.bottom() - 120, 96)
        emoji(p, "🦄", r.left() + 90 + 10 * math.sin(tick * 0.2), r.bottom() - 90, 64)
        emoji(p, "🌸", r.left() + 60, r.top() + 70, 40)
        emoji(p, "⭐", r.right() - 80, r.top() + 70 + 6 * math.sin(tick * 0.3), 40)

    def _rainbow(self, p, r, w, h, tick):
        c = QPointF(r.right() - 40, r.bottom() + 40)
        for i, col in enumerate(("#FF6B6B", "#FFA94D", "#FFD43B", "#51CF66", "#4DABF7", "#9775FA")):
            rad = 360 - i * 26
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col))
            p.drawEllipse(c, rad, rad)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(self.t["sky"][0]))
        g.setColorAt(1, QColor(self.t["sky"][1]))
        p.setBrush(g)
        p.drawEllipse(c, 360 - 6 * 26, 360 - 6 * 26)
        emoji(p, "☀️", r.left() + 80, r.top() + 80 + 4 * math.sin(tick * 0.2), 64)
        for i in range(3):
            emoji(p, "☁️", r.left() + ((tick * (1 + i) + i * 350) % (w + 200)) - 100, r.top() + 60 + i * 60, 50 - i * 6)


def render(tid, path, width=3840, height=2160):
    """The theme's scene as a wallpaper picture (a still frame), for the child's desktop. Drawn at 1920×1080 and
    scaled up, so the friends and planets are the size the scenes were made for."""
    from PySide6.QtGui import QImage
    img = QImage(1920, 1080, QImage.Format_RGB32)
    p = QPainter(img)
    Scene(tid).paint(p, QRectF(0, 0, 1920, 1080), 12)
    p.end()
    img.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).save(str(path))
    return path
