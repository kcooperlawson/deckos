"""DecKoOS Hub's Vibe editor: make your own Vibe from any photo. The photo shows as it will fill the screen; click
to put a light where the picture has one (a lamp, a window, a sign), click a light to choose what it answers to
(bass, melody, highs), scroll to size it, right-click to take it away. "Find the lights" spots the bright places
for you. The lights pulse to a made-up song while you work, so you see the Vibe before using it.

vibes.py checks and saves it (your config: no password); `deckos vibe apply` puts it on the desktop.
"""
import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFormLayout,
                               QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vibes"))
import hub_style as S  # noqa: E402
import vibes  # noqa: E402
from hub_widgets import button, label, row  # noqa: E402

PART_NAMES = {"bass": "Bass", "mid": "Melody", "high": "Highs"}
THEME_NAMES = {"org.deckos.ember": "Ember", "org.deckos.midnight": "Midnight", "org.deckos.graphite": "Graphite",
               "org.deckos.aurora": "Aurora", "org.deckos.crimson": "Crimson", "org.deckos.paper": "Paper",
               "org.deckos.desktop": "DecKoOS"}


def crop_16_9(img):
    """The part of a photo a 16:9 screen shows when the picture fills it (what the wallpaper does)."""
    w, h = img.width(), img.height()
    if w / max(h, 1) > 16 / 9:
        cw = int(h * 16 / 9)
        return img.copy((w - cw) // 2, 0, cw, h)
    ch = int(w * 9 / 16)
    return img.copy(0, (h - ch) // 2, w, ch)


def find_lights(img, limit=12):
    """Bright spots worth lighting up: local peaks of brightness on a small copy, strongest first, kept apart.
    Returns [[x, y, size, part]] in fractions of the 16:9 view."""
    small = crop_16_9(img).scaled(160, 90, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    w, h = small.width(), small.height()
    lum = [[QColor(small.pixel(x, y)).lightnessF() for x in range(w)] for y in range(h)]
    avg = sum(map(sum, lum)) / (w * h)
    peaks = []
    for y in range(2, h - 2):
        for x in range(2, w - 2):
            v = lum[y][x]
            if v < max(0.55, avg + 0.3):
                continue
            near = [lum[y + dy][x + dx] for dy in (-2, -1, 0, 1, 2) for dx in (-2, -1, 0, 1, 2)]
            if v < max(near) or sum(n >= v - 0.04 for n in near) > 9:
                continue  # not the brightest here, or part of a broad bright area (a sky, a wall) rather than a point
            # A light stands out from what's around it; a bright cloud or a pale wall doesn't
            ring = [lum[min(h - 1, max(0, y + dy))][min(w - 1, max(0, x + dx))]
                    for dy, dx in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3))]
            if v - sum(ring) / len(ring) > 0.18:
                peaks.append((v, x, y))
    peaks.sort(reverse=True)
    out = []
    for v, x, y in peaks:
        fx, fy = x / w, y / h
        if all(math.hypot(fx - o[0], (fy - o[1]) * 9 / 16) > 0.05 for o in out):
            # Lower in the picture (nearer) lights are bigger; brightest ones answer to the bass
            out.append([round(fx, 3), round(fy, 3), round(0.08 + 0.1 * fy, 3), "bass" if len(out) < 4 else
                        "mid" if len(out) < 9 else "high"])
        if len(out) >= limit:
            break
    return out


def photo_colours(img):
    """Two colours from a photo for the Vibe: its most vivid hue, and a second, different one."""
    small = img.scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    buckets = {}
    for y in range(32):
        for x in range(32):
            c = QColor(small.pixel(x, y))
            hh, s, v, _ = c.getHsvF()
            if s < 0.25 or v < 0.25:
                continue
            k = int(max(hh, 0) * 12)
            b = buckets.setdefault(k, [0, c, 0.0])
            b[0] += 1
            if s * v > b[2]:
                b[1], b[2] = c, s * v
    ranked = sorted(buckets.items(), key=lambda kv: -kv[1][0] * (0.5 + kv[1][2]))
    if not ranked:
        return "#FF9E7A", "#B36BFF"
    a = QColor.fromHsvF(max(ranked[0][1][1].hsvHueF(), 0), 0.65, 1.0)
    second = next((b[1] for k, b in ranked[1:] if min(abs(k - ranked[0][0]), 12 - abs(k - ranked[0][0])) >= 2), None)
    b = QColor.fromHsvF(max(second.hsvHueF(), 0), 0.6, 0.95) if second else \
        QColor.fromHsvF((a.hsvHueF() + 0.45) % 1, 0.6, 0.95)
    return a.name().upper(), b.name().upper()


class PhotoView(QWidget):
    """The photo with its lights, pulsing to a made-up song. Click to add, click a light to change its part,
    scroll on one to size it, right-click to remove."""

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.img, self.pm = QImage(), None
        self.lights = []
        self.t = 0.0
        self.setMinimumSize(640, 360)
        self.setCursor(Qt.CrossCursor)
        self.clock = QTimer(self, interval=33, timeout=self.step)
        self.clock.start()

    def set_photo(self, img):
        self.img = crop_16_9(img) if not img.isNull() else QImage()
        self.pm = None
        self.update()

    def step(self):
        self.t += 0.033
        self.update()

    def area(self):
        w = self.width()
        h = w * 9 / 16
        if h > self.height():
            h = self.height()
            w = h * 16 / 9
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def music(self):
        """A made-up song: a kick every half second, a melody swelling, hi-hats."""
        kick = math.exp(-((self.t % 0.5) * 8))
        return {"bass": kick, "mid": 0.4 + 0.4 * math.sin(self.t * 1.3), "high": 0.3 + 0.5 * (self.t * 4 % 1 < 0.15)}

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(S.SURFACE))
        r = self.area()
        if self.img.isNull():
            p.setPen(QColor(S.SUBTEXT))
            p.setFont(QFont("Inter", 13))
            p.drawText(r, Qt.AlignCenter, "Pick a photo to start")
            return
        if self.pm is None or self.pm.size() != r.size().toSize():
            self.pm = QPixmap.fromImage(self.img.scaled(r.size().toSize(), Qt.IgnoreAspectRatio,
                                                        Qt.SmoothTransformation))
        p.drawPixmap(r.topLeft(), self.pm)
        m = self.music()
        a, b = QColor(self.editor.colour_a), QColor(self.editor.colour_b)
        for x, y, size, part in self.lights:
            v = m[part]
            c = QPointF(r.left() + x * r.width(), r.top() + y * r.height())
            rad = r.height() * size * (1 + 0.5 * v)  # the same reach as on the desktop (PhotoScene)
            col = a if part == "bass" else b if part == "mid" else QColor("#F4F6FF")
            g = QRadialGradient(c, rad)
            k = QColor(col)
            k.setAlphaF(min(1.0, 0.25 + 0.7 * v))
            g.setColorAt(0, k)
            k2 = QColor(col)
            k2.setAlphaF(0.2 * (0.3 + v))
            g.setColorAt(0.25, k2)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, rad, rad)
            # The marker: so each light can be found and changed
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, 7, 7)
            p.setFont(QFont("Inter", 8, QFont.Bold))
            p.drawText(QRectF(c.x() + 9, c.y() - 8, 60, 16), Qt.AlignLeft | Qt.AlignVCenter, PART_NAMES[part])

    def hit(self, pos):
        r = self.area()
        for i, (x, y, _s, _p) in enumerate(self.lights):
            if math.hypot(pos.x() - (r.left() + x * r.width()), pos.y() - (r.top() + y * r.height())) < 12:
                return i
        return -1

    def mousePressEvent(self, e):
        if self.img.isNull():
            return
        i = self.hit(e.position())
        if e.button() == Qt.RightButton:
            if i >= 0:
                self.lights.pop(i)
        elif i >= 0:
            parts = list(PART_NAMES)
            self.lights[i][3] = parts[(parts.index(self.lights[i][3]) + 1) % 3]
        elif len(self.lights) < 40:
            r = self.area()
            if r.contains(e.position()):
                fx, fy = (e.position().x() - r.left()) / r.width(), (e.position().y() - r.top()) / r.height()
                self.lights.append([round(fx, 3), round(fy, 3), 0.12, self.editor.part()])
        self.update()

    def wheelEvent(self, e):
        i = self.hit(e.position())
        if i >= 0:
            s = self.lights[i][2] * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1)
            self.lights[i][2] = round(min(0.6, max(0.02, s)), 3)
            self.update()


class VibeEditor(QDialog):
    def __init__(self, parent, key=None):
        super().__init__(parent)
        self.key = key
        old = vibes.all_vibes().get(key, {}) if key else {}
        self.setWindowTitle("Edit your Vibe" if key else "Make your own Vibe")
        self.resize(1180, 700)
        self.photo = old.get("photo", "")
        self.colour_a, self.colour_b = old.get("colorA", "#FF9E7A"), old.get("colorB", "#B36BFF")
        outer = QHBoxLayout(self)
        outer.setSpacing(16)
        left = QVBoxLayout()
        self.view = PhotoView(self)
        left.addWidget(self.view, 1)
        left.addWidget(label("Click to add a light where the picture has one · click a light to change what it "
                             "follows · scroll on it to size it · right-click to remove", "muted"))
        outer.addLayout(left, 3)

        form_host = QWidget()
        form_host.setFixedWidth(400)
        form = QFormLayout(form_host)
        form.setVerticalSpacing(10)
        self.name = QLineEdit(old.get("name", ""))
        self.name.setPlaceholderText("My Vibe")
        form.addRow("Name", self.name)
        form.addRow(row(button("Pick a photo…", "primary", self.pick_photo, icon="image"),
                        button("Find the lights", slot=self.auto_lights, icon="star")))
        self.parts = QButtonGroup(self)
        seg = []
        for k, text in PART_NAMES.items():
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(k == "bass")
            b.setProperty("part", k)
            self.parts.addButton(b)
            seg.append(b)
        form.addRow("Lights follow", row(*seg))
        self.a_btn = button("", slot=lambda: self.pick_colour("a"))
        self.b_btn = button("", slot=lambda: self.pick_colour("b"))
        form.addRow("Colours", row(self.a_btn, self.b_btn, button("From the photo", slot=self.colours_from_photo)))
        self.theme = QComboBox()
        for tid, text in THEME_NAMES.items():
            self.theme.addItem(text, tid)
        self.theme.setCurrentIndex(max(0, self.theme.findData(old.get("theme", "org.deckos.graphite"))))
        form.addRow("Theme", self.theme)
        self.corners = QComboBox()
        for k, text in (("round", "Round"), ("default", "Medium"), ("sharp", "Sharp")):
            self.corners.addItem(text, k)
        self.corners.setCurrentIndex(max(0, self.corners.findData(old.get("corners", "default"))))
        form.addRow("Corners", self.corners)
        self.overlay = QComboBox()
        for k, text in (("none", "Nothing (the lights are it)"), ("bars", "Bars"), ("wave", "Wave"),
                        ("ring", "Ring")):
            self.overlay.addItem(text, k)
        self.overlay.setCurrentIndex(max(0, self.overlay.findData(old.get("visualizer", "none"))))
        form.addRow("Music on top", self.overlay)
        self.grain = QSlider(Qt.Horizontal)
        self.grain.setRange(0, 20)
        self.grain.setValue(int(old.get("grain", 0.05) * 100))
        form.addRow("Film grain", self.grain)
        self.vignette = QSlider(Qt.Horizontal)
        self.vignette.setRange(0, 90)
        self.vignette.setValue(int(old.get("vignette", 0.5) * 100))
        form.addRow("Dark corners", self.vignette)
        self.clock = QCheckBox("Follow the time of day")
        self.clock.setToolTip("Bluer at night, warm in the evening, pink at dawn")
        self.clock.setChecked(old.get("clock", True))
        form.addRow(self.clock)
        form.addRow(row(button("Cancel", slot=self.reject), button("Save", slot=lambda: self.save(False)),
                        button("Save and use", "primary", lambda: self.save(True), icon="check")))
        outer.addWidget(form_host)
        self.use = False
        self.paint_colours()
        if self.photo:
            self.view.set_photo(QImage(self.photo))
            self.view.lights = [list(x) for x in old.get("lights", [])]

    def part(self):
        b = self.parts.checkedButton()
        return b.property("part") if b else "bass"

    def paint_colours(self):
        for btn, c in ((self.a_btn, self.colour_a), (self.b_btn, self.colour_b)):
            btn.setFixedWidth(40)
            btn.setStyleSheet(f"background: {c}; border: 1px solid {S.BORDER}; border-radius: 8px; min-height: 26px;")
        self.view.update()

    def pick_colour(self, which):
        start = QColor(self.colour_a if which == "a" else self.colour_b)
        c = QColorDialog.getColor(start, self, "A colour for the Vibe")
        if c.isValid():
            if which == "a":
                self.colour_a = c.name().upper()
            else:
                self.colour_b = c.name().upper()
            self.paint_colours()

    def colours_from_photo(self):
        if not self.view.img.isNull():
            self.colour_a, self.colour_b = photo_colours(self.view.img)
            self.paint_colours()

    def pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "A photo for your Vibe", str(Path.home() / "Pictures"),
                                              "Pictures (*.jpg *.jpeg *.png *.webp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, "Vibe", "That file isn't a picture DecKoOS can open.")
            return
        self.photo = path
        self.view.set_photo(img)
        if not self.view.lights:
            self.view.lights = find_lights(img)
        self.colours_from_photo()
        if not self.name.text().strip():
            self.name.setText(Path(path).stem.replace("_", " ").replace("-", " ").title()[:40])

    def auto_lights(self):
        if not self.view.img.isNull():
            self.view.lights = find_lights(self.view.img)
            self.view.update()

    def vibe(self):
        return {"name": self.name.text().strip() or "My Vibe", "summary": "Your own photo, alive with the music",
                "scene": "photo", "visualizer": self.overlay.currentData(), "colorA": self.colour_a,
                "colorB": self.colour_b, "accent": self.colour_a, "theme": self.theme.currentData(),
                "corners": self.corners.currentData(), "photo": self.photo, "lights": self.view.lights,
                "grain": self.grain.value() / 100, "vignette": self.vignette.value() / 100,
                "clock": self.clock.isChecked()}

    def save(self, use):
        if not self.photo:
            QMessageBox.information(self, "Vibe", "Pick a photo first.")
            return
        try:
            self.key = vibes.save(self.vibe(), key=self.key)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Vibe", f"Couldn't save it: {e}")
            return
        self.use = use
        self.accept()
