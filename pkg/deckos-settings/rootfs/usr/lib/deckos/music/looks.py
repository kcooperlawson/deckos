"""How Vibe mode looks: which stage it draws, and in whose colours. No Qt; tests/test_music.py checks it.

Four stages, all spanning every monitor as one world:
  aurora    curtains of light, stars and a shockwave on every beat (the full show)
  spectrum  a 2000s spectrum analyzer: chunky lit-up bars with falling peaks, across all the screens
  trails    a 2000s feedback visualizer (the Milkdrop kind): a ring of sound around the cover leaves trails that
            zoom and swirl outward with the bass
  glow      calm: the colours drift and breathe slowly behind the cover

By default the stage follows your Vibe (each Vibe names one: vibes.py "stage"), and so do the colours; you can pick
another stage, or the album cover's colours, in Vibe mode (V cycles the stages). Kept in ~/.config/deckos/music.conf.
"""
import sys
from pathlib import Path

STYLES = ["aurora", "spectrum", "trails", "glow"]
NAMES = {"aurora": "Aurora", "spectrum": "Spectrum", "trails": "Trails", "glow": "Glow"}
COLOURS = ["vibe", "cover"]
CONF = Path.home() / ".config/deckos/music.conf"
VIBE_FILE = Path.home() / ".config/deckos/vibe"
DEFAULT = {"style": "auto", "colours": "vibe"}

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vibes"))
import vibes  # noqa: E402


def load(path=None):
    """Your choices: style (auto: the Vibe's, or one of STYLES) and colours (vibe or cover)."""
    out = dict(DEFAULT)
    try:
        for line in Path(path or CONF).read_text().splitlines():
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if (k == "style" and v in ["auto", *STYLES]) or (k == "colours" and v in COLOURS):
                out[k] = v
    except OSError:
        pass
    return out


def save(choices, path=None):
    path = Path(path or CONF)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Vibe mode's look (DecKoOS Music): style auto|" + "|".join(STYLES) + ", colours vibe|cover\n"
                    + "".join(f"{k}={choices[k]}\n" for k in DEFAULT))


def current_vibe(vibe_file=None, folder=None):
    """The Vibe you're on, or None (no Vibe, or one that's since been deleted)."""
    try:
        key = Path(vibe_file or VIBE_FILE).read_text().strip()
    except OSError:
        return None
    return vibes.all_vibes(folder).get(key)


def resolve(choices, vibe):
    """(style, colours) to draw: the Vibe's stage when the style is auto (glow with no Vibe), and the cover's colours
    when there's no Vibe to take them from."""
    style = choices["style"] if choices["style"] in STYLES else (vibe or {}).get("stage", "glow")
    colours = choices["colours"] if vibe else "cover"
    return style, colours


def vibe_colours(vibe):
    """(base, accent, second) as #RRGGBB from a Vibe: its two colours, and a ground that's its first colour, dark."""
    a = vibe["colorA"]
    r, g, b = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    base = "#{:02X}{:02X}{:02X}".format(*(int(4 + c * 0.1) for c in (r, g, b)))
    return base, vibe["colorA"], vibe["colorB"]
