"""Kid mode's home: the panels a child may have, the themes, and DecKoOS's own games (played by the rules, on a fake
screen; nothing touches the real desktop)."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos"
sys.path[:0] = [str(LIB / "kids"), str(LIB / "hub"), str(LIB / "gamepanel")]

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

APP = QApplication.instance() or QApplication(["test"])
import deckos_kids  # noqa: E402
import kids  # noqa: E402
import kids_games  # noqa: E402
import kids_themes  # noqa: E402


class PanelTests(unittest.TestCase):
    def test_only_kid_widgets_pass(self):
        ok = deckos_kids.kid_panels_ok
        self.assertTrue(ok([["org.deckos.taskbar", "org.kde.plasma.volume", "org.kde.plasma.digitalclock"]]))
        # The full DecKoOS panel (its menu shows every app), on any screen, means the kid layout goes back on
        self.assertFalse(ok([["org.deckos.taskbar"], ["org.deckos.menu", "org.deckos.taskbar"]]))
        self.assertFalse(ok([["org.deckos.taskbar", "org.kde.plasma.systemtray"]]))
        self.assertFalse(ok([]))  # no panel: their tiles' taskbar is missing

    def test_new_children_start_with_the_kid_look(self):
        self.assertIn("LookAndFeelPackage=org.deckos.kids", kids.KIOSK)
        lnf = LIB.parent.parent / "share/plasma/look-and-feel/org.deckos.kids/contents/layouts"
        self.assertIn('loadTemplate("org.deckos.layout.kids")',
                      (lnf / "org.kde.plasma.desktop-layout.js").read_text())


class DesktopTests(unittest.TestCase):
    TILES = [{"id": "org.kde.kolourpaint", "name": "Paint", "icon": "kolourpaint", "exec": "kolourpaint %U"},
             {"id": "game:snes/Mario World.sfc", "name": "Mario", "icon": "", "exec": "",
              "argv": ["retroarch", "-L", "/usr/lib/libretro/snes9x.so", "/srv/deckos-kids/games/snes/Mario World.sfc"]}]

    def test_launchers_for_games_and_apps(self):
        e = kids.desktop_entries(self.TILES)
        self.assertEqual(list(e), ["deckos-kids-games.desktop", "deckos-kid-org-kde-kolourpaint.desktop",
                                   "deckos-kid-game-snes-mario-world-sfc.desktop"])
        self.assertIn("Exec=kolourpaint\n", e["deckos-kid-org-kde-kolourpaint.desktop"])  # no %U on a launcher
        self.assertIn('"/srv/deckos-kids/games/snes/Mario World.sfc"', e["deckos-kid-game-snes-mario-world-sfc.desktop"])
        self.assertNotIn("deckos-kids-games.desktop", kids.desktop_entries(self.TILES, games_on=False))

    def test_sync_keeps_the_childs_own_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home / "Desktop").mkdir()
            (home / "Desktop/my-drawing.desktop").write_text("[Desktop Entry]\nName=Mine\n")  # theirs: stays
            pins = kids.sync_desktop(home, kids.desktop_entries(self.TILES))
            self.assertEqual(pins[0], "applications:deckos-kids-games.desktop")
            paint = home / "Desktop/deckos-kid-org-kde-kolourpaint.desktop"
            self.assertTrue(paint.exists() and paint.stat().st_mode & 0o111)  # starts without asking
            # The parent takes Paint away: Kid mode's launcher goes, the child's own file stays
            kids.sync_desktop(home, kids.desktop_entries(self.TILES[1:]))
            self.assertFalse(paint.exists())
            self.assertFalse((home / ".local/share/applications/deckos-kid-org-kde-kolourpaint.desktop").exists())
            self.assertTrue((home / "Desktop/my-drawing.desktop").exists())

    def test_kid_panel_has_the_time_widget(self):
        layout = (LIB.parent.parent / "share/plasma/layout-templates/org.deckos.layout.kids/contents/layout.js").read_text()
        self.assertIn('"org.deckos.kidtime"', layout)
        self.assertIn("org.deckos.kidtime", deckos_kids.KID_WIDGETS)


class ThemeTests(unittest.TestCase):
    def test_every_theme_paints(self):
        img = QImage(640, 400, QImage.Format_ARGB32)
        for tid in kids_themes.THEMES:
            p = QPainter(img)
            kids_themes.Scene(tid).paint(p, QRectF(0, 0, 640, 400), 5)
            p.end()
            t = kids_themes.theme(tid)
            self.assertEqual(t["id"], tid)
            self.assertGreaterEqual(len(t["tiles"]), 6)

    def test_unknown_theme_falls_back(self):
        self.assertEqual(kids_themes.theme("nonsense")["id"], kids_themes.DEFAULT)
        self.assertEqual(kids.DEFAULTS["theme"], kids_themes.DEFAULT)
        # deckos kids theme only takes these (its own list, in bash)
        self.assertIn("space|ocean|dinos|castle|rainbow",
                      (LIB.parent.parent / "bin/deckos").read_text())
        self.assertEqual(set(kids_themes.THEMES), {"space", "ocean", "dinos", "castle", "rainbow"})


class GameTests(unittest.TestCase):
    def test_memory_pairs_stay_and_misses_turn_back(self):
        g = kids_games.MemoryMatch("space")
        g.resize(1280, 800)
        g.start()
        pics = [c["pic"] for c in g.cards]
        self.assertTrue(all(pics.count(x) == 2 for x in pics))  # six pairs
        a = 0
        b = next(i for i in range(1, 12) if pics[i] == pics[a])
        miss = next(i for i in range(1, 12) if pics[i] != pics[a])
        g.turn(a)
        g.turn(miss)
        self.assertEqual(g.moves, 1)
        for _ in range(31):
            g.step()  # a second to look, then they turn back
        self.assertFalse(g.cards[a]["up"] or g.cards[miss]["up"])
        g.turn(a)
        g.turn(b)
        self.assertTrue(g.cards[a]["done"] and g.cards[b]["done"])
        g.turn(a)  # a found pair can't be turned again
        self.assertEqual(g.turned, [])

    def test_bubbles_pop_by_wand(self):
        g = kids_games.BubblePop("ocean")
        g.resize(1280, 800)
        g.start()
        g.bubbles = [{"x": 400, "y": 300, "r": 50, "v": 0, "phase": 0, "who": "🐱", "hue": "#7AB8FF"}]
        g.wand = QPointF(400, 300)
        g.key(Qt.Key_Return)
        self.assertEqual((g.score, g.bubbles), (1, []))
        g.key(Qt.Key_Left)
        self.assertEqual(g.wand.x(), 340)

    def test_back_leaves_the_game(self):
        g = kids_games.make("bubbles", "space")
        left = []
        g.back.connect(lambda: left.append(1))
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        g.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        self.assertEqual(left, [1])


if __name__ == "__main__":
    unittest.main()
