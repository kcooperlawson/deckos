"""DecKoOS Retro's scanning, BIOS handling and Steam shortcuts, on fake files and a fake Steam (never the real ones)."""
import dataclasses
import hashlib
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
sys.path[:0] = [str(LIB / 'retro'), str(LIB / 'gamedoctor')]


def disc(header_at, header, size=0x10000):
    data = bytearray(size)
    data[header_at:header_at + len(header)] = header
    return bytes(data)


class RetroTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        os.environ['DECKOS_RETRO_HOME'] = str(self.home)
        os.environ['DECKOS_STEAM_ROOT'] = str(self.home / 'steam')
        import steamfiles
        import retro
        self.sf = importlib.reload(steamfiles)
        self.r = importlib.reload(retro)
        self.games = self.home / 'ROMs'

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop('DECKOS_RETRO_HOME', None)
        os.environ.pop('DECKOS_STEAM_ROOT', None)

    def put(self, rel, data=b'\0' * 64):
        p = self.games / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    # ---- scanning

    def test_consoles_are_told_apart_and_nothing_is_guessed(self):
        self.put('misc/Chrono Trigger (USA) [!].sfc')
        self.put('misc/Legend of Zelda, The - Link\'s Awakening (USA, Europe).gb')
        self.put('misc/mystery.bin')  # no header anything knows: left out, not guessed
        self.put('misc/readme.txt')
        self.put('psx/Ape Escape (USA).chd')  # compressed: the folder says what it is
        self.put('discs/Melee.iso', disc(0x1C, b'\xC2\x33\x9F\x3D'))
        self.put('discs/Galaxy.iso', disc(0x18, b'\x5D\x1C\x9E\xA3'))
        self.put('discs/Shadow.iso', disc(0x9000, b'BOOT2 = cdrom0:\\SLUS_209.19;1'))
        self.put('discs/Patapon.iso', disc(0x8008, b'PSP GAME'))
        self.put('discs/Sonic CD.bin', disc(0x10, b'SEGADISCSYSTEM'))
        self.put('arcade/sf2.zip')
        self.put('snes/collection.zip')  # zipped cart in a console's folder: fine
        self.put('elsewhere/random.zip')  # a zip anywhere else: not a game
        games = {g.path.name: g for g in self.r.scan([self.games])}
        self.assertEqual(games['Chrono Trigger (USA) [!].sfc'].system, 'snes')
        self.assertEqual(games['Chrono Trigger (USA) [!].sfc'].title, 'Chrono Trigger')
        self.assertEqual(games['Chrono Trigger (USA) [!].sfc'].region, 'USA')
        zelda = games["Legend of Zelda, The - Link's Awakening (USA, Europe).gb"]
        self.assertEqual(zelda.title, "Legend of Zelda, The - Link's Awakening")
        self.assertEqual(games['Ape Escape (USA).chd'].system, 'psx')
        self.assertEqual(games['Melee.iso'].system, 'gamecube')
        self.assertEqual(games['Galaxy.iso'].system, 'wii')
        self.assertEqual(games['Shadow.iso'].system, 'ps2')
        self.assertEqual(games['Patapon.iso'].system, 'psp')
        self.assertEqual(games['Sonic CD.bin'].system, 'segacd')
        self.assertEqual(games['sf2.zip'].system, 'arcade')
        self.assertEqual(games['collection.zip'].system, 'snes')
        for left_out in ('mystery.bin', 'readme.txt', 'random.zip'):
            self.assertNotIn(left_out, games)

    def test_the_article_moves_to_the_front(self):
        self.assertEqual(self.r.title_of(Path('Legend of Zelda, The (USA).sfc')), ('The Legend of Zelda', 'USA'))

    def test_cue_sheets_and_discs_make_one_game(self):
        header = disc(0x9310, b'PLAYSTATION')
        for n in (1, 2, 3):
            self.put(f'ff7/Final Fantasy VII (USA) (Disc {n}).bin', header)
            self.put(f'ff7/Final Fantasy VII (USA) (Disc {n}).cue',
                     f'FILE "Final Fantasy VII (USA) (Disc {n}).bin" BINARY\n  TRACK 01 MODE2/2352\n'.encode())
        self.put('mgs/Metal Gear Solid (USA) (Disc 1).cue', b'FILE "mgs1.bin" BINARY\n')
        self.put('mgs/mgs1.bin', header)
        self.put('mgs/Metal Gear Solid (USA) (Disc 2).cue', b'FILE "mgs2.bin" BINARY\n')
        self.put('mgs/mgs2.bin', header)
        self.put('mgs/Metal Gear Solid (USA).m3u',
                 b'Metal Gear Solid (USA) (Disc 1).cue\nMetal Gear Solid (USA) (Disc 2).cue\n')
        games = self.r.scan([self.games])
        self.assertEqual(len(games), 2, [g.path.name for g in games])
        ff7 = next(g for g in games if g.title == 'Final Fantasy VII')
        self.assertEqual((ff7.system, ff7.discs), ('psx', 3))
        self.assertTrue(ff7.path.name.endswith('(Disc 1).cue'))
        mgs = next(g for g in games if g.title == 'Metal Gear Solid')
        self.assertEqual(mgs.path.suffix, '.m3u')  # the playlist, so the emulator can change discs
        self.assertEqual(mgs.system, 'psx')

    # ---- BIOS

    def test_bios_is_found_by_checksum_whatever_its_name(self):
        dump = b'not really a bios, but it stands in for one'
        digest = hashlib.md5(dump).hexdigest()
        psx = self.r.BY_ID['psx']
        fake = dataclasses.replace(psx, bios=(self.r.Bios('scph5501.bin', (digest,), True),))
        with patch.object(self.r, 'SYSTEMS', [fake if s.id == 'psx' else s for s in self.r.SYSTEMS]), \
                patch.dict(self.r.BY_ID, {'psx': fake}):
            self.assertEqual(self.r.bios_status('psx')[0][1], 'missing')
            backup = self.home / 'my console backup'
            backup.mkdir()
            (backup / 'SCPH-5501 (dumped 2009).BIN').write_bytes(dump)
            (backup / 'photo.jpg').write_bytes(b'jpeg')
            done = self.r.import_bios(backup)
            self.assertEqual([name for _, name in done], ['scph5501.bin'])
            self.assertEqual(self.r.bios_status('psx')[0][1], 'ok')
            (self.r.RETROARCH_SYSTEM / 'scph5501.bin').write_bytes(b'something else')
            self.assertEqual(self.r.bios_status('psx')[0][1], 'unknown dump')

    def test_launch_commands(self):
        g = self.r.Game(path=Path('/g/Chrono Trigger.sfc'), system='snes', title='Chrono Trigger')
        self.assertEqual(self.r.command(g), ['retroarch', '-f', '-L', '/usr/lib/libretro/snes9x_libretro.so',
                                             '/g/Chrono Trigger.sfc'])
        p2 = self.r.Game(path=Path('/g/Shadow.iso'), system='ps2', title='Shadow')
        self.assertEqual(self.r.command(p2)[:3], ['flatpak', 'run', 'net.pcsx2.PCSX2'])
        self.assertEqual(self.r.packages_for(['snes', 'gb', 'ps2']),
                         (['libretro-core-info', 'libretro-gambatte', 'libretro-snes9x', 'retroarch'], ['net.pcsx2.PCSX2']))

    # ---- Steam

    def steam_user(self):
        user = self.home / 'steam/userdata/123'
        (user / 'config').mkdir(parents=True)
        (user / 'config/localconfig.vdf').write_text('"UserLocalConfigStore"\n{\n}\n')
        return user

    def test_binary_keyvalues_round_trip_exactly(self):
        # The layout Steam writes, with a float and a 64-bit value DecKoOS doesn't edit
        data = (b'\x00shortcuts\x00\x000\x00\x02appid\x00' + struct.pack('<i', -123456) +
                b'\x01AppName\x00Doom\x00\x01Exe\x00"/usr/bin/gzdoom"\x00\x03scale\x00' + struct.pack('<f', 1.5) +
                b'\x07big\x00' + struct.pack('<Q', 2 ** 40) + b'\x00tags\x00\x010\x00FPS\x00\x08\x08\x08\x08')
        loaded = self.sf.load_binary(data)
        self.assertEqual(loaded['shortcuts']['0']['AppName'], 'Doom')
        self.assertEqual(loaded['shortcuts']['0']['appid'], -123456)
        self.assertEqual(self.sf.dump_binary(loaded), data)

    def test_shortcut_appid_is_steams(self):
        # Steam's id for a non-Steam game: crc32(exe + name) with the top bit set, as a signed int32
        self.assertEqual(self.sf.shortcut_appid('"/usr/bin/x"', 'X') & 0x80000000, 0x80000000)
        self.assertLess(self.sf.shortcut_appid('"/usr/bin/x"', 'X'), 0)

    def test_steam_sync_adds_keeps_and_cleans_up(self):
        user = self.steam_user()
        other = {'appid': 42, 'AppName': 'Heroic', 'Exe': '"/usr/bin/heroic"', 'LaunchOptions': '',
                 'tags': {'0': 'Launchers'}, 'LastPlayTime': 1700000000}
        self.sf.write_shortcuts(user, [other])
        sfc = self.put('snes/Chrono Trigger (USA).sfc')
        gba = self.put('gba/Golden Sun (USA).gba')
        with patch.object(self.sf, 'steam_running', return_value=False):
            games = self.r.scan([self.games])
            self.assertEqual(self.r.sync_steam(games), (2, 0))
            entries = self.sf.read_shortcuts(user)
            self.assertEqual(entries[0], other)  # the user's own non-Steam game, untouched
            names = {e['AppName']: e for e in entries[1:]}
            self.assertEqual(set(names), {'Chrono Trigger', 'Golden Sun'})
            self.assertEqual(names['Golden Sun']['tags'], {'0': 'DecKoOS Retro', '1': 'Game Boy Advance'})
            self.assertIn(str(gba), names['Golden Sun']['LaunchOptions'])
            # Steam records play time in our entry: a second sync keeps it and adds nothing
            entries[1]['LastPlayTime'] = 1710000000
            self.sf.write_shortcuts(user, entries)
            self.assertEqual(self.r.sync_steam(games), (0, 0))
            self.assertIn(1710000000, [e['LastPlayTime'] for e in self.sf.read_shortcuts(user)])
            # A deleted game leaves Steam; the backup of the previous file is there
            sfc.unlink()
            self.assertEqual(self.r.sync_steam(self.r.scan([self.games])), (0, 1))
            self.assertEqual([e['AppName'] for e in self.sf.read_shortcuts(user)], ['Heroic', 'Golden Sun'])
            self.assertTrue((user / 'config/shortcuts.vdf.deckos-bak').exists())

    def test_steam_must_be_closed(self):
        self.steam_user()
        with patch.object(self.sf, 'steam_running', return_value=True):
            with self.assertRaises(RuntimeError):
                self.r.sync_steam([])


if __name__ == '__main__':
    unittest.main()
