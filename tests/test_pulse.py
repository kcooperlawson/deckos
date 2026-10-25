"""DecKoOS Pulse: the timeline, its undo rules and the pacman hook's events, on throwaway files."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos/pulse'))
import pulse  # noqa: E402


class PulseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        d = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'DECKOS_PULSE_USER': str(d / 'user.jsonl'),
                                           'DECKOS_PULSE_SYSTEM': str(d / 'system.jsonl')})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_events_merge_newest_first(self):
        with patch.object(pulse, '_now', return_value=100.0):
            pulse.emit('update', 'Updated 3 packages', system=True)
        with patch.object(pulse, '_now', return_value=200.0):
            pulse.emit('theme', 'Theme: DecKoOS Ember', undo=['deckos', 'theme', 'apply', 'org.deckos.desktop'])
        rows = pulse.entries()
        self.assertEqual([r['title'] for r in rows], ['Theme: DecKoOS Ember', 'Updated 3 packages'])
        self.assertEqual([r['source'] for r in rows], ['user', 'system'])
        self.assertTrue(rows[0]['can_undo'])
        self.assertFalse(rows[1]['can_undo'])

    def test_only_deckos_commands_on_the_list_can_be_undos(self):
        for bad in (['rm', '-rf', '/'], ['deckos', 'update'], ['deckos'], ['bash', '-c', 'deckos theme'],
                    ['deckos', 'theme', 'apply', 'x\nrm -rf /']):
            with self.assertRaises(ValueError):
                pulse.emit('theme', 'x', undo=bad)
        # a hand-edited timeline line can't sneak one in either: it's never offered
        Path(os.environ['DECKOS_PULSE_USER']).write_text(json.dumps(
            {'id': 'abc123', 'time': 1, 'kind': 'theme', 'title': 'evil', 'undo': ['sh', '-c', 'boom']}) + '\n')
        self.assertFalse(pulse.find('abc123')['can_undo'])
        self.assertEqual(pulse.undo('abc123', runner=lambda *a, **k: self.fail('ran it'))[0], False)

    def test_undo_runs_once_and_system_undos_ask_for_the_password(self):
        user = pulse.emit('theme', 'Theme: Ember', undo=['deckos', 'theme', 'apply', 'org.deckos.desktop'])
        system = pulse.emit('update', 'Updated', undo=['deckos', 'undo', '41'], system=True)
        ran = []

        def runner(argv, **_):
            ran.append(argv)
            return subprocess.CompletedProcess(argv, 0, '', '')
        with patch.object(pulse.os, 'geteuid', return_value=1000):
            self.assertTrue(pulse.undo(user['id'], runner)[0])
            self.assertTrue(pulse.undo(system['id'], runner)[0])
            self.assertFalse(pulse.undo(user['id'], runner)[0])  # already undone
        self.assertEqual(ran, [['deckos', 'theme', 'apply', 'org.deckos.desktop'], ['pkexec', 'deckos', 'undo', '41']])
        rows = {r['id']: r for r in pulse.entries()}
        self.assertTrue(rows[user['id']]['undone'])
        self.assertTrue(rows[system['id']]['undone'])

    def test_a_broken_line_doesnt_lose_the_rest(self):
        pulse.emit('theme', 'one')
        with open(os.environ['DECKOS_PULSE_USER'], 'a') as f:
            f.write('{"id": "half-writ')
        pulse.emit('theme', 'two')
        self.assertEqual([r['title'] for r in pulse.entries()], ['two', 'one'])

    def test_the_file_stays_small(self):
        with patch.object(pulse, 'MAX_BYTES', 2000):
            for i in range(200):
                pulse.emit('theme', f'event {i}')
        self.assertLess(Path(os.environ['DECKOS_PULSE_USER']).stat().st_size, 4000)
        self.assertEqual(pulse.entries(1)[0]['title'], 'event 199')

    def test_pacman_events(self):
        k, title, detail, undo = pulse.pacman_event('upgrade', ['deckos-settings', 'mesa', 'linux'], '0.9.4', 57)
        self.assertEqual((k, title, undo), ('update', 'Updated to DecKoOS 0.9.4', ['deckos', 'undo', '57']))
        k, title, _, undo = pulse.pacman_event('install', ['obs-studio'], '', None)
        self.assertEqual((k, title, undo), ('install', 'Installed obs-studio', None))
        _, title, _, _ = pulse.pacman_event('remove', ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(title, 'Removed a, b, c and 2 more')

    def test_when_reads_naturally(self):
        import time
        now = time.mktime((2026, 10, 25, 15, 0, 0, 0, 0, -1))
        self.assertEqual(pulse.when(now - 20, now), 'just now')
        self.assertEqual(pulse.when(now - 600, now), '10 min ago')
        self.assertTrue(pulse.when(now - 3 * 3600, now).startswith('today'))
        self.assertTrue(pulse.when(now - 86400, now).startswith('yesterday'))


if __name__ == '__main__':
    unittest.main()
