"""DeckOS Hub building blocks: cards, tiles, live graphs, toasts."""
from collections import deque

from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

import hub_style as S


def label(text="", cls=None, wrap=True):
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.RichText if "<" in text else Qt.AutoText)
    if cls:
        lab.setObjectName(cls)
    return lab


def icon_label(name, color=S.SUBTEXT, size=18):
    lab = QLabel()
    lab.setPixmap(S.pixmap(name, color, size))
    lab.setFixedSize(size, size)
    return lab


def button(text, kind=None, slot=None, icon=None, tip=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    if kind:
        b.setObjectName(kind)
    if icon:
        b.setIcon(S.icon(icon, "white" if kind in ("primary", "danger") else S.TEXT, 16))
        b.setIconSize(QSize(16, 16))
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    return b


def row(*widgets, spacing=6, stretch=True):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(spacing)
    for x in widgets:
        h.addWidget(x)
    if stretch:
        h.addStretch(1)
    return w


def restyle(w):
    w.style().unpolish(w)
    w.style().polish(w)


class Card(QFrame):
    """Surface card with an optional icon, kicker and title; add content to `body`."""

    def __init__(self, kicker=None, title=None, icon=None):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 15, 18, 16)
        self.body.setSpacing(9)
        if kicker or title:
            head = QHBoxLayout()
            head.setSpacing(10)
            if icon:
                head.addWidget(icon_label(icon, S.P.accent, 20), 0, Qt.AlignTop)
            titles = QVBoxLayout()
            titles.setSpacing(1)
            if kicker:
                titles.addWidget(label(kicker.upper(), "kicker"))
            if title:
                titles.addWidget(label(title, "cardTitle"))
            head.addLayout(titles, 1)
            self.actions = QHBoxLayout()
            self.actions.setSpacing(6)
            head.addLayout(self.actions)
            self.body.addLayout(head)
            self.body.addSpacing(2)


class Meter(QWidget):
    """4px rounded track with the accent gradient; value is 0..1, colour overridable."""

    def __init__(self, height=4):
        super().__init__()
        self.value, self.color = 0.0, None
        self.setFixedHeight(height)

    def set(self, v, color=None):
        self.value, self.color = max(0.0, min(1.0, v)), color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.rect()
        rad = r.height() / 2
        p.setBrush(QColor(S.BORDER))
        p.drawRoundedRect(r, rad, rad)
        if self.value > 0:
            if self.color:
                p.setBrush(QColor(self.color))
            else:
                g = QLinearGradient(0, 0, r.width(), 0)
                g.setColorAt(0, QColor(S.P.accent))
                g.setColorAt(1, QColor(S.P.grad_b))
                p.setBrush(g)
            p.drawRoundedRect(0, 0, max(r.height(), int(r.width() * self.value)), r.height(), rad, rad)


class Sparkline(QWidget):
    """The last `points` samples as a line with a soft fill. Values are 0..1; the graph zooms to
    the recent range (at least `span` tall) so small changes still show, unless `fixed` (0..1 always,
    for a graph people read levels off)."""

    span = 0.15

    def __init__(self, points=60, height=34, fixed=False, color=None):
        super().__init__()
        self.data = deque(maxlen=points)
        self.fixed, self.color = fixed, color
        if height:
            self.setFixedHeight(height)

    def push(self, v):
        self.data.append(max(0.0, min(1.0, v)))
        self.update()

    def paintEvent(self, _):
        if len(self.data) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 2
        step = w / (self.data.maxlen - 1)
        x0 = w - step * (len(self.data) - 1)
        if self.fixed:
            lo, hi = 0.0, 1.0
        else:
            lo, hi = min(self.data), max(self.data)
            mid, half = (lo + hi) / 2, max(hi - lo, self.span) / 2 * 1.2
            lo, hi = max(0.0, mid - half), min(1.0, mid + half)
        rng = (hi - lo) or 1
        pts = [QPointF(x0 + i * step, 1 + h * (1 - (v - lo) / rng)) for i, v in enumerate(self.data)]
        line = QPainterPath(pts[0])
        for pt in pts[1:]:
            line.lineTo(pt)
        fill = QPainterPath(line)
        fill.lineTo(pts[-1].x(), h + 1)
        fill.lineTo(pts[0].x(), h + 1)
        fill.closeSubpath()
        g = QLinearGradient(0, 0, 0, h)
        top = QColor(self.color or S.P.accent)
        top.setAlpha(70)
        bottom = QColor(self.color or S.P.accent)
        bottom.setAlpha(0)
        g.setColorAt(0, top)
        g.setColorAt(1, bottom)
        p.fillPath(fill, g)
        pen = QPen(QColor(self.color or S.P.accent), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(line)


class StatTile(QFrame):
    """Live number with an icon, a name and a sparkline (Home page)."""

    def __init__(self, icon, name):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 10)
        v.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(7)
        head.addWidget(icon_label(icon, S.SUBTEXT, 15))
        head.addWidget(label(name.upper(), "kicker", wrap=False), 1)
        v.addLayout(head)
        self.value = label("—", "big", wrap=False)
        v.addWidget(self.value)
        self.spark = Sparkline()
        v.addWidget(self.spark)

    def set(self, text, frac):
        self.value.setText(text)
        if frac is not None:
            self.spark.push(frac)


class StatusTile(QFrame):
    """Clickable status summary: icon, title, value and a detail line, tinted by state."""

    clicked = Signal()
    COLORS = {"ok": S.SUCCESS, "warn": S.WARNING, "bad": S.DANGER, "info": None, "off": S.MUTED}

    def __init__(self, icon, title):
        super().__init__()
        self.setObjectName("tile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = icon
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 12, 12)
        h.setSpacing(12)
        self.badge = QLabel()
        self.badge.setFixedSize(36, 36)
        self.badge.setAlignment(Qt.AlignCenter)
        h.addWidget(self.badge, 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(1)
        v.addWidget(label(title.upper(), "kicker", wrap=False))
        self.value = label("…", "cardTitle", wrap=False)
        v.addWidget(self.value)
        self.detail = label("", "muted")
        v.addWidget(self.detail)
        h.addLayout(v, 1)
        h.addWidget(icon_label("chevron", S.MUTED, 14), 0, Qt.AlignVCenter)
        self.set("…", "", "info")

    def set(self, value, detail, state="info"):
        color = self.COLORS.get(state) or S.P.accent
        c = QColor(color)
        self.badge.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},40); border-radius: 10px;")
        self.badge.setPixmap(S.pixmap(self._icon, color, 19))
        self.value.setText(value)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class RowItem(QFrame):
    """A list row: icon, title + detail, and widgets on the right."""

    def __init__(self, icon, title, detail="", color=S.SUBTEXT, right=()):
        super().__init__()
        self.setObjectName("rowItem")
        self.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 9, 10, 9)
        h.setSpacing(11)
        if icon:
            h.addWidget(icon_label(icon, color, 18))
        v = QVBoxLayout()
        v.setSpacing(0)
        self.title = label(title, wrap=False)
        v.addWidget(self.title)
        self.detail = label(detail, "muted")
        self.detail.setVisible(bool(detail))
        v.addWidget(self.detail)
        h.addLayout(v, 1)
        for w in right:
            h.addWidget(w)


class Art:
    """Album art from a file:// or https:// URL, cached; calls done(QPixmap)."""
    _nam, _cache = None, {}

    @classmethod
    def load(cls, url, done):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QPixmap
        if url in cls._cache:
            done(cls._cache[url])
            return
        if url.startswith("file://"):
            pm = QPixmap(QUrl(url).toLocalFile())
            cls._cache[url] = pm
            done(pm)
            return
        if not url.startswith("http"):
            done(QPixmap())
            return
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        if cls._nam is None:
            cls._nam = QNetworkAccessManager()
        reply = cls._nam.get(QNetworkRequest(QUrl(url)))

        def finished():
            pm = QPixmap()
            if reply.error() == reply.NetworkError.NoError:
                pm.loadFromData(bytes(reply.readAll()))
            reply.deleteLater()
            cls._cache[url] = pm
            done(pm)
        reply.finished.connect(finished)


class SeekBar(Meter):
    """A Meter you can click to jump to that point."""
    seek = Signal(float)

    def __init__(self):
        super().__init__(6)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.width():
            self.seek.emit(max(0.0, min(1.0, e.position().x() / self.width())))


def fmt_time(sec):
    sec = int(max(0, sec))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class NowPlaying(QFrame):
    """What's playing in any MPRIS player (Spotify, Firefox, VLC…), with art, seek and controls."""

    control = Signal(str)   # play-pause / next / previous
    seek = Signal(float)    # 0..1

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.art_url = None
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 14, 18, 14)
        h.setSpacing(16)
        self.art = QLabel()
        self.art.setFixedSize(84, 84)
        self.art.setAlignment(Qt.AlignCenter)
        h.addWidget(self.art)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.kicker = label("NOW PLAYING", "kicker", wrap=False)
        v.addWidget(self.kicker)
        self.title = label("", "cardTitle", wrap=False)
        v.addWidget(self.title)
        self.sub = label("", "sub", wrap=False)
        v.addWidget(self.sub)
        v.addSpacing(6)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.pos = label("0:00", "muted", wrap=False)
        self.bar = SeekBar()
        self.bar.seek.connect(self.seek)
        self.length = label("0:00", "muted", wrap=False)
        bar.addWidget(self.pos)
        bar.addWidget(self.bar, 1)
        bar.addWidget(self.length)
        self.bar_row = QWidget()
        self.bar_row.setLayout(bar)
        bar.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.bar_row)
        h.addLayout(v, 1)
        self.buttons = {}
        ctl = QHBoxLayout()
        ctl.setSpacing(6)
        for action, ic, big in (("previous", "previous", False), ("play-pause", "pause", True), ("next", "next", False)):
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            size = 44 if big else 34
            b.setFixedSize(size, size)
            b.setIconSize(QSize(20 if big else 16, 20 if big else 16))
            b.setObjectName("primary" if big else "")
            b.setStyleSheet(f"QPushButton {{ border-radius: {size // 2}px; padding: 0; }}")
            b.clicked.connect(lambda _c=False, a=action: self.control.emit(a))
            self.buttons[action] = b
            ctl.addWidget(b)
        self.paint_buttons(False)
        h.addLayout(ctl)
        self.show_nothing()

    def paint_buttons(self, playing):
        self.buttons["previous"].setIcon(S.icon("previous", S.TEXT, 16))
        self.buttons["next"].setIcon(S.icon("next", S.TEXT, 16))
        self.buttons["play-pause"].setIcon(S.icon("pause" if playing else "play", "white", 20))

    def show_nothing(self):
        self.art_url = None
        self.art.setPixmap(S.pixmap("music", S.MUTED, 34))
        self.art.setStyleSheet(f"background: {S.RAISED}; border-radius: 12px;")
        self.kicker.setText("NOW PLAYING")
        self.title.setText("Nothing playing")
        self.sub.setText("Music and videos from Spotify, Firefox and other players show up here.")
        self.bar_row.hide()
        for b in self.buttons.values():
            b.hide()

    def show_track(self, t, position):
        self.kicker.setText(f"NOW PLAYING · {t['label'].upper()}")
        self.title.setText(t["title"])
        self.sub.setText(" — ".join(x for x in (t["artist"], t["album"]) if x))
        self.bar_row.setVisible(t["length"] > 0)
        self.bar.set(position / t["length"] if t["length"] else 0)
        self.pos.setText(fmt_time(position))
        self.length.setText(fmt_time(t["length"]))
        for b in self.buttons.values():
            b.show()
        self.paint_buttons(t["status"] == "Playing")
        if t["art"] != self.art_url:
            self.art_url = t["art"]
            self.art.setPixmap(S.pixmap("music", S.MUTED, 34))
            Art.load(t["art"], lambda pm, url=t["art"]: self._set_art(pm, url))

    def _set_art(self, pm, url):
        if url != self.art_url or pm.isNull():
            return
        from PySide6.QtGui import QPainterPath, QPixmap
        from PySide6.QtCore import QRectF
        s = self.art.width() * 2
        pm = pm.scaled(s, s, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        out = QPixmap(s, s)
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, s, s), 22, 22)
        p.setClipPath(path)
        p.drawPixmap((s - pm.width()) // 2, (s - pm.height()) // 2, pm)
        p.end()
        out.setDevicePixelRatio(2)
        self.art.setStyleSheet("background: transparent;")
        self.art.setPixmap(out)


class Toast(QFrame):
    """Short message in the bottom-right corner of its parent; fades out after a few seconds."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 9, 14, 9)
        h.setSpacing(9)
        self.icon = QLabel()
        h.addWidget(self.icon)
        self.text = label("", wrap=False)
        h.addWidget(self.text)
        self.timer = QTimer(self, singleShot=True, timeout=self.hide)
        self.hide()

    def show_message(self, text, kind="info", ms=5000):
        name, color = {"ok": ("check", S.SUCCESS), "warn": ("alert", S.WARNING),
                       "bad": ("alert", S.DANGER)}.get(kind, ("info", S.P.accent))
        self.icon.setPixmap(S.pixmap(name, color, 16))
        self.text.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        self.move(par.width() - self.width() - 22, par.height() - self.height() - 20)
        self.show()
        self.raise_()
        self.timer.start(ms)


class Empty(QWidget):
    """Centered empty state: icon, message and an optional action button."""

    def __init__(self, icon, title, text, action=None):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 18, 0, 18)
        v.setSpacing(6)
        v.setAlignment(Qt.AlignHCenter)
        ic = icon_label(icon, S.MUTED, 34)
        v.addWidget(ic, 0, Qt.AlignHCenter)
        t = label(title, "cardTitle")
        t.setAlignment(Qt.AlignHCenter)
        v.addWidget(t)
        s = label(text, "sub")
        s.setAlignment(Qt.AlignHCenter)
        s.setMaximumWidth(460)
        v.addWidget(s, 0, Qt.AlignHCenter)
        if action:
            v.addSpacing(6)
            v.addWidget(action, 0, Qt.AlignHCenter)
