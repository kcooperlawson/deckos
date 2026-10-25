"""Generates DeckOS Pointers, the DeckOS mouse cursor theme: a slate arrow with a white rim (visible on light
and dark alike), the DeckOS blue where a pointer means "something happens", and the thumbstick ring for busy.

Two forms from the same drawings, both committed:
- cursors_scalable/NAME/*.svg + metadata.json: Plasma 6 draws these at any size and scale, sharp.
- cursors/NAME: classic Xcursor files (24-64 px) for X11 apps and anything that doesn't read SVG cursors.
Every standard name (CSS, X11, and the hashes Qt and GTK ask for) links to one of the drawn shapes.

    python assets/cursors.py           (needs PySide6 for the Xcursor pixels)
"""
import math
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "pkg/deckos-settings/rootfs/usr/share/icons/DeckOS-cursors"
NOMINAL = 24
SIZES = (24, 32, 48, 64)  # Plasma 6 draws the SVGs at any size; these are the fallback
DARK, RIM, ACCENT, ACCENT_B, DANGER = "#161A22", "#FFFFFF", "#4C8DFF", "#7A5CFF", "#FF5A5F"

# Every shape is drawn on a 32-unit canvas (room for the shadow) and shown at 24 nominal: hotspots
# below are in canvas units and scaled when written.
SCALE = NOMINAL / 32


def svg(body, extra_defs=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
            '<defs><filter id="sh" x="-30%" y="-30%" width="160%" height="160%">'
            '<feDropShadow dx="0" dy="1.1" stdDeviation="1.1" flood-color="#000" flood-opacity=".45"/></filter>'
            f'<linearGradient id="ac" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}"/>'
            f'<stop offset="1" stop-color="{ACCENT_B}"/></linearGradient>{extra_defs}</defs>'
            f'<g filter="url(#sh)">{body}</g></svg>\n')


def outlined(d, fill=DARK, rim=RIM, width=1.6):
    """A shape with the white rim outside (painted under) and the fill inside."""
    return (f'<path d="{d}" fill="none" stroke="{rim}" stroke-width="{width * 2}" stroke-linejoin="round" '
            f'stroke-linecap="round"/><path d="{d}" fill="{fill}"/>')


ARROW = "M6 4.5v19.2l4.7-4.6 3 7.2 3.3-1.4-3-7h6.6z"


def arrow(badge=""):
    return outlined(ARROW) + badge


def badge_circle(cx, cy, inner, fill="url(#ac)"):
    return (f'<circle cx="{cx}" cy="{cy}" r="5.4" fill="{RIM}"/><circle cx="{cx}" cy="{cy}" r="4.3" fill="{fill}"/>'
            f'{inner}')


def plus(cx, cy, s=2.2, color=RIM):
    return f'<path d="M{cx - s} {cy}h{2 * s}M{cx} {cy - s}v{2 * s}" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'


HAND = ("M12.2 5.6c0-1.1.8-1.9 1.8-1.9s1.8.8 1.8 1.9v6.1l.6-.1c.9-.2 1.8.4 2 1.3l.1.4.6-.1c.9-.2 1.8.4 2 1.3"
        "l.1.5.4-.1c.9-.1 1.7.5 1.9 1.4.4 2.4.3 4.4-.6 6.4l-1.1 2.4c-.6 1.2-1.8 2-3.1 2h-4.6c-1.1 0-2.2-.6-2.8-1.5"
        "l-4.6-6.7c-.6-.9-.4-2.1.5-2.7.8-.6 2-.4 2.6.4l1.4 1.8z")
GRAB = ("M9.2 13.4c0-1 .8-1.7 1.7-1.7s1.7.7 1.7 1.7v-1.6c0-1 .8-1.7 1.7-1.7s1.7.7 1.7 1.7v.4c0-1 .8-1.7 1.7-1.7"
        "s1.7.7 1.7 1.7v.9c0-1 .8-1.7 1.7-1.7s1.7.7 1.7 1.7v5.6c0 3.9-2.6 6.9-6.4 6.9h-1.6c-2.6 0-4.1-1.3-5.4-3.4"
        "l-2.7-4.4c-.5-.9-.3-2 .6-2.5.9-.5 2-.3 2.5.6l.6 1z")


def double_arrow(angle):
    d = ("M16 4l5 5.5h-3.2v13h3.2L16 28l-5-5.5h3.2v-13H11z")
    return f'<g transform="rotate({angle} 16 16)">{outlined(d)}</g>'


def ring(frame, frames):
    """The thumbstick ring: a gate ring with the accent arc turning around it (busy)."""
    a = 2 * math.pi * frame / frames
    r = 8.5
    start = (16 + r * math.cos(a), 16 + r * math.sin(a))
    end = (16 + r * math.cos(a + 1.9), 16 + r * math.sin(a + 1.9))
    return (f'<circle cx="16" cy="16" r="{r}" fill="none" stroke="{RIM}" stroke-width="6.2"/>'
            f'<circle cx="16" cy="16" r="{r}" fill="none" stroke="{DARK}" stroke-width="3.6"/>'
            f'<path d="M{start[0]:.2f} {start[1]:.2f}A{r} {r} 0 0 1 {end[0]:.2f} {end[1]:.2f}" fill="none" '
            f'stroke="url(#ac)" stroke-width="3.6" stroke-linecap="round"/>'
            f'<circle cx="16" cy="16" r="3" fill="{RIM}"/><circle cx="16" cy="16" r="1.8" fill="{DARK}"/>')


def small_ring(frame, frames, cx, cy):
    a = 2 * math.pi * frame / frames
    r = 3.6
    start = (cx + r * math.cos(a), cy + r * math.sin(a))
    end = (cx + r * math.cos(a + 2.1), cy + r * math.sin(a + 2.1))
    return (f'<circle cx="{cx}" cy="{cy}" r="5.6" fill="{RIM}"/><circle cx="{cx}" cy="{cy}" r="4.6" fill="{DARK}"/>'
            f'<path d="M{start[0]:.2f} {start[1]:.2f}A{r} {r} 0 0 1 {end[0]:.2f} {end[1]:.2f}" fill="none" '
            f'stroke="url(#ac)" stroke-width="2" stroke-linecap="round"/>')


# name: (frames: list of svg bodies, hotspot x, y in canvas units, frame delay ms)
def shapes():
    s = {}
    s["default"] = ([arrow()], 6, 4.5)
    s["pointer"] = ([outlined(HAND)], 14, 4)
    s["grab"] = ([outlined(GRAB)], 16, 14)
    s["grabbing"] = ([outlined(GRAB.replace("v-1.6", "v-0.2").replace("v.4", "v.2"))], 16, 15)
    s["text"] = ([f'<path d="M12.5 6h2.2c.9 0 1.3.5 1.3 1.2 0-.7.4-1.2 1.3-1.2h2.2M16 7.2v17.6M12.5 26h2.2c.9 0 1.3-.5 '
                  f'1.3-1.2 0 .7.4 1.2 1.3 1.2h2.2" fill="none" stroke="{RIM}" stroke-width="4" stroke-linecap="round"/>'
                  f'<path d="M12.5 6h2.2c.9 0 1.3.5 1.3 1.2 0-.7.4-1.2 1.3-1.2h2.2M16 7.2v17.6M12.5 26h2.2c.9 0 1.3-.5 '
                  f'1.3-1.2 0 .7.4 1.2 1.3 1.2h2.2" fill="none" stroke="{DARK}" stroke-width="1.7" stroke-linecap="round"/>'],
                 16, 16)
    s["vertical-text"] = ([f'<g transform="rotate(90 16 16)">{s["text"][0][0]}</g>'], 16, 16)
    s["crosshair"] = ([f'<path d="M16 4v9M16 19v9M4 16h9M19 16h9" stroke="{RIM}" stroke-width="4" stroke-linecap="round"/>'
                       f'<path d="M16 4v9M16 19v9M4 16h9M19 16h9" stroke="{DARK}" stroke-width="1.7" stroke-linecap="round"/>'
                       f'<circle cx="16" cy="16" r="1.6" fill="{ACCENT}" stroke="{RIM}"/>'], 16, 16)
    s["cell"] = ([f'<path d="M13 5h6v8h8v6h-8v8h-6v-8H5v-6h8z" fill="{DARK}" stroke="{RIM}" stroke-width="1.6" '
                  f'stroke-linejoin="round"/>'], 16, 16)
    s["move"] = ([outlined("M16 3l4.6 4.8h-3v6.6h6.6v-3L29 16l-4.8 4.6v-3h-6.6v6.6h3L16 29l-4.6-4.8h3v-6.6H7.8v3L3 16"
                           "l4.8-4.6v3h6.6V7.8h-3z")], 16, 16)
    s["not-allowed"] = ([f'<circle cx="16" cy="16" r="10" fill="{RIM}"/><circle cx="16" cy="16" r="8.4" fill="{DANGER}"/>'
                         f'<circle cx="16" cy="16" r="5.6" fill="{DARK}"/><path d="M10.3 21.7l11.4-11.4" '
                         f'stroke="{DANGER}" stroke-width="2.8"/>'], 16, 16)
    s["help"] = ([arrow(badge_circle(22, 23, '<path d="M20.6 21.6a1.5 1.5 0 1 1 2 1.4c-.4.2-.6.5-.6.9v.3" fill="none" '
                                       f'stroke="{RIM}" stroke-width="1.4" stroke-linecap="round"/>'
                                       f'<circle cx="22" cy="25.9" r=".8" fill="{RIM}"/>'))], 6, 4.5)
    s["copy"] = ([arrow(badge_circle(22, 23, plus(22, 23)))], 6, 4.5)
    s["alias"] = ([arrow(badge_circle(22, 23, f'<path d="M20 24.5l4-4M21.2 20.4h2.8v2.8" fill="none" stroke="{RIM}" '
                                        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'))], 6, 4.5)
    s["context-menu"] = ([arrow(f'<rect x="17.5" y="17.5" width="10" height="10" rx="2" fill="{RIM}"/>'
                                f'<rect x="18.6" y="18.6" width="7.8" height="7.8" rx="1.3" fill="url(#ac)"/>'
                                f'<path d="M20.5 21h4M20.5 23h4M20.5 25h2.5" stroke="{RIM}" stroke-width="1"/>')], 6, 4.5)
    s["zoom-in"] = ([f'<circle cx="14" cy="14" r="8.5" fill="{RIM}"/><circle cx="14" cy="14" r="7" fill="{DARK}"/>'
                     f'<path d="M20.2 20.2l6 6" stroke="{RIM}" stroke-width="5.2" stroke-linecap="round"/>'
                     f'<path d="M20.2 20.2l6 6" stroke="{DARK}" stroke-width="2.6" stroke-linecap="round"/>'
                     + plus(14, 14, 3)], 14, 14)
    s["zoom-out"] = ([s["zoom-in"][0][0].replace(plus(14, 14, 3), f'<path d="M11 14h6" stroke="{RIM}" stroke-width="1.5" '
                                                                   'stroke-linecap="round"/>')], 14, 14)
    s["ew-resize"] = ([double_arrow(90)], 16, 16)
    s["ns-resize"] = ([double_arrow(0)], 16, 16)
    s["nwse-resize"] = ([double_arrow(-45)], 16, 16)
    s["nesw-resize"] = ([double_arrow(45)], 16, 16)
    s["col-resize"] = ([outlined("M14.4 5h3.2v22h-3.2z") + f'<g transform="translate(0 0)">{double_arrow(90)}</g>'
                        .replace(outlined("M16 4l5 5.5h-3.2v13h3.2L16 28l-5-5.5h3.2v-13H11z"), outlined(
                            "M16 4l5 5.5h-3.2v13h3.2L16 28l-5-5.5h3.2v-13H11z"))], 16, 16)
    s["row-resize"] = ([f'<g transform="rotate(90 16 16)">{s["col-resize"][0][0]}</g>'], 16, 16)
    frames = 10
    s["wait"] = ([ring(i, frames) for i in range(frames)], 16, 16)
    s["progress"] = ([arrow(small_ring(i, frames, 22.5, 23.5)) for i in range(frames)], 6, 4.5)
    return s


# Standard names -> drawn shape. CSS names first, then X11's and the hashes Qt/GTK use.
ALIASES = {
    "default": ["left_ptr", "arrow", "top_left_arrow", "left-arrow", "right_ptr", "draft", "X_cursor",
                "center_ptr", "up-arrow", "down-arrow", "right-arrow"],
    "pointer": ["hand1", "hand2", "pointing_hand", "e29285e634086352946a0e7090d73106",
                "9d800788f1b08800ae810202380a0822", "openhand"],
    "grab": ["fleur_hand", "5aca4d189052212118709018842178c0", "208530c400c041818281048008011002"],
    "grabbing": ["closedhand", "dnd-move", "dnd-none", "fcf21c00b30f7e3f83fe0dfd12e71cff", "move-grab"],
    "text": ["xterm", "ibeam", "text-cursor"],
    "vertical-text": ["vertical-ibeam", "048008013003cff3c00c801001200000"],
    "crosshair": ["cross", "tcross", "cross_reverse", "diamond_cross", "target", "color-picker", "pencil"],
    "cell": ["plus"],
    "move": ["fleur", "all-scroll", "size_all", "4498f0e0c1937ffe01fd06f973665830", "9081237383d90e509aa00f00170e968f"],
    "not-allowed": ["crossed_circle", "forbidden", "no-drop", "dnd-no-drop", "circle", "pirate", "X-cursor",
                    "03b6e0fcb3499374a867c041f52298f0"],
    "help": ["question_arrow", "left_ptr_help", "whats_this", "d9ce0ab605698f320427677b458ad60b",
             "5c6cd98b3f3ebcb1f9c7f1c204630408", "dnd-ask"],
    "copy": ["dnd-copy", "1081e37283d90000800003c07f3ef6bf", "6407b0e94181790501fd1e167b474872",
             "b66166c04f8c3109214a4fbd64a50fc8"],
    "alias": ["link", "dnd-link", "3085a0e285430894940527032f8b26df", "640fb0e74195791501fd1ed57b41487f",
              "a2a266d0498c3104214a47bd64ab0fc8"],
    "context-menu": ["08ffe1cb5fe6fc01f906f1c063814ccf"],
    "zoom-in": ["zoom_in", "f41c0e382c94c0958e07017e42b00462"],
    "zoom-out": ["zoom_out", "f41c0e382c97c0938e07017e42800402"],
    "ew-resize": ["e-resize", "w-resize", "h_double_arrow", "sb_h_double_arrow", "size_hor", "left_side", "right_side",
                  "split_h", "028006030e0e7ebffc7f7070c0600140", "14fef782d02440884392942c11205230"],
    "ns-resize": ["n-resize", "s-resize", "v_double_arrow", "sb_v_double_arrow", "size_ver", "top_side", "bottom_side",
                  "split_v", "00008160000006810000408080010102", "2870a09082c103050810ffdffffe0204",
                  "double_arrow"],
    "nwse-resize": ["nw-resize", "se-resize", "top_left_corner", "bottom_right_corner", "size_fdiag", "bd_double_arrow",
                    "c7088f0f3e6c8088236ef8e1e3e70000", "38c5dff7c7b8962045400281044508d2"],
    "nesw-resize": ["ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner", "size_bdiag", "fd_double_arrow",
                    "fcf1c3c7cd4491d801f1e1c78f100000", "50585d75b494802d0151028115016902"],
    "col-resize": ["sb_h_double_arrow_col", "split-h", "ew-resize-col"],
    "row-resize": ["sb_v_double_arrow_row", "split-v"],
    "wait": ["watch", "clock", "busy"],
    "progress": ["left_ptr_watch", "half-busy", "08e8e1c95fe2fc01f976f1e063a24ccd", "3ecb610c1bf2410f44200f48c40d3599",
                 "00000000000000020006000e7e9ffc3f"],
}
DELAY = 70  # ms per busy frame: one turn in 0.7 s


def render(svg_text, size):
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    canvas = round(size * 32 / NOMINAL)
    img = QImage(canvas, canvas, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(svg_text.encode())).render(p, QRectF(0, 0, canvas, canvas))
    p.end()
    return img


def xcursor(frames, hx, hy):
    """An Xcursor file (the format libXcursor reads): a TOC and one image chunk per size and frame."""
    images = []
    for size in SIZES:
        for i, body in enumerate(frames):
            img = render(body, size)
            w = h = img.width()
            pixels = bytes(img.constBits())[:w * h * 4]  # premultiplied ARGB32, as Xcursor wants (little-endian)
            images.append((size, w, h, round(hx * w / 32), round(hy * h / 32), DELAY if len(frames) > 1 else 0, pixels))
    header = 16
    toc = 12 * len(images)
    out = bytearray(struct.pack("<4sIII", b"Xcur", header, 0x10000, len(images)))
    pos = header + toc
    chunks = bytearray()
    for size, w, h, x, y, delay, pixels in images:
        out += struct.pack("<III", 0xFFFD0002, size, pos)
        chunk = struct.pack("<IIIIIIIII", 36, 0xFFFD0002, size, 1, w, h, x, y, delay) + pixels
        chunks += chunk
        pos += len(chunk)
    return bytes(out + chunks)


def write():
    # The repo is checked out on Windows too: two names differing only in case can't both exist
    names = [n.lower() for n in list(shapes()) + [a for v in ALIASES.values() for a in v]]
    clash = sorted({n for n in names if names.count(n) > 1})
    assert not clash, f"names that clash (ignoring case): {clash}"
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(["x"])  # noqa: F841
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "cursors").mkdir(parents=True)
    scalable = OUT / "cursors_scalable"
    for name, (frames, hx, hy) in shapes().items():
        d = scalable / name
        d.mkdir(parents=True)
        meta = []
        for i, body in enumerate(frames):
            fname = f"{name}.svg" if len(frames) == 1 else f"{name}-{i + 1:02}.svg"
            (d / fname).write_text(svg(body), newline="\n")
            entry = {"filename": fname, "hotspot_x": round(hx * SCALE, 2), "hotspot_y": round(hy * SCALE, 2),
                     "nominal_size": NOMINAL}
            if len(frames) > 1:
                entry["delay"] = DELAY
            meta.append(entry)
        import json
        (d / "metadata.json").write_text(json.dumps(meta, indent=4) + "\n", newline="\n")
        (OUT / "cursors" / name).write_bytes(xcursor([svg(b) for b in frames], hx, hy))
        for alias in ALIASES.get(name, []):
            for base in (OUT / "cursors", scalable):
                link = base / alias
                if not link.exists() and not link.is_symlink():
                    link.symlink_to(name)
    (OUT / "index.theme").write_text("[Icon Theme]\nName=DeckOS Pointers\nComment=The DeckOS mouse pointers\n"
                                     "Inherits=breeze_cursors\n", newline="\n")
    n = len(shapes())
    print(f"{n} pointers ({sum(len(v) for v in ALIASES.values()) + n} names) -> {OUT}")


def sheet(path):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
    app = QGuiApplication.instance() or QGuiApplication(["x"])  # noqa: F841
    items = list(shapes().items())
    cols = 9
    img = QImage(cols * 110 + 20, ((len(items) + cols - 1) // cols) * 120 + 20, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("#0F1115"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    for i, (name, (frames, hx, hy)) in enumerate(items):
        x, y = 20 + (i % cols) * 110, 20 + (i // cols) * 120
        # half on light, half on dark: the rim has to work on both
        p.fillRect(QRectF(x, y, 45, 64), QColor("#E8EAF0"))
        p.drawImage(x + 2, y + 6, render(svg(frames[len(frames) // 3]), 48))
        p.setPen(QColor("#8C94A6"))
        p.setFont(QFont("Inter", 8))
        p.drawText(QRectF(x - 10, y + 72, 100, 30), Qt.AlignHCenter | Qt.TextWordWrap, name)
    p.end()
    img.save(str(path))
    print("->", path)


if __name__ == "__main__":
    write()
    if "--sheet" in sys.argv:
        sheet(HERE / "cursors-preview.png")
