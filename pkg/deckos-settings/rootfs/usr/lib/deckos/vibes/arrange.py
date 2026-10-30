"""Lines DecKoOS's desktop widgets up along the right edge of the screen (the left is the Desktop shelf's, or where
Plasma puts desktop icons), or the left if you'd rather: then they start past the shelf. The shelf stays put. `deckos vibe widgets arrange` runs it.

Plasma 6 keeps a desktop's widget positions in its ItemGeometries settings ("Applet-ID:x,y,w,h,rotation;" per screen
size) and ignores positions set from a script while it runs, so this edits plasma-org.kde.plasma.desktop-appletsrc
while the desktop shell is stopped, then starts it again. Widgets keep their size; a column that fills the screen
continues to its left. No Qt; tests/test_vibes.py checks it.

    arrange.py [right|left] [--dry-run]
"""
import re
import subprocess
import sys
import time
from pathlib import Path

APPLETSRC = Path.home() / ".config/plasma-org.kde.plasma.desktop-appletsrc"
ORDER = ["org.deckos.bigclock", "org.deckos.weather", "org.deckos.calendar", "org.deckos.countdown",
         "org.deckos.nowplaying", "org.deckos.photos", "org.deckos.perfgraphs", "org.deckos.focus", "org.deckos.note"]
MARGIN, GAP, BOTTOM = 40, 24, 110  # px; BOTTOM leaves room for the panel


def plugins(text):
    """{applet id: plugin} for every applet in the file."""
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^\[Containments\]\[\d+\]\[Applets\]\[(\d+)\]$", line)
        if m:
            cur = m.group(1)
            continue
        if line.startswith("["):
            cur = None
        elif cur and line.startswith("plugin="):
            out[cur] = line.split("=", 1)[1].strip()
    return out


def parse(value):
    """'Applet-1:x,y,w,h,r;…' into [(id, [x, y, w, h, r])]."""
    out = []
    for part in value.strip().split(";"):
        m = re.match(r"^Applet-(\d+):(-?\d+),(-?\d+),(\d+),(\d+),(-?\d+)$", part.strip())
        if m:
            out.append((m.group(1), [int(x) for x in m.groups()[1:]]))
    return out


def lay_out(items, kinds, width, height, side="right"):
    """New positions for DecKoOS's widgets (stacked down one edge, column after column toward the middle); other
    applets keep theirs. A Desktop shelf on that side is kept clear of."""
    ours = sorted((i for i in items if kinds.get(i[0]) in ORDER), key=lambda i: ORDER.index(kinds[i[0]]))
    edge = MARGIN  # edge: distance of this column from the screen's side
    for aid, (x, _y, w, _h, _r) in items:
        if kinds.get(aid) == "org.deckos.shelf" and (x + w / 2 < width / 2) == (side == "left"):
            edge = max(edge, (x + w if side == "left" else width - x) + GAP)
    placed, y, colw = {}, MARGIN, 0
    for aid, (_x, _y, w, h, r) in ours:
        if y + h > height - BOTTOM and y > MARGIN:
            edge, y, colw = edge + colw + GAP, MARGIN, 0
        placed[aid] = [width - edge - w if side == "right" else edge, y, w, h, r]
        y += h + GAP
        colw = max(colw, w)
    return [(aid, placed.get(aid, geo)) for aid, geo in items]


def arrange(text, side="right"):
    """The file with each desktop's ItemGeometries lines rearranged for their screen size (in the key's name;
    ItemGeometriesHorizontal follows that desktop's biggest real screen). Sizes too small to be a screen (leftovers
    like 320x240) are left as they are."""
    kinds = plugins(text)
    out, block = [], []

    def flush():
        sizes = [(int(m.group(1)), int(m.group(2))) for m in (re.match(r"^ItemGeometries-(\d+)x(\d+)=", ln)
                                                               for ln in block) if m and int(m.group(1)) >= 800]
        biggest = max(sizes, key=lambda s: s[0] * s[1]) if sizes else None
        for ln in block:
            m = re.match(r"^(ItemGeometries(?:-(\d+)x(\d+)|Horizontal))=(.*)$", ln)
            items = parse(m.group(4)) if m else []
            size = (int(m.group(2)), int(m.group(3))) if m and m.group(2) else biggest
            if not items or not size or size[0] < 800:
                out.append(ln)
                continue
            out.append(f"{m.group(1)}=" + "".join(f"Applet-{a}:{','.join(map(str, g))};"
                                                    for a, g in lay_out(items, kinds, *size, side)))
        block.clear()

    for line in text.splitlines():
        if line.startswith("["):
            flush()
            out.append(line)
        else:
            block.append(line)
    flush()
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def main(argv):
    side = "left" if "left" in argv else "right"
    text = APPLETSRC.read_text()
    new = arrange(text, side)
    if "--dry-run" in argv:
        print(new)
        return 0
    if new == text:
        return 0
    # The shell writes its own positions back on exit: stop it first, then edit, then start it again
    subprocess.run(["systemctl", "--user", "stop", "plasma-plasmashell.service"], check=False)
    time.sleep(1)
    APPLETSRC.with_name(APPLETSRC.name + ".deckos-bak").write_text(APPLETSRC.read_text())
    APPLETSRC.write_text(arrange(APPLETSRC.read_text(), side))
    subprocess.run(["systemctl", "--user", "start", "plasma-plasmashell.service"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
