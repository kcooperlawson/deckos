"""DecKoOS Shelf's helper (shelf.py): each thing on the Desktop said as the right tile, newest first, with downloads
still arriving on top, and nothing it shouldn't touch (a link stays a link)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path.insert(0, str(LIB / 'shelf'))
import shelf  # noqa: E402


class ShelfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / 'Desktop'
        self.d.mkdir()
        self.now = time.time()

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, data=b'', ago=0):
        p = self.d / name
        p.write_bytes(data)
        os.utime(p, (self.now - ago, self.now - ago))
        return p

    def test_each_kind(self):
        self.put('notes.md', b'# Plan\n\n- one\n<p>not markup</p>\n- three\n', ago=10)
        self.put('poster.png', b'\x89PNG', ago=20)
        self.put('song.flac', b'x' * 2048, ago=30)
        self.put('big.iso.part', b'x' * 4096, ago=40)
        (self.d / 'Shots').mkdir()
        (self.d / 'Shots/a.jpg').write_bytes(b'x' * 1000)
        (self.d / 'Shots/b.txt').write_bytes(b'x' * 24)
        os.utime(self.d / 'Shots', (self.now - 50, self.now - 50))
        self.put('Tool.desktop', b'[Desktop Entry]\nName=Tool\nIcon=tool\nExec=tool\nComment=Does things\n', ago=60)
        tiles = {t['name']: t for t in shelf.items(self.d, self.now)}
        self.assertEqual(tiles['notes.md']['kind'], 'text')
        self.assertEqual(tiles['notes.md']['lines'], ['# Plan', '- one', '<p>not markup</p>'])
        self.assertEqual(tiles['poster.png']['kind'], 'image')
        self.assertEqual(tiles['song.flac']['detail'], 'Music · 2.0 KB')
        self.assertEqual(tiles['big.iso.part']['kind'], 'partial')
        self.assertEqual(tiles['big.iso.part']['title'], 'big.iso')
        self.assertEqual(tiles['Shots']['kind'], 'folder')
        self.assertEqual(tiles['Shots']['detail'], '2 things · 1.0 KB')
        self.assertEqual(len(tiles['Shots']['pictures']), 1)
        self.assertEqual((tiles['Tool.desktop']['kind'], tiles['Tool.desktop']['title'], tiles['Tool.desktop']['icon']),
                         ('app', 'Tool', 'tool'))
        self.assertEqual([t['name'] for t in shelf.items(self.d, self.now)][:3], ['notes.md', 'poster.png', 'song.flac'])

    def test_a_steam_game(self):
        self.put('Game.desktop', b'[Desktop Entry]\nName=Some Game\nExec=steam steam://rungameid/284160\n')
        played = {'284160': (self.now - 2 * 3600, 86 * 60)}
        with patch.object(shelf, 'steam_art', return_value='/x/library_hero.jpg'):
            t = shelf.describe(self.d / 'Game.desktop', self.now, played)
        self.assertEqual((t['kind'], t['appid'], t['launch']), ('game', '284160', 'steam://rungameid/284160'))
        self.assertEqual(t['detail'], 'Played 2 h ago · 86 h in all')
        self.assertEqual(t['art'], 'file:///x/library_hero.jpg')
        t = shelf.describe(self.d / 'Game.desktop', self.now, {})
        self.assertEqual(t['detail'], 'Not played yet')

    def test_a_link_stays_a_link(self):
        target = Path(self.tmp.name) / 'real.txt'
        target.write_text('hello\n')
        (self.d / 'link.txt').symlink_to(target)
        (self.d / 'gone.txt').symlink_to(Path(self.tmp.name) / 'nothing')
        tiles = {t['name']: t for t in shelf.items(self.d, self.now)}
        self.assertEqual(tiles['link.txt']['url'], (self.d / 'link.txt').as_uri())  # trashing it trashes the link
        self.assertEqual(tiles['gone.txt']['detail'], "Link to something that's gone")

    def test_downloads_arriving_come_first_and_old_ones_dont(self):
        self.put('note.txt', b'hi\n')
        dl = Path(self.tmp.name) / 'Downloads'
        dl.mkdir()
        (dl / 'new.zip.part').write_bytes(b'x' * 10)
        (dl / 'stale.zip.part').write_bytes(b'x' * 10)
        os.utime(dl / 'stale.zip.part', (self.now - 3600, self.now - 3600))
        (dl / 'done.zip').write_bytes(b'x')
        names = [t['name'] for t in shelf.items(self.d, self.now, downloads=dl)]
        self.assertEqual(names, ['new.zip.part', 'note.txt'])

    def test_hidden_and_binary(self):
        self.put('.hidden', b'x')
        self.put('blob', b'\0\1\2')
        self.assertEqual([(t['name'], t['kind']) for t in shelf.items(self.d, self.now)], [('blob', 'file')])

    def test_times(self):
        self.assertEqual([shelf.ago_text(self.now - s, self.now) for s in (30, 600, 7200, 90000, 5 * 86400)],
                         ['just now', '10 min ago', '2 h ago', 'yesterday', '5 days ago'])

    def test_runs_as_a_program(self):
        self.put('a.txt', b'one\n')
        r = subprocess.run([sys.executable, str(LIB / 'shelf/shelf.py'), str(self.d), str(self.d / 'none')],
                           capture_output=True, text=True, timeout=30)
        out = json.loads(r.stdout)
        self.assertEqual((out['folder'], [t['name'] for t in out['items']]), (str(self.d), ['a.txt']))


if __name__ == '__main__':
    unittest.main()
