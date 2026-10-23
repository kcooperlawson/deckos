"""Generates the DeckOS brand: icon, wordmark, wallpaper, GRUB theme art, installer art.

Same family as Steady Downloader: deep slate surfaces, quiet 1px borders, and the
blue→violet gradient tile with a white rounded glyph. The O in "DeckOS" is a gear ring.

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


# ------------------------------------------------------------------ the gear O

def gear_ring(cx, cy, r_out, thickness, teeth=8, tooth_depth=0.13, steps=960):
    """A ring whose outer edge carries soft rounded teeth. evenodd path (outer + round hole)."""
    r_root = r_out * (1 - tooth_depth)
    r_in = r_root - thickness
    pts = []
    for i in range(steps):
        t = i / steps
        a = 2 * math.pi * t - math.pi / 2
        # Tooth profile: flat top over ~38% of the pitch, smooth cosine flanks.
        p = (t * teeth) % 1.0
        top, flank = 0.38, 0.16
        lo, hi = 0.5 - top / 2, 0.5 + top / 2
        if lo <= p <= hi:
            k = 1.0
        elif lo - flank < p < lo:
            k = 0.5 - 0.5 * math.cos(math.pi * (p - (lo - flank)) / flank)
        elif hi < p < hi + flank:
            k = 0.5 + 0.5 * math.cos(math.pi * (p - hi) / flank)
        else:
            k = 0.0
        r = r_root + (r_out - r_root) * k
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    outer = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"
    hole = (f"M{cx - r_in:.2f},{cy:.2f} a{r_in:.2f},{r_in:.2f} 0 1,0 {2 * r_in:.2f},0 "
            f"a{r_in:.2f},{r_in:.2f} 0 1,0 {-2 * r_in:.2f},0 Z")
    return outer + " " + hole


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
        out.append(f'<path fill="{stick or body}" fill-rule="evenodd" d="{stick_ring(sx, sy, sr * 0.80)}"/>')
    out.append("</g>")
    return "".join(out)


def stick_ring(cx, cy, r, thickness=None):
    """The thumbstick 'O' of DeckO: a ring with fine grip ridges round its edge."""
    return gear_ring(cx, cy, r, thickness or r * 0.34, teeth=18, tooth_depth=0.07)


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


def wordmark(x, baseline, size, text=TEXT, gear_fill="url(#deckos-grad)", with_gear=True, glow=None):
    """'Deck' + gear-O + 'S' in Inter Display SemiBold. Returns (svg, width, gear(cx, cy, r))."""
    s = size / INTER.upm
    deck, w_deck = text_path(INTER, "Deck", x, baseline, size)
    # The gear takes the exact box of Inter's "O" so it optically matches the caps.
    ox0, oy0, ox1, oy1 = INTER.bounds("O")
    # Teeth stick out past the O's outline, so the gear gets extra room on both sides.
    margin = size * 0.045
    o_left = x + w_deck + ox0 * s + margin
    r = (oy1 - oy0) * s / 2 * 1.02
    cx = o_left + (ox1 - ox0) * s / 2
    cy = baseline - (oy0 + oy1) / 2 * s
    stem = size * 0.112
    S_x = x + w_deck + INTER.advance("O") * s + 2 * margin
    S, w_S = text_path(INTER, "S", S_x, baseline, size)
    width = S_x + w_S - x
    parts = [f'<path fill="{text}" d="{deck}"/>', f'<path fill="{text}" d="{S}"/>']
    if with_gear:
        ring = stick_ring(cx, cy, r, stem)
        parts.insert(1, f'<path fill="{gear_fill}" fill-rule="evenodd" d="{ring}"/>')
        if glow:  # neon halo under the gear (filter id supplied by the caller's defs)
            parts.insert(0, f'<path fill="{gear_fill}" fill-rule="evenodd" opacity="0.85" filter="url(#{glow})" d="{ring}"/>')
    return "".join(parts), width, (cx, cy, r)


def svg(w, h, body, defs="", vb=None):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{vb or f"0 0 {w} {h}"}">'
            f"<defs>{defs}</defs>{body}</svg>\n")


# ------------------------------------------------------------------ pieces

def icon(size=256):
    """Steady-style app tile: blue-violet squircle, white controller with the thumbstick O."""
    ph = size * 0.50
    pw = ph * PAD_W / PAD_H
    body = (f'<rect width="{size}" height="{size}" rx="{size * 0.22}" fill="url(#tile)"/>'
            + controller("i", (size - pw) / 2, (size - ph) / 2 + size * 0.015, ph, "#FFFFFF"))
    return svg(size, size, body, gradient("tile"))


def wordmark_file(with_gear=True, size=200):
    pad = size * 0.12
    frag, w, gear = wordmark(pad, pad + INTER.cap * size / INTER.upm + size * 0.04, size, with_gear=with_gear)
    h = pad * 2 + INTER.cap * size / INTER.upm + size * 0.08
    defs = gradient("deckos-grad", units="userSpaceOnUse", x1=f"{gear[0] - gear[2]:.1f}", y1=f"{gear[1] - gear[2]:.1f}",
                    x2=f"{gear[0] + gear[2]:.1f}", y2=f"{gear[1] + gear[2]:.1f}")
    return svg(round(w + pad * 2), round(h), frag, defs), gear, (w + pad * 2, h)


def gear_file(r_px=60):
    size = r_px * 2 + 4
    c = size / 2
    defs = gradient("g", units="userSpaceOnUse", x1=f"{c - r_px}", y1=f"{c - r_px}", x2=f"{c + r_px}", y2=f"{c + r_px}")
    return svg(size, size, f'<path fill="url(#g)" fill-rule="evenodd" d="{stick_ring(c, c, r_px, r_px * 0.88 * 0.112 / 0.51)}"/>', defs)


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
    # Fine dot matrix that only shows around the gear.
    step = 48 * k
    defs += (f'<pattern id="dots" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
             f'<circle cx="{step / 2}" cy="{step / 2}" r="{2.2 * k}" fill="{TEXT}"/></pattern>'
             f'<radialGradient id="dotfade" cx="{cx / w}" cy="{cy / h}" r="0.45" gradientUnits="objectBoundingBox">'
             f'<stop offset="0" stop-color="#fff" stop-opacity="0.07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
             f'<mask id="dotmask"><rect width="{w}" height="{h}" fill="url(#dotfade)"/></mask>')
    body += f'<rect width="{w}" height="{h}" fill="url(#dots)" mask="url(#dotmask)"/>'
    body += streaks(w, h, k)
    ring = gear_ring(cx, cy, r, 120 * k, teeth=30, tooth_depth=0.045)
    # Neon: a wide soft halo, a tighter glow, then the crisp edge on top.
    body += f'<path d="{ring}" fill="none" stroke="url(#line)" stroke-opacity="0.35" stroke-width="{14 * k}" filter="url(#glowsoft)"/>'
    body += f'<path d="{ring}" fill="url(#line)" fill-opacity="0.05" stroke="url(#line)" stroke-opacity="0.55" stroke-width="{5 * k}" filter="url(#glow)"/>'
    body += f'<path d="{ring}" fill="none" stroke="url(#line)" stroke-opacity="0.9" stroke-width="{2.5 * k}"/>'
    inner = gear_ring(cx, cy, r * 0.55, 60 * k, teeth=8, tooth_depth=0.10)
    body += f'<path d="{inner}" fill="none" stroke="url(#line)" stroke-opacity="0.22" stroke-width="{2 * k}"/>'
    body += gauge(cx, cy, r * 1.17, k)
    return svg(w, h, body, defs)


def grub_background(w=1920, h=1080):
    defs, body = backdrop(w, h, glow_a=(0.5, 0.0), glow_b=(0.5, 1.15))
    size = 120
    frag, ww, gear = wordmark(0, 0, size)
    x = (w - ww) / 2
    baseline = h * 0.25
    frag, ww, gear = wordmark(x, baseline, size, glow="glow")
    defs += gradient("deckos-grad", units="userSpaceOnUse", x1=f"{gear[0] - gear[2]}", y1=f"{gear[1] - gear[2]}",
                     x2=f"{gear[0] + gear[2]}", y2=f"{gear[1] + gear[2]}") + glow_filter("glow", 14)
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
    frag, ww, gear = wordmark(0, 0, 96)
    frag, ww, gear = wordmark((w - ww) / 2, h * 0.62, 96, glow="glow")
    defs += gradient("deckos-grad", units="userSpaceOnUse", x1=f"{gear[0] - gear[2]}", y1=f"{gear[1] - gear[2]}",
                     x2=f"{gear[0] + gear[2]}", y2=f"{gear[1] + gear[2]}") + glow_filter("glow", 12)
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
    wm, wm_gear, wm_size = wordmark_file()
    wm_nogear, _, _ = wordmark_file(with_gear=False)
    files = {
        "logo.svg": icon(),
        "wordmark.svg": wm,
        "wordmark-nogear.svg": wm_nogear,
        "gear.svg": gear_file(round(wm_gear[2])),
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
    print(f"gear centre in wordmark.svg: ({wm_gear[0]:.1f}, {wm_gear[1]:.1f}) r={wm_gear[2]:.1f} "
          f"of ({wm_size[0]:.0f}, {wm_size[1]:.0f})")

    # Preview sheet for eyeballing (not committed).
    show = [("wordmark.svg", 420), ("logo.svg", 160), ("wallpaper.svg", 1200),
            ("grub-background.svg", 900), ("installer-welcome.svg", 600),
            ("choice-desktop.svg", 400), ("choice-gaming.svg", 400), ("choice-display.svg", 400)]
    cells = "".join(
        f'<figure><figcaption>{n}</figcaption><div style="width:{wd}px;max-width:calc(100vw - 40px)">'
        + files[n].replace("<svg ", '<svg style="width:100%;height:auto;display:block" ', 1) + "</div></figure>"
        for n, wd in show)
    (HERE / "preview.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>DeckOS brand preview</title>'
        f'<style>body{{background:{BG};color:{SUBTEXT};font:13px sans-serif;margin:16px;display:flex;flex-wrap:wrap;'
        f'gap:18px;align-items:flex-start}}figure{{margin:0}}figure div{{border:1px solid {BORDER}}}</style>' + cells,
        encoding="utf-8")


if __name__ == "__main__":
    main()
