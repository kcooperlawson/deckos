"""DecKoOS Hub's settings search: everything leads somewhere real, and everyday words find the right place."""
import sys
import tempfile
import unittest
from pathlib import Path

HUB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos/hub'
sys.path.insert(0, str(HUB))
import hub_settings as hs  # noqa: E402

ICONS = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/share/deckos/icons'
PAGES = {"home", "timeline", "games", "display", "gaming", "drives", "aidev", "system", "appearance", "more"}


class SettingsIndexTests(unittest.TestCase):
    def test_every_entry_leads_somewhere(self):
        for e in hs.entries():
            with self.subTest(title=e["title"]):
                kind, target = e["go"]
                self.assertIn(kind, ("hub", "plasma", "action"))
                if kind == "hub":
                    self.assertIn(target, PAGES)
                if kind == "plasma":
                    self.assertRegex(target, r"^kcm_[a-z_-]+$")
                self.assertTrue((ICONS / f"{e['icon']}.svg").exists(), e["icon"])

    def test_everyday_words(self):
        for query, title in (("vrr", "Gaming Mode"), ("bluetooth", "Bluetooth"), ("night light", "Night Light"),
                             ("mouse speed", "Mouse"), ("wifi", "Wi-Fi and network connections"),
                             ("undo update", "Snapshots and undo"), ("shortcut", "Keyboard shortcuts"),
                             ("ollama", "Local AI"), ("accent", "Theme and colours")):
            with self.subTest(query=query):
                self.assertEqual(hs.search(query)[0]["title"], title)

    def test_every_word_must_match(self):
        self.assertEqual(hs.search("bluetooth printer"), [])
        self.assertEqual(hs.search("   "), [])

    def test_missing_panels_are_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "systemsettings").mkdir()
            (root / "systemsettings" / "kcm_bluetooth.so").touch()
            self.assertTrue(hs.installed_kcm("kcm_bluetooth", root))
            self.assertFalse(hs.installed_kcm("kcm_printer_manager", root))


if __name__ == '__main__':
    unittest.main()
