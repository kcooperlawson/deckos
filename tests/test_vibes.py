"""DecKoOS Vibes: every Vibe is complete and points at things that exist, the visualizer hears the right notes, and
the photos are credited and free to share."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RFS = ROOT / 'pkg/deckos-settings/rootfs'
WALL = RFS / 'usr/share/plasma/wallpapers/org.deckos.vibe/contents'
sys.path.insert(0, str(RFS / 'usr/lib/deckos/vibes'))
import vibes  # noqa: E402
import visualizer as vis  # noqa: E402
import numpy as np  # noqa: E402


class VibesTests(unittest.TestCase):
    def test_every_vibe_is_complete(self):
        for key, v in vibes.VIBES.items():
            with self.subTest(vibe=key):
                self.assertRegex(key, r'^[a-z]+$')
                self.assertTrue((WALL / 'ui' / f"{v['scene'].title()}Scene.qml").exists())
                self.assertIn(v['visualizer'], vibes.VISUALIZERS)
                for c in ('colorA', 'colorB', 'accent'):
                    self.assertRegex(v[c], r'^#[0-9A-F]{6}$')
                self.assertTrue((RFS / 'usr/share/plasma/look-and-feel' / v['theme']).is_dir(), v['theme'])
                self.assertIn(v['corners'], ('sharp', 'default', 'round'))
                self.assertTrue((WALL / 'previews' / f'{key}.jpg').exists(), 'run assets/preview_vibes.py')

    def test_photos_are_credited(self):
        credits = (WALL / 'images/CREDITS.md').read_text()
        for photo in (WALL / 'images').glob('*.jpg'):
            with self.subTest(photo=photo.name):
                line = next((ln for ln in credits.splitlines() if ln.startswith(f'| {photo.name} ')), '')
                self.assertRegex(line, r'CC0|Public domain', 'every photo needs a free licence and its source')

    def test_a_tone_lights_its_own_bar(self):
        t = np.arange(vis.FRAME) / vis.RATE
        an = vis.Analyser()
        for _ in range(10):
            levels = an.feed(np.sin(2 * np.pi * 440 * t))
        loudest = int(np.argmax(levels))
        lo, hi = vis.edges()[loudest]
        freqs = np.fft.rfftfreq(vis.FRAME, 1 / vis.RATE)
        self.assertTrue(freqs[lo] - 40 <= 440 <= freqs[hi - 1] + 40)
        self.assertLess(sorted(levels)[-3], 0.5)  # and not the others

    def test_silence_and_wire_format(self):
        an = vis.Analyser()
        self.assertEqual(vis.Analyser.rms(np.zeros(vis.FRAME)), 0)
        frame = vis.encode(an.feed(np.zeros(vis.FRAME)))
        self.assertEqual(len(frame), vis.BARS)
        self.assertEqual(max(frame), 0)

    def test_games_stop_the_listening(self):
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='-mode') as f:
            f.write('game=1245620\n')
            f.flush()
            self.assertTrue(vis.gaming(f.name))
        self.assertFalse(vis.gaming('/nonexistent'))

    def test_qml_property_names(self):
        # QML refuses a property named with a capital letter, and the whole wallpaper (or widget) then fails to
        # load: the Vibe wallpaper was black on the first try that way (roles are read through `model` instead)
        for f in (RFS / 'usr/share/plasma').rglob('*.qml'):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                with self.subTest(file=f.name, line=n):
                    self.assertNotRegex(line, r'^\s*(required |readonly )*property \w+ [A-Z]\w*')

    def test_visualizer_is_local_only(self):
        src = (RFS / 'usr/lib/deckos/vibes/visualizer.py').read_text()
        self.assertIn('QHostAddress.LocalHost', src)
        self.assertNotIn('QHostAddress.Any', src)


if __name__ == '__main__':
    unittest.main()
