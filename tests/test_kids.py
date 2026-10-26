"""Kid mode: children's settings, their tiles, time left, and what their home gets. Never touches real accounts."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos/kids'


class KidsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'apps').mkdir()
        for app, extra in (('org.kde.kolourpaint', ''), ('steam', ''), ('firefox', ''), ('hidden', 'NoDisplay=true\n')):
            (root / 'apps' / f'{app}.desktop').write_text(
                f'[Desktop Entry]\nType=Application\nName={app.title()}\nIcon={app}\nExec={app} %U\n{extra}')
        os.environ['DECKOS_KIDS_DIR'] = str(root / 'conf')
        os.environ['DECKOS_KIDS_STATE'] = str(root / 'state')
        os.environ['DECKOS_KIDS_GAMES'] = str(root / 'shared')
        os.environ['DECKOS_APPS_DIRS'] = str(root / 'apps')
        sys.path.insert(0, str(LIB))
        sys.modules.pop('kids', None)
        import kids
        self.k = kids
        self.root = root

    def tearDown(self):
        os.environ.pop('DECKOS_KIDS_DIR')
        os.environ.pop('DECKOS_KIDS_STATE')
        os.environ.pop('DECKOS_KIDS_GAMES')
        os.environ.pop('DECKOS_APPS_DIRS')
        self.tmp.cleanup()

    def test_names(self):
        for good in ('mia', 'leo2', 'ana-b'):
            self.assertTrue(self.k.valid_name(good))
        for bad in ('Mia', '1mia', 'root', 'a', 'mia; rm -rf /', '../x', ''):
            self.assertFalse(self.k.valid_name(bad), bad)

    def test_apps_and_tiles(self):
        apps = self.k.installed_apps()
        self.assertNotIn('hidden', apps)
        self.assertEqual(apps['steam']['exec'], 'steam')  # %U is dropped
        self.assertIn('deckos-kids-browser', apps)  # the web tile when Firefox is there
        self.assertEqual(self.k.suggested(apps), ['org.kde.kolourpaint', 'deckos-kids-browser'])
        self.k.write_conf('mia', {'display': 'Mia', 'apps': 'deckos-kids-browser,org.kde.kolourpaint,gone'})
        self.assertEqual([a['id'] for a in self.k.approved('mia', apps)], ['deckos-kids-browser', 'org.kde.kolourpaint'])
        self.k.write_conf('mia', {**self.k.read_conf('mia'), 'web': 'off'})
        self.assertEqual([a['id'] for a in self.k.approved('mia', apps)], ['org.kde.kolourpaint'])
        self.assertEqual([k['name'] for k in self.k.kids()], ['mia'])

    def loginctl(self, active=True, locked=False, user='mia'):
        def run(cmd):
            if cmd[1] == 'list-sessions':
                return f"7 1001 {user} seat0 4242 user tty3 no -\n2 1000 dad seat0 99 user tty2 no -\n"
            return f"Active={'yes' if active else 'no'}\nType=wayland\nLockedHint={'yes' if locked else 'no'}\n"
        return run

    def test_time_service_counts_only_on_screen_and_ends_sessions(self):
        self.k.write_conf('mia', {'display': 'Mia', 'minutes': '2'})
        ended = []
        self.k.step(run=self.loginctl(active=False), end=ended.append)  # switched away: not counted
        self.assertEqual(self.k.minutes_used(self.k.state_file('mia')), 0)
        self.k.step(run=self.loginctl(locked=True), end=ended.append)  # locked: not counted
        self.assertEqual(self.k.minutes_used(self.k.state_file('mia')), 0)
        for _ in range(2):  # the whole limit: "time's up" shows, the session goes on for the minute of grace
            self.k.step(run=self.loginctl(), end=ended.append)
        self.assertEqual(ended, [])
        self.k.step(run=self.loginctl(), end=ended.append)
        self.assertEqual(ended, ['mia'])
        self.assertEqual(self.k.week('mia')[-1][1], 3)

    def test_not_a_child_isnt_watched(self):
        ended = []
        self.k.step(run=self.loginctl(user='dad'), end=ended.append)
        self.assertEqual(ended, [])

    def test_shared_games(self):
        lib = self.root / 'lib/nes'
        lib.mkdir(parents=True)
        (lib / 'Super Mario Bros. (USA).nes').write_bytes(b'NES\x1a' + bytes(40000))
        (lib / 'Kirby (USA).nes').write_bytes(b'NES\x1a' + bytes(40000))
        self.assertEqual(self.k.sync_games([lib / 'Super Mario Bros. (USA).nes']), 1)
        tiles = self.k.shared_games()
        self.assertEqual([t['name'] for t in tiles], ['Super Mario Bros.'])
        self.assertIn('retroarch', tiles[0]['argv'][0])
        self.k.sync_games([])  # nothing ticked: nothing shared
        self.assertEqual(self.k.shared_games(), [])

    def test_time_left(self):
        at = lambda h, m: time.struct_time((2026, 10, 25, h, m, 0, 6, 298, 0))  # noqa: E731
        conf = dict(self.k.DEFAULTS)
        self.assertIsNone(self.k.time_left(conf, 500, at(12, 0)))
        conf['minutes'] = '60'
        self.assertEqual(self.k.time_left(conf, 20, at(12, 0)), 40)
        self.assertEqual(self.k.time_left(conf, 90, at(12, 0)), 0)
        conf['bedtime'] = '19:30'
        self.assertEqual(self.k.time_left(conf, 20, at(19, 0)), 30)  # bedtime comes first
        self.assertEqual(self.k.time_left(conf, 0, at(21, 0)), 0)
        self.assertEqual(self.k.time_left(conf, 0, at(2, 0)), 0)  # the middle of the night is after bedtime

    def test_minutes_add_up_per_day(self):
        f = self.root / 'state.json'
        self.k.add_minutes(f, 1, today='2026-10-25')
        self.k.add_minutes(f, 1, today='2026-10-25')
        self.assertEqual(self.k.minutes_used(f, today='2026-10-25'), 2)
        self.assertEqual(self.k.minutes_used(f, today='2026-10-26'), 0)

    def test_presets_are_sane(self):
        for age, (minutes, bed, vol) in self.k.PRESETS.items():
            self.assertTrue(0 < minutes <= 240 and 10 <= vol <= 100, age)
            self.assertRegex(bed, r'^\d{2}:\d{2}$')

    def test_children_cant_shut_down(self):
        rule = (LIB.parents[2] / 'share/polkit-1/rules.d/49-deckos-kids.rules').read_text()
        self.assertIn('isInGroup("deckos-kids")', rule)
        for action in ('power-off', 'reboot', 'suspend', 'hibernate'):
            self.assertIn(action, rule)

    def test_home_gets_kiosk_and_filtered_firefox(self):
        home = self.root / 'home'
        self.k.seed(home, 'mia', 'filtered')
        self.assertIn('shell_access=false', (home / '.config/kdeglobals').read_text())
        self.assertIn('offerShutdown=false', (home / '.config/ksmserverrc').read_text())
        self.assertIn('deckos-kids --session', (home / '.config/autostart/deckos-kids.desktop').read_text())
        prefs = (home / '.mozilla/firefox/kidmode.default/user.js').read_text()
        self.assertIn(self.k.FAMILY_DOH, prefs)
        self.assertIn('"network.trr.mode", 3', prefs)
        self.k.seed(home, 'mia', 'open')
        self.assertNotIn('trr', (home / '.mozilla/firefox/kidmode.default/user.js').read_text())


if __name__ == '__main__':
    unittest.main()
