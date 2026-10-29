"""Vibe mode's world: every monitor is a window onto one stage, laid out as the screens are. No Qt, so the tests
can feed it any arrangement.

The cover goes on the screen in the middle (by position; of two, the main one), and everything else (waves,
comets, the aurora, the horizon) lives in world coordinates, so it runs on from one screen into the next. Laid out
from the monitors' real sizes and the gap between them on the desk, when they report their sizes.
"""
import re


def _home(placed, primary):
    by_x = sorted(placed, key=lambda s: (s["x"] + s["width"] / 2, s["y"]))
    n = len(by_x)
    if n % 2:
        return by_x[n // 2]
    pair = by_x[n // 2 - 1:n // 2 + 1]  # two in the middle: the main screen if it's one of them, else the left one
    return next((s for s in pair if s["index"] == primary), pair[0])


def _in_a_row(screens):
    """Side by side, left to right, none overlapping: the arrangement real sizes and gaps apply to."""
    xs = sorted(screens, key=lambda s: s[0])
    return all(b[0] >= a[0] + a[2] - 1 for a, b in zip(xs, xs[1:]))


def layout(screens, primary=0, physical=None, gap_mm=0):
    """screens: [(x, y, width, height)] as the desktop places them (logical pixels). physical: each one's real size
    [(width_mm, height_mm)], when the monitors report it; gap_mm: the space between them on the desk.

    With real sizes and the screens in a row, the world is laid out as the desk is: each screen as wide as it really
    is, the gap between them, centred on each other, in units of the cover screen's pixels; so something crossing
    from one screen to the next keeps its size and speed and passes behind the gap. Otherwise (no sizes, screens
    stacked) as the desktop has them. Returns the world's size, each screen's place in it (x, y, width, height in
    world units; pw, ph its own pixels; scale = pixels per world unit), which holds the cover and the cover's centre."""
    if not screens:
        screens = [(0, 0, 1920, 1080)]
    # Sizes are trusted only when every screen reports one shaped like its pixels (some report 0, or nonsense)
    real = (physical and len(physical) == len(screens) and len(screens) > 1 and _in_a_row(screens)
            and all(mw > 0 and mh > 0 and abs((mw / mh) / (s[2] / s[3]) - 1) < 0.1
                    for (mw, mh), s in zip(physical, screens)))
    if real:
        # the cover's screen sets the unit: its pixels stay pixels
        rough = [{"index": i, "x": x, "y": y, "width": w, "height": h} for i, (x, y, w, h) in enumerate(screens)]
        home = _home(rough, primary)
        per_mm = screens[home["index"]][2] / physical[home["index"]][0]
        gap = max(0, gap_mm) * per_mm
        # each as wide as it really is; its height from its own pixels' shape, so its pixels stay square
        sizes = [(mw * per_mm, mw * per_mm * s[3] / s[2]) for (mw, _mh), s in zip(physical, screens)]
        tallest = max(h for _w, h in sizes)
        placed, x = [], 0.0
        for i in sorted(range(len(screens)), key=lambda i: screens[i][0]):
            w, h = sizes[i]
            placed.append({"index": i, "x": round(x, 1), "y": round((tallest - h) / 2, 1), "width": round(w, 1),
                           "height": round(h, 1), "pw": screens[i][2], "ph": screens[i][3],
                           "scale": round(screens[i][2] / w, 6)})
            x += w + gap
        placed.sort(key=lambda s: s["index"])
        width, height = round(x - gap, 1), round(tallest, 1)
    else:
        left = min(s[0] for s in screens)
        top = min(s[1] for s in screens)
        width = max(s[0] + s[2] for s in screens) - left
        height = max(s[1] + s[3] for s in screens) - top
        placed = [{"index": i, "x": x - left, "y": y - top, "width": w, "height": h, "pw": w, "ph": h, "scale": 1.0}
                  for i, (x, y, w, h) in enumerate(screens)]
    home = _home(placed, primary)
    cover = (home["x"] + home["width"] / 2, home["y"] + home["height"] * 0.4)
    return {"width": width, "height": height, "screens": placed, "home": home["index"], "cover": cover}


def lyrics_screen(lay):
    """The screen lyrics go on when there's more than one: the cover screen's nearest neighbour (the right one if
    it's between two), or None for a single screen."""
    others = [s for s in lay["screens"] if s["index"] != lay["home"]]
    if not others:
        return None
    home = next(s for s in lay["screens"] if s["index"] == lay["home"])
    hx = home["x"] + home["width"] / 2
    return min(others, key=lambda s: (abs(s["x"] + s["width"] / 2 - hx), -(s["x"] > hx)))["index"]


def main_output(text):
    """The name of the output with priority 1 in `kscreen-doctor -o`, or ""."""
    name = ""
    for line in re.sub(r"\x1b\[[0-9;]*m", "", text).splitlines():
        m = re.match(r"Output:\s+\d+\s+(\S+)", line.strip())
        if m:
            name = m.group(1)
        elif re.match(r"priority\s+1\b", line.strip()) and name:
            return name
    return ""
