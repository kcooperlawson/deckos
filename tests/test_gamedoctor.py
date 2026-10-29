"""Game Doctor: Steam's files read and written faithfully, failed launches found, fixes undone cleanly.
Everything runs against a fake Steam folder; the real one is never touched."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/gamedoctor'))

CONFIG = '''"InstallConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"Accounts"\t\t"x"
\t\t\t}
\t\t}
\t}
}
'''
LOCAL = '''"UserLocalConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"apps"
\t\t\t\t{
\t\t\t\t\t"42"
\t\t\t\t\t{
\t\t\t\t\t\t"LaunchOptions"\t\t"-skipintro \\"quoted\\""
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
'''


class GameDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'config').mkdir()
        (root / 'config/config.vdf').write_text(CONFIG)
        (root / 'userdata/1/config').mkdir(parents=True)
        (root / 'userdata/1/config/localconfig.vdf').write_text(LOCAL)
        (root / 'steamapps/compatdata/42/pfx').mkdir(parents=True)
        (root / 'steamapps/appmanifest_42.acf').write_text('"AppState"\n{\n\t"name"\t\t"Test Game"\n\t"installdir"\t\t"Test"\n}\n')
        (root / 'steamapps/libraryfolders.vdf').write_text('"libraryfolders"\n{\n}\n')
        (root / 'logs').mkdir()
        os.environ['DECKOS_STEAM_ROOT'], os.environ['XDG_STATE_HOME'] = str(root), str(root / 'state')
        for mod in ('steamfiles', 'gamedoctor'):
            sys.modules.pop(mod, None)
        import gamedoctor
        import steamfiles
        self.sf, self.gd, self.root = steamfiles, gamedoctor, root
        steamfiles.steam_running = lambda: False
        steamfiles.start_steam = lambda url=None: None

    def tearDown(self):
        self.tmp.cleanup()

    def test_vdf_round_trip_keeps_escapes(self):
        data = self.sf.read(self.root / 'userdata/1/config/localconfig.vdf')
        self.assertEqual(self.sf.loads(self.sf.dumps(data)), data)
        self.assertEqual(self.sf.launch_options(42), '-skipintro "quoted"')

    def test_quick_exits_are_found_and_long_sessions_ignored(self):
        (self.root / 'logs/console_log.txt').write_text(
            '[2026-10-24 15:00:00] Game process added : AppID 42 "x"\n'
            '[2026-10-24 15:00:04] Game process removed: AppID 42 "x"\n'
            '[2026-10-24 15:01:00] Game process added : AppID 7 "x"\n'
            '[2026-10-24 15:30:00] Game process removed: AppID 7 "x"\n')
        self.gd.LOGS = self.root / 'logs'
        sessions = self.gd.sessions(self.gd.LOGS / 'console_log.txt')
        self.assertEqual([(s['appid'], s['seconds']) for s in sessions], [('42', 4.0), ('7', 1740.0)])
        quick = [s for s in sessions if s['seconds'] < self.gd.QUICK]
        self.assertEqual([s['appid'] for s in quick], ['42'])

    def test_rules(self):
        cases = {'err:module:import_dll Library MSVCP140.dll (needed by game.exe) not found': 'missing-dll',
                 'EasyAntiCheat: Launch Error': 'anticheat',
                 'wine: Unhandled page fault on read access': 'crash',
                 'vkCreateDevice failed': 'vulkan'}
        for line, rule in cases.items():
            self.assertEqual(self.gd.diagnose([line])[0]['id'], rule, line)
        self.assertEqual(self.gd.diagnose([])[0]['id'], 'unknown')
        self.assertEqual(self.gd.diagnose(['EasyAntiCheat: Launch Error'])[0]['fixes'], [])  # nothing to offer

    def test_launch_option_fixes_undo_independently(self):
        self.gd.apply('wined3d', '42')
        self.gd.apply('no-fsync', '42')
        self.gd.undo('wined3d', '42')
        options = self.sf.launch_options(42)
        self.assertIn('PROTON_NO_FSYNC=1', options)
        self.assertNotIn('WINED3D', options)
        self.assertIn('-skipintro', options)
        self.gd.undo('no-fsync', '42')
        self.assertNotIn('PROTON_', self.sf.launch_options(42))
        self.assertEqual(self.gd.applied('42'), [])

    def test_prefix_reset_keeps_the_old_one_and_brings_it_back(self):
        self.gd.apply('prefix-reset', '42')
        compat = self.root / 'steamapps/compatdata'
        self.assertFalse((compat / '42').exists())
        (compat / '42/pfx').mkdir(parents=True)  # Proton made a new one
        self.gd.undo('prefix-reset', '42')
        self.assertTrue((compat / '42/pfx').exists())
        self.assertEqual(len(list(compat.glob('42.deckos-fresh-*'))), 1)  # the fresh one is kept too

    def test_rules_ignore_names_and_good_news(self):
        # "Resynced" holds "esync", and fsync running is fine: neither is a sync problem
        lines = ['[2026-10-28 21:13:45] chdir "/games/Assassin\'s Creed Black Flag Resynced"',
                 'fsync: up and running.']
        self.assertNotIn('sync', [f['id'] for f in self.gd.diagnose(lines)])
        self.assertEqual(self.gd.diagnose(['fsync: futex_waitv not supported'])[0]['id'], 'sync')

    def test_a_windows_drive_gets_its_prefixes_moved_home_and_back(self):
        line = ("OSError: [Errno 22] Invalid argument: '../drive_c' -> "
                "'/mnt/SSD/SteamLibrary/steamapps/compatdata/3751950/pfx//dosdevices/c:'")
        found = self.gd.diagnose([line])
        self.assertEqual(found[0]['id'], 'ntfs-prefix')
        self.assertEqual(found[0]['fixes'], ['prefix-home'])
        self.gd.PREFIXES = self.root / 'home-prefixes'
        compat = self.root / 'steamapps/compatdata'
        self.gd.apply('prefix-home', '42')
        self.assertTrue(compat.is_symlink())
        self.assertTrue((compat / '42/pfx').is_dir())  # through the link, on the "Linux drive"
        with self.assertRaises(RuntimeError):
            self.gd.apply('prefix-home', '42')  # once is enough
        self.gd.undo('prefix-home', '42')
        self.assertFalse(compat.is_symlink())
        self.assertTrue((compat / '42/pfx').is_dir())
        self.assertEqual(self.gd.applied('42'), [])

    def test_a_drive_without_links_is_left_alone(self):
        self.gd.PREFIXES = self.root / 'home-prefixes'
        compat = self.root / 'steamapps/compatdata'
        real = Path.symlink_to
        def refuse(path, *a, **k):
            raise OSError(22, 'Invalid argument')
        asked = []
        self.gd.admin = lambda args: asked.append(args) or 126  # the password prompt was dismissed
        Path.symlink_to = refuse
        try:
            with self.assertRaises(RuntimeError):
                self.gd.apply('prefix-home', '42')
        finally:
            Path.symlink_to = real
        self.assertTrue((compat / '42/pfx').is_dir())  # nothing moved
        self.assertFalse(compat.is_symlink())
        self.assertEqual(self.gd.applied('42'), [])
        self.assertEqual(asked, [['drives', 'prefixes', str(self.root), 'on']])  # the mount was offered

    def test_a_drive_without_links_gets_the_mount_and_it_comes_off(self):
        asked = []
        self.gd.admin = lambda args: asked.append(args) or 0
        real = Path.symlink_to
        def refuse(path, *a, **k):
            raise OSError(22, 'Invalid argument')
        Path.symlink_to = refuse
        try:
            self.gd.apply('prefix-home', '42')
        finally:
            Path.symlink_to = real
        self.assertEqual(self.gd.applied('42')[0]['mount'], str(self.root))
        self.gd.undo('prefix-home', '42')
        self.assertEqual(asked[-1], ['drives', 'prefixes', str(self.root), 'off'])
        self.assertEqual(self.gd.applied('42'), [])

    def test_writes_keep_a_backup(self):
        self.gd.apply('wined3d', '42')
        self.assertTrue((self.root / 'userdata/1/config/localconfig.vdf.deckos-bak').exists())


if __name__ == '__main__':
    unittest.main()
