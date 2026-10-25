"""Generates the DecKoOS brand: icon, wordmark, wallpaper, GRUB theme art, installer art.

Same family as Steady Downloader: deep slate surfaces, quiet 1px borders, and the
blue→violet gradient tile with a white rounded glyph. The O in "DeckOS" is a thumbstick seen
from above: its gate ring, and the cap (raised rim, dished centre) tilted slightly up-right.

Run with fontTools available (the outputs are committed, so builds don't need it):
    python -m pip install fonttools && python assets/generate.py
"""
import math
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "pkg/deckos-settings/rootfs/usr/share/deckos/branding"
FONTS = HERE.parent / "pkg/deckos-settings/rootfs/usr/share/fonts/deckos"
FONT = FONTS / "InterDisplay-SemiBold.otf"
FONT_MEDIUM = FONTS / "InterDisplay-Medium.otf"

# Steady Downloader palette (App.xaml) + its icon gradient.
BG = "#0F1115"
BG_DEEP = "#0B0D11"
SURFACE = "#171A21"
BORDER = "#262B36"
TEXT = "#E8EAF0"
SUBTEXT = "#8C94A6"
MUTED = "#5A6172"
GRAD_A = "#4C8DFF"
GRAD_B = "#7A5CFF"


# ------------------------------------------------------------------ type

class Font:
    def __init__(self, path):
        self.f = TTFont(path)
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upm = self.f["head"].unitsPerEm
        self.cap = self.f["OS/2"].sCapHeight

    def glyph(self, ch):
        return self.cmap[ord(ch)]

    def advance(self, ch):
        return self.f["hmtx"][self.glyph(ch)][0]

    def bounds(self, ch):
        bp = BoundsPen(self.gs)
        self.gs[self.glyph(ch)].draw(bp)
        return bp.bounds  # xMin, yMin, xMax, yMax (font units, y up)

    def path(self, ch, x, baseline, scale):
        """SVG path for one glyph with its origin at (x, baseline) in SVG coordinates."""
        sp = SVGPathPen(self.gs)
        tp = TransformPen(sp, (scale, 0, 0, -scale, x, baseline))
        self.gs[self.glyph(ch)].draw(tp)
        return sp.getCommands()


INTER = Font(FONT)
INTER_MED = Font(FONT_MEDIUM)


def text_path(font, text, x, baseline, size, tracking=0.0):
    """Path data + advance width for a run of text at a pixel size (no kerning needed at these sizes)."""
    s = size / font.upm
    d, cx = [], x
    for ch in text:
        if ch == " ":
            cx += font.advance(ch) * s + tracking
            continue
        d.append(font.path(ch, cx, baseline, s))
        cx += font.advance(ch) * s + tracking
    return " ".join(d), cx - x - tracking


# ------------------------------------------------------------------ the thumbstick O
#
# One emblem everywhere (wordmark O, app tile, boot splash, wallpaper): the gate ring at the
# letters' stroke weight, and the stick's cap, a raised rim with a dished centre, tilted slightly
# toward the upper right. Spun around the gate's centre (the boot splash), the cap circles the gate.

STICK_W = 0.30     # gate ring weight, as a share of the radius (matches Inter's stems in the O)
CAP_TILT = 0.08    # cap offset toward the upper right, share of the radius
CAP_R = 0.47       # cap radius
CAP_RIM = 0.55     # cap rim weight, share of the gate weight
CAP_DISH = 0.30    # dished centre radius, share of the cap radius


def circle_path(cx, cy, r):
    return (f"M{cx - r:.2f},{cy:.2f} a{r:.2f},{r:.2f} 0 1,0 {2 * r:.2f},0 "
            f"a{r:.2f},{r:.2f} 0 1,0 {-2 * r:.2f},0 Z")


def ring_path(cx, cy, r_out, r_in):
    """An annulus (draw with fill-rule evenodd)."""
    return circle_path(cx, cy, r_out) + " " + circle_path(cx, cy, r_in)


def thumbstick(cx, cy, r, weight=None, tilt=CAP_TILT):
    """(gate, cap, cap centre) for the emblem at centre (cx, cy), radius r. evenodd paths.
    `tilt` pushes the cap further for illustrations (the wallpaper); the emblem keeps CAP_TILT."""
    w = weight or r * STICK_W
    ox, oy, cr = cx + r * tilt, cy - r * tilt, r * CAP_R
    gate = ring_path(cx, cy, r, r - w)
    cap = ring_path(ox, oy, cr, cr - w * CAP_RIM) + " " + circle_path(ox, oy, cr * CAP_DISH)
    return gate, cap, (ox, oy, cr)


def thumbstick_svg(cx, cy, r, fill, weight=None, extra=""):
    """The emblem as two filled paths; `extra` adds attributes (opacity, filter) to both."""
    gate, cap, _ = thumbstick(cx, cy, r, weight)
    return "".join(f'<path fill="{fill}" fill-rule="evenodd" {extra} d="{d}"/>' for d in (gate, cap))


def gradient(id_, x1="0", y1="0", x2="1", y2="1", a=GRAD_A, b=GRAD_B, units=None):
    u = f' gradientUnits="{units}"' if units else ""
    return (f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"{u}>'
            f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>')


# ------------------------------------------------------------------ controller mark
#
# A gamepad whose left thumbstick is the "O" and whose face-button side carries a cut-out
# "S": the controller spells OS. Drawn in a 240 x 160 box, scaled by callers.

PAD_W, PAD_H = 240.0, 160.0
PAD_PATH = ("M60,24 C88,14 152,14 180,24 C206,32 222,48 230,78 C238,110 238,140 216,148 "
            "C198,154 184,144 174,128 L163,110 C157,101 149,98 140,98 L100,98 C91,98 83,101 77,110 "
            "L66,128 C56,144 42,154 24,148 C2,140 2,110 10,78 C18,48 34,32 60,24 Z")
STICK = (72.0, 60.0, 34.0)   # well centre + radius (the O sits inside)
S_BOX = (169.0, 60.0, 58.0)  # S centre + cap height


def controller(id_, x, y, height, body, stick=None, ring=True, glow=None, right="buttons"):
    """Controller mark at (x, y) top-left. body/stick are fills; ring=False leaves the well empty (splash)."""
    k = height / PAD_H
    sx, sy, sr = STICK
    cx, cy, ch = S_BOX
    # The S, centred on S_BOX, as a cut-out.
    s_size = ch / INTER.cap * INTER.upm
    b = INTER.bounds("S")
    s_w = (b[2] - b[0]) * s_size / INTER.upm
    S, _ = text_path(INTER, "S", cx - s_w / 2 - b[0] * s_size / INTER.upm, cy + ch / 2, s_size)
    if right == "S":
        cut = f'<path d="{S}" fill="#000"/>'
    else:  # four face buttons in a diamond
        g, br = 21.0, 8.5
        cut = "".join(f'<circle cx="{cx + dx:.1f}" cy="{cy + dy:.1f}" r="{br}" fill="#000"/>'
                      for dx, dy in ((0, -g), (g, 0), (0, g), (-g, 0)))
    mask = (f'<mask id="m-{id_}" maskUnits="userSpaceOnUse" x="-20" y="-20" width="{PAD_W + 40}" height="{PAD_H + 40}">'
            f'<path d="{PAD_PATH}" fill="#fff"/><circle cx="{sx}" cy="{sy}" r="{sr}" fill="#000"/>{cut}</mask>')
    out = [f'<g transform="translate({x:.2f},{y:.2f}) scale({k:.5f})">', mask]
    if glow:
        out.append(f'<path d="{PAD_PATH}" fill="{body}" opacity="0.45" filter="url(#{glow})"/>')
    out.append(f'<path d="{PAD_PATH}" fill="{body}" mask="url(#m-{id_})"/>')
    if ring:
        out.append(thumbstick_svg(sx, sy, sr * 0.80, stick or body))
    out.append("</g>")
    return "".join(out)


def controller_file(size=512, bg=None):
    h = size * 0.62
    w = h * PAD_W / PAD_H
    defs = gradient("pad", units="userSpaceOnUse", x1="0", y1="0", x2=f"{PAD_W}", y2=f"{PAD_H}")
    body = controller("f", (size - w) / 2, (size - h) / 2 + size * 0.02, h, "url(#pad)")
    return svg(size, size, (f'<rect width="{size}" height="{size}" fill="{bg}"/>' if bg else "") + body, defs)


# ------------------------------------------------------------------ wordmark

def wordmark_pad(x, baseline, size, text=TEXT, fill="url(#padgrad)", ring=True, glow=None, id_="w"):
    """'Deck' + controller-as-OS. Returns (svg, width, (pad_x, pad_y, pad_h))."""
    deck, w_deck = text_path(INTER, "Deck", x, baseline, size)
    cap = INTER.cap * size / INTER.upm
    xh = INTER.f["OS/2"].sxHeight * size / INTER.upm
    pad_h = xh / (S_BOX[2] / PAD_H) * 1.06       # the S comes out ~6% taller than x-height
    k = pad_h / PAD_H
    pad_x = x + w_deck + size * 0.05
    pad_y = baseline - xh / 2 - S_BOX[1] * k     # O/S centred on the x-height
    pad = controller(id_, pad_x, pad_y, pad_h, fill, ring=ring, glow=glow)
    width = pad_x + pad_h * PAD_W / PAD_H - x
    return f'<path fill="{text}" d="{deck}"/>' + pad, width, (pad_x, pad_y, pad_h)


def pad_gradient(*_unused, id_="padgrad"):
    """Gradient across the controller, in the controller's own 240x160 drawing space."""
    return gradient(id_, units="userSpaceOnUse", x1="0", y1="0", x2=f"{PAD_W}", y2=f"{PAD_H}")


# The DecKoOS wordmark: blocky letters on a 100-unit cap grid (26-unit strokes, 45-degree cuts) and the
# "oO" as a controller, the small o a thumbstick and the O the face buttons. Letter paths take x in
# grid units; wordmark() scales them.

GRID_T = 26
GRID_GAP = 13


def _D(x):
    t = GRID_T
    return (f"M{x},0 H{x + 64} L{x + 90},26 V74 L{x + 64},100 H{x} Z "
            f"M{x + t},{t} H{x + 58} L{x + 64},32 V68 L{x + 58},74 H{x + t} Z"), 90


def _e(x):
    t = GRID_T
    return f"M{x},28 H{x + 72} V72 H{x + t} V78 H{x + 72} V100 H{x} Z M{x + t},48 H{x + 46} V56 H{x + t} Z", 72


def _c(x):
    return f"M{x},28 H{x + 70} V50 H{x + GRID_T} V78 H{x + 70} V100 H{x} Z", 70


def _K(x):
    t = GRID_T
    return f"M{x},0 H{x + t} V100 H{x} Z M{x + t + 4},42 L{x + 60},0 H{x + 92} L{x + 52},50 L{x + 92},100 H{x + 60} L{x + t + 4},58 Z", 92


def _S(x):
    t = GRID_T
    return (f"M{x + 14},0 H{x + 86} V24 H{x + t} V38 H{x + 72} L{x + 86},52 V86 L{x + 72},100 H{x} V76 H{x + 60} "
            f"V62 H{x + 14} L{x},48 V14 Z"), 86


STICK_GRID = (36, 64, 36)    # small o: centre x offset, centre y, radius (grid units)
BUTTONS_GRID = (50, 50, 50)  # big O


def stick_pupil(cx, cy, r, cap):
    """The thumbstick's raised cap, tilted up. On the splash screens it is one of the two eyes' pupils."""
    return f'<ellipse cx="{cx + r * 0.06:.2f}" cy="{cy - r * 0.16:.2f}" rx="{r * 0.36:.2f}" ry="{r * 0.25:.2f}" fill="{cap}"/>'


def buttons_pupil(cx, cy, r, btn, g=0.30, br=0.15):
    """The four face buttons in a diamond: the other eye's pupil."""
    return "".join(f'<circle cx="{cx + dx * r * g:.2f}" cy="{cy + dy * r * g:.2f}" r="{r * br:.2f}" fill="{btn}"/>'
                   for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)))


def _well(cx, cy, r, ring, hole, w):
    return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r - w / 2:.2f}" fill="none" stroke="{ring}" stroke-width="{w:.2f}"/>'
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r - w:.2f}" fill="{hole}"/>')


def stick_mark(cx, cy, r, ring, cap, hole, w):
    """The thumbstick o: ring, dark well, raised cap."""
    return _well(cx, cy, r, ring, hole, w) + stick_pupil(cx, cy, r, cap)


def buttons_mark(cx, cy, r, ring, btn, hole, w, g=0.30, br=0.15):
    """The face-button O: ring, dark well, four buttons in a diamond."""
    return _well(cx, cy, r, ring, hole, w) + buttons_pupil(cx, cy, r, btn, g, br)


EYES = {}  # the two eyes' (cx, cy, r) in the last wordmark drawn: "o" (stick) and "O" (buttons)


def wordmark(x, baseline, size, text=TEXT, stick_fill="url(#deckos-grad)", with_stick=True, glow=None, hole=BG):
    """'DecK' + stick-o + buttons-O + 'S', cap height = size * 0.73. Returns (svg, width, stick(cx, cy, r)).
    with_stick=False leaves both pupils out: the splash screens draw them as eyes that glance and blink."""
    k = size * 0.73 / 100
    top = baseline - 100 * k
    gx, letters = 0, []
    for f in (_D, _e, _c, _K):
        d, w = f(gx)
        letters.append(d)
        gx += w + GRID_GAP
    sx, sy, sr = gx + STICK_GRID[0], STICK_GRID[1], STICK_GRID[2]
    gx = sx + sr + GRID_GAP * 0.8
    bx, by, brr = gx + BUTTONS_GRID[0], BUTTONS_GRID[1], BUTTONS_GRID[2]
    gx = bx + brr + GRID_GAP
    d, w = _S(gx)
    letters.append(d)
    gx += w
    ring_w = GRID_T * 0.62
    pos = lambda u, v: (x + u * k, top + v * k)
    stick_c = (*pos(sx, sy), sr * k)
    parts = [f'<path fill="{text}" fill-rule="evenodd" transform="translate({x:.2f},{top:.2f}) scale({k:.5f})" d="{" ".join(letters)}"/>']
    buttons_c = (*pos(bx, by), brr * k)
    EYES.update(o=stick_c, O=buttons_c)
    marks = _well(*stick_c, stick_fill, hole, ring_w * k) + _well(*buttons_c, stick_fill, hole, ring_w * k)
    if with_stick:
        marks += stick_pupil(*stick_c, stick_fill) + buttons_pupil(*buttons_c, stick_fill)
    if glow:  # soft halo under the controller (filter id supplied by the caller's defs)
        parts.insert(0, f'<g opacity="0.7" filter="url(#{glow})">{marks}</g>')
    parts.append(marks)
    return "".join(parts), gx * k, stick_c


def svg(w, h, body, defs="", vb=None):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{vb or f"0 0 {w} {h}"}">'
            f"<defs>{defs}</defs>{body}</svg>\n")


# ------------------------------------------------------------------ pieces

def icon(size=256):
    """The app tile: blue-violet squircle, the white oO controller."""
    k = size / 240
    sr, br, w = 36 * k, 50 * k, GRID_T * 0.62 * k
    left = (size - (2 * sr + 10 * k + 2 * br)) / 2
    body = (f'<rect width="{size}" height="{size}" rx="{size * 0.22}" fill="url(#tile)"/>'
            + stick_mark(left + sr, size / 2 + 14 * k, sr, "#FFFFFF", "#FFFFFF", "url(#tile)", w)
            + buttons_mark(left + 2 * sr + 10 * k + br, size / 2, br, "#FFFFFF", "#FFFFFF", "url(#tile)", w))
    return svg(size, size, body, gradient("tile", units="userSpaceOnUse", x2=f"{size}", y2=f"{size}"))


def icon_small(size=24):
    """16-24 px: the face-button O alone, heavier, so it still reads in a taskbar or tab."""
    c, r = size / 2, size * 0.36
    body = (f'<rect width="{size}" height="{size}" rx="{size * 0.22}" fill="url(#tile)"/>'
            + buttons_mark(c, c, r, "#FFFFFF", "#FFFFFF", "url(#tile)", size * 0.13, g=0.42, br=0.20))
    return svg(size, size, body, gradient("tile", units="userSpaceOnUse", x2=f"{size}", y2=f"{size}"))


def wordmark_defs(stick, width):
    return gradient("deckos-grad", units="userSpaceOnUse", x1=f"{stick[0] - stick[2]:.1f}", y1=f"{stick[1] - stick[2] * 2:.1f}",
                    x2=f"{stick[0] + stick[2] * 5:.1f}", y2=f"{stick[1] + stick[2]:.1f}")


def wordmark_file(with_stick=True, size=200):
    pad = size * 0.12
    cap = size * 0.73
    frag, w, stick = wordmark(pad, pad + cap, size, with_stick=with_stick)
    h = pad * 2 + cap
    return svg(round(w + pad * 2), round(h), frag, wordmark_defs(stick, w)), stick, (w + pad * 2, h)


def eye_file(which, eyes, defs):
    """One eye's pupil from wordmark-bare.svg's last draw, in a box 100 wordmark units wide centred on its well,
    with the wordmark's gradient: placed at the well centre, it lines up with the bare wordmark."""
    cx, cy, r = eyes[which]
    pupil = stick_pupil(cx, cy, r, "url(#deckos-grad)") if which == "o" else buttons_pupil(cx, cy, r, "url(#deckos-grad)")
    return svg(100, 100, pupil, defs, vb=f"{cx - 50:.2f} {cy - 50:.2f} 100 100")


def backdrop(w, h, glow_a=(0.18, 0.92), glow_b=(0.86, 0.12)):
    """Deep slate with two soft light sources in the brand colours. No grid, no clutter."""
    k = w / 3840
    defs = (f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/>'
            f'<stop offset="1" stop-color="{BG_DEEP}"/></linearGradient>'
            f'<radialGradient id="ga" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{GRAD_A}" stop-opacity="0.22"/>'
            f'<stop offset="1" stop-color="{GRAD_A}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="gb" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{GRAD_B}" stop-opacity="0.16"/>'
            f'<stop offset="1" stop-color="{GRAD_B}" stop-opacity="0"/></radialGradient>')
    body = (f'<rect width="{w}" height="{h}" fill="url(#bg)"/>'
            f'<ellipse cx="{w * glow_a[0]}" cy="{h * glow_a[1]}" rx="{2000 * k}" ry="{1400 * k}" fill="url(#ga)"/>'
            f'<ellipse cx="{w * glow_b[0]}" cy="{h * glow_b[1]}" rx="{1700 * k}" ry="{1200 * k}" fill="url(#gb)"/>')
    return defs, body


def glow_filter(id_, blur):
    return (f'<filter id="{id_}" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB">'
            f'<feGaussianBlur stdDeviation="{blur}"/></filter>')


def gauge(cx, cy, r, k, start=40, sweep=212, ticks=54, grad="url(#line)"):
    """Tachometer ticks around a circle; every 5th tick is long, opacity rises along the sweep."""
    out = []
    for i in range(ticks):
        t = i / (ticks - 1)
        a = math.radians(start + sweep * t)
        major = i % 5 == 0
        r0 = r - (34 if major else 18) * k
        op = 0.14 + 0.66 * t ** 2.0
        out.append(f'<line x1="{cx + r0 * math.cos(a):.1f}" y1="{cy + r0 * math.sin(a):.1f}" '
                   f'x2="{cx + r * math.cos(a):.1f}" y2="{cy + r * math.sin(a):.1f}" stroke="{grad}" '
                   f'stroke-opacity="{op:.2f}" stroke-width="{(5 if major else 3) * k:.1f}" stroke-linecap="round"/>')
    # Redline: the last 15% of the sweep as a bright arc.
    a0, a1 = math.radians(start + sweep * 0.85), math.radians(start + sweep)
    rr = r + 16 * k
    out.append(f'<path d="M{cx + rr * math.cos(a0):.1f},{cy + rr * math.sin(a0):.1f} '
               f'A{rr:.1f},{rr:.1f} 0 0,1 {cx + rr * math.cos(a1):.1f},{cy + rr * math.sin(a1):.1f}" '
               f'fill="none" stroke="{GRAD_B}" stroke-opacity="0.8" stroke-width="{6 * k:.1f}" stroke-linecap="round"/>')
    return "".join(out)


def streaks(w, h, k, count=7, seed=7):
    """Angled light streaks (speed lines) sweeping up toward the right."""
    rnd = __import__("random").Random(seed)
    out = []
    for i in range(count):
        y = h * (0.52 + 0.06 * i) + rnd.uniform(-40, 40) * k
        x = rnd.uniform(-200, 900) * k
        length = rnd.uniform(700, 1500) * k
        thick = rnd.uniform(3, 9) * k
        op = rnd.uniform(0.10, 0.30)
        skew = length * 0.30
        out.append(f'<path d="M{x:.0f},{y:.0f} L{x + length:.0f},{y - skew:.0f} L{x + length:.0f},{y - skew + thick:.0f} '
                   f'L{x:.0f},{y + thick:.0f} Z" fill="url(#streak)" opacity="{op:.2f}"/>')
    return "".join(out)


def wallpaper(w=3840, h=2160):
    k = w / 3840
    defs, body = backdrop(w, h)
    cx, cy, r = 2960 * k, 1130 * k, 840 * k
    defs += gradient("line", units="userSpaceOnUse", x1=f"{cx - r}", y1=f"{cy - r}", x2=f"{cx + r}", y2=f"{cy + r}")
    defs += (f'<linearGradient id="streak" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{GRAD_A}" stop-opacity="0"/>'
             f'<stop offset="0.7" stop-color="{GRAD_A}"/><stop offset="1" stop-color="{GRAD_B}"/></linearGradient>')
    defs += glow_filter("glow", 26 * k) + glow_filter("glowsoft", 60 * k)
    # Fine dot matrix that only shows around the emblem.
    step = 48 * k
    defs += (f'<pattern id="dots" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
             f'<circle cx="{step / 2}" cy="{step / 2}" r="{2.2 * k}" fill="{TEXT}"/></pattern>'
             f'<radialGradient id="dotfade" cx="{cx / w}" cy="{cy / h}" r="0.45" gradientUnits="objectBoundingBox">'
             f'<stop offset="0" stop-color="#fff" stop-opacity="0.07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
             f'<mask id="dotmask"><rect width="{w}" height="{h}" fill="url(#dotfade)"/></mask>')
    body += f'<rect width="{w}" height="{h}" fill="url(#dots)" mask="url(#dotmask)"/>'
    body += streaks(w, h, k)
    # The emblem as neon outlines: the gate ring, then the tilted cap (rim and dished centre).
    gate, cap, (ox, oy, cr) = thumbstick(cx, cy, r, weight=110 * k, tilt=0.15)
    for d, soft, mid, edge in ((gate, 0.35, 0.55, 0.9), (cap, 0.22, 0.40, 0.75)):
        # A wide soft halo, a tighter glow, then the crisp edge on top.
        body += f'<path d="{d}" fill="none" stroke="url(#line)" stroke-opacity="{soft}" stroke-width="{14 * k}" filter="url(#glowsoft)"/>'
        body += (f'<path d="{d}" fill="url(#line)" fill-opacity="0.05" fill-rule="evenodd" stroke="url(#line)" '
                 f'stroke-opacity="{mid}" stroke-width="{5 * k}" filter="url(#glow)"/>')
        body += f'<path d="{d}" fill="none" stroke="url(#line)" stroke-opacity="{edge}" stroke-width="{2.5 * k}"/>'
    # The cap's travel: a faint circle it would trace if the stick went all the way round.
    travel = math.hypot(ox - cx, oy - cy)
    body += (f'<circle cx="{cx}" cy="{cy}" r="{travel + cr:.1f}" fill="none" stroke="url(#line)" stroke-opacity="0.30" '
             f'stroke-width="{3 * k}" stroke-dasharray="{4 * k} {16 * k}" stroke-linecap="round"/>')
    # A short motion trail behind the cap, along that circle.
    for i, op in enumerate((0.20, 0.12, 0.06)):
        a = math.atan2(oy - cy, ox - cx) - (i + 1) * 0.22
        body += (f'<circle cx="{cx + travel * math.cos(a):.1f}" cy="{cy + travel * math.sin(a):.1f}" r="{cr:.1f}" '
                 f'fill="none" stroke="url(#line)" stroke-opacity="{op}" stroke-width="{2 * k}"/>')
    body += gauge(cx, cy, r * 1.17, k)
    return svg(w, h, body, defs)


def grub_background(w=1920, h=1080):
    defs, body = backdrop(w, h, glow_a=(0.5, 0.0), glow_b=(0.5, 1.15))
    size = 120
    frag, ww, stick = wordmark(0, 0, size)
    x = (w - ww) / 2
    baseline = h * 0.25
    frag, ww, stick = wordmark(x, baseline, size, glow="glow")
    defs += wordmark_defs(stick, ww) + glow_filter("glow", 14)
    defs += (f'<linearGradient id="streak" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{GRAD_A}" stop-opacity="0"/>'
             f'<stop offset="0.7" stop-color="{GRAD_A}"/><stop offset="1" stop-color="{GRAD_B}"/></linearGradient>')
    body += streaks(w, h, w / 3840, count=5, seed=3)
    body += frag
    tag, tw = text_path(INTER_MED, "Choose what to start", 0, 0, 26)
    tag, tw = text_path(INTER_MED, "Choose what to start", (w - tw) / 2, baseline + 70, 26)
    body += f'<path fill="{SUBTEXT}" d="{tag}"/>'
    return svg(w, h, body, defs)


def grub_select_pieces(r=10, fill="#1C2130", stroke="#2E3546"):
    """9-slice highlight bar for the GRUB menu: rounded corners, 1px border."""
    out = {}
    q = r + 1
    # Corners are drawn from one full rounded rect clipped to each corner box.
    full = (f'<rect x="0.5" y="0.5" width="{2 * q - 1}" height="{2 * q - 1}" rx="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
    for name, (ox, oy) in {"nw": (0, 0), "ne": (q, 0), "sw": (0, q), "se": (q, q)}.items():
        out[f"select_{name}.svg"] = svg(q, q, full, vb=f"{ox} {oy} {q} {q}")
    out["select_n.svg"] = svg(4, q, f'<rect width="4" height="{q}" fill="{fill}"/><rect width="4" height="1" fill="{stroke}"/>')
    out["select_s.svg"] = svg(4, q, f'<rect width="4" height="{q}" fill="{fill}"/><rect y="{q - 1}" width="4" height="1" fill="{stroke}"/>')
    out["select_w.svg"] = svg(q, 4, f'<rect width="{q}" height="4" fill="{fill}"/><rect width="1" height="4" fill="{stroke}"/>')
    out["select_e.svg"] = svg(q, 4, f'<rect width="{q}" height="4" fill="{fill}"/><rect x="{q - 1}" width="1" height="4" fill="{stroke}"/>')
    out["select_c.svg"] = svg(4, 4, f'<rect width="4" height="4" fill="{fill}"/>')
    return out


def installer_welcome(w=900, h=260):
    defs, body = backdrop(w, h, glow_a=(0.2, 1.0), glow_b=(0.9, 0.0))
    frag, ww, stick = wordmark(0, 0, 96)
    frag, ww, stick = wordmark((w - ww) / 2, h * 0.62, 96, glow="glow")
    defs += wordmark_defs(stick, ww) + glow_filter("glow", 12)
    return svg(w, h, f'<rect width="{w}" height="{h}" rx="14" fill="{BG}"/>' + body + frag, defs)


def _choice_frame(w, h, inner):
    defs, body = backdrop(w, h, glow_a=(0.15, 1.0), glow_b=(0.95, 0.0))
    return svg(w, h, f'<clipPath id="r"><rect width="{w}" height="{h}" rx="14"/></clipPath><g clip-path="url(#r)">'
               + body + inner + "</g>", defs + gradient("acc"))


def choice_desktop(w=640, h=360):
    """Mini desktop: two windows and the floating dock."""
    win = lambda x, y, ww, hh, title: (
        f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" rx="10" fill="{SURFACE}" stroke="{BORDER}"/>'
        f'<rect x="{x}" y="{y}" width="{ww}" height="26" rx="10" fill="#13161C"/>'
        f'<rect x="{x}" y="{y + 16}" width="{ww}" height="10" fill="#13161C"/>'
        + "".join(f'<circle cx="{x + ww - 14 - 14 * i}" cy="{y + 13}" r="4" fill="{MUTED}"/>' for i in range(3))
        + f'<rect x="{x + 14}" y="{y + 10}" width="{len(title) * 6}" height="6" rx="3" fill="{SUBTEXT}"/>')
    lines = "".join(f'<rect x="{70}" y="{120 + 18 * i}" width="{220 - 30 * (i % 3)}" height="7" rx="3.5" fill="{BORDER}"/>' for i in range(5))
    code = "".join(f'<rect x="{350}" y="{96 + 16 * i}" width="{40 + (i * 37) % 150}" height="6" rx="3" fill="url(#acc)" opacity="{0.35 + 0.1 * (i % 3)}"/>' for i in range(8))
    dock = (f'<rect x="{w / 2 - 120}" y="{h - 52}" width="240" height="36" rx="12" fill="{SURFACE}" stroke="{BORDER}"/>'
            + "".join(f'<rect x="{w / 2 - 100 + 42 * i}" y="{h - 44}" width="20" height="20" rx="6" fill="{"url(#acc)" if i == 2 else BORDER}"/>' for i in range(5)))
    return _choice_frame(w, h, win(50, 70, 260, 160, "Dolphin") + lines + win(330, 50, 260, 200, "Code") + code + dock)


def choice_gaming(w=640, h=360):
    """Mini Steam Big Picture: a hero tile and a row of game covers."""
    hero = (f'<rect x="40" y="46" width="{w - 80}" height="150" rx="12" fill="url(#acc)" opacity="0.85"/>'
            f'<rect x="64" y="150" width="150" height="12" rx="6" fill="#FFFFFF" opacity="0.9"/>'
            f'<rect x="64" y="170" width="90" height="8" rx="4" fill="#FFFFFF" opacity="0.6"/>'
            f'<rect x="{w - 170}" y="150" width="106" height="30" rx="8" fill="#FFFFFF"/>')
    covers = "".join(f'<rect x="{40 + i * 114}" y="216" width="100" height="120" rx="10" fill="{SURFACE}" stroke="{BORDER}"/>'
                     f'<rect x="{52 + i * 114}" y="310" width="{50 + (i * 13) % 30}" height="7" rx="3.5" fill="{BORDER}"/>' for i in range(5))
    pad = controller("cg", w - 118, 60, 56, "#FFFFFF")
    return _choice_frame(w, h, hero + covers + pad)


def choice_display(w=640, h=360):
    """A monitor with a steady signal: the blackout fix."""
    mon = (f'<rect x="150" y="50" width="340" height="200" rx="12" fill="{SURFACE}" stroke="{BORDER}" stroke-width="2"/>'
           f'<rect x="166" y="66" width="308" height="168" rx="6" fill="#0B0D11"/>'
           f'<rect x="300" y="250" width="40" height="34" fill="{BORDER}"/><rect x="250" y="284" width="140" height="10" rx="5" fill="{BORDER}"/>')
    pulse = (f'<path d="M186,150 L270,150 L285,110 L300,190 L315,130 L330,150 L454,150" fill="none" stroke="url(#acc)" '
             f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>')
    badge = (f'<circle cx="474" cy="70" r="26" fill="url(#acc)"/>'
             f'<path d="M462,70 L471,79 L487,61" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
    t, tw = text_path(INTER_MED, "4K  ·  144 Hz  ·  no blackouts", 0, 0, 18)
    t, tw = text_path(INTER_MED, "4K  ·  144 Hz  ·  no blackouts", (w - tw) / 2, 330, 18)
    return _choice_frame(w, h, mon + pulse + badge + f'<path fill="{SUBTEXT}" d="{t}"/>')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "grub").mkdir(exist_ok=True)
    wm, wm_stick, wm_size = wordmark_file()
    wm_bare, _, _ = wordmark_file(with_stick=False)
    eyes = dict(EYES)  # later wordmarks (GRUB, installer) redraw EYES at other sizes
    eye_defs = wordmark_defs(eyes["o"], 0)
    files = {
        "logo.svg": icon(),
        "logo-small.svg": icon_small(),
        "wordmark.svg": wm,
        "wordmark-bare.svg": wm_bare,
        "eye-stick.svg": eye_file("o", eyes, eye_defs),
        "eye-buttons.svg": eye_file("O", eyes, eye_defs),
        "wallpaper.svg": wallpaper(),
        "grub-background.svg": grub_background(),
        "installer-welcome.svg": installer_welcome(),
        "choice-desktop.svg": choice_desktop(),
        "choice-gaming.svg": choice_gaming(),
        "choice-display.svg": choice_display(),
    }
    for name, data in grub_select_pieces().items():
        files[f"grub/{name}"] = data
    for name, data in files.items():
        (OUT / name).write_text(data, encoding="utf-8", newline="\n")
        print("wrote", name)
    print(f"eye centres in wordmark.svg (for Splash.qml, deckos.script, boot_movie.py): "
          f"o ({eyes['o'][0]:.1f}, {eyes['o'][1]:.1f}), O ({eyes['O'][0]:.1f}, {eyes['O'][1]:.1f}) of ({wm_size[0]:.0f}, {wm_size[1]:.0f})")

    # Preview sheet for eyeballing (not committed).
    show = [("wordmark.svg", 420), ("logo.svg", 160), ("wallpaper.svg", 1200),
            ("grub-background.svg", 900), ("installer-welcome.svg", 600),
            ("choice-desktop.svg", 400), ("choice-gaming.svg", 400), ("choice-display.svg", 400)]
    cells = "".join(
        f'<figure><figcaption>{n}</figcaption><div style="width:{wd}px;max-width:calc(100vw - 40px)">'
        + files[n].replace("<svg ", '<svg style="width:100%;height:auto;display:block" ', 1) + "</div></figure>"
        for n, wd in show)
    (HERE / "preview.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>DecKoOS brand preview</title>'
        f'<style>body{{background:{BG};color:{SUBTEXT};font:13px sans-serif;margin:16px;display:flex;flex-wrap:wrap;'
        f'gap:18px;align-items:flex-start}}figure{{margin:0}}figure div{{border:1px solid {BORDER}}}</style>' + cells,
        encoding="utf-8")


if __name__ == "__main__":
    main()
