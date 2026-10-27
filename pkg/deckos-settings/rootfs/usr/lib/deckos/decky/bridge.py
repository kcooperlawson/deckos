"""What DecKoOS's Decky plugin (apps/deckos-decky) shows and changes in Gaming Mode's quick access menu: the game
that's running and its profile, the power profile, sound (output, a slider per kind, the equalizer), Game Doctor's
last finding and the self-test. No Qt and no Decky: the plugin's main.py imports this, so all of it is tested here
(tests/test_decky.py) and works the same on the desktop.

Gaming Mode has no password prompt, so nothing here needs root: everything is the player's own (profiles, power via
power-profiles-daemon, sound via pactl). Root things (updates, undo) stay in the Hub.

    bridge.py snapshot | power PROFILE | profile ID KEY VALUE [NAME] | output NAME | kind KIND PERCENT | eq PRESET|off
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ("sound", "profiles", "gamedoctor", "selftest"):
    sys.path.insert(0, str(HERE.parent / sub))
import profiles  # noqa: E402
import sound  # noqa: E402

MODE_STATE = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "deckos-mode"
POWER = ("performance", "balanced", "power-saver")


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def game_now(path=None):
    """{"id", "name"} of the game workload modes see running, or None."""
    try:
        kv = dict(ln.split("=", 1) for ln in Path(path or MODE_STATE).read_text().splitlines() if "=" in ln)
    except OSError:
        return None
    if kv.get("mode") != "gaming" or not kv.get("game"):
        return None
    return {"id": kv.get("gameid") or kv["game"], "name": kv["game"]}


def power_now():
    out = run(["powerprofilesctl", "get"])
    return out.strip() if out and out.strip() in POWER else ""


def doctor_note():
    """Game Doctor's newest quick exit, as one line, or ""."""
    try:
        import gamedoctor
        import steamfiles
        s = gamedoctor.last_failure()
        name = (steamfiles.game(s["appid"]) or {}).get("name") if s else ""
    except Exception:  # Steam's files are best effort here
        return ""
    if not s:
        return ""
    return f"{name or 'App ' + str(s.get('appid'))} closed after {int(s.get('seconds', 0))} s: open DecKoOS Hub > Games " \
           "> Game Doctor on the desktop to see why."


def selftest_problems():
    try:
        import selftest
        return [f"{r['title']}: {r.get('cause', '')}" for r in selftest.load().get("results", []) if not r.get("ok")]
    except Exception:
        return []


def snapshot():
    """Everything the panel shows, in one call (the plugin asks when the menu opens)."""
    st = sound.state()
    outs = [d for d in st.get("devices", []) if d["kind"] == "output"]
    kinds = {}
    for a in st.get("apps", []):
        kinds.setdefault(a["kind"], []).append(a["volume"])
    game = game_now()
    return {
        "game": game,
        "profile": profiles.load().get(game["id"], {}) if game else {},
        "power": power_now(),
        "outputs": [{"name": d["name"], "label": d["label"], "default": d["default"], "volume": d["volume"]}
                    for d in outs],
        "kinds": [{"id": k, "name": n, "volume": round(sum(kinds[k]) / len(kinds[k]))}
                  for k, n, _ in sound.KINDS if k in kinds],
        "eq": st.get("eq") or "off",
        "eq_presets": [{"id": "off", "name": "Off"}] + [{"id": k, "name": v[0]} for k, v in sound.EQ_PRESETS.items()],
        "doctor": doctor_note(),
        "problems": selftest_problems(),
    }


def set_power(profile):
    if profile not in POWER:
        raise ValueError("power is performance, balanced or power-saver")
    if not shutil.which("powerprofilesctl"):
        raise RuntimeError("power-profiles-daemon isn't installed")
    if run(["powerprofilesctl", "set", profile]) is None:
        raise RuntimeError("power-profiles-daemon didn't take it")


def set_profile(game_id, key, value, name=""):
    """One setting of a game's profile: applies from the next start (and now, for power and Do Not Disturb)."""
    if key not in profiles.FIELDS:
        raise ValueError(f"profile setting is one of: {', '.join(profiles.FIELDS)}")
    if key == "dnd":
        value = value in (True, "true", "1", 1)
    profiles.set_(game_id, key, value, name)
    if key == "power" and value:
        set_power(value)


def set_output(name):
    if not any(d["name"] == name for d in sound.state()["devices"] if d["kind"] == "output"):
        raise ValueError("no such output")
    sound.set_default(name)
    # Move what's playing too: in Gaming Mode the game is already running when you switch
    for a in sound.state()["apps"]:
        sound.move_app(a["index"], name)


def main(argv):
    try:
        if argv[:1] == ["snapshot"]:
            print(json.dumps(snapshot()))
        elif argv[:1] == ["power"] and len(argv) == 2:
            set_power(argv[1])
        elif argv[:1] == ["profile"] and len(argv) in (4, 5):
            set_profile(*argv[1:])
        elif argv[:1] == ["output"] and len(argv) == 2:
            set_output(argv[1])
        elif argv[:1] == ["kind"] and len(argv) == 3:
            sound.set_kind_volume(argv[1], int(argv[2]))
        elif argv[:1] == ["eq"] and len(argv) == 2:
            sound.set_eq(argv[1])
        else:
            print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
            return 2
    except (ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
