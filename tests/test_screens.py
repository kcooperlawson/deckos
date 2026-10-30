"""A soundbar on HDMI is told from a screen (screens.py): HDMI, a sink by that name in HDMI audio, and no physical
size in its EDID. Monitors and TVs (with a size), and a soundbar's name with no sound behind it, stay screens."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/screens'))
import screens  # noqa: E402


def edid(name, w, h):
    e = bytearray(128)
    e[:8] = b'\x00\xff\xff\xff\xff\xff\xff\x00'
    e[21], e[22] = w, h
    e[54:59] = b'\x00\x00\x00\xfc\x00'
    e[59:72] = (name.encode() + b'\n').ljust(13, b' ')
    return bytes(e)


class ScreensTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys, self.proc = Path(self.tmp.name) / 'sys', Path(self.tmp.name) / 'proc'

    def tearDown(self):
        self.tmp.cleanup()

    def output(self, conn, name, w, h, status='connected'):
        d = self.sys / 'class/drm' / f'card1-{conn}'
        d.mkdir(parents=True)
        (d / 'status').write_text(status + '\n')
        (d / 'edid').write_bytes(edid(name, w, h))

    def eld(self, n, name, present=1):
        d = self.proc / 'asound/card1'
        d.mkdir(parents=True, exist_ok=True)
        (d / f'eld#0.{n}').write_text(f'monitor_present\t\t{present}\neld_valid\t\t1\nmonitor_name\t\t{name}\n')

    def test_a_soundbar_beside_real_screens(self):
        self.output('HDMI-A-1', 'SAMSUNG', 0, 0)
        self.output('DP-3', 'Odyssey G70B', 62, 34)
        self.output('HDMI-A-2', 'LG TV', 121, 68)
        for i, n in enumerate(('SAMSUNG', 'Odyssey G70B', 'LG TV')):
            self.eld(i, n)
        self.assertEqual(screens.audio_only(self.sys, self.proc), ['HDMI-A-1'])

    def test_no_sound_or_unplugged_is_left_alone(self):
        self.output('HDMI-A-1', 'SAMSUNG', 0, 0)
        self.eld(0, 'SAMSUNG', present=0)
        self.assertEqual(screens.audio_only(self.sys, self.proc), [])
        self.output('HDMI-A-2', 'Receiver', 0, 0, status='disconnected')
        self.eld(1, 'Receiver')
        self.assertEqual(screens.audio_only(self.sys, self.proc), [])

    def test_edid_reading(self):
        e = edid('SAMSUNG', 0, 0)
        self.assertEqual((screens.edid_size(e), screens.edid_name(e)), ((0, 0), 'SAMSUNG'))
        self.assertIsNone(screens.edid_size(b'\x00' * 10))


if __name__ == '__main__':
    unittest.main()
