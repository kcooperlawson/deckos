"""Soundbars and AV receivers on a graphics card's HDMI: the card only sends sound to an HDMI output that's switched
on, so the desktop gains a screen nobody can see (the pointer and windows wander into it, and Plasma may even turn
the real main screen off for it). DecKoOS mirrors such an output onto the main screen instead: the sound keeps
flowing, and to everything else it isn't a screen at all.

An output is taken for audio only when it's HDMI, has sound (its ELD names a sink) and its EDID gives no physical
size (0 x 0 cm): soundbars and receivers say that; monitors and TVs give their size. A projector can say 0 x 0 too,
and mirroring the main screen onto one is what you'd want from it anyway. `deckos screens soundbar off` stops it.
No Qt; tests/test_screens.py checks it on a made-up /sys and /proc.

    screens.py audio-only        the connectors (HDMI-A-1) that look audio-only, one per line
"""
import os
import re
import sys
from pathlib import Path

SYS = Path(os.environ.get("DECKOS_SYS") or "/sys")
PROC = Path(os.environ.get("DECKOS_PROC") or "/proc")


def edid_size(edid):
    """(width, height) in cm from an EDID's basic block, or None when it's too short to say."""
    return (edid[21], edid[22]) if len(edid) >= 23 and edid[:8] == b"\x00\xff\xff\xff\xff\xff\xff\x00" else None


def edid_name(edid):
    """The monitor name an EDID gives (its 0xFC descriptor), or ""."""
    for i in range(54, 126, 18):
        d = edid[i:i + 18]
        if len(d) == 18 and d[:3] == b"\x00\x00\x00" and d[3] == 0xFC:
            return d[5:].split(b"\n")[0].decode("ascii", "replace").strip()
    return ""


def has_sound(name, proc=None):
    """Whether HDMI audio has a sink called `name` (an ELD with the monitor present and that monitor_name)."""
    for eld in Path(proc or PROC).glob("asound/card*/eld#*"):
        try:
            text = eld.read_text(errors="replace")
        except OSError:
            continue
        m = re.search(r"^monitor_name\s+(.*)$", text, re.M)
        if re.search(r"^monitor_present\s+1", text, re.M) and m and m.group(1).strip() == name:
            return True
    return False


def audio_only(root=None, proc=None):
    """Connector names (HDMI-A-1) whose screen is really a soundbar or receiver."""
    root = Path(root or SYS) / "class/drm"
    out = []
    for c in sorted(root.glob("card*-HDMI-*")):
        try:
            if (c / "status").read_text().strip() != "connected":
                continue
            edid = (c / "edid").read_bytes()
        except OSError:
            continue
        name = edid_name(edid)
        if edid_size(edid) == (0, 0) and name and has_sound(name, proc):
            out.append(c.name.split("-", 1)[1])
    return out


def main(argv):
    if argv[:1] == ["audio-only"]:
        print("\n".join(audio_only()))
        return 0
    print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
