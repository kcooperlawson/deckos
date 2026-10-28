"""Moments: Vibes that change with what you're doing. You pick a Vibe for each moment (playing a game, music playing,
morning, day, evening, night; "" keeps whatever is on), and DecKoOS switches when the moment changes. Only on a change:
a Vibe you pick yourself stays until the next one, so it never fights you.

~/.config/deckos/moments.json holds {"on": bool, "pick": {moment: vibe key}}. The user unit deckos-moments runs
`watch` while it's on: every 20 s it reads the workload mode's state file (a game running) and playerctl (music
playing). No Qt; tests/test_vibes.py feeds `moment()` made-up situations.

    moments.py show | set MOMENT KEY|keep | on | off | watch
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CONF = Path.home() / ".config/deckos/moments.json"
MODE_STATE = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "deckos-mode"
MOMENTS = [("game", "Playing a game"), ("music", "Music playing"), ("morning", "Morning (6–11)"),
           ("day", "Day (11–17)"), ("evening", "Evening (17–22)"), ("night", "Night (22–6)")]
NAMES = dict(MOMENTS)


def load(path=None):
    try:
        data = json.loads(Path(path or CONF).read_text())
        pick = {k: v for k, v in (data.get("pick") or {}).items()
                if k in NAMES and isinstance(v, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,30}", v)}
        return {"on": bool(data.get("on")), "pick": pick}
    except (OSError, ValueError, AttributeError):
        return {"on": False, "pick": {}}


def save(data, path=None):
    p = Path(path or CONF)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1))


def time_slot(hour):
    return "morning" if 6 <= hour < 11 else "day" if 11 <= hour < 17 else "evening" if 17 <= hour < 22 else "night"


def moment(gaming, music, hour, pick):
    """The moment that counts now and its Vibe: a game first, then music, then the time of day. A moment with no
    Vibe picked steps aside for the next one. (moment, vibe) or (moment, "") when nothing is picked."""
    for m in [m for m, on in (("game", gaming), ("music", music)) if on] + [time_slot(hour)]:
        if pick.get(m):
            return m, pick[m]
    return time_slot(hour), ""


def gaming_now(path=None):
    try:
        return "mode=gaming" in Path(path or MODE_STATE).read_text()
    except OSError:
        return False


def music_now():
    try:
        out = subprocess.run(["playerctl", "-a", "status"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "Playing" in out.split()


def watch():
    last = None
    while True:
        data = load()
        if not data["on"]:
            return
        now, key = moment(gaming_now(), music_now(), time.localtime().tm_hour, data["pick"])
        # Only when the moment changes: what you picked yourself stays until then
        if now != last:
            last = now
            if key:
                subprocess.run(["deckos", "vibe", "apply", key], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        time.sleep(20)


def main(argv):
    data = load()
    if argv[:1] == ["show"] or not argv:
        print(f"Moments: {'on' if data['on'] else 'off'}")
        for m, name in MOMENTS:
            print(f"  {name:<20} {data['pick'].get(m) or '(keep what is on)'}")
        return 0
    if argv[:1] == ["set"] and len(argv) == 3 and argv[1] in NAMES:
        if argv[2] == "keep":
            data["pick"].pop(argv[1], None)
        elif re.fullmatch(r"[a-z][a-z0-9-]{0,30}", argv[2]):
            data["pick"][argv[1]] = argv[2]
        else:
            print("not a Vibe name", file=sys.stderr)
            return 2
        save(data)
        return 0
    if argv[:1] in (["on"], ["off"]):
        data["on"] = argv[0] == "on"
        save(data)
        subprocess.run(["systemctl", "--user", "enable" if data["on"] else "disable", "--now",
                        "deckos-moments.service"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    if argv[:1] == ["watch"]:
        watch()
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
