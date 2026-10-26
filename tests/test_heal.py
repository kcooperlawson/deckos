"""DecKoOS fixes (heal.py): an AI may only pick a vetted recipe and fill its blanks. Hostile blanks, unknown recipes
and anything touching sudo, polkit, PAM, SSH, passwords or the firewall are refused, and the Assistant runs nothing
the person declines."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / 'heal'), str(LIB / 'assistant')]
import heal  # noqa: E402
import assistant  # noqa: E402

IN_REPOS = {'vlc', 'mesa', 'intel-ucode'}.__contains__
SAMPLES = {'install-package': {'package': 'vlc'}, 'repair-package': {'package': 'mesa'},
           'restart-user-service': {'unit': 'pipewire.service'}, 'restart-system-service': {'unit': 'bluetooth.service'},
           'display-fix-level': {'level': '2'}, 'undo-update': {'snapshot': '42'}}


class RecipeTests(unittest.TestCase):
    def test_every_recipe_plans(self):
        for rid in heal.RECIPES:
            with self.subTest(recipe=rid):
                p = heal.plan(rid, SAMPLES.get(rid, {}), check=IN_REPOS, home='/home/someone')
                self.assertTrue(p['steps'])
                self.assertEqual(p['snapshot'], p['root'] and rid != 'undo-update')

    def test_hostile_blanks(self):
        for rid, values in (('install-package', {'package': 'vlc; rm -rf /'}), ('install-package', {'package': 'yay'}),
                            ('install-package', {'package': '../../etc/shadow'}), ('install-package', {'package': '-Syu'}),
                            ('install-package', {'package': '$(id)'}), ('restart-system-service', {'unit': 'sshd.service'}),
                            ('restart-user-service', {'unit': 'pipewire.service --now'}),
                            ('display-fix-level', {'level': '9'}), ('display-fix-level', {'level': '1 && id'}),
                            ('undo-update', {'snapshot': '-1'}), ('rm-everything', {}),
                            ('skip-network-wait', {'unit': 'x'})):
            with self.subTest(recipe=rid, values=values):
                with self.assertRaises(heal.Refused):
                    heal.plan(rid, values, check=IN_REPOS)

    def test_the_deny_list_is_a_second_wall(self):
        # Even a bad recipe added by mistake can't touch what no fix may
        for step in (['chmod', '777', '/etc/sudoers'], ['cp', 'x', '/etc/polkit-1/rules.d/00.rules'],
                     ['usermod', '-aG', 'wheel', 'mia'], ['curl', 'http://example.com/x'], ['bash', '-c', 'id'],
                     ['systemctl', 'disable', 'firewalld.service'], ['tee', '/home/x/.ssh/authorized_keys']):
            bad = {'title': 'bad', 'why': '', 'params': {}, 'root': True, 'steps': [step]}
            with self.subTest(step=step), patch.dict(heal.RECIPES, {'bad': bad}):
                with self.assertRaises(heal.Refused):
                    heal.plan('bad', {})

    def test_root_fixes_need_root(self):
        p = heal.plan('skip-network-wait', {})
        with patch.object(heal.os, 'geteuid', return_value=1000), self.assertRaises(heal.Refused):
            heal.apply(p)


class AssistantTests(unittest.TestCase):
    def tools(self, answer):
        asked = []
        t = assistant.Tools(confirm=lambda title, detail: asked.append((title, detail)) or answer)
        return t, asked

    def test_offered_to_the_model(self):
        t, _ = self.tools(True)
        names = [s['function']['name'] for s in t.schemas()]
        self.assertIn('use_fix', names)

    def test_refused_fix_never_asks_or_runs(self):
        t, asked = self.tools(True)
        with patch.object(assistant, 'run') as run:
            out = t.call('use_fix', {'fix': 'install-package', 'values': {'package': 'vlc; rm -rf /'}})
        self.assertIn('refused', out)
        self.assertEqual(asked, [])
        run.assert_not_called()

    def test_declined_fix_runs_nothing(self):
        t, asked = self.tools(False)
        with patch.object(assistant, 'run') as run:
            out = t.call('use_fix', {'fix': 'rebuild-font-cache'})
        self.assertEqual(out, 'the person said no')
        self.assertIn('fc-cache -f', asked[0][1])  # they saw the exact command
        run.assert_not_called()

    def test_root_fix_goes_through_pkexec(self):
        t, _ = self.tools(True)
        with patch.object(assistant, 'run', return_value=(0, 'ok')) as run:
            t.call('use_fix', {'fix': 'skip-network-wait'})
        self.assertEqual(run.call_args[0][0][:4], ['pkexec', 'deckos', 'heal', 'apply'])


if __name__ == '__main__':
    unittest.main()
