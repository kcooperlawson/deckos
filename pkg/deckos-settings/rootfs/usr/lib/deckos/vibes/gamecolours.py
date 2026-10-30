"""A game's two colours, from its Steam art: what the desktop takes on while the game runs (`deckos mode watch`, when
DecKoOS reacts: style.conf react=on). The most colourful hue in the art, and a second one far enough round the wheel
to make a gradient; a grey cover gets the first hue turned 40 degrees. Plain QImage, no window.

    gamecolours.py APPID       prints "#RRGGBB #RRGGBB", or nothing (no art, or no colour in it)
"""
import colorsys
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shelf"))


def pick(pixels):
    """(colorA, colorB) as '#RRGGBB' from (r, g, b) 0..255 pixels, or None when the art has no real colour."""
    bins = [[0.0, 0.0, 0.0, 0.0] for _ in range(12)]  # weight, r, g, b per 30-degree slice of the wheel
    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.35 or v < 0.3:
            continue
        w = s * v
        slot = bins[int(h * 12) % 12]
        slot[0] += w
        slot[1] += r * w
        slot[2] += g * w
        slot[3] += b * w
    order = sorted(range(12), key=lambda i: bins[i][0], reverse=True)
    if bins[order[0]][0] < 1.5:  # a handful of coloured pixels isn't a colour scheme
        return None

    def colour(i):
        w, r, g, b = bins[i]
        h, s, v = colorsys.rgb_to_hsv(r / w / 255, g / w / 255, b / w / 255)
        r, g, b = colorsys.hsv_to_rgb(h, max(s, 0.55), max(v, 0.8))  # bright enough to light an edge on dark glass
        return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))

    a = order[0]
    far = [i for i in order[1:] if min(abs(i - a), 12 - abs(i - a)) >= 2 and bins[i][0] >= bins[a][0] * 0.15]
    if far:
        return colour(a), colour(far[0])
    w, r, g, b = bins[a]
    h, s, v = colorsys.rgb_to_hsv(r / w / 255, g / w / 255, b / w / 255)
    r, g, b = colorsys.hsv_to_rgb((h + 40 / 360) % 1, max(s, 0.55), max(v, 0.8))
    return colour(a), "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


def from_art(path):
    from PySide6.QtGui import QImage
    img = QImage(str(path))
    if img.isNull():
        return None
    img = img.scaled(40, 40)
    return pick([(c.red(), c.green(), c.blue()) for c in (img.pixelColor(x, y) for y in range(40) for x in range(40))])


def main(argv):
    if not argv or not argv[0].isdigit():
        return 2
    import shelf
    art = shelf.steam_art(argv[0])
    found = from_art(art) if art else None
    if found:
        print(*found)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
