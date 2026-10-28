"""DecKoOS Music: your music and Spotify in one player that moves with the sound.

Now playing shows whatever plays (the Spotify app, followed through MPRIS; or your own files, played here), and
everything on it reacts to the sound coming out of the PC (analysis.py): the cover's colours tint the window, the
glow swells with the bass and flashes on the beat, the cover pulses, a spectrum rings it and particles drift
faster as the song gets more intense. Scenes (V) fill the window with Nebula, Tunnel or Waves. The library
(library.py) is your Music folders, as albums and songs.

Drawing runs only while the window is visible and something is playing; paused, it rests.

    deckos-music [--demo] [--screenshot DIR]
"""
import hashlib
import math
import random
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QKeySequence, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient, QShortcut)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSlider, QStackedWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]
import analysis  # noqa: E402
import hub_style as S  # noqa: E402
import library  # noqa: E402
import sources  # noqa: E402

DEMO = "--demo" in sys.argv
ART_CACHE = library.CACHE / "art"


# ------------------------------------------------------------------ colours from a cover

def palette(img):
    """(base, accent, second) colours from a cover: the base dark enough for white text, the accent the most vivid
    colour that's really in the picture, the second a different hue from it."""
    if img is None or img.isNull():
        return QColor("#141826"), QColor(S.P.accent), QColor("#7A5CFF")
    small = img.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    px = [small.pixelColor(x, y) for x in range(24) for y in range(24)]
    buckets = {}
    for c in px:
        h, s, v, _ = c.getHsvF()
        if s < 0.25 or v < 0.2:
            continue
        key = int((h if h >= 0 else 0) * 12)
        b = buckets.setdefault(key, [0, QColor(c), 0.0])
        b[0] += 1
        if s * v > b[2]:
            b[1], b[2] = QColor(c), s * v
    avg = QColor(sum(c.red() for c in px) // len(px), sum(c.green() for c in px) // len(px),
                 sum(c.blue() for c in px) // len(px))
    base = QColor.fromHsvF(max(avg.hsvHueF(), 0), min(avg.hsvSaturationF() * 0.9, 0.6), 0.16)
    ranked = sorted(buckets.items(), key=lambda kv: -(kv[1][0] * (0.5 + kv[1][2])))
    if not ranked:
        return base, QColor(S.P.accent), QColor("#7A5CFF")
    accent = QColor.fromHsvF(max(ranked[0][1][1].hsvHueF(), 0), max(ranked[0][1][1].hsvSaturationF(), 0.55), 1.0)
    second = next((QColor.fromHsvF(max(b[1].hsvHueF(), 0), max(b[1].hsvSaturationF(), 0.5), 0.95)
                   for k, b in ranked[1:] if min(abs(k - ranked[0][0]), 12 - abs(k - ranked[0][0])) >= 2),
                  QColor.fromHsvF((accent.hsvHueF() + 0.45) % 1, 0.6, 0.95))
    return base, accent, second


def blurred(img, size):
    """A soft, blown-up copy of the cover for the background: shrunk to a few pixels and smoothed back up."""
    tiny = img.scaled(18, 18, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    mid = tiny.scaled(180, 180, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    return QPixmap.fromImage(mid.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))


def demo_cover(seed=1):
    """A made-up album cover for the demo (no pictures shipped): bold shapes in two colours."""
    img = QImage(600, 600, QImage.Format_RGB32)
    rng = random.Random(seed)
    a = QColor.fromHsvF(rng.random(), 0.75, 0.95)
    b = QColor.fromHsvF((a.hsvHueF() + 0.5) % 1, 0.7, 0.55)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 600, 600)
    g.setColorAt(0, b.darker(180))
    g.setColorAt(1, b)
    p.fillRect(img.rect(), g)
    p.setPen(Qt.NoPen)
    for i in range(6):
        c = QColor(a)
        c.setAlphaF(0.25 + 0.12 * i)
        p.setBrush(c)
        r = 260 - i * 40
        p.drawEllipse(QPointF(300 + rng.randint(-60, 60), 300 + rng.randint(-60, 60)), r, r)
    p.end()
    return img


# ------------------------------------------------------------------ the picture behind it all

class Art(QWidget):
    """Loads covers (files, or URLs into a cache) and keeps the colours that go with them."""
    ready = Signal()

    def __init__(self):
        super().__init__()
        self.net = QNetworkAccessManager(self)
        self.img, self.key = QImage(), None
        self.base, self.accent, self.second = palette(None)

    def load(self, ref, demo_seed=None):
        if ref == self.key:
            return
        self.key = ref
        if demo_seed is not None:
            self.set(demo_cover(demo_seed))
        elif ref.startswith("http"):
            cached = ART_CACHE / (hashlib.sha1(ref.encode()).hexdigest() + ".jpg")
            if cached.exists():
                self.set(QImage(str(cached)))
                return
            reply = self.net.get(QNetworkRequest(QUrl(ref)))
            reply.finished.connect(lambda r=reply, c=cached, k=ref: self.got(r, c, k))
        elif ref:
            self.set(QImage(ref.removeprefix("file://")))
        else:
            self.set(QImage())

    def got(self, reply, cached, key):
        data = bytes(reply.readAll())
        reply.deleteLater()
        if key != self.key or not data:
            return
        ART_CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        self.set(QImage.fromData(data))

    def set(self, img):
        self.img = img
        self.base, self.accent, self.second = palette(img if not img.isNull() else None)
        self.ready.emit()


class Particles:
    """Specks drifting out from the middle: more of them, and faster, as the song gets more intense."""

    def __init__(self, n=140):
        self.rng = random.Random(5)
        self.p = [self.spawn(far=True) for _ in range(n)]

    def spawn(self, far=False):
        return [self.rng.random() * math.tau, self.rng.uniform(0.15, 1.0) if far else self.rng.uniform(0.12, 0.2),
                self.rng.uniform(0.6, 1.4), self.rng.uniform(1.0, 2.6)]

    def step(self, f):
        speed = 0.0015 + 0.012 * f["intensity"] + (0.02 * f["beat_strength"] if f["beat"] else 0)
        for q in self.p:
            q[1] += speed * q[2]
            if q[1] > 1.15:
                q[:] = self.spawn()

    def paint(self, p, c, radius, colour, f):
        p.setPen(Qt.NoPen)
        col = QColor(colour)
        for a, d, _s, size in self.p:
            col.setAlphaF(max(0.0, min(1.0, (1.15 - d))) * (0.35 + 0.5 * f["high"]))
            p.setBrush(col)
            p.drawEllipse(QPointF(c.x() + math.cos(a) * d * radius, c.y() + math.sin(a) * d * radius), size, size)


class NowPlaying(QWidget):
    """The cover, alive: everything here is drawn each frame from the latest sound."""

    def __init__(self, art):
        super().__init__()
        self.art = art
        self.now = sources.Now()
        self.f = dict(analysis.Features().state)
        self.bg, self.bg_key = None, None
        self.cover, self.cover_key = None, None
        self.particles = Particles()
        self.flash = 0.0
        self.pulse = 0.0
        self.spin = 0.0  # the record turns while it plays, faster as the song gets more intense
        self.setMinimumSize(640, 420)

    def feed(self, f):
        self.f = f
        self.particles.step(f)
        if self.now.playing:
            self.spin = (self.spin + 0.12 + 0.5 * f["intensity"]) % 360
        if f["beat"]:
            self.flash = max(self.flash, 0.55 + 0.45 * f["beat_strength"])
            self.pulse = 1.0
        self.flash *= 0.88
        self.pulse *= 0.84
        self.update()

    def ensure(self):
        key = (self.art.key, self.size().width(), self.size().height())
        if self.bg_key != key:
            self.bg_key = key
            self.bg = blurred(self.art.img, self.size()) if not self.art.img.isNull() else None
        if self.cover_key != self.art.key:
            self.cover_key = self.art.key
            self.cover = QPixmap.fromImage(self.art.img.scaled(720, 720, Qt.KeepAspectRatioByExpanding,
                                                               Qt.SmoothTransformation)) if not self.art.img.isNull() else None

    def paintEvent(self, _e):
        self.ensure()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        f, art = self.f, self.art
        base, accent, second = art.base, art.accent, art.second
        # The cover, blown up and blurred, under a wash of its own darkest colour
        p.fillRect(r, base)
        if self.bg:
            p.setOpacity(0.55)
            p.drawPixmap(int((r.width() - self.bg.width()) / 2), int((r.height() - self.bg.height()) / 2), self.bg)
            p.setOpacity(1.0)
        shade = QColor(base)
        shade.setAlphaF(0.55)
        p.fillRect(r, shade)
        size = min(r.width() * 0.34, r.height() * 0.5)
        c = QPointF(r.center().x(), r.top() + r.height() * 0.44)
        # The glow: swells with the bass, flashes on the beat
        glow = QRadialGradient(c, size * (0.9 + 0.7 * f["bass"] + 0.4 * self.flash))
        g1 = QColor(accent)
        g1.setAlphaF(min(1.0, 0.25 + 0.45 * f["bass"] + 0.35 * self.flash))
        g2 = QColor(second)
        g2.setAlphaF(0.12 + 0.2 * f["mid"])
        glow.setColorAt(0, g1)
        glow.setColorAt(0.55, g2)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(r, glow)
        self.particles.paint(p, c, max(r.width(), r.height()) * 0.6, accent.lighter(130), f)
        # The ring: 128 bars around the cover, mirrored, low notes at the top
        bars = f["bars"]
        inner = size * 0.58
        n = len(bars) * 2
        for i in range(n):
            v = bars[i if i < len(bars) else n - 1 - i]
            a = -math.pi / 2 + i * math.tau / n
            length = 6 + v * size * (0.2 + 0.16 * f["intensity"])
            col = QColor.fromHsvF((accent.hsvHueF() + (second.hsvHueF() - accent.hsvHueF()) * v) % 1,
                                  max(accent.hsvSaturationF(), 0.5), 1.0, 0.55 + 0.45 * v)
            pen = QPen(col, max(2.0, size * 0.012))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(c.x() + math.cos(a) * inner, c.y() + math.sin(a) * inner),
                       QPointF(c.x() + math.cos(a) * (inner + length), c.y() + math.sin(a) * (inner + length)))
        # The cover, as a record: round, turning while it plays, pulsing on the beat
        s = size * (1 + 0.035 * self.pulse + 0.015 * f["bass"])
        box = QRectF(c.x() - s / 2, c.y() - s / 2, s, s)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 130))
        p.drawEllipse(box.adjusted(-2, 12, 2, 16))
        clip = QPainterPath()
        clip.addEllipse(box)
        p.save()
        p.setClipPath(clip)
        p.translate(c)
        p.rotate(self.spin)
        p.translate(-c)
        if self.cover:
            p.drawPixmap(box.toRect(), self.cover)
        else:
            p.fillRect(box, accent.darker(200))
        p.restore()
        # The record's grooves and label hole, so the turning shows even on a plain cover
        p.setBrush(Qt.NoBrush)
        for k in (0.36, 0.42, 0.48):
            p.setPen(QPen(QColor(255, 255, 255, 22), 1))
            p.drawEllipse(c, s * k, s * k)
        p.setPen(Qt.NoPen)
        p.setBrush(base.darker(140))
        p.drawEllipse(c, s * 0.045, s * 0.045)
        p.setPen(QPen(QColor(255, 255, 255, int(40 + 150 * self.flash)), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(box)
        # How far into the song: a thin arc just outside the record
        if self.now.length:
            arc = box.adjusted(-10, -10, 10, 10)
            p.setPen(QPen(QColor(255, 255, 255, 40), 3))
            p.drawEllipse(arc)
            pen = QPen(accent.lighter(120), 3)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(arc, 90 * 16, int(-360 * 16 * min(1.0, self.now.position / self.now.length)))
        # Title and artist
        now = self.now
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Inter Display", 26, QFont.Bold))
        y = box.bottom() + 34
        title = now.title or ("Nothing playing" if not now.available else "")
        p.drawText(QRectF(0, y, r.width(), 44), Qt.AlignHCenter | Qt.AlignTop,
                   p.fontMetrics().elidedText(title, Qt.ElideRight, int(r.width() * 0.8)))
        p.setPen(QColor(255, 255, 255, 190))
        p.setFont(QFont("Inter", 14))
        sub = " · ".join(x for x in (now.artist, now.album) if x) or \
            "Play something in Spotify, or pick music from your library"
        p.drawText(QRectF(0, y + 44, r.width(), 30), Qt.AlignHCenter | Qt.AlignTop,
                   p.fontMetrics().elidedText(sub, Qt.ElideRight, int(r.width() * 0.8)))


# ------------------------------------------------------------------ scenes

class Scene(QWidget):
    """Full-window visuals. Click or Esc goes back."""
    leave = Signal()
    NAMES = ["Nebula", "Tunnel", "Waves"]

    def __init__(self, art):
        super().__init__()
        self.art, self.kind, self.t = art, 0, 0.0
        self.f = dict(analysis.Features().state)
        self.stars = [[random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0.05, 1)] for _ in range(420)]
        self.rings = []
        self.flash = 0.0
        self.setCursor(Qt.BlankCursor)

    def feed(self, f):
        self.f = f
        self.t += 1 / 60 * (0.6 + 1.6 * f["intensity"])
        if f["beat"]:
            self.flash = 0.6 + 0.4 * f["beat_strength"]
            self.rings.append([0.02, QColor(self.art.accent if len(self.rings) % 2 else self.art.second)])
        self.flash *= 0.9
        for ring in self.rings:
            ring[0] += 0.012 + 0.03 * f["intensity"]
        self.rings = [x for x in self.rings if x[0] < 1.6]
        speed = 0.004 + 0.03 * f["intensity"] + 0.05 * f["bass"]
        for s in self.stars:
            s[2] -= speed
            if s[2] <= 0.02:
                s[:] = [random.uniform(-1, 1), random.uniform(-1, 1), 1.0]
        self.update()

    def mousePressEvent(self, _e):
        self.leave.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.fillRect(r, QColor("#05060A"))
        getattr(self, ["nebula", "tunnel", "waves"][self.kind])(p, r)
        p.setPen(QColor(255, 255, 255, 120))
        p.setFont(QFont("Inter", 11))
        p.drawText(r.adjusted(0, 0, -20, -14), Qt.AlignRight | Qt.AlignBottom,
                   f"{self.NAMES[self.kind]}  ·  V: next scene  ·  Esc: back")

    def nebula(self, p, r):
        """Stars rushing past, faster with the energy; clouds of the cover's colours breathing with the bass."""
        c = r.center()
        for i, col in enumerate((self.art.accent, self.art.second)):
            g = QRadialGradient(QPointF(c.x() + math.sin(self.t * 0.3 + i * 2) * r.width() * 0.2,
                                        c.y() + math.cos(self.t * 0.25 + i) * r.height() * 0.15),
                                r.width() * (0.35 + 0.25 * self.f["bass"]))
            k = QColor(col)
            k.setAlphaF(0.25 + 0.3 * (self.f["bass"] if i == 0 else self.f["mid"]) + 0.2 * self.flash)
            g.setColorAt(0, k)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(r, g)
        # Stars as streaks: the faster the music, the longer they stretch toward you
        stretch = 1 + 4 * self.f["intensity"] + 6 * self.f["bass"]
        for i, (x, y, z) in enumerate(self.stars):
            sx, sy = c.x() + x / z * r.width() * 0.25, c.y() + y / z * r.height() * 0.25
            if not r.contains(QPointF(sx, sy)):
                continue
            z2 = min(1.0, z + 0.012 * stretch)
            tx, ty = c.x() + x / z2 * r.width() * 0.25, c.y() + y / z2 * r.height() * 0.25
            tint = self.art.accent if i % 5 == 0 else self.art.second if i % 7 == 0 else QColor("#FFFFFF")
            col = QColor(tint)
            col.setAlphaF(min(1.0, (1 - z) * 1.5))
            pen = QPen(col, (1 - z) * 3 + 0.5)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(tx, ty), QPointF(sx, sy))

    def tunnel(self, p, r):
        """Rings fired outward on each beat, a slow twisting tunnel of the spectrum behind them."""
        c = r.center()
        bars = self.f["bars"]
        for k in range(14):
            depth = ((k / 14) + self.t * 0.15) % 1
            radius = depth ** 2 * max(r.width(), r.height()) * 0.75
            v = bars[int(depth * (len(bars) - 1))]
            col = QColor.fromHsvF((self.art.accent.hsvHueF() + depth * 0.25) % 1, 0.7, 1.0, 0.15 + 0.55 * v)
            p.setPen(QPen(col, 1.5 + 8 * v * depth))
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            sides = 6
            for j in range(sides + 1):
                a = j * math.tau / sides + self.t * 0.4 + depth
                pt = QPointF(c.x() + math.cos(a) * radius, c.y() + math.sin(a) * radius)
                path.moveTo(pt) if j == 0 else path.lineTo(pt)
            p.drawPath(path)
        for radius, col in self.rings:
            k = QColor(col)
            k.setAlphaF(max(0.0, 1 - radius / 1.6))
            p.setPen(QPen(k, 4))
            p.drawEllipse(c, radius * r.width() * 0.5, radius * r.width() * 0.5)
        g = QRadialGradient(c, r.height() * 0.2)
        k = QColor(self.art.accent)
        k.setAlphaF(0.3 + 0.6 * self.flash)
        g.setColorAt(0, k)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(r, g)

    def waves(self, p, r):
        """Ribbons of the spectrum rolling across, low notes at the bottom, high at the top."""
        bars = self.f["bars"]
        layers = 7
        for L in range(layers):
            frac = L / (layers - 1)
            band = bars[int(frac * (len(bars) - 1)):int(frac * (len(bars) - 1)) + 6] or [0]
            amp = (0.03 + 0.22 * (sum(band) / len(band))) * r.height()
            base_y = r.bottom() - (0.15 + 0.7 * frac) * r.height() * 0.9
            col = QColor.fromHsvF((self.art.accent.hsvHueF() + frac * 0.35) % 1, 0.65, 1.0, 0.25 + 0.3 * (1 - frac))
            path = QPainterPath()
            path.moveTo(r.left(), r.bottom())
            for i in range(0, int(r.width()) + 24, 24):
                y = base_y + math.sin(i / r.width() * math.tau * (1.5 + L * 0.4) + self.t * (1 + L * 0.3)) * amp
                path.lineTo(r.left() + i, y)
            path.lineTo(r.right(), r.bottom())
            path.closeSubpath()
            g = QLinearGradient(0, base_y - amp, 0, r.bottom())
            g.setColorAt(0, col)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillPath(path, g)
        if self.flash > 0.05:
            k = QColor(255, 255, 255, int(40 * self.flash))
            p.fillRect(r, k)


# ------------------------------------------------------------------ the library

class AlbumTile(QPushButton):
    def __init__(self, album, cover):
        super().__init__()
        self.album = album
        self.pm = cover
        self.setFixedSize(190, 240)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{album['title']} — {album['artist']}")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        box = QRectF(5, 5, 180, 180)
        clip = QPainterPath()
        clip.addRoundedRect(box, 12, 12)
        p.save()
        p.setClipPath(clip)
        if self.pm and not self.pm.isNull():
            p.drawPixmap(box.toRect(), self.pm)
        else:
            p.fillRect(box, QColor("#232837"))
            p.setPen(QColor(255, 255, 255, 120))
            p.setFont(QFont("Inter Display", 48, QFont.Bold))
            p.drawText(box, Qt.AlignCenter, "♪")
        p.restore()
        if self.underMouse() or self.hasFocus():
            p.setPen(QPen(QColor(S.P.accent), 3))
            p.drawRoundedRect(box, 12, 12)
        p.setPen(QColor(S.TEXT))
        p.setFont(QFont("Inter", 11, QFont.DemiBold))
        fm = p.fontMetrics()
        p.drawText(QRectF(6, 192, 180, 20), Qt.AlignLeft, fm.elidedText(self.album["title"], Qt.ElideRight, 178))
        p.setPen(QColor(S.SUBTEXT))
        p.setFont(QFont("Inter", 10))
        p.drawText(QRectF(6, 212, 180, 20), Qt.AlignLeft,
                   p.fontMetrics().elidedText(self.album["artist"], Qt.ElideRight, 178))


class Scanner(QThread):
    done = Signal(list)

    def run(self):
        tracks = library.scan()
        for t in tracks:
            t["cover"] = library.cover_for(t)
        self.done.emit(tracks)


DEMO_ALBUMS = [("Neon Harbour", "Lumen Drive"), ("Glass Weather", "Saint Ivory"), ("Low Orbit", "Kairo"),
               ("Paper Suns", "The Avenues"), ("Velvet Static", "Mara Lune"), ("Night Garden", "Holloway"),
               ("Cinder Bloom", "Ostra"), ("Tidal", "Fen & Rye")]


def demo_tracks():
    out = []
    for i, (album, artist) in enumerate(DEMO_ALBUMS):
        for n in range(1, 9):
            out.append({"path": f"/demo/{i}/{n}.flac", "title": f"{['Afterglow', 'Undertow', 'Satellites', 'Halcyon', 'Copper Sky', 'Slow Burn', 'Tangent', 'Driftwood'][n - 1]}",
                        "artist": artist, "album": album, "track": n, "duration": 180 + n * 13, "cover": f"demo:{i}"})
    return out


# ------------------------------------------------------------------ the window

class Music(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("DecKoOS Music")
        self.setWindowIcon(S.icon("music", S.P.accent, 32))
        self.resize(1280, 820)
        self.art = Art()
        self.analyzer = analysis.FakeAnalyzer() if DEMO else analysis.Analyzer()
        self.spotify = sources.Spotify(demo=sources.Now(
            "spotify", "Afterglow (Extended Mix)", "Lumen Drive", "Neon Harbour", "demo:0", 252, 81, True, True)
            if DEMO else None)
        self.local = None  # made on first use: Qt Multimedia starts its backend then
        self.active = self.spotify
        self.tracks = []
        self.covers = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.side = self.sidebar()
        outer.addWidget(self.side)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.pages = QStackedWidget()
        self.now_view = NowPlaying(self.art)
        self.scene = Scene(self.art)
        self.scene.leave.connect(lambda: self.show_page("now"))
        self.albums_page, self.album_grid = self.albums_view()
        self.songs_page = self.songs_view()
        for w in (self.now_view, self.scene, self.albums_page, self.songs_page):
            self.pages.addWidget(w)
        right.addWidget(self.pages, 1)
        self.bar = self.controls()
        right.addWidget(self.bar)
        outer.addLayout(right, 1)

        self.spotify.changed.connect(lambda n: self.source_changed(self.spotify, n))
        self.art.ready.connect(self.colours_changed)
        self.frame = QTimer(self, interval=16, timeout=self.tick)  # ~60 frames a second, only while it matters
        QShortcut(QKeySequence("Space"), self, activated=lambda: self.active.play_pause())
        QShortcut(QKeySequence("V"), self, activated=self.next_scene)
        QShortcut(QKeySequence("Escape"), self, activated=lambda: self.show_page("now"))
        QShortcut(QKeySequence("F11"), self, activated=lambda: self.showNormal() if self.isFullScreen()
                  else self.showFullScreen())
        self.show_page("now")
        if DEMO:
            self.got_tracks(demo_tracks())
        else:
            self.scanner = Scanner()
            self.scanner.done.connect(self.got_tracks)
            self.scanner.start()

    # ---- parts

    def sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 18, 14, 14)
        v.setSpacing(4)
        title = QLabel("Music")
        title.setStyleSheet("font-family: 'Inter Display'; font-size: 20pt; font-weight: 700; padding: 4px 8px 14px;")
        v.addWidget(title)
        self.nav, group = {}, QButtonGroup(self)
        for key, text, icon in (("now", "Now playing", "play"), ("scene", "Scenes", "star"), ("albums", "Albums", "grid"),
                                ("songs", "Songs", "list")):
            b = QPushButton("  " + text)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setIcon(S.icon(icon, S.SUBTEXT, 18, active=S.TEXT))
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(lambda _c=False, k=key: self.show_page(k))
            group.addButton(b)
            v.addWidget(b)
            self.nav[key] = b
        v.addStretch(1)
        self.source_label = QLabel()
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet(f"color: {S.SUBTEXT}; padding: 6px 8px;")
        v.addWidget(self.source_label)
        return side

    def controls(self):
        bar = QFrame()
        bar.setObjectName("playbar")
        bar.setFixedHeight(84)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 10, 20, 10)
        h.setSpacing(12)
        self.mini_art = QLabel()
        self.mini_art.setFixedSize(56, 56)
        h.addWidget(self.mini_art)
        info = QVBoxLayout()
        info.setSpacing(0)
        self.bar_title = QLabel("")
        self.bar_title.setStyleSheet("font-weight: 600;")
        self.bar_sub = QLabel("")
        self.bar_sub.setStyleSheet(f"color: {S.SUBTEXT};")
        info.addWidget(self.bar_title)
        info.addWidget(self.bar_sub)
        holder = QWidget()
        holder.setLayout(info)
        holder.setFixedWidth(260)
        h.addWidget(holder)

        def ctl(icon, slot, tip, big=False):
            b = QPushButton()
            b.setObjectName("playbtn" if big else "ctl")
            b.setIcon(S.icon(icon, "#FFFFFF" if big else S.TEXT, 22 if big else 18))
            b.setIconSize(QSize(22, 22) if big else QSize(18, 18))
            b.setFixedSize(QSize(48, 48) if big else QSize(36, 36))
            b.setToolTip(tip)
            b.clicked.connect(slot)
            return b
        h.addStretch(1)
        h.addWidget(ctl("previous", lambda: self.active.previous(), "Previous"))
        self.play_btn = ctl("play", lambda: self.active.play_pause(), "Play / pause (Space)", big=True)
        h.addWidget(self.play_btn)
        h.addWidget(ctl("next", lambda: self.active.next(), "Next"))
        self.pos_label = QLabel("0:00")
        self.pos_label.setStyleSheet(f"color: {S.SUBTEXT};")
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setFixedWidth(380)
        self.seek.setRange(0, 1000)
        self.seek.sliderReleased.connect(lambda: self.active.seek(self.seek.value() / 1000 * (self.active.now.length or 0)))
        self.len_label = QLabel("0:00")
        self.len_label.setStyleSheet(f"color: {S.SUBTEXT};")
        h.addSpacing(12)
        h.addWidget(self.pos_label)
        h.addWidget(self.seek)
        h.addWidget(self.len_label)
        h.addStretch(1)
        h.addWidget(ctl("star", self.next_scene, "Scenes (V)"))
        return bar

    def albums_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(28, 24, 28, 24)
        grid.setSpacing(12)
        grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        scroll.setWidget(holder)
        return scroll, grid

    def songs_view(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(28, 22, 28, 12)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Search your music")
        self.find.addAction(S.icon("search", S.SUBTEXT, 16), QLineEdit.LeadingPosition)
        self.find.textChanged.connect(self.fill_songs)
        v.addWidget(self.find)
        self.songs = QTreeWidget()
        self.songs.setHeaderLabels(["Title", "Artist", "Album", "Time"])
        self.songs.setRootIsDecorated(False)
        self.songs.setColumnWidth(0, 340)
        self.songs.setColumnWidth(1, 220)
        self.songs.setColumnWidth(2, 260)
        self.songs.itemDoubleClicked.connect(self.play_song)
        v.addWidget(self.songs, 1)
        return w

    # ---- library

    def cover_pixmap(self, ref):
        if ref not in self.covers:
            img = demo_cover(int(ref.split(":")[1]) + 1) if ref.startswith("demo:") else QImage(ref) if ref else QImage()
            self.covers[ref] = QPixmap.fromImage(img.scaled(360, 360, Qt.KeepAspectRatioByExpanding,
                                                            Qt.SmoothTransformation)) if not img.isNull() else None
        return self.covers[ref]

    def got_tracks(self, tracks):
        self.tracks = tracks
        while self.album_grid.count():
            w = self.album_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        albums = library.albums(tracks)
        cols = 5
        for i, a in enumerate(albums):
            tile = AlbumTile(a, self.cover_pixmap(a["tracks"][0].get("cover", "")))
            tile.clicked.connect(lambda _c=False, al=a: self.play_album(al))
            self.album_grid.addWidget(tile, i // cols, i % cols)
        if not albums:
            empty = QLabel("No music found yet. Put music in your Music folder (or a Music folder on any drive) and "
                           "it shows up here. Spotify plays in Now playing.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {S.SUBTEXT}; font-size: 13pt;")
            self.album_grid.addWidget(empty, 0, 0)
        self.fill_songs()
        self.update_source_label()

    def fill_songs(self):
        self.songs.clear()
        shown = library.search(self.tracks, self.find.text()) if self.find.text().strip() else self.tracks
        for t in shown[:3000]:
            it = QTreeWidgetItem([t.get("title", ""), t.get("artist", ""), t.get("album", ""),
                                  library.fmt_time(t.get("duration"))])
            it.setData(0, Qt.UserRole, t)
            self.songs.addTopLevelItem(it)

    def ensure_local(self):
        if self.local is None:
            self.local = sources.Local()
            self.local.changed.connect(lambda n: self.source_changed(self.local, n))
        return self.local

    def play_album(self, album):
        if DEMO:
            return
        if self.spotify.now.playing:
            self.spotify.play_pause()  # one thing at a time
        self.ensure_local().play_tracks(album["tracks"])
        self.show_page("now")

    def play_song(self, item):
        if DEMO:
            return
        t = item.data(0, Qt.UserRole)
        queue = [self.songs.topLevelItem(i).data(0, Qt.UserRole) for i in range(self.songs.topLevelItemCount())]
        if self.spotify.now.playing:
            self.spotify.play_pause()
        self.ensure_local().play_tracks(queue, queue.index(t))
        self.show_page("now")

    # ---- what's playing

    def source_changed(self, src, now):
        # The one that's playing is the one shown; Spotify stays when nothing plays
        if now.playing or src is self.active or not self.active.now.playing:
            self.active = src
        a = self.active.now
        self.now_view.now = a
        self.art.load(a.art, demo_seed=1 if DEMO else None)
        self.play_btn.setIcon(S.icon("pause" if a.playing else "play", "#FFFFFF", 22))
        self.bar_title.setText(self.bar_title.fontMetrics().elidedText(a.title or "Nothing playing", Qt.ElideRight, 250))
        self.bar_sub.setText(self.bar_sub.fontMetrics().elidedText(a.artist, Qt.ElideRight, 250))
        self.update_source_label()
        self.running()

    def update_source_label(self):
        a = self.active.now
        where = ("Playing from Spotify" if a.source == "spotify" else "Playing from your music") if a.playing else \
            ("Spotify is open" if self.spotify.now.available else "Spotify isn't open")
        self.source_label.setText(f"{where}<br>{len(self.tracks)} songs in your library")

    def colours_changed(self):
        base, accent = self.art.base, self.art.accent
        if not self.art.img.isNull():
            self.mini_art.setPixmap(QPixmap.fromImage(self.art.img.scaled(56, 56, Qt.KeepAspectRatioByExpanding,
                                                                          Qt.SmoothTransformation)))
        # The play bar and the play button take the cover's colours too
        self.setStyleSheet(f"""
            #playbar {{ background: {base.darker(130).name()}; border-top: 1px solid {base.lighter(170).name()}; }}
            #playbtn {{ background: {accent.name()}; border: none; border-radius: 24px; }}
            #playbtn:hover {{ background: {accent.lighter(115).name()}; }}
            #ctl {{ background: transparent; border: none; border-radius: 18px; }}
            #ctl:hover {{ background: rgba(255,255,255,0.08); }}
            QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.15); border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {accent.name()}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: white; width: 12px; height: 12px; margin: -4px 0;
                                          border-radius: 6px; }}
            #sidebar {{ background: {base.darker(160).name()}; }}""")
        self.now_view.update()

    # ---- the frame clock

    def show_page(self, key):
        self.page = key
        # Scenes fill the window: no sidebar or play bar (Esc or a click brings them back)
        for w in (self.side, self.bar):
            w.setVisible(key != "scene")
        target = {"now": self.now_view, "scene": self.scene, "albums": self.albums_page, "songs": self.songs_page}[key]
        self.pages.setCurrentWidget(target)
        if key in self.nav:
            self.nav[key].setChecked(True)
        self.running()

    def next_scene(self):
        if self.page == "scene":
            self.scene.kind = (self.scene.kind + 1) % len(Scene.NAMES)
        self.show_page("scene")

    def running(self):
        """Draw (and listen) only while there's something to see: a visible window, a moving page, music on."""
        on = self.isVisible() and not self.isMinimized() and self.page in ("now", "scene") and \
            (self.active.now.playing or DEMO)
        if on and not self.frame.isActive():
            self.analyzer.start()
            self.frame.start()
        elif not on and self.frame.isActive():
            self.frame.stop()
            self.analyzer.stop()

    def showEvent(self, e):
        super().showEvent(e)
        self.running()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.running()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.WindowStateChange:
            self.running()

    def tick(self):
        f = self.analyzer.step() if DEMO else self.analyzer.latest
        (self.scene if self.page == "scene" else self.now_view).feed(f)
        a = self.active.now
        if self.active is self.local and self.local:
            a.position = self.local.now.position
        if a.length:
            if not self.seek.isSliderDown():
                self.seek.setValue(int(a.position / a.length * 1000))
            self.pos_label.setText(library.fmt_time(a.position))
            self.len_label.setText(library.fmt_time(a.length))

    def closeEvent(self, e):
        self.frame.stop()
        self.analyzer.stop()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Music")
    app.setDesktopFileName("deckos-music")
    fonts = HERE.parent.parent.parent / "share/fonts/deckos"
    for f in fonts.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont("Inter", 10))
    app.setStyleSheet(S.qss())
    w = Music()
    if "--screenshot" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)
        w.show()
        shots = [("now", None), ("scene", 0), ("scene", 1), ("scene", 2), ("albums", None)]

        def take(i=0):
            if i:
                page, kind = shots[i - 1]
                w.grab().save(str(out / f"music-{page}{'' if kind is None else '-' + Scene.NAMES[kind].lower()}.png"))
            if i == len(shots):
                app.exit(0)
                return
            page, kind = shots[i]
            if kind is not None:
                w.scene.kind = kind
            w.show_page(page)
            QTimer.singleShot(1500, lambda: take(i + 1))
        QTimer.singleShot(300, take)
    else:
        w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
