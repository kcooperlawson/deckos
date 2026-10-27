"""DecKoOS Sound: one place for what the PC plays and records, on top of PipeWire (which stays the engine).
No Qt: the Hub's Sound page and `deckos sound` use it; tests/test_sound.py feeds it canned pactl/pw-top output.

- Outputs and inputs, and every app that plays, sorted into kinds: games, music, voice chat, browsers, system sounds.
  A kind's slider sets every app of that kind at once; an app can be sent to another output.
- The buffer: the smallest chunk an app may ask PipeWire for. Tiny chunks are what crackle when a game loads the CPU
  while music plays; DecKoOS keeps a floor (BUFFERS), applied live and kept in the user's PipeWire config.
- An equalizer: a "DecKoOS EQ" output made of PipeWire's own filters (no plugins), playing into the device it was
  made for. It runs as its own small PipeWire client (user unit deckos-eq), so turning it on or off never restarts
  the sound server or cuts what's playing. Presets only, so no setting can be harmful.
- Dropouts (what crackling is, to PipeWire): counted per device from pw-top, for System Doctor and the Hub.

    sound.py status | kinds | set-kind KIND PERCENT | set-app INDEX PERCENT | move-app INDEX SINK
             buffer [NAME] | eq [PRESET|off] | dropouts
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
PW_CONF = HOME / ".config/pipewire/pipewire.conf.d"
PULSE_CONF = HOME / ".config/pipewire/pipewire-pulse.conf.d"
BUFFER_FILE = PW_CONF / "60-deckos-buffer.conf"
PULSE_BUFFER_FILE = PULSE_CONF / "60-deckos-buffer.conf"
EQ_FILE = HOME / ".config/deckos/sound-eq.conf"  # run by the deckos-eq user unit: its own small PipeWire client
EQ_NODE = "deckos_eq"

# The smallest buffer apps may ask for, in samples at 48 kHz (256 = 5.3 ms)
BUFFERS = {
    "steady": (512, "Steady", "No crackles, even under heavy load (about 11 ms)"),
    "balanced": (256, "Balanced", "The DecKoOS default: no crackles in games, quick enough for voice chat (about 5 ms)"),
    "quick": (64, "Quick", "For music making and instruments only: may crackle while a game runs (about 1 ms)"),
}
DEFAULT_BUFFER = "balanced"

KINDS = [  # (id, name, icon)
    ("game", "Games", "gaming"), ("music", "Music and video", "music"), ("voice", "Voice chat", "mic"),
    ("browser", "Browsers", "globe"), ("system", "System sounds", "bell"), ("other", "Other apps", "grid"),
]
KIND_NAMES = {k: n for k, n, _ in KINDS}
MUSIC_APPS = re.compile(r"spotify|strawberry|elisa|rhythmbox|lollypop|amarok|clementine|audacious|deadbeef|"
                        r"cmus|mpd|tauon|vlc|mpv|haruna|celluloid|totem|kodi|jellyfin|plex|tidal|deezer|cider", re.I)
VOICE_APPS = re.compile(r"discord|vesktop|webcord|teamspeak|ts3client|mumble|skype|zoom|slack|teams|element|"
                        r"signal|telegram|webrtc", re.I)
BROWSERS = re.compile(r"firefox|chrom|brave|vivaldi|opera|librewolf|zen|floorp|edge|epiphany|falkon", re.I)
GAMES = re.compile(r"\.exe$|wine|proton|gamescope|steam_app|retroarch|dolphin-emu|pcsx2|rpcs3|ppsspp|duckstation|"
                   r"cemu|ryujinx|yuzu|citra|xemu|minecraft|java", re.I)
SYSTEM = re.compile(r"libcanberra|plasmashell|kwin|knotify|notification|xdg-desktop-portal|sddm|DecKoOS", re.I)

# Equalizer presets: [(type, Hz, dB, Q)], PipeWire's built-in biquad filters
EQ_PRESETS = {
    "bass": ("More bass", "Fuller low end for music and games",
             [("bq_lowshelf", 90, 5.0, 0.7), ("bq_peaking", 250, 1.5, 1.0)]),
    "voices": ("Clear voices", "Dialogue and voice chat stand out; less rumble",
               [("bq_highpass", 90, 0.0, 0.7), ("bq_peaking", 2500, 4.0, 1.0), ("bq_peaking", 300, -2.0, 1.0)]),
    "footsteps": ("Footsteps", "Lifts the range where footsteps and reloads are in shooters",
                  [("bq_lowshelf", 100, -3.0, 0.7), ("bq_peaking", 2000, 4.0, 0.9), ("bq_peaking", 5000, 3.0, 1.2)]),
    "headphones": ("Warm headphones", "Takes the edge off bright headphones",
                   [("bq_highshelf", 8000, -3.0, 0.7), ("bq_lowshelf", 120, 2.0, 0.7)]),
    "night": ("Night", "Less bass, so it doesn't carry through walls",
              [("bq_lowshelf", 150, -8.0, 0.7), ("bq_peaking", 2500, 2.0, 1.0)]),
}

DEMO = "--demo" in sys.argv or os.environ.get("DECKOS_SOUND_DEMO") == "1"


def run(cmd, timeout=6):
    """A command's output ("" when it printed nothing), or None when it isn't there or failed."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def text(cmd, timeout=6):
    return run(cmd, timeout) or ""


def _json(text):
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except ValueError:
        return []


def percent(volume):
    """pactl's volume ({"front-left": {"value_percent": "40%"}, …}) as one number, the loudest channel."""
    vals = [int(str(c.get("value_percent", "0")).rstrip("%") or 0) for c in (volume or {}).values() if isinstance(c, dict)]
    return max(vals, default=0)


def kind_of(props):
    """Which kind an app's sound is, from what it says about itself (role first, then names)."""
    role = (props.get("media.role") or "").lower()
    name = " ".join(props.get(k) or "" for k in ("application.name", "application.process.binary", "node.name",
                                                    "application.id", "media.name"))
    if role in ("game",) or GAMES.search(props.get("application.process.binary") or "") or \
            GAMES.search(props.get("application.name") or ""):
        return "game"
    if role in ("phone", "communication") or VOICE_APPS.search(name):
        return "voice"
    if role in ("event", "notification", "a11y") or SYSTEM.search(name):
        return "system"
    if role in ("music", "video", "movie") or MUSIC_APPS.search(name):
        return "music"
    if BROWSERS.search(name):
        return "browser"
    return "other"


def devices(sinks_json, sources_json="[]", default_sink="", default_source=""):
    """Outputs and inputs: [{index, name, label, volume, mute, default, kind}]. Monitors (the recording side of an
    output) are left out: nobody picks one as a microphone."""
    out = []
    for kind, text, default in (("output", sinks_json, default_sink), ("input", sources_json, default_source)):
        for d in _json(text):
            props = d.get("properties") or {}
            if kind == "input" and (d.get("monitor_source") or props.get("device.class") == "monitor" or
                                    str(d.get("name", "")).endswith(".monitor")):
                continue
            out.append({"index": d.get("index"), "name": d.get("name", ""), "kind": kind,
                        "label": d.get("description") or props.get("device.description") or d.get("name", ""),
                        "volume": percent(d.get("volume")), "mute": bool(d.get("mute")),
                        "default": d.get("name") == default})
    return out


def apps(inputs_json):
    """Apps playing sound: [{index, name, kind, volume, mute, sink, binary}], DecKoOS's own visualizer left out."""
    out = []
    for s in _json(inputs_json):
        props = s.get("properties") or {}
        name = props.get("application.name") or props.get("media.name") or props.get("application.process.binary") \
            or "Something"
        if name == "DecKoOS visualizer":
            continue
        out.append({"index": s.get("index"), "name": name, "kind": kind_of(props), "volume": percent(s.get("volume")),
                    "mute": bool(s.get("mute")), "sink": s.get("sink"),
                    "binary": props.get("application.process.binary", ""),
                    "corked": bool(s.get("corked"))})
    return out


def state():
    """Everything the Sound page shows, read in one go."""
    if DEMO:
        return demo_state()
    info = text(["pactl", "-f", "json", "info"])
    try:
        i = json.loads(info) if info else {}
    except ValueError:
        i = {}
    devs = devices(text(["pactl", "-f", "json", "list", "sinks"]), text(["pactl", "-f", "json", "list", "sources"]),
                   i.get("default_sink_name", ""), i.get("default_source_name", ""))
    return {"devices": devs, "apps": apps(text(["pactl", "-f", "json", "list", "sink-inputs"])),
            "buffer": buffer_now(), "eq": eq_now(), "running": bool(info)}


def demo_state():
    return {"running": True, "buffer": "balanced", "eq": "footsteps",
            "devices": [
                {"index": 62, "name": "a50.game", "kind": "output", "label": "Astro A50 Game", "volume": 60,
                 "mute": False, "default": True},
                {"index": 63, "name": "a50.chat", "kind": "output", "label": "Astro A50 Chat", "volume": 45,
                 "mute": False, "default": False},
                {"index": 66, "name": "analog", "kind": "output", "label": "Speakers (Ryzen HD Audio)", "volume": 76,
                 "mute": False, "default": False},
                {"index": 69, "name": "hdmi", "kind": "output", "label": "LG ULTRAGEAR (HDMI)", "volume": 40,
                 "mute": True, "default": False},
                {"index": 64, "name": "a50.mic", "kind": "input", "label": "Astro A50 microphone", "volume": 80,
                 "mute": False, "default": True}],
            "apps": [
                {"index": 1, "name": "Cyberpunk 2077", "kind": "game", "volume": 100, "mute": False, "sink": 62,
                 "binary": "Cyberpunk2077.exe", "corked": False},
                {"index": 2, "name": "Spotify", "kind": "music", "volume": 55, "mute": False, "sink": 62,
                 "binary": "spotify", "corked": False},
                {"index": 3, "name": "Discord", "kind": "voice", "volume": 90, "mute": False, "sink": 63,
                 "binary": "Discord", "corked": False},
                {"index": 4, "name": "Firefox", "kind": "browser", "volume": 100, "mute": False, "sink": 62,
                 "binary": "firefox", "corked": True}]}


# ------------------------------------------------------------------ volumes and routing

def set_app_volume(index, pct):
    return DEMO or run(["pactl", "set-sink-input-volume", str(int(index)), f"{clamp(pct)}%"]) is not None


def set_kind_volume(kind, pct, current=None):
    """Every app of one kind to the same volume. Returns how many."""
    targets = [a for a in (current if current is not None else state()["apps"]) if a["kind"] == kind]
    for a in targets:
        set_app_volume(a["index"], pct)
    return len(targets)


def set_device_volume(index, pct, kind="output"):
    if DEMO:
        return True
    cmd = "set-sink-volume" if kind == "output" else "set-source-volume"
    return run(["pactl", cmd, str(int(index)), f"{clamp(pct)}%"]) is not None


def set_mute(index, mute, what="app"):
    if DEMO:
        return True
    cmd = {"app": "set-sink-input-mute", "output": "set-sink-mute", "input": "set-source-mute"}[what]
    return run(["pactl", cmd, str(int(index)), "1" if mute else "0"]) is not None


def move_app(index, sink):
    if DEMO:
        return True
    return run(["pactl", "move-sink-input", str(int(index)), str(sink)]) is not None


def set_default(name, kind="output"):
    if DEMO:
        return True
    return run(["pactl", "set-default-sink" if kind == "output" else "set-default-source", name]) is not None


def clamp(pct):
    return max(0, min(150, int(pct)))


# ------------------------------------------------------------------ the buffer

def buffer_conf(name):
    """The PipeWire and pipewire-pulse settings for a buffer floor."""
    q = BUFFERS[name][0]
    pw = ("# Written by DecKoOS (Hub > Sound > Buffer): the smallest buffer apps may ask for\n"
          f"context.properties = {{\n    default.clock.min-quantum = {q}\n}}\n")
    pulse = ("# Written by DecKoOS (Hub > Sound > Buffer): apps using the PulseAudio interface get the same floor\n"
             f"pulse.properties = {{\n    pulse.min.req = {q}/48000\n    pulse.min.quantum = {q}/48000\n"
             f"    pulse.min.frag = {q}/48000\n}}\n")
    return pw, pulse


def buffer_now():
    """The buffer setting in use: the user's file, else DecKoOS's default (shipped in /usr/share)."""
    try:
        m = re.search(r"min-quantum\s*=\s*(\d+)", BUFFER_FILE.read_text())
    except OSError:
        return DEFAULT_BUFFER
    q = int(m.group(1)) if m else 0
    return next((k for k, (v, _, _) in BUFFERS.items() if v == q), DEFAULT_BUFFER)


def set_buffer(name):
    """Keeps the floor in the user's PipeWire config, and applies it now (pw-metadata) without restarting sound."""
    if name not in BUFFERS:
        raise ValueError(f"buffer is one of: {', '.join(BUFFERS)}")
    pw, pulse = buffer_conf(name)
    if DEMO:
        return
    PW_CONF.mkdir(parents=True, exist_ok=True)
    PULSE_CONF.mkdir(parents=True, exist_ok=True)
    BUFFER_FILE.write_text(pw)
    PULSE_BUFFER_FILE.write_text(pulse)
    run(["pw-metadata", "-n", "settings", "0", "clock.min-quantum", str(BUFFERS[name][0])])


# ------------------------------------------------------------------ equalizer

def eq_conf(preset, target):
    """A filter-chain module: an output called DecKoOS EQ whose sound goes through the preset's filters into
    `target` (an output's name)."""
    title, _desc, bands = EQ_PRESETS[preset]
    nodes, links = [], []
    for i, (kind, hz, db, q) in enumerate(bands):
        nodes.append(f'                {{ type = builtin name = eq{i} label = {kind} '
                     f'control = {{ "Freq" = {hz} "Q" = {q} "Gain" = {db} }} }}')
        if i:
            links.append(f'                {{ output = "eq{i - 1}:Out" input = "eq{i}:In" }}')
    return f"""# Written by DecKoOS (Hub > Sound > Equalizer): {title}
# preset={preset} target={target}
context.properties = {{
    log.level = 0
}}
context.spa-libs = {{
    audio.convert.* = audioconvert/libspa-audioconvert
    support.*       = support/libspa-support
}}
context.modules = [
    {{ name = libpipewire-module-rt args = {{ }} flags = [ ifexists nofail ] }}
    {{ name = libpipewire-module-protocol-native }}
    {{ name = libpipewire-module-client-node }}
    {{ name = libpipewire-module-adapter }}
    {{ name = libpipewire-module-filter-chain
        args = {{
            node.description = "DecKoOS EQ ({title})"
            media.name = "DecKoOS EQ"
            filter.graph = {{
                nodes = [
{chr(10).join(nodes)}
                ]
                links = [
{chr(10).join(links)}
                ]
            }}
            audio.channels = 2
            audio.position = [ FL FR ]
            capture.props = {{
                node.name = "{EQ_NODE}"
                media.class = Audio/Sink
            }}
            playback.props = {{
                node.name = "{EQ_NODE}_out"
                node.passive = true
                target.object = "{target}"
            }}
        }}
    }}
]
"""


def eq_now():
    try:
        m = re.search(r"# preset=(\w+)", EQ_FILE.read_text())
        return m.group(1) if m and m.group(1) in EQ_PRESETS else ""
    except OSError:
        return ""


def set_eq(preset, target=None):
    """Turns the equalizer on with a preset (into `target`, else today's default output) and makes it the default
    output, or off with "off" (the default goes back to the device it played into)."""
    if preset != "off" and preset not in EQ_PRESETS:
        raise ValueError(f"preset is one of: {', '.join(EQ_PRESETS)}, off")
    if DEMO:
        return
    before = eq_target()
    if preset == "off":
        EQ_FILE.unlink(missing_ok=True)
        run(["systemctl", "--user", "disable", "--now", "deckos-eq.service"])
        if before:
            run(["pactl", "set-default-sink", before])
        return
    if not target:
        info = text(["pactl", "get-default-sink"]).strip()
        target = info if info and info != EQ_NODE else before
    if not target:
        raise RuntimeError("no output to put the equalizer in front of")
    EQ_FILE.parent.mkdir(parents=True, exist_ok=True)
    EQ_FILE.write_text(eq_conf(preset, target))
    run(["systemctl", "--user", "enable", "deckos-eq.service"])  # back after a restart
    run(["systemctl", "--user", "restart", "deckos-eq.service"], timeout=15)
    for _ in range(20):  # make the equalizer the default output once it's there
        if run(["pactl", "set-default-sink", EQ_NODE]) is not None and EQ_NODE in text(["pactl", "get-default-sink"]):
            break
        time.sleep(0.25)


def eq_target():
    """The output the equalizer plays into, from its file."""
    try:
        m = re.search(r"target=(\S+)", EQ_FILE.read_text())
        return m.group(1) if m else ""
    except OSError:
        return ""


# ------------------------------------------------------------------ dropouts

def dropouts(pw_top_text):
    """{device or app name: dropouts} from `pw-top -b` output, only where there were any. The ERR column counts
    the times a node wasn't ready in time: that's what crackling is."""
    out = {}
    for line in pw_top_text.splitlines():
        cols = line.split()
        if len(cols) < 9 or not cols[1].isdigit() or cols[0] not in ("R", "S", "I", "C"):
            continue
        try:
            err = int(cols[8])
        except ValueError:
            continue
        name = cols[-1]
        if err:
            out[name] = max(out.get(name, 0), err)
    return out


def measure_dropouts(seconds=3):
    return dropouts(text(["pw-top", "-b", "-n", str(max(2, seconds))], timeout=seconds + 5))


def main(argv):
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    try:
        if cmd == "status":
            print(json.dumps(state(), indent=1))
        elif cmd == "kinds":
            for k, n, _ in KINDS:
                print(f"{k}\t{n}")
        elif cmd == "set-kind" and len(args) == 2 and args[0] in KIND_NAMES:
            print(f"{set_kind_volume(args[0], int(args[1]))} app(s)")
        elif cmd == "set-app" and len(args) == 2:
            set_app_volume(int(args[0]), int(args[1]))
        elif cmd == "move-app" and len(args) == 2:
            move_app(int(args[0]), args[1])
        elif cmd == "buffer" and len(args) <= 1:
            if args:
                set_buffer(args[0])
            name = buffer_now()
            print(f"{name}: {BUFFERS[name][2]}")
        elif cmd == "eq" and len(args) <= 2:
            if args:
                set_eq(args[0], args[1] if len(args) > 1 else None)
            print(eq_now() or "off")
        elif cmd == "dropouts":
            found = measure_dropouts(5)
            print("\n".join(f"{n}\t{c}" for n, c in found.items()) or "none")
        else:
            print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
            return 2
    except (ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main([a for a in sys.argv[1:] if a != "--demo"]))
