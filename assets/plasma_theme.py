"""DecKoOS Plasma style: the panel, popups, tooltips and widget backgrounds as notched plates: the wordmark's cut
corner at the top right and bottom left, and the accent lighting the other two corners' edges.

Writes a Plasma desktop theme (pkg/deckos-settings/.../plasma/desktoptheme/deckos). Each frame is
a 9-slice SVG with Plasma's element names (topleft, top, ..., center, hint-*-margin, shadow-*).
Colours come from Plasma's colour-scheme classes, so the style follows whatever colour scheme is
active (DecKoOS, TMpikes...). Anything not drawn here falls back to Breeze. Run after changes:
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


def notch_corner(name, ox, oy, r, fill, border, lit):
    """A corner piece r x r of a notched plate: topright and bottomleft are cut on the diagonal, the other two are
    square with their edges lit in the accent (ColorScheme-Highlight) at `lit`."""
    fx, fy = name in ("topright", "bottomright"), name in ("bottomleft", "bottomright")

    def p(x, y):
        return f"{ox + (r - x if fx else x):g},{oy + (r - y if fy else y):g}"

    bg, fg, hi = "ColorScheme-Background", "ColorScheme-Text", "ColorScheme-Highlight"
    if name in ("topright", "bottomleft"):  # the cut: a diagonal from (0, r) to (r, 0) in the piece's own frame
        d = 1.42
        body = (f'<path d="M{p(r, d)} L{p(r, r)} L{p(d, r)} Z" class="{bg}" style="fill:currentColor;fill-opacity:{fill}"/>'
                f'<path d="M{p(0, r)} L{p(r, 0)} L{p(r, d)} L{p(d, r)} Z" class="{fg}" '
                f'style="fill:currentColor;fill-opacity:{border}"/>')
    else:
        body = (f'<path d="M{p(1, 1)} L{p(r, 1)} L{p(r, r)} L{p(1, r)} Z" class="{bg}" '
                f'style="fill:currentColor;fill-opacity:{fill}"/>'
                f'<path d="M{p(0, 0)} L{p(r, 0)} L{p(r, 1)} L{p(1, 1)} L{p(1, r)} L{p(0, r)} Z" class="{hi}" '
                f'style="fill:currentColor;fill-opacity:{lit}"/>')
    return f'<g id="{name}">{body}</g>'


def frame(r, fill, border, bolts=False, margins=None, shadow=None, notch=False, lit=0.85):
    """All pieces of one frame. margins: content insets (t, b, l, r); shadow: sizes (t, b, l, r); notch: the
    DecKoOS cut corners instead of round ones (bolts don't apply)."""
    m = margins or (r, r, r, r)
    a, b, c = 0, r + GAP, r + W + 2 * GAP  # columns / rows of the 3x3 grid
    if notch:
        out = [notch_corner(n, x, y, r, fill, border, lit) for n, x, y in
               (("topleft", a, a), ("topright", c, a), ("bottomleft", a, c), ("bottomright", c, c))]
    else:
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
    # the floating dock
    "widgets/panel-background.svg": frame(14, 0.90, 0.12, margins=(6, 6, 12, 12), shadow=(10, 22, 16, 16),
                                         notch=True),
    # The same dock, see-through: Plasma uses translucent/ while nothing is maximised against the panel (adaptive
    # opacity) or always (translucent). Then DecKoOS's widgets draw their own notched islands (start, apps, tray);
    # a maximised window brings the plate above back
    "translucent/widgets/panel-background.svg": frame(14, 0.0, 0.0, margins=(6, 6, 12, 12), notch=True, lit=0.0),
    # the Start menu, Quick Settings, tray popups, menus
    "dialogs/background.svg": frame(16, 0.95, 0.12, margins=(12, 12, 12, 12), shadow=(14, 28, 22, 22), notch=True),
    "widgets/tooltip.svg": frame(8, 0.97, 0.12, margins=(8, 8, 10, 10), shadow=(8, 16, 12, 12), notch=True, lit=0.6),
    # desktop widgets
    "widgets/background.svg": frame(14, 0.84, 0.12, margins=(12, 12, 12, 12), shadow=(10, 20, 16, 16), notch=True),
}

METADATA = {
    "KPlugin": {
        "Authors": [{"Name": "DecKoOS"}],
        "Category": "",
        "Description": "DecKoOS: notched plates with accent-lit edges, following your colour scheme and accent",
        "Id": "deckos",
        "License": "MIT",
        "Name": "DecKoOS",
        "Version": "1.0",
    },
    "X-Plasma-API-Minimum-Version": "6.0",
}

# No blur or contrast behind panels and popups: the dock's islands float on a see-through panel, and KWin's blur
# would frost the whole strip behind them; the popups are 95% solid, so they don't miss it
PLASMARC = """[ContrastEffect]
enabled=false

[BlurBehindEffect]
enabled=false

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
