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
    the recent range (at least `span` tall) so small changes still show."""

    span = 0.15

    def __init__(self, points=60, height=34):
        super().__init__()
        self.data = deque(maxlen=points)
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
        top = QColor(S.P.accent)
        top.setAlpha(70)
        bottom = QColor(S.P.accent)
        bottom.setAlpha(0)
        g.setColorAt(0, top)
        g.setColorAt(1, bottom)
        p.fillPath(fill, g)
        pen = QPen(QColor(S.P.accent), 1.6)
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
