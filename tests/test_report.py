"""deckos report: what's in it, and that personal details never are."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos/report'))
import deckos_report as report  # noqa: E402


class ScrubTests(unittest.TestCase):
    def test_personal_details_go(self):
        text = ('/home/alex/.config  alex@gamebox  UUID=4C3CACD83CACBDF8  7ca4b8f1-388a-4d5f-b991-c15726e006f3\n'
                'Serial Number: S4EVNX0R123  ether 3c:7c:3f:aa:bb:cc  inet 192.168.1.20  fe80::1c2b:3cff:fe4d:5e6f\n'
                'core.python3.1000.eca0df79973a4a09b81f9cbdddac03d7.933866.zst')
        out = report.scrub(text, user='alex', host='gamebox')
        for secret in ('alex', 'gamebox', '4C3CACD8', '7ca4b8f1', 'S4EVNX0R123', '3c:7c:3f', '192.168', 'fe80',
                       'eca0df79'):
            self.assertNotIn(secret, out)
        self.assertIn('/home/<user>/.config', out)
        self.assertIn('20:13:43', report.scrub('2026-10-25T20:13:43 started', user='alex', host='gamebox'))

    def test_hardware_names_stay(self):
        text = 'NVIDIA GeForce RTX 5070 Ti [10de:2c05]  Intel(R) Core(TM) i9-14900K  microcode: 0x12f  03:00.0 VGA'
        self.assertEqual(report.scrub(text, user='alex', host='gamebox'), text)

    def test_common_names_arent_scrubbed(self):
        # A user called "deckos" mustn't turn every DecKoOS line into <user>
        self.assertIn('deckos', report.scrub('deckos display status', user='deckos', host='deckos'))


class BuildTests(unittest.TestCase):
    def test_a_broken_section_doesnt_stop_the_rest(self):
        def boom():
            raise RuntimeError('no such thing')
        with patch.object(report, 'sections', return_value=[('One', boom), ('Two', lambda: 'fine')]):
            text = report.build()
        self.assertIn('===== One =====\n(no such thing)', text)
        self.assertIn('===== Two =====\nfine', text)

    def test_missing_commands(self):
        self.assertIn("isn't installed", report.run(['deckos-no-such-command']))


if __name__ == '__main__':
    unittest.main()
