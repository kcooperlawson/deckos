"""DecKoOS actions: the catalog stays honest (real icons, real commands, real Hub pages), search finds the right
thing, and DecKoOS Assistant only does an action the person confirms."""
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RootFS = ROOT / 'pkg/deckos-settings/rootfs'
sys.path[:0] = [str(RootFS / 'usr/lib/deckos/actions'), str(RootFS / 'usr/lib/deckos/pulse'),
                str(RootFS / 'usr/lib/deckos/assistant')]
import actions  # noqa: E402

CATALOG = RootFS / 'usr/share/deckos/actions.toml'
HUB_PAGES = {'home', 'timeline', 'games', 'display', 'gaming', 'drives', 'aidev', 'system', 'appearance'}
# What an action may start with: a DecKoOS command (checked below), or one of these system ones
SYSTEM_COMMANDS = {'sudo', 'systemctl'}


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.acts = actions.load(CATALOG)

    def test_catalog_is_well_formed(self):
        ids = [a['id'] for a in self.acts]
        self.assertEqual(len(ids), len(set(ids)), 'an id is listed twice')
        raw = tomllib.loads(CATALOG.read_text())['action']
        self.assertEqual(len(raw), len(self.acts), 'an action is missing its id, title or run')
        icons = {p.stem for p in (RootFS / 'usr/share/deckos/icons').glob('*.svg')}
        for a in self.acts:
            with self.subTest(a['id']):
                self.assertIn(a['how'], ('app', 'terminal'))
                self.assertIn(a.get('icon', 'info'), icons, 'not a DecKoOS line icon')
                cmd = a['run'][1] if a['run'][0] == 'sudo' else a['run'][0]
                self.assertTrue(cmd in SYSTEM_COMMANDS or (RootFS / 'usr/bin' / cmd).exists(),
                                f'{cmd} is not a DecKoOS command')
                if a['run'][:2] == ['deckos-hub', '--page']:
                    self.assertIn(a['run'][2], HUB_PAGES)

    def test_search(self):
        def ids(q):
            return [a['id'] for a in actions.find(q, 3, self.acts)]
        self.assertEqual(ids('drive')[0], 'drives-relink')
        self.assertEqual(ids('task manager'), ['sysmon'])
        self.assertIn('game-doctor', ids('game wont start'))
        self.assertEqual(ids('xyzzy'), [])
        self.assertEqual(ids(''), [])

    def test_terminal_actions_stay_open(self):
        a = next(x for x in self.acts if x['id'] == 'update')
        cmd = actions.command(a)
        self.assertIn(cmd[0], ('deckos-terminal', 'konsole'))
        self.assertEqual(cmd[1:4], ['--hold', '-e', 'deckos'])

    def test_unknown_action_is_refused(self):
        with self.assertRaises(KeyError):
            actions.run('rm-everything', self.acts)


class AssistantToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DECKOS_PULSE_USER': self.temp.name + '/u.jsonl',
                                           'DECKOS_PULSE_SYSTEM': self.temp.name + '/s.jsonl',
                                           'DECKOS_ACTIONS': str(CATALOG)})
        self.env.start()
        import assistant
        self.assistant = assistant

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_actions_are_offered_and_need_a_yes(self):
        names = [s['function']['name'] for s in self.assistant.Tools(lambda *_: False).schemas()]
        self.assertIn('do_action', names)
        self.assertIn('what_changed', names)
        with patch.object(actions, 'run') as run:
            said_no = self.assistant.Tools(lambda *_: False).t_do_action('checkup')
            self.assertEqual(said_no, 'the person said no')
            run.assert_not_called()
            self.assertIn('started', self.assistant.Tools(lambda *_: True).t_do_action('checkup'))
            run.assert_called_once_with('checkup')
        self.assertIn('error', self.assistant.Tools(lambda *_: True).t_do_action('format-disk'))

    def test_what_changed_reads_the_timeline(self):
        import pulse
        pulse.emit('update', 'Updated mesa', undo=['deckos', 'undo', '12'], system=True)
        out = self.assistant.Tools(lambda *_: False).t_what_changed()
        self.assertIn('Updated mesa', out)
        self.assertIn('can be undone', out)


if __name__ == '__main__':
    unittest.main()
