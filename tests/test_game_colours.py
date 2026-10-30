"""While a game runs the desktop wears its colours (vibes/gamecolours.py): the art's most colourful hue and a second
one far enough round the wheel, bright enough for an edge; grey art gives nothing. And the session card's time."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RFS = ROOT / 'pkg/deckos-settings/rootfs'
sys.path.insert(0, str(RFS / 'usr/lib/deckos/vibes'))
import gamecolours as gc  # noqa: E402


class GameColoursTests(unittest.TestCase):
    def test_two_hues_from_the_art(self):
        art = [(220, 90, 40)] * 600 + [(40, 90, 220)] * 300 + [(30, 30, 30)] * 700
        a, b = gc.pick(art)
        self.assertRegex(a, r'^#[0-9A-F]{6}$')
        ra, ga, ba = (int(a[i:i + 2], 16) for i in (1, 3, 5))
        rb, gb, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(ra, ba)  # the orange first: there's more of it
        self.assertGreater(bb, rb)

    def test_one_hue_gets_a_partner(self):
        a, b = gc.pick([(200, 40, 40)] * 900)
        self.assertNotEqual(a, b)

    def test_grey_art_gives_nothing(self):
        self.assertIsNone(gc.pick([(120, 120, 120)] * 1600))

    def test_session_time(self):
        lib = subprocess.run(['bash', '-c', 'n=$(grep -n "^case " "$1" | tail -1 | cut -d: -f1); '
                              'source <(head -n $((n-1)) "$1"); for s in 20 1500 4320; do game_time $s; done',
                              '_', str(RFS / 'usr/bin/deckos')], capture_output=True, text=True, timeout=30)
        self.assertEqual(lib.stdout.split('\n')[:3], ['under a minute', '25 min', '1 h 12 min'])


if __name__ == '__main__':
    unittest.main()
