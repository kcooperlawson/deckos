"""DecKoOS apps' look: palette, stylesheet, the DecKo notch and the DecKoOS line icons.

The DecKo look, as on the desktop: cards, tiles and buttons are plates with the wordmark's notch (the top right and
bottom left corners cut), a 1px edge lit by the accent's gradient; Chakra Petch for labels and numbers, Inter for
names and sentences; slate surfaces. A stylesheet can't cut corners, so the plates are painted here (`paint_plate`):
cards, tiles, list rows and toasts by an application-wide painter, buttons by `DecoStyle`; both are installed the
first time an app asks for the stylesheet (`qss()`), so every DecKoOS app gets them. The accent follows Plasma's
(Appearance page), so the apps match the rest of the desktop.
"""
import os
import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle
from PySide6.QtSvg import QSvgRenderer

# /usr/share/deckos/... on DecKoOS; the package's own rootfs when run from the repo.
_SHARE = Path(__file__).resolve().parents[3] / "share/deckos"
BRANDING = Path(os.environ.get("DECKOS_BRANDING") or (
    "/usr/share/deckos/branding" if Path("/usr/share/deckos/branding").is_dir() else _SHARE / "branding"))
ICONS = Path(os.environ.get("DECKOS_ICONS") or (
    "/usr/share/deckos/icons" if Path("/usr/share/deckos/icons").is_dir() else _SHARE / "icons"))

BG, SIDEBAR, SURFACE, RAISED = "#0F1115", "#0B0D11", "#171A21", "#1D212A"
BORDER, HOVER, PRESSED = "#262B36", "#2A2F3B", "#353B49"
TEXT, SUBTEXT, MUTED = "#E8EAF0", "#8C94A6", "#5A6172"
SUCCESS, WARNING, DANGER = "#3DD68C", "#F5B84B", "#FF6B6B"
DEFAULT_ACCENT = "#4C8DFF"


def plasma_accent():
    """Plasma's accent colour from kdeglobals, or the DecKoOS blue."""
    try:
        text = (Path.home() / ".config/kdeglobals").read_text()
        m = re.search(r"^AccentColor=(\d+),(\d+),(\d+)", text, re.M)
        if m:
            return QColor(*map(int, m.groups())).name()
    except OSError:
        pass
    return DEFAULT_ACCENT


class Palette:
    """Accent-derived colours; `set_accent` updates them in place for a live restyle."""

    def __init__(self, accent):
        self.set_accent(accent)

    def set_accent(self, accent):
        a = QColor(accent)
        self.accent = a.name()
        self.accent_hover = a.lighter(118).name()
        # The gradient runs from the accent to a violet-shifted partner, like the brand tile.
        h, s, v, _ = a.getHsv()
        self.grad_b = QColor.fromHsv((h + 32) % 360, min(255, s + 10), v).name()
        self.grad_b_hover = QColor(self.grad_b).lighter(118).name()
        self.tint = QColor(a.red(), a.green(), a.blue(), 38).name(QColor.HexArgb)


P = Palette(plasma_accent())

# Appearance > Style: logo (gradient, flat), corners (sharp, default, round), text (small, normal, large).
# Every DecKoOS app reads it through qss() and brand_svg(); `deckos`-free, since it's only the user's own file.
STYLE_CONF = Path.home() / ".config/deckos/style.conf"
STYLE_DEFAULTS = {"logo": "gradient", "corners": "default", "text": "normal"}
CORNERS = {"sharp": 0.35, "default": 1.0, "round": 1.6}
TEXT_SCALE = {"small": 0.9, "normal": 1.0, "large": 1.15}


def load_style():
    style = dict(STYLE_DEFAULTS)
    try:
        for line in STYLE_CONF.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() in style:
                style[k.strip()] = v.strip()
    except OSError:
        pass
    return style


STYLE = load_style()


def corner(px):
    """A corner radius drawn by hand (covers, album art), following Appearance > Style > Corners."""
    return px * CORNERS.get(STYLE["corners"], 1.0)


def scaled(px):
    """A fixed width that holds text, grown or shrunk with the text size setting."""
    return round(px * TEXT_SCALE.get(STYLE["text"], 1.0))


def save_style(**changes):
    STYLE.update(changes)
    STYLE_CONF.parent.mkdir(parents=True, exist_ok=True)
    STYLE_CONF.write_text("# DecKoOS apps' style (Hub > Appearance > Style)\n" +
                          "".join(f"{k}={v}\n" for k, v in STYLE.items()))

# The brand art is drawn in DecKoOS blue and its violet partner; apps show it in the person's accent instead,
# like the icon theme's colour variants do on the taskbar.
BRAND_BLUE, BRAND_VIOLET = "#4C8DFF", "#7A5CFF"


def brand_svg(name):
    """A branding SVG (logo.svg, store-logo.svg...) recoloured to the current accent, for QSvgWidget.load()."""
    try:
        text = (BRANDING / name).read_text()
    except OSError:
        return QByteArray()
    text = re.sub(BRAND_BLUE, P.accent, text, flags=re.I)
    text = re.sub(BRAND_VIOLET, P.accent if STYLE["logo"] == "flat" else P.grad_b, text, flags=re.I)
    return QByteArray(text.encode())


def brand_widget(name, size=34):
    """The logo as a widget that follows the accent: `refresh_brand(window)` reloads every one after a change."""
    from PySide6.QtSvgWidgets import QSvgWidget
    w = QSvgWidget()
    w.setProperty("brand", name)
    w.load(brand_svg(name))
    w.setFixedSize(size, size)
    return w


def refresh_brand(root):
    from PySide6.QtSvgWidgets import QSvgWidget
    for w in root.findChildren(QSvgWidget):
        if w.property("brand"):
            w.load(brand_svg(w.property("brand")))


def brand_icon(name, size=128):
    """A window icon from the recoloured logo."""
    r = QSvgRenderer(brand_svg(name))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    r.render(p, QRectF(0, 0, size, size))
    p.end()
    return QIcon(pm)


def qss():
    _install()
    return styled(_qss())


# ------------------------------------------------------------------ the DecKo notch

HUD = "Chakra Petch"  # labels, numbers, buttons (the wordmark's cut corners as type)
# The frames drawn as notched plates (by object name): their cut, and what kind of plate. card: lit at half strength;
# tile: lighter under the pointer; row: a raised row; toast: lit; hero: the accent's gradient. The apps' own frames
# are here too (What's New, System Monitor, Disks), so every DecKoOS window has the same plates.
PLATES = {"card": (14, "card"), "tile": (12, "tile"), "rowItem": (8, "row"), "toast": (10, "toast"),
          "feature": (12, "card"), "hero": (14, "hero"), "device": (10, "tile"), "stat": (8, "row"),
          "disk": (10, "tile"), "erase": (9, "row"), "banner": (12, "row")}


def notch_path(rect, cut):
    """The plate's outline: the wordmark's notch at the top right and bottom left."""
    r = QRectF(rect)
    return _poly(r, min(cut, r.width() / 3, r.height() / 3))


def _poly(r, cut):
    path = QPainterPath()
    path.addPolygon(QPolygonF([
        QPointF(r.left(), r.top()), QPointF(r.right() - cut, r.top()), QPointF(r.right(), r.top() + cut),
        QPointF(r.right(), r.bottom()), QPointF(r.left() + cut, r.bottom()), QPointF(r.left(), r.bottom() - cut)]))
    path.closeSubpath()
    return path


def paint_plate(p, rect, fill, cut=12, lit=False, edge=None, gradient_fill=False):
    """A DecKo plate: the notched shape filled, with a 1px edge. lit: the edge in the accent's gradient (strongest at
    the top left and bottom right, like the desktop's cards), as strong as lit (True: fully; a card in an app page
    full of them, about half); else a faint line, or `edge` if given. gradient_fill: the inside in the accent's
    gradient (primary buttons)."""
    r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    path = _poly(r, cut)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    if gradient_fill:
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(P.accent))
        g.setColorAt(1, QColor(P.grad_b))
        p.fillPath(path, g)
    else:
        p.fillPath(path, QColor(fill))
    if lit:
        k = 1.0 if lit is True else float(lit)
        a, b = QColor(P.accent), QColor(P.grad_b)
        a.setAlphaF(k)
        b.setAlphaF(k)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, a)
        g.setColorAt(0.35, QColor(255, 255, 255, 30))
        g.setColorAt(0.65, QColor(255, 255, 255, 22))
        g.setColorAt(1, b)
        p.setPen(QPen(g, 1))
    else:
        p.setPen(QPen(QColor(edge or BORDER), 1))
    if not gradient_fill:
        p.drawPath(path)
    p.restore()


class _Plates(QObject):
    """Paints the notched plates behind every card, tile, list row and toast (by their object names), before the
    frame paints its own contents. The stylesheet leaves those frames see-through for it. A frame's "picked"
    property (or focus) tints and lights it; its "plateColor" property (a QColor) tints it in that colour instead of
    the accent's (System Monitor's resource colours, Disks' warning banner)."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Paint and obj.isWidgetType() and obj.objectName() in PLATES:
            if not obj.testAttribute(Qt.WA_Hover):
                obj.setAttribute(Qt.WA_Hover, True)  # a repaint when the pointer comes and goes
            cut, kind = PLATES[obj.objectName()]
            colour = obj.property("plateColor")
            picked = bool(obj.property("picked")) or obj.hasFocus()
            hover = kind == "tile" and obj.underMouse() and not picked
            fill = RAISED if kind == "row" or hover else "#22262F" if kind == "toast" else SURFACE
            p = QPainter(obj)
            if kind == "hero":
                paint_plate(p, obj.rect(), fill, cut, gradient_fill=True)
            elif isinstance(colour, QColor) and (picked or kind == "row"):
                tint, edge = QColor(colour), QColor(colour)
                tint.setAlphaF(0.10)
                edge.setAlphaF(0.55)
                paint_plate(p, obj.rect(), fill, cut)
                paint_plate(p, obj.rect(), tint, cut, edge=edge.name(QColor.HexArgb))
            else:
                paint_plate(p, obj.rect(), P.tint if picked else fill, cut,
                            lit=True if picked or kind == "toast" else 0.5 if kind == "card" else False,
                            edge=HOVER if hover else None)
            p.end()
        return False


class DecoStyle(QProxyStyle):
    """Push buttons as DecKo plates: notched; primary ones filled with the accent's gradient, danger ones red;
    checked ones tinted and lit. Buttons with their own stylesheet look (nav, seg, swatch) keep it."""

    OWN = {"nav", "seg", "swatch"}

    def _plate(self, opt, p, w):
        name = w.objectName() if w else ""
        st = opt.state
        r = opt.rect
        cut = min(8, r.height() / 3)
        on = bool(st & QStyle.State_Enabled)
        down = bool(st & QStyle.State_Sunken)
        hover = bool(st & QStyle.State_MouseOver)
        if name == "primary" and on:
            paint_plate(p, r, "", cut, gradient_fill=True)
            if hover or down:
                p.save()
                p.setRenderHint(QPainter.Antialiasing)
                p.fillPath(_poly(QRectF(r), cut), QColor(255, 255, 255, 40 if down else 26))
                p.restore()
        elif name == "danger" and on:
            paint_plate(p, r, DANGER if hover else "#C9474A", cut, edge="transparent")
        elif st & QStyle.State_On:
            paint_plate(p, r, P.tint, cut, lit=True)
        else:
            fill = "#13161C" if not on else PRESSED if down else HOVER if hover else SURFACE
            paint_plate(p, r, fill, cut, edge="#1E222A" if not on else None)

    def drawControl(self, el, opt, p, w=None):
        if el == QStyle.CE_PushButtonBevel and not (w and w.objectName() in self.OWN):
            self._plate(opt, p, w)
            return
        super().drawControl(el, opt, p, w)

    def drawPrimitive(self, el, opt, p, w=None):
        if el == QStyle.PE_PanelButtonCommand and not (w and w.objectName() in self.OWN):
            self._plate(opt, p, w)
            return
        if el == QStyle.PE_FrameFocusRect and w is not None and w.inherits("QPushButton"):
            return  # the plate shows focus itself
        super().drawPrimitive(el, opt, p, w)


_installed = []


def _install():
    """The DecKo plates and buttons, once per app (from qss(): every DecKoOS app asks for the stylesheet)."""
    app = QApplication.instance()
    if app is None or _installed:
        return
    _installed.append(_Plates(app))
    app.installEventFilter(_installed[0])
    if not isinstance(app.style(), DecoStyle):
        app.setStyle(DecoStyle())


def styled(sheet):
    """A stylesheet with the person's corners and text size: radii and point sizes scaled. Swatches and radio
    buttons are circles and stay circles. Installs the plates and buttons too (apps that add to _qss() come here)."""
    _install()
    r = CORNERS.get(STYLE["corners"], 1.0)
    t = TEXT_SCALE.get(STYLE["text"], 1.0)
    out = []
    for line in sheet.splitlines():
        if r != 1.0 and "swatch" not in line and "QRadioButton" not in line:
            line = re.sub(r"border-radius: (\d+)px", lambda m: f"border-radius: {round(int(m.group(1)) * r)}px", line)
        if t != 1.0:
            line = re.sub(r"font-size: ([\d.]+)pt", lambda m: f"font-size: {float(m.group(1)) * t:.1f}pt", line)
        out.append(line)
    return "\n".join(out)


def _qss():
    return f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: "Inter", "Noto Sans"; font-size: 10pt; }}
#root {{ background: {BG}; }}
QDialog {{ background: {BG}; }}
#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; border: none; }}
QLabel#title {{ font-family: "Inter Display", "Inter"; font-size: 17pt; font-weight: 600; }}
QLabel#brand {{ font-family: "Inter Display", "Inter"; font-size: 12pt; font-weight: 600; }}
QLabel#sub, QLabel#value {{ color: {SUBTEXT}; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#kicker {{ color: {SUBTEXT}; font-family: "{HUD}"; font-size: 9pt; font-weight: 600; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 600; }}
QPushButton#seg {{ padding: 6px 14px; border-radius: 2px; background: transparent; border: 1px solid transparent; }}
QPushButton#seg:hover {{ background: {RAISED}; }}
QPushButton#seg:checked {{ background: {RAISED}; border-color: {BORDER}; color: {TEXT}; }}
QLabel#big {{ font-family: "{HUD}", "Inter Display"; font-size: 16pt; font-weight: 600; }}
QLabel#mono {{ font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; color: {SUBTEXT}; }}
/* cards, tiles, rows and toasts are notched plates painted underneath (_Plates): the frames stay see-through */
#card, #tile {{ background: transparent; border: none; }}
#card QLabel, #card QCheckBox, #card QRadioButton, #tile QLabel {{ background: transparent; }}
#rowItem {{ background: transparent; border: none; }}
#rowItem QLabel {{ background: transparent; }}
/* push buttons are notched plates drawn by DecoStyle: no background or border here, or the stylesheet would draw them */
QPushButton {{ padding: 7px 14px; }}
QPushButton:checked {{ color: {TEXT}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ color: #0B0D16; font-family: "{HUD}"; font-size: 10.5pt; font-weight: 700; padding: 7px 16px; }}
QPushButton#primary:disabled {{ color: {MUTED}; }}
QPushButton#danger {{ color: white; font-family: "{HUD}"; font-size: 10.5pt; font-weight: 700; padding: 7px 16px; }}
QPushButton#nav {{ text-align: left; border: none; border-radius: 2px; padding: 9px 12px; color: {SUBTEXT};
    font-weight: 600; background: transparent; }}
QPushButton#nav:hover {{ background: {SURFACE}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {P.tint}; color: {TEXT}; }}
QPushButton#nav:focus {{ border: 1px solid {P.accent}; }}
QPushButton#swatch {{ border-radius: 15px; border: 2px solid transparent; padding: 0; }}
QPushButton#swatch:checked {{ border: 2px solid {TEXT}; }}
QLineEdit, QSpinBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 2px; padding: 5px 8px; }}
QLineEdit:focus, QSpinBox:focus {{ border-color: {P.accent}; }}
QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 2px; padding: 6px 10px; }}
QComboBox:hover {{ background: {HOVER}; }}
QComboBox QAbstractItemView {{ background: #22262F; border: 1px solid {BORDER}; selection-background-color: {P.accent}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 2px; border: 1px solid {BORDER}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {P.accent}; border-color: {P.accent}; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 1px solid {MUTED}; background: {SURFACE}; }}
QRadioButton::indicator:checked {{ background: {P.accent}; border: 1px solid {P.accent}; }}
QPlainTextEdit {{ background: {SIDEBAR}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px;
    font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; color: {SUBTEXT}; }}
QToolTip {{ background: #22262F; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px; }}
#toast {{ background: transparent; border: none; }}
#toast QLabel {{ background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {HOVER}; border-radius: 4px; margin: 2px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: {HOVER}; border-radius: 4px; margin: 2px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {MUTED}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


_cache = {}


def pixmap(name, color=TEXT, size=18, ratio=2.0):
    """A DecKoOS line icon recoloured to `color`, rendered crisp for HiDPI."""
    key = (name, color, size, ratio)
    if key not in _cache:
        try:
            data = (ICONS / f"{name}.svg").read_text().replace("#000", QColor(color).name())
        except OSError:
            data = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"/>'
        pm = QPixmap(int(size * ratio), int(size * ratio))
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        QSvgRenderer(QByteArray(data.encode())).render(p, QRectF(0, 0, pm.width(), pm.height()))
        p.end()
        pm.setDevicePixelRatio(ratio)
        _cache[key] = pm
    return _cache[key]


def icon(name, color=TEXT, size=18, active=None):
    """QIcon with an optional brighter colour for the checked/hovered state (sidebar)."""
    ic = QIcon(pixmap(name, color, size))
    if active:
        ic.addPixmap(pixmap(name, active, size), QIcon.Normal, QIcon.On)
        ic.addPixmap(pixmap(name, active, size), QIcon.Active, QIcon.Off)
    return ic
