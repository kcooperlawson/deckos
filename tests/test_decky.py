"""DecKoOS's Decky bridge: the running game, the profile and sound calls, on canned state (never the real system),
and that the plugin committed in deckos-settings is the one in apps/deckos-decky."""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/decky'))


class DeckyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        import bridge
        self.b = importlib.reload(bridge)

    def tearDown(self):
        self.temp.cleanup()

    def test_game_now_from_the_mode_state(self):
        state = self.home / 'deckos-mode'
        self.assertIsNone(self.b.game_now(state))  # no file: no game
        state.write_text("mode=gaming\ngame=Elden Ring\ngameid=1245620\nsince=1\n")
        self.assertEqual(self.b.game_now(state), {"id": "1245620", "name": "Elden Ring"})
        state.write_text("mode=gaming\ngame=Diablo IV\nsince=1\n")  # a game Steam doesn't know: its name is the id
        self.assertEqual(self.b.game_now(state), {"id": "Diablo IV", "name": "Diablo IV"})
        state.write_text("mode=normal\n")
        self.assertIsNone(self.b.game_now(state))

    def test_snapshot_shape_on_demo_sound(self):
        with patch.object(self.b.sound, "DEMO", True), patch.object(self.b, "game_now", lambda: {"id": "1", "name": "G"}), \
                patch.object(self.b.profiles, "load", lambda: {"1": {"power": "performance", "dnd": True}}), \
                patch.object(self.b, "power_now", lambda: "balanced"), patch.object(self.b, "doctor_note", lambda: ""), \
                patch.object(self.b, "selftest_problems", lambda: []):
            s = self.b.snapshot()
        self.assertEqual(s["profile"], {"power": "performance", "dnd": True})
        self.assertEqual([k["id"] for k in s["kinds"]], ["game", "music", "voice", "browser"])
        self.assertEqual(s["eq_presets"][0], {"id": "off", "name": "Off"})
        self.assertTrue(any(o["default"] for o in s["outputs"]))

    def test_profile_and_power_are_checked(self):
        saved = []
        with patch.object(self.b.profiles, "set_", lambda *a: saved.append(a)), \
                patch.object(self.b, "set_power", lambda p: saved.append(("power-now", p))):
            self.b.set_profile("1", "dnd", "true", "G")
            self.b.set_profile("1", "power", "performance", "G")
            with self.assertRaises(ValueError):
                self.b.set_profile("1", "overclock", "max")
        self.assertEqual(saved, [("1", "dnd", True, "G"), ("1", "power", "performance", "G"),
                                 ("power-now", "performance")])
        with self.assertRaises(ValueError):
            self.b.set_power("turbo")

    def test_committed_plugin_matches_its_source(self):
        src, built = ROOT / 'apps/deckos-decky', ROOT / 'pkg/deckos-settings/rootfs/usr/share/deckos/decky/DecKoOS'
        for name in ("plugin.json", "package.json", "main.py"):
            self.assertEqual((src / name).read_text(), (built / name).read_text(), name)
        self.assertIn("DecKoOS", (built / "dist/index.js").read_text())


if __name__ == '__main__':
    unittest.main()
