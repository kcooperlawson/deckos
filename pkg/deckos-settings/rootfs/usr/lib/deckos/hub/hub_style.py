"""DecKoOS Hub look: palette, stylesheet and the DecKoOS line icons.

The DecKoOS visual language: slate surfaces, 1px borders, 10px radii, Inter, and
a gradient on primary actions. The accent follows Plasma's accent colour (Appearance page), so
the Hub matches whatever the rest of the desktop uses.
"""
import os
import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
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
    return styled(_qss())


def styled(sheet):
    """A stylesheet with the person's corners and text size: radii and point sizes scaled. Swatches and radio
    buttons are circles and stay circles."""
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
#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; border: none; }}
QLabel#title {{ font-family: "Inter Display", "Inter"; font-size: 17pt; font-weight: 600; }}
QLabel#brand {{ font-family: "Inter Display", "Inter"; font-size: 12pt; font-weight: 600; }}
QLabel#sub, QLabel#value {{ color: {SUBTEXT}; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#kicker {{ color: {SUBTEXT}; font-size: 8.5pt; font-weight: 600; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 600; }}
QPushButton#seg {{ padding: 6px 14px; border-radius: 8px; background: transparent; border: 1px solid transparent; }}
QPushButton#seg:hover {{ background: {RAISED}; }}
QPushButton#seg:checked {{ background: {RAISED}; border-color: {BORDER}; color: {TEXT}; }}
QLabel#big {{ font-family: "Inter Display", "Inter"; font-size: 15pt; font-weight: 600; }}
QLabel#mono {{ font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; color: {SUBTEXT}; }}
#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#tile {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#tile:hover {{ background: {RAISED}; border-color: {HOVER}; }}
#tile[picked="true"] {{ border: 1px solid {P.accent}; background: {P.tint}; }}
#card QLabel, #card QCheckBox, #card QRadioButton, #tile QLabel {{ background: transparent; }}
#rowItem {{ background: {RAISED}; border-radius: 8px; }}
#rowItem QLabel {{ background: transparent; }}
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 12px; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {PRESSED}; }}
QPushButton:checked {{ background: {P.tint}; border-color: {P.accent}; color: {TEXT}; }}
QPushButton:disabled {{ color: {MUTED}; background: #13161C; border-color: #1E222A; }}
QPushButton#primary {{ color: white; font-weight: 600; border: none; padding: 7px 15px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {P.accent}, stop:1 {P.grad_b}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {P.accent_hover}, stop:1 {P.grad_b_hover}); }}
QPushButton#primary:disabled {{ color: {MUTED}; background: #1B1F27; }}
QPushButton#danger {{ color: white; font-weight: 600; border: none; padding: 7px 15px; background: #C9474A; }}
QPushButton#danger:hover {{ background: {DANGER}; }}
QPushButton#nav {{ text-align: left; border: none; border-radius: 8px; padding: 9px 12px; color: {SUBTEXT};
    font-weight: 600; background: transparent; }}
QPushButton#nav:hover {{ background: {SURFACE}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {P.tint}; color: {TEXT}; }}
QPushButton#swatch {{ border-radius: 15px; border: 2px solid transparent; padding: 0; }}
QPushButton#swatch:checked {{ border: 2px solid {TEXT}; }}
QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 10px; }}
QComboBox:hover {{ background: {HOVER}; }}
QComboBox QAbstractItemView {{ background: #22262F; border: 1px solid {BORDER}; selection-background-color: {P.accent}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {P.accent}; border-color: {P.accent}; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 1px solid {MUTED}; background: {SURFACE}; }}
QRadioButton::indicator:checked {{ background: {P.accent}; border: 1px solid {P.accent}; }}
QPlainTextEdit {{ background: {SIDEBAR}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px;
    font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; color: {SUBTEXT}; }}
QToolTip {{ background: #22262F; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px; }}
#toast {{ background: #22262F; border: 1px solid {BORDER}; border-radius: 9px; }}
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
