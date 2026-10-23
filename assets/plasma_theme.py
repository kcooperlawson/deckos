"""DeckOS Plasma style: the panel, popups, tooltips and widget backgrounds as "bolted plates".

Writes a Plasma desktop theme (pkg/deckos-settings/.../plasma/desktoptheme/deckos). Each frame is
a 9-slice SVG with Plasma's element names (topleft, top, ..., center, hint-*-margin, shadow-*).
Colours come from Plasma's colour-scheme classes, so the style follows whatever colour scheme is
active (DeckOS, TMpikes...). Anything not drawn here falls back to Breeze. Run after changes:
    python assets/plasma_theme.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "pkg/deckos-settings/rootfs/usr/share/plasma/desktoptheme/deckos"
STYLE = ('<style type="text/css" id="current-color-scheme">'
         '.ColorScheme-Background{color:#171a21;} .ColorScheme-Text{color:#e8eaf0;}</style>')
W = 10      # sample length of the stretched edges / centre
GAP = 4     # space between pieces in the file (cosmetic)


def rect(x, y, w, h, cls, opacity):
    return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" class="{cls}" '
            f'style="fill:currentColor;fill-opacity:{opacity}"/>')


def corner(name, ox, oy, r, fill, border, bolt):
    """A rounded corner piece r x r. Drawn as the top-left corner, then mirrored for the others."""
    fx, fy = name in ("topright", "bottomright"), name in ("bottomleft", "bottomright")
    sweep = "0" if fx != fy else "1"

    def p(x, y):
        return f"{ox + (r - x if fx else x):g},{oy + (r - y if fy else y):g}"

    q = r - 1
    fill_d = f"M{p(r, r)} L{p(1, r)} A{q},{q} 0 0 {sweep} {p(r, 1)} Z"
    border_d = (f"M{p(0, r)} A{r},{r} 0 0 {sweep} {p(r, 0)} L{p(r, 1)} "
                f"A{q},{q} 0 0 {'1' if sweep == '0' else '0'} {p(1, r)} Z")
    body = (f'<path d="{fill_d}" class="ColorScheme-Background" style="fill:currentColor;fill-opacity:{fill}"/>'
            f'<path d="{border_d}" class="ColorScheme-Text" style="fill:currentColor;fill-opacity:{border}"/>')
    if bolt:  # the screw head of the plate
        b = r * 0.6
        cx, cy = p(b, b).split(",")
        body += (f'<circle cx="{cx}" cy="{cy}" r="1.5" class="ColorScheme-Text" '
                 f'style="fill:currentColor;fill-opacity:0.22"/>')
    return f'<g id="{name}">{body}</g>'


def frame(r, fill, border, bolts=False, margins=None, shadow=None):
    """All pieces of one frame. margins: content insets (t, b, l, r); shadow: sizes (t, b, l, r)."""
    m = margins or (r, r, r, r)
    a, b, c = 0, r + GAP, r + W + 2 * GAP  # columns / rows of the 3x3 grid
    out = [corner("topleft", a, a, r, fill, border, bolts), corner("topright", c, a, r, fill, border, bolts),
           corner("bottomleft", a, c, r, fill, border, bolts), corner("bottomright", c, c, r, fill, border, bolts)]
    bg, fg = "ColorScheme-Background", "ColorScheme-Text"
    out.append(f'<g id="top">{rect(b, a, W, 1, fg, border)}{rect(b, a + 1, W, r - 1, bg, fill)}</g>')
    out.append(f'<g id="bottom">{rect(b, c, W, r - 1, bg, fill)}{rect(b, c + r - 1, W, 1, fg, border)}</g>')
    out.append(f'<g id="left">{rect(a, b, 1, W, fg, border)}{rect(a + 1, b, r - 1, W, bg, fill)}</g>')
    out.append(f'<g id="right">{rect(c, b, r - 1, W, bg, fill)}{rect(c + r - 1, b, 1, W, fg, border)}</g>')
    out.append(f'<g id="center">{rect(b, b, W, W, bg, fill)}</g>')
    hy = c + r + 20
    for i, (side, size) in enumerate(zip(("top", "bottom", "left", "right"), m)):
        w, h = (1, size) if side in ("top", "bottom") else (size, 1)
        out.append(f'<rect id="hint-{side}-margin" x="{i * 30}" y="{hy}" width="{w}" height="{h}" '
                   f'style="fill:#000;fill-opacity:0"/>')
    out.append(f'<rect id="hint-stretch-borders" x="130" y="{hy}" width="1" height="1" style="fill-opacity:0"/>')
    if shadow:
        out.append(shadows(*shadow, oy=hy + 40))
    return out


def shadows(st, sb, sl, sr, oy, alpha=0.32):
    """Soft drop shadow pieces (gradients, no filters), deeper below than above."""
    defs, parts = [], []
    x0, x1, x2 = 0, sl + GAP, sl + W + 2 * GAP
    y0, y1, y2 = oy, oy + st + GAP, oy + st + W + 2 * GAP

    def radial(gid, cx, cy, rad):
        defs.append(f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{rad}" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="#000" stop-opacity="{alpha}"/>'
                    f'<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>')

    def linear(gid, xa, ya, xb, yb):
        defs.append(f'<linearGradient id="{gid}" x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="#000" stop-opacity="{alpha}"/>'
                    f'<stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>')

    def piece(name, x, y, w, h, grad):
        parts.append(f'<rect id="shadow-{name}" x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{grad})"/>')

    radial("s-tl", x0 + sl, y0 + st, max(sl, st)); piece("topleft", x0, y0, sl, st, "s-tl")
    radial("s-tr", x2, y0 + st, max(sr, st)); piece("topright", x2, y0, sr, st, "s-tr")
    radial("s-bl", x0 + sl, y2, max(sl, sb)); piece("bottomleft", x0, y2, sl, sb, "s-bl")
    radial("s-br", x2, y2, max(sr, sb)); piece("bottomright", x2, y2, sr, sb, "s-br")
    linear("s-t", 0, y0 + st, 0, y0); piece("top", x1, y0, W, st, "s-t")
    linear("s-b", 0, y2, 0, y2 + sb); piece("bottom", x1, y2, W, sb, "s-b")
    linear("s-l", x0 + sl, 0, x0, 0); piece("left", x0, y1, sl, W, "s-l")
    linear("s-r", x2, 0, x2 + sr, 0); piece("right", x2, y1, sr, W, "s-r")
    return f'<defs>{"".join(defs)}</defs>{"".join(parts)}'


def svg(pieces):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><defs>{STYLE}</defs>'
            f'{"".join(pieces)}</svg>\n')


FRAMES = {
    # the floating dock: a bolted plate
    "widgets/panel-background.svg": frame(12, 0.90, 0.10, bolts=True, margins=(6, 6, 10, 10),
                                         shadow=(10, 22, 16, 16)),
    # Kickoff, tray popups, menus
    "dialogs/background.svg": frame(10, 0.96, 0.10, bolts=True, margins=(12, 12, 12, 12), shadow=(14, 28, 22, 22)),
    "widgets/tooltip.svg": frame(8, 0.97, 0.10, margins=(8, 8, 10, 10), shadow=(8, 16, 12, 12)),
    # desktop widgets
    "widgets/background.svg": frame(10, 0.86, 0.10, bolts=True, margins=(12, 12, 12, 12), shadow=(10, 20, 16, 16)),
}

METADATA = {
    "KPlugin": {
        "Authors": [{"Name": "DeckOS"}],
        "Category": "",
        "Description": "DeckOS: slate plates with a 1px edge and screw heads, following your colour scheme",
        "Id": "deckos",
        "License": "MIT",
        "Name": "DeckOS",
        "Version": "1.0",
    },
    "X-Plasma-API-Minimum-Version": "6.0",
}

PLASMARC = """[ContrastEffect]
enabled=true
contrast=0.3
intensity=1.4
saturation=1.6

[BlurBehindEffect]
enabled=true

[AdaptiveTransparency]
enabled=true
"""


def write():
    for rel, pieces in FRAMES.items():
        f = OUT / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(svg(pieces), newline="\n")
    (OUT / "metadata.json").write_text(json.dumps(METADATA, indent=4) + "\n", newline="\n")
    (OUT / "plasmarc").write_text(PLASMARC, newline="\n")
    print(f"{len(FRAMES)} frames -> {OUT}")


if __name__ == "__main__":
    write()
