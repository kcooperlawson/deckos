"""DecKoOS Store widgets: app icons, cards, source badges, the responsive grid, screenshots."""
import hashlib
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkRequest
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

import hub_style as S
from hub_widgets import label
from store_catalog import CACHE, DEMO, SOURCE_NAMES

BADGE = {"repo": "#4C8DFF", "flathub": "#22C7B8", "aur": "#F5B84B"}


class Net:
    """One network manager with a disk cache, for icons and screenshots."""
    _nam = None

    @classmethod
    def get(cls, url, done):
        if cls._nam is None:
            cls._nam = QNetworkAccessManager()
            cache = QNetworkDiskCache(cls._nam)
            CACHE.mkdir(parents=True, exist_ok=True)
            cache.setCacheDirectory(str(CACHE / "net"))
            cache.setMaximumCacheSize(400 << 20)
            cls._nam.setCache(cache)
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.PreferCache)
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
        reply = cls._nam.get(req)

        def finished():
            data = bytes(reply.readAll()) if reply.error() == reply.NetworkError.NoError else b""
            reply.deleteLater()
            done(data)
        reply.finished.connect(finished)


def letter_icon(name, size):
    """Fallback app icon: the accent gradient tile with the app's first letter."""
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    hue = int(hashlib.md5(name.encode()).hexdigest()[:2], 16) * 360 // 256
    g = QLinearGradient(0, 0, pm.width(), pm.height())
    g.setColorAt(0, QColor.fromHsv(hue, 150, 235))
    g.setColorAt(1, QColor.fromHsv((hue + 40) % 360, 170, 200))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, pm.width(), pm.height()), pm.width() * 0.22, pm.width() * 0.22)
    p.fillPath(path, g)
    f = QFont("Inter Display", int(size * 0.8))
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(pm.rect(), Qt.AlignCenter, (name[:1] or "?").upper())
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


class AppIcon(QLabel):
    def __init__(self, size=48):
        super().__init__()
        self.size_ = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)

    def show_app(self, app):
        self.setPixmap(letter_icon(app.name, self.size_))
        if app.icon and Path(app.icon).exists():
            self._set(QPixmap(app.icon))
        elif app.icon and QIcon.hasThemeIcon(app.icon):
            self.setPixmap(QIcon.fromTheme(app.icon).pixmap(QSize(self.size_, self.size_)))
        elif app.icon_url:
            Net.get(app.icon_url, lambda data: self._set(self._from(data)))

    @staticmethod
    def _from(data):
        pm = QPixmap()
        pm.loadFromData(data)
        return pm

    def _set(self, pm):
        if not pm.isNull():
            s = self.size_ * 2
            pm = pm.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            self.setPixmap(pm)


def badge(source, small=True):
    c = QColor(BADGE[source])
    lab = QLabel(SOURCE_NAMES[source])
    lab.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},38); color: {c.name()}; "
                      f"border-radius: 2px; padding: {'1px 6px' if small else '3px 9px'}; "
                      f"font-size: {'8pt' if small else '9pt'}; font-weight: 600;")
    return lab


class AppCard(QFrame):
    """Icon, name, summary and source badges; click to open the app's page."""

    clicked = Signal(object)

    def __init__(self, app, installed):
        super().__init__()
        self.app = app
        self.setObjectName("tile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 13, 14, 13)
        h.setSpacing(13)
        ic = AppIcon(52)
        ic.show_app(app)
        h.addWidget(ic, 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        name = label(app.name, "cardTitle", wrap=False)
        top.addWidget(name, 1)
        if installed.app_installed(app):
            top.addWidget(label(f"<span style='color:{S.SUCCESS}'>Installed</span>", "muted", wrap=False))
        v.addLayout(top)
        summary = label(app.summary, "sub")
        summary.setToolTip(app.summary)
        summary.ensurePolished()  # the stylesheet's font (and text size setting), not the default one
        # Two whole lines at whatever the text size is: a fixed height cut the third line in half
        summary.setMaximumHeight(summary.fontMetrics().lineSpacing() * 2 + 2)
        summary.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        v.addWidget(summary)
        badges = QHBoxLayout()
        badges.setSpacing(5)
        for s in ("repo", "flathub", "aur"):
            if s in app.sources:
                badges.addWidget(badge(s))
        badges.addStretch(1)
        v.addLayout(badges)
        v.addStretch(1)
        h.addLayout(v, 1)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.app)


class CardGrid(QWidget):
    """Cards in as many columns as fit (each at least `min_width` wide)."""

    def __init__(self, min_width=270):
        super().__init__()
        self.min_width = min_width
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.cards, self.cols = [], 0

    def set_cards(self, cards):
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards = cards
        self.cols = 0
        self._layout()

    def _layout(self):
        cols = max(1, (self.width() + 10) // (self.min_width + 10)) if self.width() > 50 else 3
        if cols == self.cols:
            return
        self.cols = cols
        for c in self.cards:
            self.grid.removeWidget(c)
        for i, c in enumerate(self.cards):
            self.grid.addWidget(c, i // cols, i % cols)
        for col in range(6):
            self.grid.setColumnStretch(col, 1 if col < cols else 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()


class Screenshots(QScrollArea):
    """A horizontal strip of screenshots, loaded as they come in."""

    def __init__(self, height=270):
        super().__init__()
        self.h = height
        self.setFixedHeight(height + 18)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; }")
        inner = QWidget()
        self.row = QHBoxLayout(inner)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(10)
        self.setWidget(inner)

    def show_urls(self, urls):
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for url in urls[:8]:
            lab = QLabel()
            lab.setFixedSize(int(self.h * 16 / 9), self.h)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet(f"background: {S.RAISED}; border-radius: 2px; color: {S.MUTED};")
            lab.setText("Loading…")
            self.row.addWidget(lab)
            if url.startswith("demo:"):
                self._set(lab, self._demo_shot(int(url[5:])))
            else:
                Net.get(url, lambda data, l=lab: self._set(l, AppIcon._from(data)))
        self.row.addStretch(1)
        self.setVisible(bool(urls))

    def _set(self, lab, pm):
        try:
            if pm.isNull():
                lab.setText("Screenshot unavailable")
                return
            w, h = lab.width() * 2, lab.height() * 2
            pm = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rounded = QPixmap(pm.size())
            rounded.fill(Qt.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.Antialiasing)
            path = S.notch_path(rounded.rect(), 28)  # the plates' notch (at twice the size: drawn at 2x)
            p.setClipPath(path)
            p.drawPixmap(0, 0, pm)
            p.end()
            rounded.setDevicePixelRatio(2)
            lab.setStyleSheet("background: transparent;")
            lab.setPixmap(rounded)
        except RuntimeError:  # the page was closed before the image arrived
            pass

    def _demo_shot(self, n):
        """Demo screenshots: the DecKoOS wallpaper and Hub previews, so the strip has something to show."""
        candidates = [S.BRANDING / "wallpaper.svg", Path(__file__).resolve().parents[7] / "assets/hub-preview.png",
                      S.BRANDING / "grub-background.svg"]
        src = candidates[(n - 1) % len(candidates)]
        if src.suffix == ".svg":
            pm = QPixmap(960, 540)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            QSvgRenderer(QByteArray(src.read_bytes())).render(p, QRectF(0, 0, 960, 540))
            p.end()
            return pm
        return QPixmap(str(src))
