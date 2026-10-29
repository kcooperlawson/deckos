"""How Vibe mode looks: which stage it draws, and in whose colours. No Qt; tests/test_music.py checks it.

Seven stages, all spanning every monitor as one world:
  aurora    curtains of light, stars and a shockwave on every beat (the full show)
  spectrum  a 2000s spectrum analyzer: chunky lit-up bars with falling peaks, across all the screens
  trails    a 2000s feedback visualizer (the Milkdrop kind): a ring of sound around the cover leaves trails that
            zoom and swirl outward with the bass
  glow      calm: the colours drift and breathe slowly behind the cover
  grid      80s neon: a grid floor racing to a striped sun behind the cover, mountains made of the spectrum
  scope     an oscilloscope: the music drawn as one glowing line through every screen, with echoes
  kaleido   a kaleidoscope turning around the cover, its mirrors cut by the beat

By default the stage follows your Vibe (each Vibe names one: vibes.py "stage"), and so do the colours; you can pick
another stage, or the album cover's colours, in Vibe mode (V cycles the stages). Also kept: lyrics on or off, and the
gap between the monitors on the desk (gap, in mm; world.py lays the screens out with it).
Kept in ~/.config/deckos/music.conf.
"""
import sys
from pathlib import Path

STYLES = ["aurora", "spectrum", "trails", "glow", "grid", "scope", "kaleido"]
NAMES = {"aurora": "Aurora", "spectrum": "Spectrum", "trails": "Trails", "glow": "Glow", "grid": "Grid",
         "scope": "Scope", "kaleido": "Kaleido"}
COLOURS = ["vibe", "cover"]
CONF = Path.home() / ".config/deckos/music.conf"
VIBE_FILE = Path.home() / ".config/deckos/vibe"
DEFAULT = {"style": "auto", "colours": "vibe", "lyrics": "on", "gap": "0"}
GAP_MAX = 1000  # mm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vibes"))
import vibes  # noqa: E402


def load(path=None):
    """Your choices: style (auto: the Vibe's, or one of STYLES), colours (vibe or cover), lyrics (on or off) and gap
    (the space between monitors, in whole mm)."""
    out = dict(DEFAULT)
    try:
        for line in Path(path or CONF).read_text().splitlines():
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if ((k == "style" and v in ["auto", *STYLES]) or (k == "colours" and v in COLOURS)
                    or (k == "lyrics" and v in ("on", "off")) or (k == "gap" and v.isdigit() and int(v) <= GAP_MAX)):
                out[k] = v
    except OSError:
        pass
    return out


def save(choices, path=None):
    path = Path(path or CONF)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Vibe mode's look (DecKoOS Music): style auto|" + "|".join(STYLES) + ", colours vibe|cover, "
                    "lyrics on|off, gap MM\n"
                    + "".join(f"{k}={choices.get(k, DEFAULT[k])}\n" for k in DEFAULT))


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
