"""DecKoOS Sounds: every sound assets/sounds.py defines is in the theme, and DecKoOS uses it by default.
(The .oga files aren't compared byte for byte: Vorbis output can differ between ffmpeg versions.)"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'pkg/deckos-settings/rootfs/usr/share/sounds/deckos'


class SoundThemeTests(unittest.TestCase):
    def names(self):
        text = (ROOT / 'assets/sounds.py').read_text()
        body = text[text.index('    return {', text.index('def sounds():')):]
        return re.findall(r'^        "([a-z-]+)":', body, re.M)

    def test_every_sound_is_generated(self):
        names = self.names()
        self.assertGreater(len(names), 40)
        for name in names:
            with self.subTest(name=name):
                self.assertGreater((THEME / 'stereo' / f'{name}.oga').stat().st_size, 1000)

    def test_theme_falls_back_and_is_the_default(self):
        index = (THEME / 'index.theme').read_text()
        self.assertIn('Inherits=ocean', index)  # anything not drawn here comes from Plasma's sounds
        self.assertIn('Example=theme-demo', index)
        self.assertRegex((ROOT / 'pkg/deckos-settings/kdeglobals.base').read_text(), r'\[Sounds\]\nTheme=deckos')


if __name__ == '__main__':
    unittest.main()
