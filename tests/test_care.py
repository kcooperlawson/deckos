"""DecKoOS Care: what it says after a crash or a system change, and that it says each thing once in a while."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / 'care'), str(LIB / 'sysdoctor'), str(LIB / 'pulse')]
import care  # noqa: E402
import sysdoctor as sd  # noqa: E402


def crash_line(comm, cmd, uid=1000):
    return json.dumps({'COREDUMP_COMM': comm, 'COREDUMP_CMDLINE': cmd, 'COREDUMP_UID': str(uid),
                       'COREDUMP_SIGNAL_NAME': 'SIGSEGV'})


class CareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = patch.object(care, 'STATE', Path(self.temp.name) / 'care.json')
        self.state.start()
        self.said, self.recorded, self.clock = [], [], [1000.0]
        self.care = care.Care(lambda *a: self.said.append(a), checks=(), uid=1000, now=lambda: self.clock[0],
                              record=lambda kind, title, **kw: self.recorded.append((kind, title)))

    def tearDown(self):
        self.state.stop()
        self.temp.cleanup()

    def test_a_crash_of_yours_is_said_once_an_hour(self):
        self.care.crash(crash_line('Discord', '/opt/discord/Discord --type=renderer'))
        self.assertEqual(len(self.said), 1)
        title, _, button, cmd = self.said[0]
        self.assertIn('closed unexpectedly', title)
        self.assertEqual((button, cmd), ('Why?', ['deckos-sysdoctor']))
        self.care.crash(crash_line('Discord', '/opt/discord/Discord'))
        self.assertEqual(len(self.said), 1)  # quiet for an hour, but still recorded
        self.assertEqual(len(self.recorded), 2)
        self.clock[0] += 3601
        self.care.crash(crash_line('Discord', '/opt/discord/Discord'))
        self.assertEqual(len(self.said), 2)

    def test_others_crashes_and_games_are_not_ours_to_say(self):
        self.care.crash(crash_line('sshd', '/usr/bin/sshd', uid=0))
        self.care.crash(crash_line('EldenRing.exe', 'Z:\\\\EldenRing.exe proton'))
        self.care.crash('not json')
        self.assertEqual(self.said, [])

    def test_after_an_update_the_quick_checks_run(self):
        restart = sd.Finding('restart', sd.WARN, 'Restart to finish an update', 'The kernel was replaced.',
                             fixes=[sd.Fix('Restart now', ['systemctl', 'reboot'])])
        info = sd.Finding('x', sd.INFO, 'fine', 'nothing to do')
        self.care.checks = (lambda: [restart, info],)
        self.care.timeline(json.dumps({'kind': 'theme'}), 'system')
        self.assertEqual(self.said, [])
        self.care.timeline(json.dumps({'kind': 'update', 'title': 'Updated 12 packages'}), 'system')
        self.assertEqual(self.said, [('Restart to finish an update', 'The kernel was replaced.', 'Restart now',
                                      ['systemctl', 'reboot'])])
        self.care.timeline(json.dumps({'kind': 'install'}), 'system')
        self.assertEqual(len(self.said), 1)  # the same finding: quiet for six hours
        self.assertIn(('care', 'Restart to finish an update'), self.recorded)

    def test_a_broken_check_doesnt_stop_the_others(self):
        def broken():
            raise RuntimeError('boom')
        disk = sd.Finding('disk:/', sd.BAD, 'Only 3 GB free', 'Almost full.')
        self.care.check([broken, lambda: [disk]])
        self.assertEqual(self.said[0][:3], ('Only 3 GB free', 'Almost full.', 'Show me'))


if __name__ == '__main__':
    unittest.main()
