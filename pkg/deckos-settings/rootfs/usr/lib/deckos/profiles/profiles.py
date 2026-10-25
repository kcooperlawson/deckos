"""DecKoOS game profiles: what a game gets while it runs, set once per game. Workload modes apply it when the game
starts and put everything back when it stops (no root: everything here is the player's own).

A profile (~/.config/deckos/game-profiles.json, keyed by Steam App ID or, for other games, the name):
  power     "performance" | "balanced" | "power-saver" | ""   power-profiles-daemon while playing
  dnd       true | false                                      Do Not Disturb while playing
  ollama    "unload" | "keep" | ""                            local AI models, instead of the workload-mode setting
  docker    "pause" | "keep" | ""                             Docker containers, the same
"" (or no key) means "as usual".

    profiles.py apply ID [NAME]    profiles.py restore    profiles.py get ID KEY
    profiles.py set ID KEY VALUE [NAME]    profiles.py list [--json]
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
try:
    import pulse
except ImportError:
    pulse = None

FIELDS = {"power": ("performance", "balanced", "power-saver", ""), "dnd": (True, False),
          "ollama": ("unload", "keep", ""), "docker": ("pause", "keep", "")}


def config_file():
    return Path(os.environ.get("DECKOS_PROFILES") or
                Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "deckos/game-profiles.json")


def runtime_file():
    return Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "deckos-profile.json"


def load():
    try:
        data = json.loads(config_file().read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


def get(game_id, key):
    return load().get(str(game_id), {}).get(key, "")


def set_(game_id, key, value, name=""):
    if key not in FIELDS:
        raise ValueError(f"profiles have no {key}")
    if key == "dnd":
        value = value in (True, "true", "1", "on", "yes")
    if value not in FIELDS[key]:
        raise ValueError(f"{key} can't be {value}")
    data = load()
    p = data.setdefault(str(game_id), {})
    if name:
        p["name"] = name
    if value in ("", False):
        p.pop(key, None)
    else:
        p[key] = value
    if not any(k in p for k in FIELDS):
        data.pop(str(game_id), None)  # nothing left: no profile
    save(data)


# ---- applying (what the system calls are, in one place, so tests swap them)

def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(argv, 127, "", "")


def power_now(run=_run):
    if not shutil.which("powerprofilesctl"):
        return ""
    return run(["powerprofilesctl", "get"]).stdout.strip()


def dnd_until(run=_run):
    return run(["kreadconfig6", "--file", "plasmanotifyrc", "--group", "DoNotDisturb", "--key", "Until"]).stdout.strip()


def apply(game_id, name="", run=_run):
    """Applies the game's profile and remembers what to put back. Returns what it did (sentences)."""
    p = load().get(str(game_id), {})
    back, did = {"game": str(game_id), "name": name or p.get("name", "")}, []
    if p.get("power") and shutil.which("powerprofilesctl"):
        before = power_now(run)
        if before and before != p["power"] and run(["powerprofilesctl", "set", p["power"]]).returncode == 0:
            back["power"] = before
            did.append(f"power: {p['power']}")
    if p.get("dnd") and not dnd_until(run):
        # Plasma watches this setting (Quick Settings' tile uses it too): on for 12 hours, or until put back
        until = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 12 * 3600))
        if run(["kwriteconfig6", "--file", "plasmanotifyrc", "--group", "DoNotDisturb", "--key", "Until",
                until]).returncode == 0:
            back["dnd"] = True
            did.append("do not disturb")
    runtime_file().write_text(json.dumps(back))
    if did and pulse:
        try:
            pulse.emit("profile", f"Profile for {back['name'] or game_id}: {', '.join(did)}", app="Game profiles")
        except (OSError, ValueError):
            pass
    return did


def restore(run=_run):
    """Puts back what apply() changed (also after a crash: the runtime file says what)."""
    try:
        back = json.loads(runtime_file().read_text())
    except (OSError, ValueError):
        return []
    did = []
    if back.get("power"):
        run(["powerprofilesctl", "set", back["power"]])
        did.append(f"power: {back['power']}")
    if back.get("dnd"):
        run(["kwriteconfig6", "--file", "plasmanotifyrc", "--group", "DoNotDisturb", "--key", "Until", "--delete"])
        did.append("notifications back on")
    runtime_file().unlink(missing_ok=True)
    return did


def main(argv):
    try:
        if argv[:1] == ["apply"] and len(argv) >= 2:
            print("; ".join(apply(argv[1], " ".join(argv[2:]))))
        elif argv == ["restore"]:
            print("; ".join(restore()))
        elif argv[:1] == ["get"] and len(argv) == 3:
            print(get(argv[1], argv[2]))
        elif argv[:1] == ["set"] and len(argv) >= 4:
            set_(argv[1], argv[2], argv[3], " ".join(argv[4:]))
        elif argv[:1] == ["list"]:
            data = load()
            print(json.dumps(data, ensure_ascii=False) if "--json" in argv else
                  "\n".join(f"{k}  {v.get('name', '')}  {', '.join(f'{f}={v[f]}' for f in FIELDS if f in v)}"
                            for k, v in data.items()))
        else:
            print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
            return 2
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
