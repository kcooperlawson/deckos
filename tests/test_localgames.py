"""Games on my drives: finding the program that starts a game, reading .exe imports, Steam id matching, launch
commands and Steam shortcuts, on fake game folders and a fake Steam (never the real ones)."""
import importlib
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / 'localgames'), str(LIB / 'gamedoctor')]


def pe(dlls=(), machine=0x8664, size=0):
    """A minimal Windows .exe: one section holding the import table and the dll names."""
    plus = machine == 0x8664
    optsize = 240 if plus else 224
    dirs = 112 if plus else 96
    hdr_end = 0x40 + 4 + 20 + optsize + 40
    raw, rva = 0x200, 0x1000
    names, table = b'', b''
    name_at = rva + 20 * (len(dlls) + 1)
    for d in dlls:
        table += struct.pack('<IIIII', 0, 0, 0, name_at + len(names), 0)
        names += d.encode() + b'\0'
    section = table + b'\0' * 20 + names
    opt = bytearray(optsize)
    opt[0:2] = struct.pack('<H', 0x20B if plus else 0x10B)
    opt[dirs + 8:dirs + 16] = struct.pack('<II', rva if dlls else 0, len(table))
    data = bytearray(b'MZ' + b'\0' * 0x3A + struct.pack('<I', 0x40))
    data += b'PE\0\0' + struct.pack('<HHIIIHH', machine, 1, 0, 0, 0, optsize, 0x22) + opt
    data += struct.pack('<8sIIIIIIHHI', b'.idata', len(section), rva, len(section), raw, 0, 0, 0, 0, 0)
    data += b'\0' * (raw - hdr_end) + section
    return bytes(data) + b'\0' * size


class LocalGamesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        os.environ['DECKOS_STEAM_ROOT'] = str(self.home / 'steam')
        import steamfiles
        import localgames
        self.sf = importlib.reload(steamfiles)
        self.lg = importlib.reload(localgames)
        for name, rel in (('CONFIG', 'config.json'), ('IDS', 'ids.json'), ('PREFIXES', 'prefixes')):
            setattr(self.lg, name, self.home / rel)
        self.lg.PROTON_DIRS = [self.home / 'proton']
        self.games = self.home / 'Games'

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop('DECKOS_STEAM_ROOT', None)

    def put(self, rel, data=b'', mode=None):
        p = self.games / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        if mode:
            p.chmod(mode)
        return p

    def by_name(self):
        return {g.name: g for g in self.lg.scan([self.games])}

    # ---- the program that starts the game

    def test_helpers_are_never_picked(self):
        self.put('Baby Steps/BabySteps.exe', pe(['d3d11.dll'], size=4000))
        self.put('Baby Steps/UnityCrashHandler64.exe', pe(size=90000))
        self.put('Baby Steps/UnityPlayer.dll')
        self.put('Baby Steps/unins000.exe', pe(size=90000))
        self.put('Baby Steps/_CommonRedist/vcredist_x64.exe', pe())
        self.put('Baby Steps/Redist/dxsetup.exe', pe())
        g = self.by_name()['Baby Steps']
        self.assertEqual((g.exe, g.engine, g.runner, g.sure), ('BabySteps.exe', 'Unity', 'proton', True))
        self.assertEqual(g.candidates, ['BabySteps.exe'])

    def test_named_like_the_game_beats_deeper_or_launcher(self):
        self.put('Mud Trucks/Sources/Bin/MudTrucks.exe', pe(size=100))
        self.put('Mud Trucks/Sources/Bin/MudTrucksLauncher.exe', pe(size=100))
        self.put('Mud Trucks/Tools/Thing.exe', pe(size=100))
        self.assertEqual(self.by_name()['Mud Trucks'].exe, 'Sources/Bin/MudTrucks.exe')

    def test_unreal_engine_detected_and_stub_kept(self):
        self.put('Windrose/Windrose.exe', pe(size=100))
        self.put('Windrose/Windrose/Binaries/Win64/Windrose-Win64-Shipping.exe', pe(['d3d12.dll'], size=100))
        self.put('Windrose/Engine/Binaries/ThirdParty/x.dll')
        g = self.by_name()['Windrose']
        self.assertEqual(g.engine, 'Unreal Engine')
        self.assertIn(g.exe, g.candidates)
        self.assertIn('Windrose/Binaries/Win64/Windrose-Win64-Shipping.exe', g.candidates)

    def test_two_lookalikes_make_it_unsure(self):
        self.put('Racer/RacerDX11.exe', pe(size=100))
        self.put('Racer/RacerDX12.exe', pe(size=100))
        self.assertFalse(self.by_name()['Racer'].sure)

    def test_nothing_to_start_is_said_not_guessed(self):
        self.put('Unpacked/data.bin', b'x')
        g = self.by_name()['Unpacked']
        self.assertEqual((g.exe, g.runner), ('', 'none'))
        self.assertIn('unpacking', g.notes[0])
        self.assertEqual(g.installer, '')

    def test_installer_is_offered_and_its_program_remembered(self):
        self.put('Old RPG/setup_old_rpg_1.0.exe', pe(size=100))
        self.put('Old RPG/_CommonRedist/vcredist_x64.exe', pe())
        g = self.by_name()['Old RPG']
        self.assertEqual((g.exe, g.installer), ('', 'setup_old_rpg_1.0.exe'))
        self.assertIn('installing', g.notes[0])
        # What the installer put in the prefix, newer than the start of the install, best match first
        prefix = self.home / 'prefixes/old-rpg'
        game = prefix / 'drive_c/GOG Games/Old RPG/OldRPG.exe'
        game.parent.mkdir(parents=True)
        game.write_bytes(pe())
        (game.parent / 'unins000.exe').write_bytes(pe())
        found = self.lg.new_programs(prefix, 0, 'Old RPG')
        self.assertEqual(found, [game])
        self.lg.pick(self.games / 'Old RPG', exe=str(game))  # absolute: the game lives in its prefix now
        g = self.by_name()['Old RPG']
        self.assertEqual((g.exe, g.installer, g.runner), (str(game), '', 'proton'))
        self.assertEqual(self.lg.command(g)[0][1], str(game))
        self.assertFalse(any('installing' in n for n in g.notes))

    def test_folders_to_look_in(self):
        self.lg.set_roots([self.games, self.games, self.home / 'More'])
        self.assertEqual(self.lg.roots(), [self.games, self.home / 'More'])
        with patch.object(self.lg, 'default_roots', lambda: [self.home / 'Found']):
            self.lg.set_roots([])
            self.assertEqual(self.lg.roots(), [self.home / 'Found'])  # empty: back to finding them

    def test_linux_games_run_as_they_are(self):
        self.put('Tux Kart/TuxKart.x86_64', b'\x7fELF' + b'\0' * 60, mode=0o755)
        self.put('Tux Kart/TuxKart_Data/x', b'')
        g = self.by_name()['Tux Kart']
        self.assertEqual((g.runner, g.exe), ('native', 'TuxKart.x86_64'))
        argv, env, cwd = self.lg.command(g)
        self.assertEqual((argv, env), ([str(self.games / 'Tux Kart/TuxKart.x86_64')], {}))

    # ---- what it needs, and what stops it

    def test_exe_imports_become_plain_needs(self):
        self.put('Old Game/OldGame.exe', pe(['KERNEL32.dll', 'd3d9.dll', 'MSVCP140.dll', 'XINPUT1_3.dll',
                                            'mscoree.dll'], machine=0x14C))
        g = self.by_name()['Old Game']
        self.assertEqual(g.arch, '32-bit')
        self.assertEqual(g.needs, ['DirectX 9', 'Visual C++ runtime', '.NET Framework', 'Controller (XInput)'])
        self.assertTrue(any('.NET' in n for n in g.notes))

    def test_not_an_exe_is_none(self):
        p = self.put('x/readme.exe', b'hello')
        self.assertIsNone(self.lg.pe_info(p))
        self.assertEqual(self.lg.pe_info(self.put('x/t.exe', pe(['a.dll']))), ('64-bit', ['a.dll']))

    def test_anticheat_and_launchers_are_named(self):
        self.put('Shooter/Shooter.exe', pe())
        self.put('Shooter/EasyAntiCheat/EasyAntiCheat_EOS_Setup.exe', pe())
        self.put('Shooter/start_protected_game.exe', pe(size=999999))
        self.put('Assassin/Assassin.exe', pe())
        self.put('Assassin/uplay_r1_loader64.dll')
        games = self.by_name()
        self.assertEqual(games['Shooter'].exe, 'Shooter.exe')
        self.assertTrue(games['Shooter'].blockers[0].startswith('EasyAntiCheat'))
        self.assertTrue(games['Assassin'].blockers[0].startswith('Ubisoft Connect'))

    # ---- which folders are games

    def test_redist_junk_and_hidden_folders_are_skipped(self):
        self.put('_CommonRedist/vcredist.exe', pe())
        self.put('jl1dcr185lbavMU9EEFh9OLSVL2kMRA1qbwSGrRkU4nlJQZLedaocQbulN6pKfod8ddlcB/x.exe', pe())
        self.put('$RECYCLE.BIN/a.exe', pe())
        self.put('Game One/GameOne.exe', pe())
        self.put('Game Two/GameTwo.exe', pe())
        self.lg.pick(self.games / 'Game Two', hidden=True)
        self.assertEqual(list(self.by_name()), ['Game One'])

    def test_the_persons_pick_wins(self):
        self.put('Racer/RacerDX11.exe', pe())
        self.put('Racer/RacerDX12.exe', pe())
        self.lg.pick(self.games / 'Racer', exe='RacerDX12.exe', name='Racer Deluxe', appid='12345')
        g = self.by_name()['Racer Deluxe']
        self.assertEqual((g.exe, g.sure, g.picked, g.appid), ('RacerDX12.exe', True, True, '12345'))

    def test_steam_appid_file_is_read(self):
        self.put('Tanks/Tanks.exe', pe())
        self.put('Tanks/steam_appid.txt', b'1874880\n')
        self.assertEqual(self.by_name()['Tanks'].appid, '1874880')

    def test_clean_names(self):
        self.assertEqual(self.lg.clean_name('Some_Game_v1.2.3 [GOG]'), 'Some Game')
        self.assertEqual(self.lg.clean_name('S.T.A.L.K.E.R. 2'), 'S.T.A.L.K.E.R. 2')

    # ---- Steam ids

    def test_title_matching_is_strict(self):
        m = self.lg.match_title
        self.assertEqual(m('RESIDENT EVIL 7 biohazard', [(418370, 'Resident Evil 7 Biohazard'),
                                                          (583810, 'Resident Evil 7 biohazard Original Soundtrack')]),
                         '418370')
        self.assertEqual(m('S.T.A.L.K.E.R. 2', [(1643320, 'S.T.A.L.K.E.R. 2: Heart of Chornobyl')]), '1643320')
        self.assertEqual(m('Derail Valley', [(1308910, 'Derail Valley Soundtrack'), (588030, 'Derail Valley')]), '588030')
        self.assertEqual(m('Cheap Car Repair', [(1, 'Car Mechanic Simulator')]), '')
        self.assertEqual(m('Anything', []), '')

    def test_steam_id_is_asked_once(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return '{"items": [{"id": 1281040, "name": "Baby Steps"}]}'
        self.assertEqual(self.lg.steam_id('Baby Steps', fetch), '1281040')
        self.assertEqual(self.lg.steam_id('Baby Steps', fetch), '1281040')
        self.assertEqual(len(calls), 1)

        def offline(url):
            raise OSError('no network')
        self.assertEqual(self.lg.steam_id('Other', offline), '')
        self.assertEqual(self.lg.steam_id('Other', fetch), '')  # 'Other' isn't Baby Steps: remembered as none

    # ---- starting

    def test_windows_games_get_their_own_prefix_and_fixes(self):
        (self.home / 'proton/proton-cachyos-slr').mkdir(parents=True)
        (self.home / 'proton/proton-cachyos-slr/proton').write_text('')
        self.put('Baby Steps/BabySteps.exe', pe())
        g = self.by_name()['Baby Steps']
        g.appid = '1281040'
        argv, env, cwd = self.lg.command(g)
        self.assertEqual(argv, ['umu-run', str(self.games / 'Baby Steps/BabySteps.exe')])
        self.assertEqual(env['GAMEID'], 'umu-1281040')
        self.assertEqual(env['WINEPREFIX'], str(self.home / 'prefixes/baby-steps'))
        self.assertEqual(env['PROTONPATH'], str(self.home / 'proton/proton-cachyos-slr'))
        self.assertEqual(cwd, str(self.games / 'Baby Steps'))
        g.appid = ''
        self.assertEqual(self.lg.command(g)[1]['GAMEID'], 'umu-default')

    # ---- Steam library

    def test_steam_shortcuts_added_kept_and_cleaned(self):
        user = self.home / 'steam/userdata/123'
        (user / 'config').mkdir(parents=True)
        (user / 'config/localconfig.vdf').write_text('"UserLocalConfigStore"\n{\n}\n')
        other = {'appid': 42, 'AppName': 'Heroic', 'Exe': '"/usr/bin/heroic"', 'LaunchOptions': '',
                 'tags': {'0': 'Launchers'}, 'LastPlayTime': 1700000000}
        self.sf.write_shortcuts(user, [other])
        self.put('Game One/GameOne.exe', pe())
        two = self.put('Game Two/GameTwo.exe', pe())
        with patch.object(self.sf, 'steam_running', return_value=False):
            self.assertEqual(self.lg.sync_steam(self.lg.scan([self.games])), (2, 0))
            entries = self.sf.read_shortcuts(user)
            self.assertEqual(entries[0], other)
            self.assertEqual({e['AppName'] for e in entries[1:]}, {'Game One', 'Game Two'})
            self.assertEqual(entries[1]['Exe'], '"/usr/bin/deckos-play"')
            self.assertEqual(self.lg.sync_steam(self.lg.scan([self.games])), (0, 0))
            two.unlink()
            two.parent.rmdir()
            self.assertEqual(self.lg.sync_steam(self.lg.scan([self.games])), (0, 1))
        with patch.object(self.sf, 'steam_running', return_value=True):
            with self.assertRaises(RuntimeError):
                self.lg.sync_steam([])


if __name__ == '__main__':
    unittest.main()
