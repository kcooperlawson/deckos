"""DeckOS line icons: the set DeckOS Hub (and anything else DeckOS draws) uses.

24 px grid, 1.75 px round strokes, drawn in #000 so apps can recolor them per state (the Hub
swaps the colour in when it loads one). Same family as the brand: rounded, mechanical, a gear
for System. Run after changing a shape:
    python assets/icons.py
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "pkg/deckos-settings/rootfs/usr/share/deckos/icons"
STROKE = 1.75


def gear(cx=12, cy=12, outer=9, inner=6.9, teeth=8, top=0.42, root=0.62):
    """Gear outline: `teeth` flat-topped teeth; top/root are each tooth's share of its pitch."""
    pts = []
    pitch = 2 * math.pi / teeth
    for i in range(teeth):
        a = i * pitch - math.pi / 2
        for ang, r in ((a - pitch * root / 2, inner), (a - pitch * top / 2, outer),
                       (a + pitch * top / 2, outer), (a + pitch * root / 2, inner)):
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"


def dot(x, y, r=0.9):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="#000" stroke="none"/>'


# name: inner SVG (paths are stroked unless they set their own fill)
ICONS = {
    # navigation
    "home": '<path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"/>',
    "display": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M9 20h6M12 16v4"/>',
    "gaming": ('<path d="M7.2 8h9.6a4 4 0 0 1 3.9 3.1l.9 4.3a2.5 2.5 0 0 1-4.4 2.1L15.6 15H8.4l-1.6 2.5a2.5 2.5 0 0 1'
               '-4.4-2.1l.9-4.3A4 4 0 0 1 7.2 8z"/><path d="M8 10.3v3.4M6.3 12h3.4"/>'
               + dot(15.4, 11) + dot(17.4, 13)),
    "drives": ('<path d="M5.5 13 7.4 5.6A1 1 0 0 1 8.4 5h7.2a1 1 0 0 1 1 .6l1.9 7.4"/>'
               '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M6.5 16.5h5"/>' + dot(17, 16.5)),
    "ai": ('<path d="M11 3.5l1.7 4.6 4.6 1.7-4.6 1.7L11 16.1l-1.7-4.6-4.6-1.7 4.6-1.7z"/>'
           '<path d="M17.5 14.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>'),
    "system": f'<path d="{gear()}"/><circle cx="12" cy="12" r="2.8"/>',
    "appearance": ('<path d="M12 3.2a8.8 8.8 0 1 0 0 17.6c1 0 1.7-.8 1.7-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0'
                   '-.9.8-1.7 1.7-1.7h2a5.4 5.4 0 0 0 5.4-5.4c0-3.6-4-6.4-9.8-6.4z"/>'
                   + dot(7.4, 12.2, 1.1) + dot(9, 8, 1.1) + dot(13.6, 6.9, 1.1) + dot(17, 9.6, 1.1)),
    # status
    "check": '<circle cx="12" cy="12" r="8.5"/><path d="M8.4 12.3l2.4 2.4 4.8-5"/>',
    "alert": '<path d="M10.3 4.9a2 2 0 0 1 3.4 0l7 12.2a2 2 0 0 1-1.7 3H5a2 2 0 0 1-1.7-3z"/><path d="M12 9.5v4"/>'
             + dot(12, 16.6),
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5"/>' + dot(12, 8),
    "shield": '<path d="M12 3.2 19 6v5.4c0 4.3-2.9 8-7 9.4-4.1-1.4-7-5.1-7-9.4V6z"/><path d="M9 12l2.1 2.1L15.2 10"/>',
    "shield-off": '<path d="M12 3.2 19 6v5.4c0 4.3-2.9 8-7 9.4-4.1-1.4-7-5.1-7-9.4V6z"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/>',
    # things
    "update": '<path d="M19.8 12a7.8 7.8 0 1 1-2.3-5.5"/><path d="M19.8 4.2v4.3h-4.3"/><path d="M12 8.5v6.2M9.5 12.4 12 14.9l2.5-2.5"/>',
    "refresh": '<path d="M19.8 12a7.8 7.8 0 1 1-2.3-5.5"/><path d="M19.8 4.2v4.3h-4.3"/>',
    "snapshot": '<path d="M4.2 12a7.8 7.8 0 1 0 2.3-5.5"/><path d="M4.2 4.2v4.3h4.3"/><path d="M12 8v4.2l2.8 1.8"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2"/><path d="M7 9.5l3 2.5-3 2.5M12.5 15h4.5"/>',
    "folder": '<path d="M3.5 7A1.5 1.5 0 0 1 5 5.5h4.2l2 2.2H19A1.5 1.5 0 0 1 20.5 9.2V18a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 18z"/>',
    "play": '<path d="M8 5.6v12.8a.8.8 0 0 0 1.2.7l9.9-6.4a.8.8 0 0 0 0-1.4L9.2 4.9A.8.8 0 0 0 8 5.6z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "pause": '<rect x="6.5" y="5" width="3.5" height="14" rx="1"/><rect x="14" y="5" width="3.5" height="14" rx="1"/>',
    "next": '<path d="M5.5 5.8v12.4a.8.8 0 0 0 1.2.7l9-6.2a.8.8 0 0 0 0-1.4l-9-6.2a.8.8 0 0 0-1.2.7z"/><path d="M18.5 5v14"/>',
    "previous": '<path d="M18.5 5.8v12.4a.8.8 0 0 1-1.2.7l-9-6.2a.8.8 0 0 1 0-1.4l9-6.2a.8.8 0 0 1 1.2.7z"/><path d="M5.5 5v14"/>',
    "package": '<path d="M12 3 20 7.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9M8 5.2l8 4.6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "download": '<path d="M12 4v10.5M7.5 10 12 14.5l4.5-4.5M5 19.5h14"/>',
    "external": '<path d="M14 4h6v6M20 4l-8.5 8.5"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    "switch": '<path d="M4 8.5h14.5M15 5l3.5 3.5L15 12"/><path d="M20 15.5H5.5M9 12l-3.5 3.5L9 19"/>',
    "code": '<path d="M8.5 7.5 4 12l4.5 4.5M15.5 7.5 20 12l-4.5 4.5M13.6 5l-3.2 14"/>',
    "image": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.6"/><path d="M20.5 15.5 15.5 11 6 19"/>',
    "drop": '<path d="M12 3.6s6 6.3 6 10.4a6 6 0 0 1-12 0c0-4.1 6-10.4 6-10.4z"/>',
    "chevron": '<path d="M9.5 6l6 6-6 6"/>',
    "chevron-left": '<path d="M14.5 6l-6 6 6 6"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "power-off": '<path d="M12 3.5v8"/><path d="M7.2 6.2a7.6 7.6 0 1 0 9.6 0"/>',
    "sleep": '<path d="M19.5 14.6A7.8 7.8 0 0 1 9.4 4.5a7.8 7.8 0 1 0 10.1 10.1z"/>',
    "keyboard": ('<rect x="2.5" y="6" width="19" height="12" rx="2"/>'
                 '<path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M6.5 14h.01M17 14h.01M9.5 14h5"/>'),
    "user": '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/>' + dot(12, 15.5),
    "log-out": ('<path d="M13.5 4.5H6.5A1.5 1.5 0 0 0 5 6v12a1.5 1.5 0 0 0 1.5 1.5h7"/>'
                '<path d="M10 12h10M16.5 8.5 20 12l-3.5 3.5"/>'),
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "calculator": ('<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8.5 7h7"/>'
                   + dot(9, 11.5) + dot(12, 11.5) + dot(15, 11.5) + dot(9, 15) + dot(12, 15) + dot(15, 15)
                   + dot(9, 18) + dot(12, 18) + dot(15, 18)),
    # DeckOS Store
    "store": ('<path d="M5 8.5h14l-1.1 10.6a1.6 1.6 0 0 1-1.6 1.4H7.7a1.6 1.6 0 0 1-1.6-1.4z"/>'
              '<path d="M9 8.5V7a3 3 0 0 1 6 0v1.5"/>'),
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    "star": '<path d="M12 3.8l2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z"/>',
    "grid": ('<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/>'
             '<rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>'),
    "music": '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>',
    "globe": ('<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.8 5.4 3.8 8.5s-1.3 5.9-3.8 8.5'
              'c-2.5-2.6-3.8-5.4-3.8-8.5S9.5 6.1 12 3.5z"/>'),
    "doc": ('<path d="M7 3.5h7l4.5 4.5v11a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5z"/>'
            '<path d="M13.5 3.5V8.5h5M8.5 13h7M8.5 16.5h5"/>'),
    "flask": ('<path d="M9.5 3.5h5M10.5 3.5v5.2L5.4 17.6A2 2 0 0 0 7.1 20.5h9.8a2 2 0 0 0 1.7-2.9L13.5 8.7V3.5"/>'
              '<path d="M7.6 14h8.8"/>'),
    "sliders": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    "gauge": ('<path d="M4.5 16.2A8 8 0 1 1 19.5 16.2M12 5.5v1.6M6.4 7.9l1.1 1.1M17.6 7.9l-1.1 1.1"/>'
              '<path d="M12 13.5l3.6-3.8"/>' + dot(12, 13.5, 1.5) + '<path d="M8.5 19.5h7"/>'),
    "trash": ('<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l.9 12.1A1.5 1.5 0 0 0 8.9 20.5h6.2a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/>'
              '<path d="M10 11v5.5M14 11v5.5"/>'),
    # hardware
    "cpu": ('<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10" y="10" width="4" height="4" rx=".5"/>'
            '<path d="M9.5 3.5V7M14.5 3.5V7M9.5 17v3.5M14.5 17v3.5M3.5 9.5H7M3.5 14.5H7M17 9.5h3.5M17 14.5h3.5"/>'),
    "gpu": ('<rect x="2.5" y="6.5" width="19" height="10.5" rx="1.5"/><circle cx="9" cy="11.75" r="2.7"/>'
            '<path d="M15 10.2h3.5M15 13.3h3.5M4.5 17v2.5"/>'),
    "memory": ('<rect x="3" y="6.5" width="18" height="9.5" rx="1.2"/><path d="M7 9.5v3.5M10.3 9.5v3.5M13.7 9.5v3.5'
               'M17 9.5v3.5M6 16v2.5M10 16v2.5M14 16v2.5M18 16v2.5"/>'),
    "temp": '<path d="M10 13.6V5.5a2 2 0 1 1 4 0v8.1a4 4 0 1 1-4 0z"/><path d="M12 9v7.5"/>',
    "power": '<path d="M13.2 3 5.8 13.2h5.6L10.6 21l7.6-10.4h-5.6z"/>',
    # DeckOS Files
    "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "list": '<path d="M9 6.5h11M9 12h11M9 17.5h11"/>' + dot(4.8, 6.5, 1.1) + dot(4.8, 12, 1.1) + dot(4.8, 17.5, 1.1),
    "details": ('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M9.5 9.5v10"/>'
                '<path d="M12.5 13h5M12.5 16.3h3.5"/>'),
    "split": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M12 4.5v15"/>',
    "panel-right": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M14.5 4.5v15M16.8 8.5h1.4M16.8 11.5h1.4"/>',
    "sidebar": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9.5 4.5v15M5.8 8.5h1.4M5.8 11.5h1.4"/>',
    "menu": '<path d="M4.5 7h15M4.5 12h15M4.5 17h15"/>',
    "close": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "copy": ('<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/>'
             '<path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>'),
    "cut": ('<circle cx="6.5" cy="17.5" r="2.7"/><circle cx="17.5" cy="17.5" r="2.7"/>'
            '<path d="M8.4 15.6 17 4M15.6 15.6 7 4"/>'),
    "paste": ('<path d="M9 4.5H7A1.5 1.5 0 0 0 5.5 6v13A1.5 1.5 0 0 0 7 20.5h10a1.5 1.5 0 0 0 1.5-1.5V6A1.5 1.5 0 0 0 17 4.5h-2"/>'
              '<rect x="9" y="3" width="6" height="3.5" rx="1"/><path d="M9 11.5h6M9 15h4"/>'),
    "undo": '<path d="M9 14.5 4.5 10 9 5.5"/><path d="M4.5 10H15a4.5 4.5 0 0 1 0 9h-3"/>',
    "rename": ('<path d="M14.6 5.4l4 4L9 19H5v-4z"/><path d="M12.6 7.4l4 4"/>'),
    "folder-plus": ('<path d="M3.5 7A1.5 1.5 0 0 1 5 5.5h4.2l2 2.2H19A1.5 1.5 0 0 1 20.5 9.2V18a1.5 1.5 0 0 1-1.5 1.5H5'
                    'A1.5 1.5 0 0 1 3.5 18z"/><path d="M12 10.8v5.4M9.3 13.5h5.4"/>'),
    "eject": '<path d="M12 5 19 13H5z"/><path d="M5 18h14"/>',
    "network": ('<rect x="9" y="3.5" width="6" height="5" rx="1"/><rect x="3" y="15.5" width="6" height="5" rx="1"/>'
                '<rect x="15" y="15.5" width="6" height="5" rx="1"/><path d="M12 8.5v3.5M6 15.5V12h12v3.5"/>'),
    "eye-off": ('<path d="M10 5.7a9.7 9.7 0 0 1 2-.2c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.4 3.2M6.6 6.9C3.9 8.6 2.5 12 2.5 12'
                'S6 18.5 12 18.5c1.8 0 3.3-.5 4.6-1.2"/><path d="M9.9 9.9a2.8 2.8 0 0 0 4 4M4 4l16 16"/>'),
    "filter": '<path d="M4 5.5h16l-6.2 7.3v5.4l-3.6 1.8v-7.2z"/>',
    "sort": '<path d="M7 4.5v15M3.8 16.3 7 19.5l3.2-3.2M14 6.5h6.5M14 11h4.5M14 15.5h2.5"/>',
    "restore": '<path d="M4.2 12a7.8 7.8 0 1 0 2.3-5.5"/><path d="M4.2 4.2v4.3h4.3"/>',
}

# DeckOS Quick Settings (the panel popup)
ICONS.update({
    "wifi": ('<path d="M2.8 9.2a13.5 13.5 0 0 1 18.4 0M5.9 12.6a9 9 0 0 1 12.2 0M9 16a4.5 4.5 0 0 1 6 0"/>'
             + dot(12, 19.2, 1.1)),
    "wifi-off": ('<path d="M9.6 5.3a13.5 13.5 0 0 1 11.6 3.9M2.8 9.2a13.5 13.5 0 0 1 3-2.1M14.4 9.5a9 9 0 0 1 3.7 3.1'
                 'M5.9 12.6a9 9 0 0 1 4-2.3M9 16a4.5 4.5 0 0 1 6 0M4 4l16 16"/>' + dot(12, 19.2, 1.1)),
    "bluetooth": '<path d="M7 7.5l10 9-5 4.5v-18l5 4.5-10 9"/>',
    "bell": ('<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2.2 2.2 0 0 0 4 0"/>'),
    "bell-off": ('<path d="M8.2 6.2A6 6 0 0 1 18 11v4M6 11v5.5L4.5 18H18M10 20.5a2.2 2.2 0 0 0 4 0M4 4l16 16"/>'),
    "night": ('<path d="M18.5 15.2A7.3 7.3 0 0 1 8.8 5.5a7.3 7.3 0 1 0 9.7 9.7z"/>'
              '<path d="M16.5 3.5v3M15 5h3M20 8.5v2M19 9.5h2"/>'),
    "volume": ('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18.2 6.5a7.5 7.5 0 0 1 0 11"/>'),
    "volume-mute": '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9.5l5 5M20.5 9.5l-5 5"/>',
    "sun": ('<circle cx="12" cy="12" r="3.8"/><path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4'
            'M17.1 17.1l1.4 1.4M5.5 18.5l1.4-1.4M17.1 6.9l1.4-1.4"/>'),
    "battery": '<rect x="2.5" y="7" width="17" height="10" rx="2"/><path d="M22 10.5v3M5.5 10v4M8.5 10v4"/>',
    "battery-charging": ('<rect x="2.5" y="7" width="17" height="10" rx="2"/><path d="M22 10.5v3"/>'
                         '<path d="M11.8 8.8 9 12.3h3.2l-1.2 2.9"/>'),
})


# The login screen can't recolour SVGs, so it gets its own light copies of the few it uses.
SDDM = OUT.parent.parent / "sddm/themes/deckos/icons"
SDDM_ICONS = ("power-off", "refresh", "sleep", "keyboard", "arrow-right", "chevron", "chevron-left", "display",
              "user", "alert")
SDDM_COLOR = "#D6DAE3"


def svg_text(body, color="#000"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
            f'stroke="#000" stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>\n'
            ).replace("#000", color)


STORE_LOGO = OUT.parent / "branding/store-logo.svg"


def store_logo():
    """The DeckOS Store app icon: the brand tile's gradient with the store bag in white."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#4C8DFF"/><stop offset="1" stop-color="#7A5CFF"/></linearGradient></defs>'
            '<rect x="6" y="6" width="116" height="116" rx="28" fill="url(#g)"/>'
            '<g transform="translate(22 20) scale(3.5)" fill="none" stroke="#fff" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS["store"]}</g></svg>\n')


FILES_LOGO = Path(__file__).resolve().parent.parent / "apps/deckos-files/data/deckos-files.svg"


def files_logo():
    """The DeckOS Files app icon: the same tile with the folder in white."""
    return store_logo().replace(ICONS["store"], ICONS["folder"])


HUB_LOGO = OUT.parent / "branding/hub-logo.svg"


def hub_logo():
    """The DeckOS Hub app icon: the same tile with the gauge, so it doesn't read as the DeckOS Menu button."""
    return store_logo().replace(ICONS["store"], ICONS["gauge"]).replace('fill="#000"', 'fill="#fff"')


def write():
    OUT.mkdir(parents=True, exist_ok=True)
    STORE_LOGO.write_text(store_logo(), newline="\n")
    HUB_LOGO.write_text(hub_logo(), newline="\n")
    FILES_LOGO.parent.mkdir(parents=True, exist_ok=True)
    FILES_LOGO.write_text(files_logo(), newline="\n")
    for name, body in ICONS.items():
        (OUT / f"{name}.svg").write_text(svg_text(body), newline="\n")
    SDDM.mkdir(parents=True, exist_ok=True)
    for name in SDDM_ICONS:
        (SDDM / f"{name}.svg").write_text(svg_text(ICONS[name], SDDM_COLOR), newline="\n")
    print(f"{len(ICONS)} icons -> {OUT}\n{len(SDDM_ICONS)} login-screen icons -> {SDDM}")


if __name__ == "__main__":
    write()
