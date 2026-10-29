"""DecKoOS Context: what you're doing right now (gaming, watching, developing, listening, away, on the desktop),
worked out on this PC from what's running, and what DecKoOS changes because of it. Design: docs/context.md.

Senses every 15 s from /proc, playerctl, logind and the workload mode's state file; `classify()` turns those facts
into (activity, confidence, why) and is a plain function the tests feed. Reactions are switches in
~/.config/deckos/context.json; whatever they change is recorded on the timeline. No Qt.

    context.py now [--json] | set ACTIVITY [MINUTES] | auto | watch | react NAME on|off
"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vibes"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktopenv"))
import desktopenv  # noqa: E402
try:
    import pulse
except ImportError:  # the timeline is a nice-to-have here
    pulse = None

# activity: (name shown, DecKoOS line icon)
ACTIVITIES = {"gaming": ("Gaming", "gaming"), "watching": ("Watching", "play"), "away": ("Away", "clock"),
              "developing": ("Developing", "code"), "listening": ("Listening", "volume"),
              "desktop": ("On the desktop", "appearance")}
CHOOSABLE = ["watching", "developing", "listening", "away", "desktop"]  # gaming belongs to workload modes

EDITORS = {"code", "codium", "code-oss", "cursor", "zed", "zeditor", "nvim", "vim", "emacs", "kate", "kwrite",
           "deckos-editor", "idea", "pycharm", "clion", "rustrover", "goland", "webstorm", "godot", "hx", "helix",
           "sublime_text", "kdevelop", "qtcreator", "android-studio"}
BUILDERS = {"cargo", "rustc", "make", "ninja", "cmake", "gcc", "g++", "cc1", "cc1plus", "clang", "clang++", "go",
            "javac", "gradle", "mvn", "tsc", "webpack", "makepkg", "pytest", "meson", "mold", "dotnet", "zig"}
VIDEO_PLAYERS = {"mpv", "vlc", "celluloid", "haruna", "totem", "smplayer", "kodi", "jellyfin", "plex", "freetube",
                 "dragonplayer", "showtime"}
VIDEO_SITES = re.compile(r"youtube\.com/(watch|shorts|live)|youtu\.be/|tiktok\.com/|twitch\.tv/|netflix\.com/"
                         r"|disneyplus\.com/|primevideo\.com/|max\.com/|crunchyroll\.com/|vimeo\.com/"
                         r"|\.(mp4|mkv|webm|avi|mov)$", re.I)
MUSIC_SITES = re.compile(r"music\.youtube\.com|open\.spotify\.com|soundcloud\.com|bandcamp\.com|deezer\.com"
                         r"|tidal\.com|music\.apple\.com", re.I)
BROWSERS = {"firefox", "chromium", "chrome", "brave", "vivaldi", "edge", "msedge", "librewolf", "zen", "opera",
            "plasma-browser-integration"}

INTERVAL = 15
HOLD = 2  # looks in a row before a new activity counts
EDITOR_TICKS = 3  # CPU ticks (1/100 s) an editor must use between looks to count as worked in
AWAY_MINUTES = 10

CONF = Path.home() / ".config/deckos/context.json"
DEFAULT_REACT = {"moments": True, "power": True, "quiet": False, "welcome": True, "vibe": True}
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
STATE = RUNTIME / "deckos-context"
MODE_STATE = RUNTIME / "deckos-mode"
PROC = Path(os.environ.get("DECKOS_PROC", "/proc"))


@dataclass
class Facts:
    gaming: str = ""  # the game's name, when one runs
    video: str = ""  # the player or site
    music: str = ""  # "Artist - Title" or the player
    idle_minutes: float = 0
    builders: list = field(default_factory=list)
    editors: list = field(default_factory=list)  # editors that used the CPU since the last look


def classify(f):
    """(activity, confidence 0..1, why: short phrases). The first that applies wins; see docs/context.md."""
    if f.gaming:
        return "gaming", 0.95, [f"playing {f.gaming}"]
    if f.video:
        return "watching", 0.85, [f"video playing in {f.video}"]
    if f.idle_minutes >= AWAY_MINUTES:
        return "away", 0.9, [f"no keyboard or mouse for {int(f.idle_minutes)} minutes"]
    if f.builders:
        why = [f"{', '.join(sorted(set(f.builders))[:3])} running"]
        if f.editors:
            why.append(f"working in {f.editors[0]}")
        return "developing", 0.9, why
    if f.editors:
        why = [f"working in {f.editors[0]}"]
        if f.music:
            why.append("music on")
        return "developing", 0.65, why
    if f.music:
        return "listening", 0.85, [f"playing {f.music}"]
    return "desktop", 0.5, ["nothing in particular"]


# ---------------------------------------------------------------- sensing

def processes(proc=None):
    """{pid: (name, CPU ticks so far)} from /proc."""
    out = {}
    for d in (proc or PROC).iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / "stat").read_text()
        except OSError:
            continue
        # "pid (name) state ...": the name can hold spaces and brackets, so split at the last ")"
        name = stat[stat.index("(") + 1:stat.rindex(")")]
        rest = stat[stat.rindex(")") + 2:].split()
        try:
            out[int(d.name)] = (name, int(rest[11]) + int(rest[12]))
        except (IndexError, ValueError):
            continue
    return out


def busy_editors(before, now):
    """Editors that used at least EDITOR_TICKS of CPU between two looks (one left open in the background doesn't)."""
    used = {}
    for pid, (name, ticks) in now.items():
        if name in EDITORS and pid in before:
            used[name] = used.get(name, 0) + ticks - before[pid][1]
    return sorted((n for n, t in used.items() if t >= EDITOR_TICKS), key=lambda n: -used[n])


def players(run=None):
    """[(player, status, artist, title, url, album)] from playerctl, or []."""
    run = run or _run
    out = run(["playerctl", "-a", "metadata", "--format",
               "{{playerName}}\x1f{{status}}\x1f{{artist}}\x1f{{title}}\x1f{{xesam:url}}\x1f{{album}}"])
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 6:
            rows.append(tuple(parts))
    return rows


def media(rows):
    """(video, music) from players(): what's playing, said plainly."""
    video = music = ""
    for player, status, artist, title, url, album in rows:
        if status != "Playing":
            continue
        base = player.split(".")[0].lower()
        # A browser playing something with no album, off the music sites, is a video far more often than a song
        browser_video = base in BROWSERS and not album and not MUSIC_SITES.search(url)
        if base in VIDEO_PLAYERS or (VIDEO_SITES.search(url) and not MUSIC_SITES.search(url)) or browser_video:
            video = video or (player.split(".")[0] if base in VIDEO_PLAYERS else "your browser")
        else:
            music = music or (f"{artist} - {title}" if artist and title else title or player.split(".")[0])
    return video, music


def idle_minutes(run=None):
    run = run or _run
    out = run(["loginctl", "show-session", "auto", "-p", "IdleHint", "-p", "IdleSinceHintMonotonic"])
    v = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    if v.get("IdleHint") != "yes":
        return 0
    try:
        since = int(v.get("IdleSinceHintMonotonic", "0")) / 1e6
        return max(0, (time.monotonic() - since) / 60)
    except ValueError:
        return 0


def game_now(path=None):
    try:
        v = dict(line.split("=", 1) for line in Path(path or MODE_STATE).read_text().splitlines() if "=" in line)
    except OSError:
        return ""
    return (v.get("game") or "a game") if v.get("mode") == "gaming" else ""


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def sense(before, now, run=None):
    video, music = media(players(run))
    return Facts(gaming=game_now(), video=video, music=music, idle_minutes=idle_minutes(run),
                 builders=sorted({n for n, _t in now.values() if n in BUILDERS}),
                 editors=busy_editors(before, now))


# ---------------------------------------------------------------- the person's say

def conf(path=None):
    try:
        data = json.loads(Path(path or CONF).read_text())
    except (OSError, ValueError):
        data = {}
    react = {k: bool((data.get("react") or {}).get(k, v)) for k, v in DEFAULT_REACT.items()}
    pin = data.get("pin") or {}
    if not (isinstance(pin, dict) and pin.get("activity") in CHOOSABLE and float(pin.get("until", 0)) > time.time()):
        pin = {}
    return {"on": data.get("on", True) is not False, "react": react, "pin": pin}


def save_conf(data, path=None):
    p = Path(path or CONF)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1))


def decide(facts, pin, now=None):
    """The activity counting now: a game always; else your own pick while it lasts; else what it sensed."""
    act, conf_, why = classify(facts)
    if act != "gaming" and pin:
        mins = max(1, int((float(pin["until"]) - (now or time.time())) / 60))
        return pin["activity"], 1.0, [f"you picked it (for {mins} more min)"]
    return act, conf_, why


class Steady:
    """A new activity counts after HOLD looks in a row; a game or your own pick counts at once."""

    def __init__(self):
        self.current, self.seen, self.count = None, None, 0

    def feed(self, activity, at_once=False):
        if activity == self.current:
            self.seen, self.count = None, 0
            return False
        if activity != self.seen:
            self.seen, self.count = activity, 0
        self.count += 1
        if at_once or self.current is None or self.count >= HOLD:
            self.current, self.seen, self.count = activity, None, 0
            return True
        return False


# ---------------------------------------------------------------- reactions

class Reactions:
    """What DecKoOS changes when the activity changes, each behind its switch, each put back after."""

    def __init__(self, run=None, spawn=None):
        self.run = run or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=30))
        # for what waits on the person (the Vibe mode offer): started and left to it, with the session's display
        # as it is now (this service can have started before Plasma set it)
        self.spawn = spawn or (lambda argv: subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                             start_new_session=True, env=desktopenv.env()))
        self.power_before = ""
        self.quiet = False
        self.game_since = 0.0
        self.built_during_game = set()

    def change(self, old, new, facts, react):
        did = []
        if old == "gaming" and new != "gaming":
            if react["welcome"]:
                self.welcome_back(facts)
        if new == "gaming":
            self.game_since = time.time()
            self.built_during_game = set(facts.builders)
        did += self.power(new, facts, react)
        did += self.notifications(new, react)
        if react["moments"]:
            self.moments(new)
        if new == "listening" and react["vibe"]:
            self.spawn(["deckos-music", "--offer"])  # a notification with a Vibe mode button; nothing without a yes
        return did

    def tick(self, activity, facts, react):
        """Between changes: power follows the build itself (it can end while you're still developing)."""
        if activity == "gaming":
            self.built_during_game |= set(facts.builders)
        return self.power(activity, facts, react)

    def power(self, activity, facts, react):
        building = react["power"] and activity == "developing" and bool(facts.builders)
        if building and not self.power_before:
            before = self.run(["powerprofilesctl", "get"]).stdout.strip()
            if before and before != "performance" and self.run(["powerprofilesctl", "set", "performance"]).returncode == 0:
                self.power_before = before
                return ["power to performance while it builds"]
        elif not building and self.power_before:
            self.run(["powerprofilesctl", "set", self.power_before])
            back, self.power_before = self.power_before, ""
            return [f"power back to {back}"]
        return []

    def notifications(self, activity, react):
        want = react["quiet"] and activity == "developing"
        if want and not self.quiet:
            until = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 12 * 3600))
            if self.run(["kwriteconfig6", "--file", "plasmanotifyrc", "--group", "DoNotDisturb", "--key", "Until",
                         until]).returncode == 0:
                self.quiet = True
                return ["notifications quiet while you work"]
        elif not want and self.quiet:
            self.run(["kwriteconfig6", "--file", "plasmanotifyrc", "--group", "DoNotDisturb", "--key", "Until",
                      "--delete"])
            self.quiet = False
            return ["notifications back on"]
        return []

    def moments(self, activity):
        try:
            import moments
        except ImportError:
            return
        data = moments.load()
        if not data["on"]:
            return
        _m, key = moments.for_activity(activity, time.localtime().tm_hour, data["pick"])
        if key:
            self.run(["deckos", "vibe", "apply", key])

    def welcome_back(self, facts):
        """One notification after a game: how long, and what happened meanwhile (from the timeline)."""
        text = welcome_text(time.time() - self.game_since, timeline_since(self.game_since),
                            sorted(self.built_during_game - set(facts.builders)))
        if text:
            self.run(["notify-send", "-a", "DecKoOS", "-i", "deckos", "Welcome back", text])


QUIET_KINDS = {"game-start", "game-stop", "context", "profile", "mode", "vibe"}


def timeline_since(since):
    if not pulse:
        return []
    try:
        return [e for e in pulse.entries(100) if e["time"] >= since and e["kind"] not in QUIET_KINDS]
    except (OSError, ValueError):
        return []


def welcome_text(seconds, events, builds_done):
    """'You played for 2 h 5 min. Meanwhile: …' or "" when it was short and nothing happened."""
    if seconds < 30 * 60 and not events and not builds_done:
        return ""
    h, m = int(seconds // 3600), int(seconds % 3600 // 60)
    lines = [f"You played for {f'{h} h ' if h else ''}{m} min."]
    news = [f"{', '.join(builds_done)} finished" if builds_done else ""]
    news += [e["title"] for e in events[:3]]
    if len(events) > 3:
        news.append(f"and {len(events) - 3} more on the timeline")
    news = [n for n in news if n]
    if news:
        lines.append("Meanwhile: " + "; ".join(news) + ".")
    return " ".join(lines)


# ---------------------------------------------------------------- state for everyone else

def write_state(activity, confidence, why, pinned):
    STATE.write_text(f"activity={activity}\nlabel={ACTIVITIES[activity][0]}\nicon={ACTIVITIES[activity][1]}\n"
                     f"confidence={confidence:.2f}\nwhy={'; '.join(why)}\npinned={1 if pinned else 0}\n")
    subprocess.run(["busctl", "--user", "emit", "/org/deckos/Context", "org.deckos.Context", "Changed", "s",
                    activity], capture_output=True, timeout=5, check=False)


def record(activity, did):
    if pulse and did:
        try:
            pulse.emit("context", f"{ACTIVITIES[activity][0]}: {', '.join(did)}", app="Context")
        except (OSError, ValueError):
            pass


def watch():
    steady, reactions = Steady(), Reactions()
    before = processes()
    current = None
    while True:
        time.sleep(INTERVAL)
        c = conf()
        if not c["on"]:
            STATE.unlink(missing_ok=True)
            reactions.power("desktop", Facts(), c["react"])
            reactions.notifications("desktop", c["react"])
            return
        now = processes()
        facts = sense(before, now)
        before = now
        activity, confidence, why = decide(facts, c["pin"])
        if steady.feed(activity, at_once=activity == "gaming" or bool(c["pin"])):
            did = reactions.change(current, activity, facts, c["react"])
            current = activity
        else:
            did = reactions.tick(current, facts, c["react"])
        record(current, did)
        write_state(current, confidence, why, bool(c["pin"]))


def main(argv):
    cmd = argv[0] if argv else "now"
    c = conf()
    if cmd == "now":
        try:
            state = dict(line.split("=", 1) for line in STATE.read_text().splitlines() if "=" in line)
        except OSError:
            state = {}
        if "--json" in argv:
            print(json.dumps(state))
        elif state:
            print(f"{state['label']} ({state['why']})")
        else:
            print("not following yet (deckos-context.service isn't running)")
        return 0
    if cmd == "set" and len(argv) in (2, 3) and argv[1] in CHOOSABLE:
        minutes = int(argv[2]) if len(argv) == 3 and argv[2].isdigit() else 60
        data = json.loads(CONF.read_text()) if CONF.exists() else {}
        data["pin"] = {"activity": argv[1], "until": time.time() + max(1, min(minutes, 24 * 60)) * 60}
        save_conf(data)
        print(f"{ACTIVITIES[argv[1]][0]} for {minutes} min")
        return 0
    if cmd == "auto":
        data = json.loads(CONF.read_text()) if CONF.exists() else {}
        data.pop("pin", None)
        save_conf(data)
        print("following what you do again")
        return 0
    if cmd in ("on", "off"):
        data = json.loads(CONF.read_text()) if CONF.exists() else {}
        data["on"] = cmd == "on"
        save_conf(data)
        subprocess.run(["systemctl", "--user", "enable" if cmd == "on" else "disable", "--now",
                        "deckos-context.service"], capture_output=True, check=False)
        return 0
    if cmd == "react" and len(argv) == 3 and argv[1] in DEFAULT_REACT and argv[2] in ("on", "off"):
        data = json.loads(CONF.read_text()) if CONF.exists() else {}
        data.setdefault("react", {})[argv[1]] = argv[2] == "on"
        save_conf(data)
        return 0
    if cmd == "watch":
        watch()
        return 0
    if cmd == "status":  # key=value for quick-status
        print(f"ctxon={1 if c['on'] else 0}")
        for k, v in c["react"].items():
            print(f"ctx_{k}={1 if v else 0}")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
