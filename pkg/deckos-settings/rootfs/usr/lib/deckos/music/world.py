"""Vibe mode's world: every monitor is a window onto one stage, laid out as the screens are. No Qt, so the tests
can feed it any arrangement.

The cover goes on the screen in the middle (by position; of two, the main one), and everything else (waves,
comets, the aurora, the horizon) lives in world coordinates, so it runs on from one screen into the next.
"""
import re


def layout(screens, primary=0):
    """screens: [(x, y, width, height)] as the desktop places them. Returns the world's size, each screen's place
    in it (origin moved to 0,0), which screen holds the cover and where the cover's centre is."""
    if not screens:
        screens = [(0, 0, 1920, 1080)]
    left = min(s[0] for s in screens)
    top = min(s[1] for s in screens)
    right = max(s[0] + s[2] for s in screens)
    bottom = max(s[1] + s[3] for s in screens)
    placed = [{"index": i, "x": x - left, "y": y - top, "width": w, "height": h}
              for i, (x, y, w, h) in enumerate(screens)]
    by_x = sorted(placed, key=lambda s: (s["x"] + s["width"] / 2, s["y"]))
    n = len(by_x)
    if n % 2:
        home = by_x[n // 2]
    else:  # two in the middle: the main screen if it's one of them, else the left one
        pair = by_x[n // 2 - 1:n // 2 + 1]
        home = next((s for s in pair if s["index"] == primary), pair[0])
    cover = (home["x"] + home["width"] / 2, home["y"] + home["height"] * 0.4)
    return {"width": right - left, "height": bottom - top, "screens": placed, "home": home["index"], "cover": cover}


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
