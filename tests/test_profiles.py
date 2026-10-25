"""DecKoOS game profiles: what's saved, what's applied when a game starts, and that it all goes back."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / 'profiles'), str(LIB / 'pulse')]
import profiles  # noqa: E402


class FakeSystem:
    """powerprofilesctl and Plasma's Do Not Disturb setting, in memory."""

    def __init__(self, power='balanced', dnd=''):
        self.power, self.dnd, self.calls = power, dnd, []

    def __call__(self, argv):
        self.calls.append(argv)
        out = ''
        if argv[:2] == ['powerprofilesctl', 'get']:
            out = self.power
        elif argv[:2] == ['powerprofilesctl', 'set']:
            self.power = argv[2]
        elif argv[0] == 'kreadconfig6':
            out = self.dnd
        elif argv[0] == 'kwriteconfig6':
            self.dnd = '' if argv[-1] == '--delete' else argv[-1]
        return subprocess.CompletedProcess(argv, 0, out, '')


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        d = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'DECKOS_PROFILES': str(d / 'profiles.json'), 'XDG_RUNTIME_DIR': str(d),
                                           'DECKOS_PULSE_USER': str(d / 'u.jsonl'),
                                           'DECKOS_PULSE_SYSTEM': str(d / 's.jsonl')})
        self.env.start()
        self.which = patch.object(profiles.shutil, 'which', return_value='/usr/bin/powerprofilesctl')
        self.which.start()

    def tearDown(self):
        self.which.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_saving_and_clearing(self):
        profiles.set_('1091500', 'power', 'performance', 'Cyberpunk 2077')
        profiles.set_('1091500', 'dnd', 'true')
        self.assertEqual(profiles.get('1091500', 'power'), 'performance')
        self.assertEqual(profiles.load()['1091500']['name'], 'Cyberpunk 2077')
        with self.assertRaises(ValueError):
            profiles.set_('1091500', 'power', 'turbo')
        with self.assertRaises(ValueError):
            profiles.set_('1091500', 'rgb', 'on')
        profiles.set_('1091500', 'power', '')
        profiles.set_('1091500', 'dnd', False)
        self.assertNotIn('1091500', profiles.load())  # nothing left: no profile at all

    def test_apply_then_restore_puts_everything_back(self):
        profiles.set_('42', 'power', 'performance', 'Game')
        profiles.set_('42', 'dnd', True)
        system = FakeSystem(power='balanced')
        did = profiles.apply('42', 'Game', run=system)
        self.assertEqual(did, ['power: performance', 'do not disturb'])
        self.assertEqual(system.power, 'performance')
        self.assertTrue(system.dnd)
        back = profiles.restore(run=system)
        self.assertEqual(system.power, 'balanced')
        self.assertEqual(system.dnd, '')
        self.assertEqual(back, ['power: balanced', 'notifications back on'])
        self.assertEqual(profiles.restore(run=system), [])  # nothing left to put back

    def test_what_was_already_on_stays_on(self):
        profiles.set_('42', 'power', 'performance')
        profiles.set_('42', 'dnd', True)
        system = FakeSystem(power='performance', dnd='2026-12-31T00:00:00')  # the player had both on already
        self.assertEqual(profiles.apply('42', run=system), [])
        profiles.restore(run=system)
        self.assertEqual((system.power, system.dnd), ('performance', '2026-12-31T00:00:00'))

    def test_no_profile_changes_nothing(self):
        system = FakeSystem()
        self.assertEqual(profiles.apply('999', run=system), [])
        self.assertFalse(any(c[:2] == ['powerprofilesctl', 'set'] or c[0] == 'kwriteconfig6' for c in system.calls))


if __name__ == '__main__':
    unittest.main()
