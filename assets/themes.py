"""DecKoOS theme packs: colour schemes, wallpapers, icon colours, global themes and desktop layouts.

Every theme is the DecKoOS look in another palette: its own colour scheme (DeckOS.colors with the
palette swapped in), accent, folder colour and wallpapers, plus four wallpaper designs in every
palette. Layouts are Plasma layout templates DecKoOS Hub applies (deckos layout set NAME).
Output is committed into pkg/deckos-settings; the PKGBUILD renders the PNGs and the icon variants.
    python assets/themes.py
"""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "pkg/deckos-settings/rootfs/usr/share"
W, H = 3840, 2160

# DeckOS.colors' own values, in the roles every palette fills in.
BASE = {
    "bg": (15, 17, 21), "surface": (23, 26, 33), "raised": (27, 30, 38), "hover": (34, 38, 47),
    "border": (42, 47, 59), "accent": (76, 141, 255), "accent_light": (106, 162, 255),
    "accent_dark": (58, 112, 214), "partner": (155, 123, 255), "tint_a": (220, 230, 255),
    "tint_b": (230, 220, 255), "text": (232, 234, 240), "subtext": (140, 148, 166), "muted": (90, 97, 114),
}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def css(c, alpha=None):
    return f"rgb({c[0]},{c[1]},{c[2]})" if alpha is None else f"rgba({c[0]},{c[1]},{c[2]},{alpha})"


def palette(bg, accent, partner, light=False):
    """A full role set from a background, an accent and its gradient partner."""
    bg, accent, partner = hexrgb(bg), hexrgb(accent), hexrgb(partner)
    white, black = (255, 255, 255), (0, 0, 0)
    if light:
        text, subtext, muted = (26, 29, 36), (88, 96, 112), (140, 148, 166)
        step = black
    else:
        text, subtext, muted = BASE["text"], BASE["subtext"], BASE["muted"]
        step = white
    return {"bg": bg, "surface": mix(bg, step, 0.04 if light else 0.035), "raised": mix(bg, step, 0.07 if light else 0.055),
            "hover": mix(bg, step, 0.10 if light else 0.09), "border": mix(bg, step, 0.16 if light else 0.14),
            "accent": accent, "accent_light": mix(accent, white, 0.22), "accent_dark": mix(accent, black, 0.2),
            "partner": partner, "tint_a": mix(accent, white, 0.82), "tint_b": mix(partner, white, 0.82),
            "text": text, "subtext": subtext, "muted": muted, "light": light}


# id, name, description, palette, folder colours (main, back tab, symbol), Plasma style
THEMES = [
    ("midnight", "Midnight Violet", "Ink-black with violet and magenta",
     palette("#0E0C16", "#8A5CFF", "#E05CFF"), ("#8a5cff", "#6a3fe0", "#25164d"), "deckos"),
    ("ember", "Ember", "Warm carbon with racing orange",
     palette("#120F0D", "#FF7A2F", "#FFB224"), ("#ff7a2f", "#e0561c", "#4d2410"), "deckos"),
    ("aurora", "Aurora", "Deep teal with green and cyan",
     palette("#0B1312", "#2AD4A8", "#3EC6FF"), ("#2ad4a8", "#1aa886", "#0e3d33"), "deckos"),
    ("crimson", "Crimson", "Dark garnet with red and rose",
     palette("#130C0E", "#FF4D5E", "#FF7AB6"), ("#ff4d5e", "#d63447", "#4d1219"), "deckos"),
    ("graphite", "Graphite", "Neutral greys, a quiet silver accent",
     palette("#111214", "#AAB3C2", "#D7DCE5"), ("#8e98a8", "#6f7888", "#23272e"), "deckos"),
    ("paper", "Paper", "A light theme: soft white with the DecKoOS blue",
     palette("#F4F5F8", "#3D6FE0", "#7A5CFF", light=True), ("#3d6fe0", "#2f56b8", "#dfe7ff"), "default"),
]
# The DecKoOS theme itself, for its extra wallpaper designs (its colour scheme and icons already exist).
DECKOS = ("deckos", "DecKoOS", "", {**BASE, "light": False}, None, "deckos")
MOTIFS = ["orbit", "streaks", "plates", "waves"]
MOTIF_NAMES = {"orbit": "Orbit", "streaks": "Streaks", "plates": "Plates", "waves": "Waves"}


# ------------------------------------------------------------------ colour schemes

def color_scheme(pal, name):
    text = (ROOT / "color-schemes/DeckOS.colors").read_text()
    for role, rgb in BASE.items():
        text = text.replace(",".join(map(str, rgb)), "@" + role + "@")
    for role in BASE:
        text = text.replace("@" + role + "@", ",".join(map(str, pal[role])))
    lines = []
    for line in text.splitlines():
        if line.startswith("Name="):
            line = f"Name={name}"
        elif line.startswith("ColorScheme="):
            line = f"ColorScheme={name.replace(' ', '')}"
        lines.append(line)
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ wallpapers

def svg(body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f"<defs>{defs}</defs>{body}</svg>\n")


def backdrop(pal, seed):
    """Background gradient and two soft glows: what every design sits on."""
    rng = random.Random(seed)
    top, bottom = (mix(pal["bg"], (255, 255, 255), 0.03), mix(pal["bg"], (0, 0, 0), 0.25)) if not pal["light"] \
        else (mix(pal["bg"], (255, 255, 255), 0.6), mix(pal["bg"], pal["accent"], 0.06))
    ga, gb = (rng.uniform(0.62, 0.85), rng.uniform(0.15, 0.35)), (rng.uniform(0.08, 0.3), rng.uniform(0.7, 0.95))
    strength = (0.22, 0.16) if not pal["light"] else (0.14, 0.10)
    defs = (f'<linearGradient id="bg" x1="0" y1="0" x2="0.3" y2="1"><stop offset="0" stop-color="{css(top)}"/>'
            f'<stop offset="1" stop-color="{css(bottom)}"/></linearGradient>'
            f'<radialGradient id="ga" cx="{ga[0]}" cy="{ga[1]}" r="0.55"><stop offset="0" stop-color="{css(pal["accent"])}" '
            f'stop-opacity="{strength[0]}"/><stop offset="1" stop-color="{css(pal["accent"])}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="gb" cx="{gb[0]}" cy="{gb[1]}" r="0.5"><stop offset="0" stop-color="{css(pal["partner"])}" '
            f'stop-opacity="{strength[1]}"/><stop offset="1" stop-color="{css(pal["partner"])}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{css(pal["accent"])}"/>'
            f'<stop offset="1" stop-color="{css(pal["partner"])}"/></linearGradient>')
    body = (f'<rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#ga)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#gb)"/>')
    return defs, body


def stars(pal, rng, n=260):
    if pal["light"]:
        return ""
    out = []
    for _ in range(n):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.choice((1.2, 1.6, 2.2, 3.0))
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#fff" opacity="{rng.uniform(0.15, 0.7):.2f}"/>')
    return "".join(out)


def orbit(pal, seed):
    defs, body = backdrop(pal, seed)
    rng = random.Random(seed)
    cx, cy = W * 0.7, H * 0.46
    ink = 0.55 if not pal["light"] else 0.35
    rings = []
    for i, r in enumerate((360, 520, 700, 900, 1120)):
        width = 3 if i in (0, 3) else 1.6
        rings.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#line)" stroke-width="{width}" '
                     f'opacity="{ink * (1 - i * 0.14):.2f}"/>')
    ticks = []
    for i in range(72):  # a gauge arc of ticks on the outer ring
        a = math.radians(200 + i * 2.2)
        r1, r2 = 1180, 1180 + (34 if i % 6 == 0 else 18)
        ticks.append(f'<line x1="{cx + r1 * math.cos(a):.0f}" y1="{cy + r1 * math.sin(a):.0f}" '
                     f'x2="{cx + r2 * math.cos(a):.0f}" y2="{cy + r2 * math.sin(a):.0f}" stroke="{css(pal["accent"])}" '
                     f'stroke-width="3" opacity="{ink * 0.8:.2f}"/>')
    return svg(body + stars(pal, rng) + "".join(rings) + "".join(ticks), defs)


def streaks(pal, seed):
    defs, body = backdrop(pal, seed)
    rng = random.Random(seed)
    lines = []
    for i in range(26):
        y0 = rng.uniform(H * 0.45, H * 1.1)
        y1 = y0 - rng.uniform(H * 0.5, H * 0.9)
        c1 = (rng.uniform(W * 0.25, W * 0.45), y0 - rng.uniform(0, 300))
        c2 = (rng.uniform(W * 0.55, W * 0.8), y1 + rng.uniform(0, 400))
        width = rng.choice((1.5, 2, 3, 5))
        op = rng.uniform(0.18, 0.6) * (0.7 if pal["light"] else 1)
        lines.append(f'<path d="M-100,{y0:.0f} C{c1[0]:.0f},{c1[1]:.0f} {c2[0]:.0f},{c2[1]:.0f} {W + 100},{y1:.0f}" '
                     f'fill="none" stroke="url(#line)" stroke-width="{width}" opacity="{op:.2f}" stroke-linecap="round"/>')
    return svg(body + stars(pal, rng, 180) + "".join(lines), defs)


def plates(pal, seed):
    defs, body = backdrop(pal, seed)
    rng = random.Random(seed)
    size, gap = 300, 26
    # colour and opacity apart, not rgba(): Qt's SVG renderer (the Hub's previews) doesn't read rgba
    edge = f'stroke="{css(pal["text"])}" stroke-opacity="{0.06 if not pal["light"] else 0.09}"'
    screw = f'fill="{css(pal["text"])}" fill-opacity="{0.16 if not pal["light"] else 0.18}"'
    cells = []
    for gx in range(-1, W // (size + gap) + 2):
        for gy in range(-1, H // (size + gap) + 2):
            x, y = gx * (size + gap) + (gy % 2) * (size // 2), gy * (size + gap)
            lit = rng.random() < 0.06
            fill = (f'fill="{css(pal["accent"])}" fill-opacity="{0.10 if not pal["light"] else 0.07}"' if lit
                    else 'fill="none"')
            cells.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="22" {fill} {edge} stroke-width="2"/>')
            for sx, sy in ((x + 26, y + 26), (x + size - 26, y + 26), (x + 26, y + size - 26), (x + size - 26, y + size - 26)):
                cells.append(f'<circle cx="{sx}" cy="{sy}" r="6" {screw}/>')
    vignette = ('<radialGradient id="vig" cx="0.5" cy="0.5" r="0.75"><stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
                f'<stop offset="1" stop-color="#000" stop-opacity="{0.55 if not pal["light"] else 0.08}"/></radialGradient>')
    return svg(body + "".join(cells) + f'<rect width="{W}" height="{H}" fill="url(#vig)"/>', defs + vignette)


def waves(pal, seed):
    defs, body = backdrop(pal, seed)
    rng = random.Random(seed)
    bands = []
    for i in range(6):
        base = H * (0.55 + i * 0.08)
        amp = rng.uniform(70, 160)
        freq = rng.uniform(1.1, 2.0)
        phase = rng.uniform(0, math.pi * 2)
        pts = [f"{x:.0f},{base + amp * math.sin(x / W * math.pi * 2 * freq + phase):.0f}" for x in range(0, W + 1, 120)]
        color = mix(pal["accent"], pal["partner"], i / 5)
        op = (0.10 + i * 0.05) if not pal["light"] else (0.06 + i * 0.03)
        bands.append(f'<path d="M0,{H} L{" L".join(pts)} L{W},{H} Z" fill="{css(color)}" opacity="{op:.2f}"/>')
    return svg(body + stars(pal, rng, 120) + "".join(bands), defs)


DESIGNS = {"orbit": orbit, "streaks": streaks, "plates": plates, "waves": waves}


def wallpaper_name(theme_name, motif):
    return f"DecKoOS {theme_name} {MOTIF_NAMES[motif]}" if theme_name != "DecKoOS" else f"DecKoOS {MOTIF_NAMES[motif]}"


def wallpaper_id(theme_id, motif):
    return f"DeckOS-{theme_id.capitalize()}-{MOTIF_NAMES[motif]}" if theme_id != "deckos" else f"DeckOS-{MOTIF_NAMES[motif]}"


# ------------------------------------------------------------------ global themes

def look_and_feel(tid, name, desc, pal, style):
    meta = {"KPackageStructure": "Plasma/LookAndFeel",
            "KPlugin": {"Authors": [{"Name": "DecKoOS"}], "Category": "", "Description": desc, "Id": f"org.deckos.{tid}",
                        "License": "MIT", "Name": f"DecKoOS {name}" if not name.startswith("DecKoOS") else name,
                        "Version": "1.0"},
            "X-Plasma-APIVersion": "2"}
    a = pal["accent"]
    defaults = (f"[kdeglobals][KDE]\nwidgetStyle=Breeze\n\n[kdeglobals][General]\nColorScheme=DeckOS{name.split()[0]}\n"
                f"AccentColor={a[0]},{a[1]},{a[2]}\n\n[kdeglobals][Icons]\nTheme=DeckOS-{tid.capitalize()}\n\n"
                f"[plasmarc][Theme]\nname={style}\n\n[kcminputrc][Mouse]\ncursorTheme=DeckOS-cursors\n\n"
                f"[kwinrc][org.kde.kdecoration2]\nlibrary=org.kde.breeze\ntheme=Breeze\n\n[KSplash]\nTheme=org.deckos.desktop\n\n"
                f"[Wallpaper]\nImage={wallpaper_id(tid, 'orbit')}\n")
    return json.dumps(meta, indent=4) + "\n", defaults


# ------------------------------------------------------------------ desktop layouts

TRAY_HIDDEN = ["org.kde.plasma.networkmanagement", "org.kde.plasma.volume", "org.kde.plasma.bluetooth",
               "org.kde.plasma.brightness", "org.kde.plasma.battery", "org.kde.plasma.mediacontroller",
               "org.kde.plasma.vault", "org.kde.kdeconnect", "org.kde.plasma.clipboard", "org.kde.kupapplet",
               "org.kde.plasma.weather", "org.kde.plasma.printmanager", "org.kde.plasma.dwellclicker",
               "org.kde.plasma.manage-inputmethod", "org.kde.kscreen", "org.kde.plasma.keyboardindicator"]
LAUNCHERS = ["preferred://filemanager", "applications:org.deckos.terminal.desktop", "preferred://browser",
             "applications:steam.desktop", "applications:deckos-hub.desktop"]

JS_HELPERS = f"""// Shared by the DecKoOS layouts (assets/themes.py writes them).
function deckosMenu(panel) {{
    var menu = panel.addWidget("org.deckos.menu");
    menu.currentConfigGroup = ["General"];
    menu.writeConfig("icon", "deckos");
}}
function deckosTasks(panel, labels) {{
    var tasks = panel.addWidget("org.deckos.taskbar");
    tasks.currentConfigGroup = ["General"];
    tasks.writeConfig("launchers", {json.dumps(LAUNCHERS)});
    tasks.writeConfig("showLabels", labels ? "true" : "false");
}}
function deckosTray(panel) {{
    panel.addWidget("org.deckos.quicksettings");
    var tray = panel.addWidget("org.kde.plasma.systemtray");
    tray.currentConfigGroup = ["General"];
    tray.writeConfig("hiddenItems", {json.dumps(TRAY_HIDDEN)});
}}
function deckosClock(panel, oneLine) {{
    var clock = panel.addWidget("org.kde.plasma.digitalclock");
    clock.currentConfigGroup = ["Appearance"];
    clock.writeConfig("showDate", "true");
    clock.writeConfig("dateFormat", oneLine ? "shortDate" : "isoDate");
}}
"""

LAYOUTS = [
    ("dock", "Dock", "One floating dock in the middle: apps, Quick Settings, the clock (the DecKoOS default)",
     """var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.6 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";
deckosMenu(panel);
deckosTasks(panel, false);
panel.addWidget("org.kde.plasma.marginsseparator");
deckosTray(panel);
deckosClock(panel, false);
"""),
    ("classic", "Classic", "A full-width taskbar along the bottom with window names, like Windows",
     """var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.4 / 2);
panel.floating = false;
panel.lengthMode = "fill";
deckosMenu(panel);
deckosTasks(panel, true);
deckosTray(panel);
deckosClock(panel, false);
"""),
    ("topbar", "Top bar + dock", "A slim bar on top (menu, clock, Quick Settings) and an app dock below, like macOS",
     """var top = new Panel;
top.location = "top";
top.height = 2 * Math.floor(gridUnit * 1.7 / 2);
top.floating = false;
top.lengthMode = "fill";
deckosMenu(top);
top.addWidget("org.kde.plasma.panelspacer");
deckosClock(top, true);
top.addWidget("org.kde.plasma.panelspacer");
deckosTray(top);
var dock = new Panel;
dock.location = "bottom";
dock.height = 2 * Math.floor(gridUnit * 3 / 2);
dock.floating = true;
dock.lengthMode = "fit";
dock.alignment = "center";
deckosTasks(dock, false);
"""),
    ("minimal", "Minimal", "The dock hides until you move the mouse to the bottom edge: all screen, no clutter",
     """var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.6 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";
panel.hiding = "autohide";
deckosMenu(panel);
deckosTasks(panel, false);
deckosTray(panel);
deckosClock(panel, false);
"""),
    ("big", "Big", "Large icons and a tall dock: easy from the couch, with a controller or a touchscreen",
     """var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 4.4 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";
deckosMenu(panel);
deckosTasks(panel, false);
deckosTray(panel);
deckosClock(panel, false);
"""),
]


def layout_preview(key):
    """A small sketch of the layout: screen, panels, app dots."""
    w, h = 320, 180
    acc, panel = "#4C8DFF", "#262B36"
    out = [f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="10" fill="#0F1115" stroke="#262B36" stroke-width="2"/>',
           f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="10" fill="url(#g)" opacity=".35"/>']

    def dock(y, width, height, dots, float_=True, hidden=False):
        x = (w - width) / 2
        op = 0.35 if hidden else 1
        out.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{6 if float_ else 0}" fill="{panel}" opacity="{op}"/>')
        for i in range(dots):
            cx = x + 12 + i * (width - 24) / max(1, dots - 1)
            out.append(f'<circle cx="{cx:.0f}" cy="{y + height / 2}" r="{height * 0.26:.1f}" fill="{acc if i == 0 else "#8C94A6"}" opacity="{op}"/>')
    if key == "dock":
        dock(h - 30, 150, 20, 7)
    elif key == "classic":
        out.append(f'<rect x="1" y="{h - 24}" width="{w - 2}" height="22" fill="{panel}"/>')
        for i in range(4):
            out.append(f'<rect x="{30 + i * 52}" y="{h - 19}" width="44" height="12" rx="3" fill="#8C94A6" opacity="{0.9 if i == 0 else 0.45}"/>')
        out.append(f'<circle cx="14" cy="{h - 13}" r="6" fill="{acc}"/>')
    elif key == "topbar":
        out.append(f'<rect x="1" y="1" width="{w - 2}" height="14" fill="{panel}"/><circle cx="12" cy="8" r="4" fill="{acc}"/>'
                   f'<rect x="{w / 2 - 18}" y="5" width="36" height="6" rx="2" fill="#8C94A6"/>')
        dock(h - 30, 130, 20, 6)
    elif key == "minimal":
        dock(h - 30, 150, 20, 7, hidden=True)
        out.append(f'<text x="{w / 2}" y="{h - 40}" text-anchor="middle" font-family="Inter" font-size="11" fill="#5A6172">hidden until needed</text>')
    elif key == "big":
        dock(h - 44, 190, 34, 6)
    defs = '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4C8DFF"/><stop offset="1" stop-color="#7A5CFF"/></linearGradient>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs>{defs}</defs>{"".join(out)}</svg>\n'


# ------------------------------------------------------------------ write it all

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, newline="\n")


def main():
    walls = 0
    variants = []
    for seed_base, (tid, name, desc, pal, folders, style) in enumerate([DECKOS] + THEMES):
        if tid != "deckos":
            write(ROOT / f"color-schemes/DeckOS{name.split()[0]}.colors", color_scheme(pal, f"DecKoOS {name.split()[0]}"))
            meta, defaults = look_and_feel(tid, name, desc, pal, style)
            write(ROOT / f"plasma/look-and-feel/org.deckos.{tid}/metadata.json", meta)
            write(ROOT / f"plasma/look-and-feel/org.deckos.{tid}/contents/defaults", defaults)
            variants.append(f"DeckOS-{tid.capitalize()}\t{name}\t" + "\t".join(folders))
        for i, motif in enumerate(MOTIFS):
            wid = wallpaper_id(tid, motif)
            write(ROOT / f"deckos/wallpapers/{wid}.svg", DESIGNS[motif](pal, seed_base * 10 + i))
            write(ROOT / f"wallpapers/{wid}/metadata.json", json.dumps(
                {"KPlugin": {"Authors": [{"Name": "DecKoOS"}], "Id": wid, "License": "MIT",
                             "Name": wallpaper_name(name.split()[0] if tid != "deckos" else "DecKoOS", motif)}}, indent=4) + "\n")
            walls += 1
    # main, back tab, symbol: what the PKGBUILD recolours Papirus' folder blue to, per icon theme
    write(ROOT / "deckos/themes/icon-variants.tsv", "# id\tname\tfolder\tback\tsymbol\n" + "\n".join(variants) + "\n")
    for key, name, desc, js in LAYOUTS:
        base = ROOT / f"plasma/layout-templates/org.deckos.layout.{key}"
        write(base / "metadata.json", json.dumps(
            {"KPackageStructure": "Plasma/LayoutTemplate",
             "KPlugin": {"Authors": [{"Name": "DecKoOS"}], "Description": desc, "Id": f"org.deckos.layout.{key}",
                         "License": "MIT", "Name": f"DecKoOS: {name}"},
             "X-Plasma-ContainmentCategories": ["panel"], "X-Plasma-Shell": "org.kde.plasma.desktop"}, indent=4) + "\n")
        write(base / "contents/layout.js", JS_HELPERS + "\n" + js)
        write(ROOT / f"deckos/layouts/{key}.svg", layout_preview(key))
    print(f"{len(THEMES)} themes, {walls} wallpapers, {len(LAYOUTS)} layouts -> {ROOT}")


if __name__ == "__main__":
    main()
