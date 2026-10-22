"""Generates the DeckOS brand SVGs (logo, wordmark, wallpaper, GRUB background, splash parts).

Run: python assets/generate.py
Output goes to pkg/deckos-settings/rootfs/usr/share/deckos/branding/ and is committed,
so the package build only has to rasterise them.
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "pkg/deckos-settings/rootfs/usr/share/deckos/branding"

# Palette shared with Steady Downloader (App.xaml) so everything reads as one family.
BG = "#0F1115"
BG_DEEP = "#0A0C10"
SURFACE = "#171A21"
BORDER = "#262B36"
HOVER = "#2A2F3B"
TEXT = "#E8EAF0"
SUBTEXT = "#8C94A6"
MUTED = "#5A6172"
ACCENT = "#4C8DFF"
ACCENT_HOVER = "#6AA2FF"
WARNING = "#F5B84B"

MONO = "JetBrainsMono Nerd Font, JetBrains Mono, monospace"

# Stencil-style letters on a 100-unit cap height with chamfered (machined) corners.
LETTERS = {
    "D": (90, "M0,0 H60 L90,30 V70 L60,100 H0 Z M22,22 V78 H52 L68,62 V38 L52,22 Z"),
    "E": (80, "M12,0 H80 V22 H22 V39 H64 V61 H22 V78 H80 V100 H12 L0,88 V12 Z"),
    "C": (86, "M18,0 H86 V22 H30 L22,30 V70 L30,78 H86 V100 H18 L0,82 V18 Z"),
    "K": (88, "M0,0 H22 V39 H34 L62,0 H88 L52,50 L88,100 H62 L34,61 H22 V100 H0 Z"),
    "S": (88, "M14,0 H86 V22 H28 V39 H74 L88,53 V86 L74,100 H0 V78 H66 V61 H14 L0,47 V14 Z"),
}
GAP = 14
GEAR_D = 116  # the shared "O": a gear, slightly taller than the caps like a bolt head


def gear_path(cx, cy, r_tip, r_root, r_hole, teeth=10):
    pitch = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = i * pitch - math.pi / 2
        for frac, r in ((-0.30, r_root), (-0.17, r_tip), (0.17, r_tip), (0.30, r_root)):
            ang = a + frac * pitch
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"
    # Counter of the O, drawn as a circle sub-path so evenodd punches it out.
    d += (f" M{cx - r_hole:.2f},{cy:.2f} a{r_hole},{r_hole} 0 1,0 {2 * r_hole},0"
          f" a{r_hole},{r_hole} 0 1,0 {-2 * r_hole},0 Z")
    return d


def hex_path(cx, cy, r, hole=0.0):
    pts = [(cx + r * math.cos(math.pi / 6 + i * math.pi / 3), cy + r * math.sin(math.pi / 6 + i * math.pi / 3)) for i in range(6)]
    d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"
    if hole:
        d += (f" M{cx - hole:.2f},{cy:.2f} a{hole},{hole} 0 1,0 {2 * hole},0"
              f" a{hole},{hole} 0 1,0 {-2 * hole},0 Z")
    return d


def gear_mark(cx, cy, d=GEAR_D, color=ACCENT, bolt=ACCENT):
    r_tip = d / 2
    body = f'<path fill="{color}" fill-rule="evenodd" d="{gear_path(cx, cy, r_tip, r_tip * 0.82, r_tip * 0.50)}"/>'
    nut = f'<path fill="{bolt}" fill-rule="evenodd" d="{hex_path(cx, cy, r_tip * 0.24, r_tip * 0.09)}"/>'
    return body + nut


def wordmark(x0=0.0, y0=0.0, scale=1.0, text=TEXT, accent=ACCENT, with_gear=True):
    """Returns (svg_fragment, width, gear_center) in the caller's coordinates."""
    parts, x = [], 0.0
    gear_center = None
    for ch in "DECK":
        w, d = LETTERS[ch]
        parts.append(f'<path transform="translate({x},0)" fill="{text}" fill-rule="evenodd" d="{d}"/>')
        x += w + GAP
    gear_center = (x + GEAR_D / 2, 50)
    if with_gear:
        parts.append(gear_mark(*gear_center, color=accent, bolt=accent))
    x += GEAR_D + GAP
    w, d = LETTERS["S"]
    parts.append(f'<path transform="translate({x},0)" fill="{text}" fill-rule="evenodd" d="{d}"/>')
    x += w
    frag = f'<g transform="translate({x0},{y0}) scale({scale})">' + "".join(parts) + "</g>"
    gx, gy = gear_center
    return frag, x * scale, (x0 + gx * scale, y0 + gy * scale)


WORD_W = wordmark()[1]  # 618 units
VB_PAD = 12


def svg(w, h, body, vb=None):
    vb = vb or f"0 0 {w} {h}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{vb}">\n'
            f"{body}\n</svg>\n")


def bolt(cx, cy, r=9):
    # Countersunk screw head: ring, face, and a slot at a jaunty angle.
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{HOVER}" stroke="{BORDER}" stroke-width="2"/>'
            f'<line x1="{cx - r * 0.6}" y1="{cy + r * 0.35}" x2="{cx + r * 0.6}" y2="{cy - r * 0.35}" '
            f'stroke="{BG}" stroke-width="{max(2, r * 0.28):.1f}" stroke-linecap="round"/>')


def plate(x, y, w, h, c=28, fill="#12151B", stroke=BORDER, sw=3, bolts=True):
    d = f"M{x + c},{y} H{x + w - c} L{x + w},{y + c} V{y + h - c} L{x + w - c},{y + h} H{x + c} L{x},{y + h - c} V{y + c} Z"
    out = f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    if bolts:
        i = c + 18
        for bx, by in ((x + i, y + 26), (x + w - i, y + 26), (x + i, y + h - 26), (x + w - i, y + h - 26)):
            out += bolt(bx, by)
    return out


def outline_gear(cx, cy, r, stroke, sw, teeth=24, rot=0.0):
    pitch = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = i * pitch + rot
        for frac, rr in ((-0.30, r * 0.90), (-0.16, r), (0.16, r), (0.30, r * 0.90)):
            ang = a + frac * pitch
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    spokes = "".join(
        f'<line x1="{cx + r * 0.30 * math.cos(rot + k * math.pi / 3):.1f}" y1="{cy + r * 0.30 * math.sin(rot + k * math.pi / 3):.1f}" '
        f'x2="{cx + r * 0.66 * math.cos(rot + k * math.pi / 3):.1f}" y2="{cy + r * 0.66 * math.sin(rot + k * math.pi / 3):.1f}" '
        f'stroke="{stroke}" stroke-width="{sw * 1.6}"/>' for k in range(6))
    return (f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.70}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.26}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<path d="{hex_path(cx, cy, r * 0.12)}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>' + spokes)


def hazard(x, y, w, h, color=WARNING, opacity=0.85):
    stripes = "".join(
        f'<path d="M{x + i},{y + h} L{x + i + h},{y} L{x + i + h + 22},{y} L{x + i + 22},{y + h} Z" fill="{color}"/>'
        for i in range(-int(h), int(w + h), 44))
    cid = f"hz{int(x)}{int(y)}"
    return (f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>'
            f'<g clip-path="url(#{cid})" opacity="{opacity}">{stripes}</g>')


def hud_corners(w, h, m=90, l=140, stroke=BORDER, sw=4):
    out = ""
    for (x, y, dx, dy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
        out += f'<path d="M{x},{y + dy * l} V{y} H{x + dx * l}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
    return out


def backdrop(w, h, k):
    """Blueprint grid, glow and machinery shared by wallpaper and GRUB background. k = scale vs 4K."""
    g1, g2 = 60 * k, 300 * k
    return f"""
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG_DEEP}"/></linearGradient>
  <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.16"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>
  <pattern id="minor" width="{g1}" height="{g1}" patternUnits="userSpaceOnUse"><path d="M{g1},0 H0 V{g1}" fill="none" stroke="#141820" stroke-width="{max(1, 1.5 * k):.1f}"/></pattern>
  <pattern id="major" width="{g2}" height="{g2}" patternUnits="userSpaceOnUse"><path d="M{g2},0 H0 V{g2}" fill="none" stroke="#1A1F29" stroke-width="{max(1, 2 * k):.1f}"/></pattern>
</defs>
<rect width="{w}" height="{h}" fill="url(#bg)"/>
<rect width="{w}" height="{h}" fill="url(#minor)"/>
<rect width="{w}" height="{h}" fill="url(#major)"/>
"""


def wallpaper(w=3840, h=2160):
    k = w / 3840
    body = backdrop(w, h, k)
    # Machinery: a big drive gear meshing with a smaller one, ghosted into the grid.
    body += f'<circle cx="{3020 * k}" cy="{1180 * k}" r="{1100 * k}" fill="url(#glow)"/>'
    body += outline_gear(3020 * k, 1180 * k, 860 * k, "#1E2430", 6 * k, teeth=28, rot=0.05)
    body += outline_gear(2050 * k, 1790 * k, 340 * k, "#1B2029", 5 * k, teeth=12, rot=0.2)
    body += outline_gear(3500 * k, 230 * k, 220 * k, "#191D26", 4 * k, teeth=10, rot=0.4)
    # Nameplate bolted to the left side.
    px, py, pw, ph = 250 * k, 800 * k, 1500 * k, 560 * k
    body += f'<ellipse cx="{px + pw / 2}" cy="{py + ph / 2}" rx="{pw * 0.7}" ry="{ph}" fill="url(#glow)"/>'
    body += plate(px, py, pw, ph, c=34 * k, sw=3 * k)
    scale = (pw - 260 * k) / WORD_W
    frag, ww, _ = wordmark(px + 130 * k, py + 140 * k, scale)
    body += frag
    ty = py + 140 * k + 100 * scale + 92 * k
    body += (f'<text x="{px + 132 * k}" y="{ty}" fill="{SUBTEXT}" font-family="{MONO}" font-size="{40 * k}" '
             f'letter-spacing="{9 * k}" font-weight="700">DECKO CLAN SYSTEMS</text>')
    body += (f'<text x="{px + pw - 132 * k}" y="{ty}" fill="{MUTED}" font-family="{MONO}" font-size="{30 * k}" '
             f'letter-spacing="{5 * k}" text-anchor="end">GAMING // AI // MODDING</text>')
    body += hazard(px + 34 * k, py + ph + 26 * k, pw - 68 * k, 22 * k)
    # Conduit running from the plate into the drive gear, with rivets.
    cy = py + ph / 2
    body += f'<path d="M{px + pw},{cy} H{1980 * k} L{2040 * k},{cy - 60 * k} H{2175 * k}" fill="none" stroke="{ACCENT}" stroke-opacity="0.55" stroke-width="{4 * k}"/>'
    for rx in (1820, 1900):
        body += f'<circle cx="{rx * k}" cy="{cy}" r="{9 * k}" fill="{BG}" stroke="{ACCENT}" stroke-opacity="0.8" stroke-width="{4 * k}"/>'
    body += hud_corners(w, h, 90 * k, 150 * k, sw=4 * k)
    body += (f'<text x="{w - 110 * k}" y="{h - 110 * k}" fill="{MUTED}" font-family="{MONO}" font-size="{26 * k}" '
             f'letter-spacing="{4 * k}" text-anchor="end">DECKOS // ROLLING // ZEN4 + RDNA4</text>')
    return svg(w, h, body)


def grub_background(w=1920, h=1080):
    k = w / 3840
    body = backdrop(w, h, k)
    body += f'<circle cx="{w / 2}" cy="{h * 0.20}" r="{900 * k}" fill="url(#glow)"/>'
    body += outline_gear(3300 * k, 1800 * k, 700 * k, "#1E2430", 6 * k, teeth=24, rot=0.1)
    body += outline_gear(500 * k, 1900 * k, 420 * k, "#1B2029", 5 * k, teeth=14, rot=0.3)
    scale = 1500 * k / WORD_W
    frag, ww, _ = wordmark(w / 2 - 750 * k, h * 0.13, scale)
    body += frag
    body += (f'<text x="{w / 2}" y="{h * 0.13 + 100 * scale + 80 * k}" fill="{SUBTEXT}" font-family="{MONO}" '
             f'font-size="{38 * k}" letter-spacing="{10 * k}" text-anchor="middle" font-weight="700">SELECT BOOT TARGET</text>')
    body += hazard(w / 2 - 450 * k, h * 0.13 + 100 * scale + 120 * k, 900 * k, 16 * k, opacity=0.7)
    body += hud_corners(w, h, 90 * k, 150 * k, sw=4 * k)
    return svg(w, h, body)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pad = VB_PAD
    vb_h = 100 + 2 * pad + (GEAR_D - 100)
    vb = f"{-pad} {-(GEAR_D - 100) / 2 - pad} {WORD_W + 2 * pad} {vb_h}"
    files = {
        "wordmark.svg": svg(int((WORD_W + 2 * pad) * 2), int(vb_h * 2), wordmark()[0], vb),
        # Splash: letters with a hole where the gear goes, plus the gear alone at the same scale.
        "wordmark-nogear.svg": svg(int((WORD_W + 2 * pad) * 2), int(vb_h * 2), wordmark(with_gear=False)[0], vb),
        "gear.svg": svg(GEAR_D * 2 + 8, GEAR_D * 2 + 8, gear_mark(GEAR_D / 2 + 2, GEAR_D / 2 + 2),
                        f"0 0 {GEAR_D + 4} {GEAR_D + 4}"),
        "logo.svg": svg(256, 256, f'<path d="{hex_path(64, 64, 62)}" fill="{SURFACE}" stroke="{BORDER}" stroke-width="2"/>'
                        + gear_mark(64, 64, 92), "0 0 128 128"),
        "wallpaper.svg": wallpaper(),
        "grub-background.svg": grub_background(),
    }
    for name, data in files.items():
        (OUT / name).write_text(data, encoding="utf-8", newline="\n")
        print("wrote", OUT / name)
    # Self-contained preview sheet (inline SVGs, scaled with CSS) for eyeballing the brand.
    widths = {"wallpaper.svg": 1200, "grub-background.svg": 960, "wordmark.svg": 480, "logo.svg": 128, "gear.svg": 96}
    cells = "".join(
        f'<figure><figcaption>{n}</figcaption><div style="width:{wd}px">'
        + files[n].replace("<svg ", '<svg style="width:100%;height:auto;display:block" ', 1) + "</div></figure>"
        for n, wd in widths.items())
    (Path(__file__).parent / "preview.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>DeckOS brand preview</title>'
        '<style>body{background:#0F1115;color:#8C94A6;font:13px sans-serif;margin:16px;display:flex;flex-wrap:wrap;gap:18px}'
        'figure{margin:0}figure div{border:1px solid #262B36}</style>' + cells, encoding="utf-8")
    # Gear position inside the wordmark, in wordmark viewBox units, for the splash script.
    _, _, (gx, gy) = wordmark()
    print(f"gear center in wordmark viewBox: ({gx + pad}, {gy + (GEAR_D - 100) / 2 + pad}) of ({WORD_W + 2 * pad}, {vb_h})")


if __name__ == "__main__":
    main()
