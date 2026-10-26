"""DecKoOS Vibes: one switch for a whole mood. A Vibe is a DecKoOS theme underneath (colours, Plasma style, icons),
an accent, the DecKoOS Vibe wallpaper (an animated scene with the music visualizer), and DecKoOS apps' Style.
`deckos vibe` applies them (as the user: they're the user's own settings) and the timeline can undo it.
No Qt: tests/test_vibes.py checks the list.

    vibes.py list [--json] | get KEY
"""
import json
import sys

# scene: a scene in the org.deckos.vibe wallpaper; visualizer: bars, wave, ring or none; theme: an org.deckos.*
# look-and-feel; style: DecKoOS apps' corners (hub_style.STYLE)
VIBES = {
    "lofi": {"name": "Lo-fi", "summary": "Warm dusk, rain on the window, mellow bars", "scene": "lofi",
             "visualizer": "bars", "colorA": "#FF9E7A", "colorB": "#B36BFF", "accent": "#FF9E7A",
             "theme": "org.deckos.ember", "corners": "round"},
    "neon": {"name": "Neon", "summary": "Synthwave sun, a glowing grid, punchy bars", "scene": "neon",
             "visualizer": "bars", "colorA": "#FF4FD8", "colorB": "#3DE0FF", "accent": "#FF4FD8",
             "theme": "org.deckos.midnight", "corners": "default"},
    "midnight": {"name": "Midnight", "summary": "Near-black and quiet: breathing stars, a thin wave",
                 "scene": "midnight", "visualizer": "wave", "colorA": "#8FA8FF", "colorB": "#4C8DFF",
                 "accent": "#8FA8FF", "theme": "org.deckos.graphite", "corners": "sharp"},
    "cozy": {"name": "Cozy", "summary": "Pine hills at dusk, fireflies, a soft ring", "scene": "cozy",
             "visualizer": "ring", "colorA": "#F2C46D", "colorB": "#6FBF8E", "accent": "#6FBF8E",
             "theme": "org.deckos.aurora", "corners": "round"},
}
VISUALIZERS = ["bars", "wave", "ring", "none"]


def main(argv):
    if argv[:1] == ["list"]:
        if "--json" in argv:
            print(json.dumps(VIBES))
        else:
            for key, v in VIBES.items():
                print(f"  {key:<10} {v['name']}: {v['summary']}")
        return 0
    if argv[:1] == ["get"] and len(argv) > 1 and argv[1] in VIBES:
        v = VIBES[argv[1]]
        # KEY=VALUE lines for the deckos tool (bash reads them without running anything)
        for k in ("scene", "visualizer", "colorA", "colorB", "accent", "theme", "corners", "name"):
            print(f"{k}={v[k]}")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
