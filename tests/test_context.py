"""DecKoOS Context: what you're doing, from made-up facts, and what it changes (with a fake runner)."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos"
sys.path.insert(0, str(LIB / "context"))
sys.path.insert(0, str(LIB / "vibes"))
import context  # noqa: E402
import moments  # noqa: E402
from context import Facts  # noqa: E402

REACT = {"moments": False, "power": True, "quiet": True, "welcome": True, "vibe": False}


class Runner:
    """Records commands; powerprofilesctl get says `balanced`."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        out = "balanced\n" if argv[:2] == ["powerprofilesctl", "get"] else ""
        return subprocess.CompletedProcess(argv, 0, out, "")


class ClassifyTests(unittest.TestCase):
    def test_order(self):
        everything = Facts(gaming="Hades", video="mpv", music="x", idle_minutes=30, builders=["cargo"], editors=["code"])
        self.assertEqual(context.classify(everything)[0], "gaming")
        self.assertEqual(context.classify(Facts(video="mpv", idle_minutes=30))[0], "watching")
        self.assertEqual(context.classify(Facts(idle_minutes=12, builders=["make"]))[0], "away")
        self.assertEqual(context.classify(Facts(builders=["cargo"], music="x"))[0], "developing")
        self.assertEqual(context.classify(Facts(editors=["nvim"], music="x"))[0], "developing")
        self.assertEqual(context.classify(Facts(music="Nujabes - Aruarian Dance"))[0], "listening")
        self.assertEqual(context.classify(Facts())[0], "desktop")

    def test_says_why(self):
        act, conf, why = context.classify(Facts(builders=["rustc", "cargo"], editors=["code"]))
        self.assertEqual(why, ["cargo, rustc running", "working in code"])
        self.assertGreater(conf, 0.8)

    def test_a_pick_wins_but_not_over_a_game(self):
        pin = {"activity": "listening", "until": time.time() + 600}
        self.assertEqual(context.decide(Facts(builders=["make"]), pin)[0], "listening")
        self.assertEqual(context.decide(Facts(gaming="Hades"), pin)[0], "gaming")


class SensingTests(unittest.TestCase):
    def test_processes_from_proc(self):
        with tempfile.TemporaryDirectory() as tmp:
            for pid, name, ut, st in ((12, "cargo", 50, 10), (13, "Web Content (x)", 1, 1)):
                d = Path(tmp) / str(pid)
                d.mkdir()
                (d / "stat").write_text(f"{pid} ({name}) S 1 1 1 0 -1 0 0 0 0 0 {ut} {st} 0 0 20 0 1 0\n")
            (Path(tmp) / "self").mkdir()
            self.assertEqual(context.processes(Path(tmp)), {12: ("cargo", 60), 13: ("Web Content (x)", 2)})

    def test_an_editor_counts_only_when_used(self):
        before = {1: ("code", 100), 2: ("kate", 50), 3: ("nvim", 10)}
        now = {1: ("code", 140), 2: ("kate", 51), 3: ("nvim", 14), 4: ("zed", 900)}  # zed: new, no baseline
        self.assertEqual(context.busy_editors(before, now), ["code", "nvim"])

    def test_media(self):
        rows = [("spotify", "Playing", "Nujabes", "Aruarian Dance", "", "Modal Soul"),
                ("firefox.instance1", "Playing", "", "Video", "https://www.youtube.com/watch?v=x", ""),
                ("vlc", "Paused", "", "film", "file:///a.mkv", "")]
        self.assertEqual(context.media(rows), ("your browser", "Nujabes - Aruarian Dance"))
        self.assertEqual(context.media([("mpv", "Playing", "", "a", "", "")]), ("mpv", ""))
        # Shorts in Firefox (what this PC really reported), and music in a browser
        self.assertEqual(context.media([("firefox", "Playing", "Roadside Ryder", "Tire #fyp",
                                         "https://www.youtube.com/shorts/vIUwtusOr28", "")])[0], "your browser")
        self.assertEqual(context.media([("chromium", "Playing", "Daft Punk", "One More Time",
                                         "https://music.youtube.com/watch?v=x", "")]), ("", "Daft Punk - One More Time"))

    def test_players_parse(self):
        out = "spotify\x1fPlaying\x1fA\x1fB\x1f\x1fC\nbroken line\n"
        self.assertEqual(context.players(lambda argv: out), [("spotify", "Playing", "A", "B", "", "C")])


class SteadyTests(unittest.TestCase):
    def test_holds_before_changing(self):
        s = context.Steady()
        self.assertTrue(s.feed("desktop"))  # the first look counts
        self.assertFalse(s.feed("listening"))
        self.assertFalse(s.feed("desktop"))  # a blip resets it
        self.assertFalse(s.feed("listening"))
        self.assertTrue(s.feed("listening"))
        self.assertTrue(s.feed("gaming", at_once=True))


class ReactionTests(unittest.TestCase):
    def test_power_while_building_then_back(self):
        run = Runner()
        r = context.Reactions(run)
        self.assertEqual(r.change("desktop", "developing", Facts(builders=["cargo"]), REACT)[0],
                         "power to performance while it builds")
        self.assertIn(["powerprofilesctl", "set", "performance"], run.calls)
        self.assertEqual(r.tick("developing", Facts(editors=["code"]), REACT), ["power back to balanced"])
        self.assertEqual(run.calls[-1], ["powerprofilesctl", "set", "balanced"])

    def test_quiet_while_developing(self):
        run = Runner()
        r = context.Reactions(run)
        self.assertIn("notifications quiet while you work", r.change("desktop", "developing", Facts(), REACT))
        self.assertIn("notifications back on", r.change("developing", "listening", Facts(), REACT))
        self.assertEqual(run.calls[-1][-1], "--delete")

    def test_music_offers_vibe_mode_once(self):
        started = []
        r = context.Reactions(Runner(), spawn=started.append)
        on = dict(REACT, vibe=True)
        r.change("desktop", "listening", Facts(music="Nujabes - Aruarian Dance"), on)
        r.change("listening", "desktop", Facts(), on)
        self.assertEqual(started, [["deckos-music", "--offer"]])  # only on the way into listening
        r.change("desktop", "listening", Facts(music="x"), dict(on, vibe=False))
        self.assertEqual(len(started), 1)

    def test_switches_off_do_nothing(self):
        run = Runner()
        off = {k: False for k in REACT}
        self.assertEqual(context.Reactions(run).change("desktop", "developing", Facts(builders=["make"]), off), [])
        self.assertEqual(run.calls, [])

    def test_welcome_back(self):
        events = [{"title": "3 packages updated"}, {"title": "Firefox crashed"}]
        self.assertEqual(context.welcome_text(2 * 3600 + 300, events, ["cargo"]),
                         "You played for 2 h 5 min. Meanwhile: cargo finished; 3 packages updated; Firefox crashed.")
        self.assertEqual(context.welcome_text(600, [], []), "")  # short, and nothing happened
        self.assertIn("and 2 more", context.welcome_text(3600, [{"title": str(i)} for i in range(5)], []))


class ConfTests(unittest.TestCase):
    def test_defaults_and_expired_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "context.json"
            self.assertEqual(context.conf(p)["react"], context.DEFAULT_REACT)
            p.write_text('{"on": false, "pin": {"activity": "listening", "until": 1}, "react": {"quiet": true}}')
            c = context.conf(p)
            self.assertFalse(c["on"])
            self.assertEqual(c["pin"], {})
            self.assertTrue(c["react"]["quiet"])
            p.write_text('{"pin": {"activity": "gaming", "until": 9999999999}}')  # gaming can't be picked
            self.assertEqual(context.conf(p)["pin"], {})


class MomentsTests(unittest.TestCase):
    def test_for_activity(self):
        pick = {"work": "midnight", "music": "neon", "evening": "lofi"}
        self.assertEqual(moments.for_activity("developing", 20, pick), ("work", "midnight"))
        self.assertEqual(moments.for_activity("listening", 20, pick), ("music", "neon"))
        self.assertEqual(moments.for_activity("watching", 20, pick), ("evening", "lofi"))  # none picked: the hour
        self.assertEqual(moments.for_activity("desktop", 12, pick), ("day", ""))


if __name__ == "__main__":
    unittest.main()
