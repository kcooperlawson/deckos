"""DeckOS Move In: finding what a Windows install has, and bringing it over, on a fake Windows drive and a
throwaway home folder. Windows must come out unchanged; Linux-side files keep a .deckos-bak."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/movein'))
import movein  # noqa: E402
import steamfiles  # noqa: E402

CHROMIUM = {"roots": {"bookmark_bar": {"type": "folder", "name": "Bookmarks bar", "children": [
    {"type": "url", "name": "DeckOS", "url": "https://example.com/deckos"},
    {"type": "folder", "name": "Games", "children": [
        {"type": "url", "name": "ProtonDB <tiers>", "url": "https://www.protondb.com/?a=1&b=2"}]}]},
    "other": {"type": "folder", "name": "Other", "children": []}}}


def tree_digest(root):
    h = hashlib.sha256()
    for path in sorted(Path(root).rglob('*')):
        h.update(str(path.relative_to(root)).encode())
        if path.is_file():
            h.update(path.read_bytes())
    return h.hexdigest()


class MoveIn(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        t = Path(self.temp.name)
        # a Windows system drive with one person, and a games drive
        self.c, self.d = t / 'c', t / 'd'
        u = self.c / 'Users/alex'
        for sub in ('Documents', 'Pictures', 'Music', 'AppData/Roaming/Mozilla/Firefox/Profiles/ab12.default-release',
                    'AppData/Local/Microsoft/Edge/User Data/Default', 'AppData/Local/Microsoft/Windows/Fonts',
                    'AppData/Roaming/Microsoft/Windows/Themes', 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs'):
            (u / sub).mkdir(parents=True)
        for sub in ('Windows', 'Users/Public/Documents', 'Users/Default/AppData',
                    'ProgramData/Microsoft/Windows/Start Menu/Programs/Discord Inc',
                    'ProgramData/Microsoft/Wlansvc/Profiles/Interfaces/{1234}', 'Program Files (x86)/Steam/steamapps'):
            (self.c / sub).mkdir(parents=True)
        (u / 'Documents/thesis.docx').write_text('words')
        (u / 'Pictures/desktop.ini').write_text('')  # only desktop.ini: empty
        (u / 'Music/song.mp3').write_text('la')
        profile = u / 'AppData/Roaming/Mozilla/Firefox/Profiles/ab12.default-release'
        (profile / 'places.sqlite').write_text('bookmarks')
        (profile / 'logins.json').write_text('{}')
        (profile / 'parent.lock').write_text('')
        (u / 'AppData/Local/Microsoft/Edge/User Data/Default/Bookmarks').write_text(json.dumps(CHROMIUM))
        (u / 'AppData/Local/Microsoft/Windows/Fonts/Fancy.ttf').write_bytes(b'font')
        (u / 'AppData/Roaming/Microsoft/Windows/Themes/TranscodedWallpaper').write_bytes(b'\xff\xd8\xff' + b'0' * 2000)
        (u / 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Spotify.lnk').write_text('')
        (self.c / 'ProgramData/Microsoft/Windows/Start Menu/Programs/Discord Inc/Discord.lnk').write_text('')
        (self.c / 'ProgramData/Microsoft/Wlansvc/Profiles/Interfaces/{1234}/a.xml').write_text(
            '<WLANProfile><name>Home &amp; Garden</name><keyMaterial>01000000D08C9DDF</keyMaterial></WLANProfile>')
        (self.c / 'Program Files (x86)/Steam/steamapps/appmanifest_228980.acf').write_text(
            '"AppState"\n{\n\t"appid"\t\t"228980"\n\t"name"\t\t"Steamworks Common Redistributables"\n}\n')
        lib = self.d / 'SteamLibrary/steamapps'
        lib.mkdir(parents=True)
        for appid, name in (('220200', 'Kerbal Space Program'), ('284160', 'BeamNG.drive')):
            (lib / f'appmanifest_{appid}.acf').write_text(f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n}}\n')
        (self.d / 'Games/Clone Hero').mkdir(parents=True)
        # the Linux side
        self.home = t / 'home'
        self.steam = self.home / '.local/share/Steam'
        (self.steam / 'steamapps').mkdir(parents=True)
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t\t"apps"\n\t\t{\n\t\t}\n\t}\n}\n' % self.steam)
        firefox = self.home / '.mozilla/firefox'
        firefox.mkdir(parents=True)
        (firefox / 'profiles.ini').write_text('[Profile0]\nName=default-release\nIsRelative=1\nPath=xyz.default-release\n'
                                              'Default=1\n\n[General]\nStartWithLastProfile=1\nVersion=2\n\n'
                                              '[Install4F96D1932A9F858E]\nDefault=xyz.default-release\nLocked=1\n')
        (firefox / 'installs.ini').write_text('[4F96D1932A9F858E]\nDefault=xyz.default-release\nLocked=1\n')
        self.places = self.home / '.local/share/user-places.xbel'
        self.places.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xbel>\n<xbel>\n <bookmark href="file:///home/alex">\n'
                               '  <title>Home</title>\n </bookmark>\n</xbel>\n')
        self.before = {'c': tree_digest(self.c), 'd': tree_digest(self.d)}
        self.patches = [
            patch.dict(os.environ, {'DECKOS_MOVEIN_ROOTS': f'{self.c}:{self.d}'}),
            patch.object(movein, 'HOME', self.home), patch.object(movein, 'PLACES', self.places),
            patch.object(movein, 'FIREFOX', firefox), patch.object(movein, 'STATE', t / 'state/movein.json'),
            patch.object(steamfiles, 'STEAM', self.steam), patch.object(steamfiles, 'steam_running', lambda: False),
            patch.object(movein, '_running', lambda name: False),
            patch.object(movein.shutil, 'which', lambda cmd: None),  # no Plasma, fc-cache, deckos, Store here
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def scan(self):
        win, items = movein.scan()
        return win, {i.key: i for i in items}

    def test_finds_windows_and_its_person(self):
        win, items = self.scan()
        self.assertEqual(win.root, self.c)
        self.assertEqual(win.users, ['alex'])  # not Public or Default
        self.assertIn('folder:Documents', items)
        self.assertIn('folder:Music', items)
        self.assertNotIn('folder:Pictures', items)  # only desktop.ini
        self.assertIn('wallpaper', items)
        self.assertIn('fonts', items)

    def test_games_and_apps(self):
        _, items = self.scan()
        steam = items[f'steam:{self.d / "SteamLibrary"}']
        self.assertEqual(steam.data['games'], ['Kerbal Space Program', 'BeamNG.drive'])
        self.assertTrue(steam.ready)
        self.assertEqual(steam.title, 'Steam games: 2 on d')
        self.assertFalse([k for k in items if 'Program Files' in k])  # only Steam's tools there
        self.assertEqual(items['other-games'].data['games'], ['Clone Hero'])
        apps = {a['windows']: a for a in items['apps'].data['apps']}
        self.assertEqual(set(apps), {'discord', 'spotify'})

    def test_wifi_passwords_cannot_come(self):
        _, items = self.scan()
        self.assertFalse(items['wifi'].ready)
        self.assertIn('Home & Garden', items['wifi'].detail)

    def test_bringing_it_over(self):
        _, items = self.scan()
        results = dict((k, (ok, msg)) for k, ok, msg in movein.apply(list(items.values())))
        self.assertTrue(all(ok for ok, _ in results.values()), results)
        # Windows: untouched
        self.assertEqual({'c': tree_digest(self.c), 'd': tree_digest(self.d)}, self.before)
        # places: added once, KDE's file otherwise as it was, with a backup
        text = self.places.read_text()
        self.assertIn('<title>Windows Documents</title>', text)
        self.assertTrue(text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xbel>\n<xbel>\n <bookmark href="file:///home/alex">'))
        self.assertTrue((self.places.parent / 'user-places.xbel.deckos-bak').is_file())
        self.assertFalse(movein.add_place('Windows Documents', str(self.c / 'Users/alex/Documents'), 'folder'))
        # wallpaper, fonts, bookmarks
        self.assertTrue((self.home / 'Pictures/Wallpapers/From Windows.jpg').is_file())
        self.assertTrue((self.home / '.local/share/fonts/windows/Fancy.ttf').is_file())
        page = (self.home / 'Documents/Bookmarks from Microsoft Edge.html').read_text()
        self.assertIn('<DT><H3>Bookmarks bar / Games</H3>', page)  # nested folders, flattened
        self.assertIn('HREF="https://www.protondb.com/?a=1&amp;b=2">ProtonDB &lt;tiers&gt;</A>', page)
        # Firefox: the profile copied (no lock files), made the default, the old one kept
        ff = self.home / '.mozilla/firefox'
        self.assertTrue((ff / 'ab12.default-release.from-windows/places.sqlite').is_file())
        self.assertFalse((ff / 'ab12.default-release.from-windows/parent.lock').exists())
        ini = (ff / 'profiles.ini').read_text()
        self.assertIn('Path=xyz.default-release', ini)
        self.assertIn('Name=From Windows', ini)
        self.assertEqual(ini.count('Default=1'), 1)
        self.assertIn('Default=ab12.default-release.from-windows', (ff / 'installs.ini').read_text())
        self.assertTrue((ff / 'profiles.ini.deckos-bak').is_file())
        # Steam: the library added, the old entry kept, a backup
        vdf = steamfiles.read(self.steam / 'steamapps/libraryfolders.vdf')['libraryfolders']
        self.assertEqual([e['path'] for e in vdf.values()], [str(self.steam), str(self.d / 'SteamLibrary')])
        self.assertTrue((self.steam / 'steamapps/libraryfolders.vdf.deckos-bak').is_file())
        # and a second run changes nothing
        _, again = self.scan()
        self.assertFalse(again[f'steam:{self.d / "SteamLibrary"}'].ready)
        self.assertEqual(movein.apply([again['firefox:ab12.default-release']])[0][1], False)

    def test_moved_drives_repoint_the_rest(self):
        _, items = self.scan()
        rest = [i for i in items.values() if i.key.startswith(('steam:', 'folder:'))]
        movein.repoint(rest, {str(self.d): '/mnt/Games', str(self.c): '/mnt/Windows'})
        paths = sorted(i.data['path'] for i in rest)
        self.assertEqual(paths, ['/mnt/Games/SteamLibrary', '/mnt/Windows/Users/alex/Documents',
                                 '/mnt/Windows/Users/alex/Music'])
        self.assertIn('steam:/mnt/Games/SteamLibrary', [i.key for i in rest])

    def test_nothing_without_windows(self):
        with patch.dict(os.environ, {'DECKOS_MOVEIN_ROOTS': str(self.d)}):
            self.assertEqual(movein.scan(), (None, []))


class Window(unittest.TestCase):
    """The window in its demo, offscreen: it renders and exits cleanly (rows built on free layouts once
    crashed PySide on the way out)."""

    def test_demo_renders_and_exits_cleanly(self):
        import subprocess
        with tempfile.TemporaryDirectory() as out:
            shot = Path(out) / 'movein.png'
            r = subprocess.run([sys.executable, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/movein/deckos_movein.py'),
                                '--demo', '--screenshot', str(shot)], capture_output=True, text=True, timeout=60,
                               env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            self.assertGreater(shot.stat().st_size, 10000)

if __name__ == '__main__':
    unittest.main()
