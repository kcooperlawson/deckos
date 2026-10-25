"""DecKoOS's Gaming Mode panel: adding it to Steam (once, other shortcuts untouched) and finding real gamepads."""
import importlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(LIB / 'gamedoctor'))


def load_panel():
    spec = importlib.util.spec_from_file_location('deckos_gamepanel', LIB / 'gamepanel/deckos_gamepanel.py')
    mod = importlib.util.module_from_spec(spec)
    with patch.object(sys, 'argv', ['deckos-gamepanel']):
        spec.loader.exec_module(mod)
    return mod


# What /proc/bus/input/devices said on the reference machine: an LED controller that claims to be a joystick,
# and an Xbox controller
DEVICES = '''I: Bus=0003 Vendor=26ce Product=01a2
N: Name="ASRock LED Controller"
H: Handlers=kbd event3 js0

I: Bus=0003 Vendor=045e Product=0b12
N: Name="Microsoft Xbox Controller"
H: Handlers=kbd event22 js1

I: Bus=0011 Vendor=0001 Product=0001
N: Name="AT Translated Set 2 keyboard"
H: Handlers=sysrq kbd event0
'''


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'DECKOS_STEAM_ROOT': str(self.root / 'steam')})
        self.env.start()
        import steamfiles
        self.sf = importlib.reload(steamfiles)
        self.panel = load_panel()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_added_to_steam_once_and_nothing_else_touched(self):
        user = self.root / 'steam/userdata/123'
        (user / 'config').mkdir(parents=True)
        (user / 'config/localconfig.vdf').write_text('"UserLocalConfigStore"\n{\n}\n')
        mine = {'appid': 7, 'AppName': 'Heroic', 'Exe': '"/usr/bin/heroic"', 'tags': {'0': 'Launchers'}}
        self.sf.write_shortcuts(user, [mine])
        with patch.object(self.sf, 'steam_running', return_value=False):
            self.assertIn('added', self.panel.add_to_steam())
            self.assertEqual(self.panel.add_to_steam(), 'already there')
        entries = self.sf.read_shortcuts(user)
        self.assertEqual(entries[0], mine)
        self.assertEqual([e['AppName'] for e in entries], ['Heroic', 'DecKoOS'])
        with patch.object(self.sf, 'steam_running', return_value=True):
            self.assertEqual(self.panel.add_to_steam(), 'Steam is running')

    def test_only_devices_with_an_a_button_are_gamepads(self):
        proc = self.root / 'devices'
        proc.write_text(DEVICES)
        for ev, keys in (('event3', 'c000 0 0 40000001000000 1200000000 c00000000000000 100000800000000 40000010cc00 '
                                    '10168000000000 0'),
                         ('event22', '7cdb000000000000 0 0 0 0')):
            d = self.root / f'sys/{ev}/device/capabilities'
            d.mkdir(parents=True)
            (d / 'key').write_text(keys)
        self.assertEqual(self.panel.gamepads(str(proc), str(self.root / 'sys')), ['/dev/input/event22'])
        self.assertTrue(self.panel.has_key('7cdb000000000000 0 0 0 0', self.panel.BTN_SOUTH))
        self.assertFalse(self.panel.has_key('0', self.panel.BTN_SOUTH))


if __name__ == '__main__':
    unittest.main()
