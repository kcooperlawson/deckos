"""Made for you (learn.py): what it notices and suggests from what the PC already keeps, and that it keeps nothing but
the suggestions you turned down."""
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/learn'))
import learn  # noqa: E402

DAY = 86400
NOW = 1_800_000_000


def game(appid, gb, last_days=None, installed_days=400, minutes=0):
    return {"appid": appid, "name": f"Game {appid}", "bytes": int(gb * 1024 ** 3), "minutes": minutes,
            "last": NOW - last_days * DAY if last_days is not None else 0, "installed": NOW - installed_days * DAY}


class LearnTests(unittest.TestCase):
    def test_pin_what_you_use(self):
        apps = {"firefox.desktop": (9.0, NOW), "steam.desktop": (8.0, NOW), "rare.desktop": (0.4, NOW)}
        s = learn.suggestions(apps, NOW - 5 * DAY, ["steam.desktop"], [], now=NOW)
        self.assertEqual([x["key"] for x in s], ["pin:firefox.desktop"])
        self.assertEqual(s[0]["run"], ["deckos", "taskbar", "pin", "firefox.desktop"])

    def test_unpin_only_once_kde_has_counted_long_enough(self):
        apps = {"old.desktop": (0.1, NOW - 60 * DAY)}
        self.assertEqual(learn.suggestions(apps, NOW - 10 * DAY, ["old.desktop"], [], now=NOW), [])
        s = learn.suggestions(apps, NOW - 90 * DAY, ["old.desktop", "never.desktop"], [], now=NOW)
        self.assertEqual([x["key"] for x in s], ["unpin:old.desktop", "unpin:never.desktop"])

    def test_big_idle_games_and_nothing_else(self):
        games = [game("1", 120, last_days=200), game("2", 120, last_days=10), game("3", 5, last_days=400),
                 game("4", 40, installed_days=300)]
        s = learn.suggestions({}, 0, [], games, now=NOW)
        self.assertEqual([x["key"] for x in s], ["space:1", "space:4"])
        self.assertIn("Free 120 GB", s[0]["title"])
        self.assertIn("not played", s[1]["detail"])
        self.assertEqual(s[0]["run"], ["steam", "steam://uninstall/1"])

    def test_said_no_stays_no(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "learn.json"
            learn.dismiss("space:1", state)
            no = learn.dismissed(state)
            self.assertEqual([x["key"] for x in learn.suggestions({}, 0, [], [game("1", 120, 200)], now=NOW, no=no)], [])
            learn.forget(state)
            self.assertEqual(learn.dismissed(state), set())

    def test_play_window_and_what_it_noticed(self):
        hours = {19: 5, 20: 4, 21: 2, 9: 1}
        self.assertEqual(learn.window(hours), (18, 22))
        self.assertIsNone(learn.window({20: 1}))
        said = learn.noticed({"a.desktop": (9, NOW)}, [game("7", 50, 1, minutes=600)], hours, now=NOW)
        self.assertEqual([n["icon"] for n in said], ["grid", "gaming", "star"])
        self.assertIn("6 PM and 10 PM", said[1]["text"])
        self.assertIn("(10 h)", said[2]["text"])

    def test_reads_kde_usage_and_can_be_off(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "database"
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE ResourceScoreCache (usedActivity, initiatingAgent, targettedResource, "
                        "scoreType, cachedScore, firstUpdate, lastUpdate)")
            con.executemany("INSERT INTO ResourceScoreCache VALUES (?,?,?,?,?,?,?)",
                            [("a", "x", "applications:firefox.desktop", 0, 7.5, 100, 500),
                             ("b", "x", "applications:firefox.desktop", 0, 3.0, 50, 900),
                             ("a", "x", "file:///home/x", 0, 9.0, 10, 10)])
            con.commit()
            con.close()
            apps, since = learn.app_usage(db)
            self.assertEqual((apps, since), ({"firefox.desktop": (7.5, 900)}, 50))
            conf = Path(d) / "learn.conf"
            self.assertTrue(learn.enabled(conf))
            conf.write_text("on=no\n")
            self.assertFalse(learn.enabled(conf))


if __name__ == '__main__':
    unittest.main()
