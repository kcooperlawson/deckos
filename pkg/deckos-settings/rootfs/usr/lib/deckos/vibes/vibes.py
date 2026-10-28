"""DecKoOS Vibes: one switch for a whole mood. A Vibe is a DecKoOS theme underneath (colours, Plasma style, icons),
an accent, the DecKoOS Vibe wallpaper (an animated scene with the music visualizer), and DecKoOS apps' Style.
`deckos vibe` applies them (as the user: they're the user's own settings) and the timeline can undo it.
No Qt: tests/test_vibes.py checks the list.

Your own Vibes live in ~/.config/deckos/vibes/KEY.json (the Hub's Vibe editor writes them), usually on the Photo
scene: your picture, with lights you placed that glow with a part of the music. Their photo is copied next to them,
so moving the original breaks nothing. A look (a Vibe and its photo) exports as one .deckos-look file to share.
Everything a Vibe holds goes into a desktop script, so every value is checked here first (CHECKS).

    vibes.py list [--json] | get KEY | save FILE.json | delete KEY | export KEY FILE | import FILE
"""
import json
import re
import shutil
import zipfile
from pathlib import Path
import sys

# scene: a scene in the org.deckos.vibe wallpaper (each reacts to the music itself); visualizer: bars, wave or ring on
# top, or none (the default: the scene is the visualizer); theme: an org.deckos.* look-and-feel; style: DecKoOS apps'
# corners (hub_style.STYLE); stage: how Vibe mode (DecKoOS Music) looks with this Vibe on
VIBES = {
    "lofi": {"name": "Rainy street", "summary": "Lisbon in the rain: the streetlights bloom with the bass", "scene": "lofi",
             "visualizer": "none", "colorA": "#FF9E7A", "colorB": "#B36BFF", "accent": "#FF9E7A",
             "theme": "org.deckos.ember", "corners": "round", "stage": "trails"},
    "neon": {"name": "City nights", "summary": "Manhattan across the river: its reflections play the song",
             "scene": "neon", "visualizer": "none", "colorA": "#FF4FD8", "colorB": "#3DE0FF", "accent": "#FF4FD8",
             "theme": "org.deckos.midnight", "corners": "default", "stage": "spectrum"},
    "midnight": {"name": "Midnight", "summary": "The Milky Way: stars glint with the music, shooting stars on drops",
                 "scene": "midnight", "visualizer": "none", "colorA": "#8FA8FF", "colorB": "#4C8DFF",
                 "accent": "#8FA8FF", "theme": "org.deckos.graphite", "corners": "sharp", "stage": "aurora"},
    "cozy": {"name": "Cozy", "summary": "Pines at dusk: fireflies flash together on the beat", "scene": "cozy",
             "visualizer": "none", "colorA": "#F2C46D", "colorB": "#6FBF8E", "accent": "#6FBF8E",
             "theme": "org.deckos.aurora", "corners": "round", "stage": "glow"},
}
VISUALIZERS = ["bars", "wave", "ring", "none"]
SCENES = ["lofi", "neon", "midnight", "cozy", "photo"]
THEMES = ["org.deckos.ember", "org.deckos.midnight", "org.deckos.graphite", "org.deckos.aurora", "org.deckos.crimson",
          "org.deckos.paper", "org.deckos.desktop"]
CORNERS = ["round", "default", "sharp"]
STAGES = ["aurora", "spectrum", "trails", "glow"]  # music/looks.py draws them
PARTS = ["bass", "mid", "high"]  # what a light in a photo answers to
USER = Path.home() / ".config/deckos/vibes"
PHOTOS = Path.home() / ".local/share/deckos/vibes"

COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
CHECKS = {
    "name": lambda v: isinstance(v, str) and 0 < len(v) <= 40 and not re.search(r"[\x00-\x1f'\"\\]", v),
    "summary": lambda v: isinstance(v, str) and len(v) <= 120 and not re.search(r"[\x00-\x1f'\"\\]", v),
    "scene": lambda v: v in SCENES,
    "visualizer": lambda v: v in VISUALIZERS,
    "colorA": lambda v: isinstance(v, str) and bool(COLOR.match(v)),
    "colorB": lambda v: isinstance(v, str) and bool(COLOR.match(v)),
    "accent": lambda v: isinstance(v, str) and bool(COLOR.match(v)),
    "theme": lambda v: v in THEMES,
    "corners": lambda v: v in CORNERS,
    "stage": lambda v: v in STAGES,
    "photo": lambda v: v == "" or (isinstance(v, str) and Path(v).is_file() and not re.search(r"['\"\\\n]", v)),
    "lights": lambda v: isinstance(v, list) and len(v) <= 40 and all(
        isinstance(l, list) and len(l) == 4 and all(isinstance(n, (int, float)) for n in l[:3])
        and 0 <= l[0] <= 1 and 0 <= l[1] <= 1 and 0.01 <= l[2] <= 0.6 and l[3] in PARTS for l in v),
    "grain": lambda v: isinstance(v, (int, float)) and 0 <= v <= 0.2,
    "vignette": lambda v: isinstance(v, (int, float)) and 0 <= v <= 0.9,
    "clock": lambda v: isinstance(v, bool),
}
DEFAULTS = {"summary": "", "visualizer": "none", "theme": "org.deckos.graphite", "corners": "default", "stage": "glow",
            "photo": "",
            "lights": [], "grain": 0.05, "vignette": 0.5, "clock": True}


def valid_key(key):
    return bool(re.fullmatch(r"[a-z][a-z0-9-]{0,30}", key or "")) and key not in VIBES


def check(vibe):
    """The Vibe with defaults filled in, or ValueError naming what's wrong."""
    v = {**DEFAULTS, **vibe}
    v.setdefault("accent", v.get("colorA", ""))
    for k, ok in CHECKS.items():
        if k in v and not ok(v[k]):
            raise ValueError(f"{k} isn't valid")
    for k in ("name", "scene", "colorA", "colorB"):
        if k not in v:
            raise ValueError(f"{k} is missing")
    if v["scene"] == "photo" and not v["photo"]:
        raise ValueError("the Photo scene needs a photo")
    return {k: v[k] for k in CHECKS if k in v}


def user_vibes(folder=None):
    """Your own Vibes: {key: vibe} (broken or tampered files are skipped)."""
    out = {}
    for f in sorted(Path(folder or USER).glob("*.json")):
        try:
            if valid_key(f.stem):
                out[f.stem] = {**check(json.loads(f.read_text())), "own": True}
        except (OSError, ValueError):
            continue
    return out


def all_vibes(folder=None):
    return {**{k: {**DEFAULTS, **v} for k, v in VIBES.items()}, **user_vibes(folder)}


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "my-vibe"
    return s if s[0].isalpha() else "v-" + s[:28]


def save(vibe, key=None, folder=None, photos=None):
    """Checks and saves one of your Vibes (its photo copied in). Returns the key."""
    folder, photos = Path(folder or USER), Path(photos or PHOTOS)
    editing = bool(key)
    key = key or slug(vibe.get("name", ""))
    if not valid_key(key):
        key = "my-" + key if valid_key("my-" + key) else slug("my " + key)
    if not editing:  # a new Vibe never replaces one you have: "rain", "rain-2", …
        base, n = key[:27], 2
        while (folder / f"{key}.json").exists():
            key, n = f"{base}-{n}", n + 1
    v = check(vibe)
    if v.get("photo"):
        src = Path(v["photo"])
        dest = photos / f"{key}{src.suffix.lower() or '.jpg'}"
        if src.resolve() != dest.resolve():
            photos.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        v["photo"] = str(dest)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.json").write_text(json.dumps(v, indent=1))
    return key


def delete(key, folder=None, photos=None):
    if not valid_key(key):
        raise ValueError("only your own Vibes can be deleted")
    (Path(folder or USER) / f"{key}.json").unlink(missing_ok=True)
    for f in Path(photos or PHOTOS).glob(f"{key}.*"):
        f.unlink()


def export(key, dest, folder=None):
    """A Vibe (and its photo) as one file to share: a zip with vibe.json and the picture."""
    vibe = all_vibes(folder).get(key)
    if not vibe:
        raise ValueError(f"no Vibe called {key}")
    vibe = {k: v for k, v in vibe.items() if k != "own"}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        if vibe.get("photo"):
            z.write(vibe["photo"], "photo" + Path(vibe["photo"]).suffix)
            vibe["photo"] = "photo" + Path(vibe["photo"]).suffix
        z.writestr("vibe.json", json.dumps(vibe, indent=1))
    return dest


def import_look(path, folder=None, photos=None):
    """Adds a shared .deckos-look as one of your Vibes. Nothing in it is trusted: the picture must be a picture
    (JPEG/PNG/WebP by its first bytes, under 30 MB) and every setting passes the same checks as your own."""
    photos = Path(photos or PHOTOS)
    with zipfile.ZipFile(path) as z:
        vibe = json.loads(z.read("vibe.json"))
        if not isinstance(vibe, dict):
            raise ValueError("not a DecKoOS look")
        pic = vibe.get("photo", "")
        if pic:
            if pic not in z.namelist() or not re.fullmatch(r"photo\.(jpg|jpeg|png|webp)", pic):
                raise ValueError("the look's picture is missing")
            data = z.read(pic)
            if len(data) > 30_000_000 or not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
                                              or data[8:12] == b"WEBP"):
                raise ValueError("the look's picture isn't a picture")
            photos.mkdir(parents=True, exist_ok=True)
            tmp = photos / ("import" + Path(pic).suffix)
            tmp.write_bytes(data)
            vibe["photo"] = str(tmp)
    key = save(vibe, folder=folder, photos=photos)
    for f in photos.glob("import.*"):
        f.unlink()
    return key


def main(argv):
    vibes = all_vibes()
    if argv[:1] == ["list"]:
        if "--json" in argv:
            print(json.dumps(vibes))
        else:
            for key, v in vibes.items():
                print(f"  {key:<12} {v['name']}: {v.get('summary', '')}" + ("  (yours)" if v.get("own") else ""))
        return 0
    if argv[:1] == ["get"] and len(argv) > 1 and argv[1] in vibes:
        v = vibes[argv[1]]
        # KEY=VALUE lines for the deckos tool (bash reads them without running anything); all checked above
        for k in ("scene", "visualizer", "colorA", "colorB", "accent", "theme", "corners", "name", "photo", "grain",
                  "vignette"):
            print(f"{k}={v.get(k, DEFAULTS.get(k, ''))}")
        print(f"clock={'true' if v.get('clock', True) else 'false'}")
        print(f"lights={json.dumps(v.get('lights', []), separators=(',', ':'))}")
        return 0
    try:
        if argv[:1] == ["save"] and len(argv) == 2:
            print(save(json.loads(Path(argv[1]).read_text())))
            return 0
        if argv[:1] == ["delete"] and len(argv) == 2:
            delete(argv[1])
            return 0
        if argv[:1] == ["export"] and len(argv) == 3:
            print(export(argv[1], argv[2]))
            return 0
        if argv[:1] == ["import"] and len(argv) == 2:
            print(import_look(argv[1]))
            return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print(f"couldn't: {e}", file=sys.stderr)
        return 1
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
