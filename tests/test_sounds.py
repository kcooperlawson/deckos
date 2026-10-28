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
        body = text[text.index('    return {', text.index('def sounds(')):]
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

    def test_each_vibe_has_the_whole_set_on_its_instruments(self):
        names = self.names()
        for scene in ('lofi', 'neon', 'midnight', 'cozy'):
            kit = THEME.with_name(f'deckos-{scene}')
            with self.subTest(scene=scene):
                self.assertIn('Inherits=deckos', (kit / 'index.theme').read_text())
                self.assertEqual(sorted(p.stem for p in (kit / 'stereo').glob('*.oga')), sorted(set(names)))

    def test_boot_tint_mixes_into_the_slate(self):
        import subprocess
        tool = ROOT / 'pkg/deckos-settings/rootfs/usr/bin/deckos'
        fn = re.search(r'^boot_tint\(\) \{.*?^\}', tool.read_text(), re.M | re.S).group(0)
        out = subprocess.run(['bash', '-c', fn + '\nboot_tint "#FFFFFF" 0; echo; boot_tint "#FFFFFF" 1'],
                             capture_output=True, text=True).stdout.split('\n')
        self.assertEqual(out[:2], ['0.059, 0.067, 0.082', '1.000, 1.000, 1.000'])


if __name__ == '__main__':
    unittest.main()
