"""deckos undo: which updates it offers, and what it calls them. The real deckos tool with a fake snapper.
The swap itself (btrfs, a restart) needs an installed DeckOS: it was checked in a VM, see docs/undo.md."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECKOS = ROOT / 'pkg/deckos-settings/rootfs/usr/bin/deckos'
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/hub'))

SNAPSHOTS = {"root": [
    {"number": 0, "type": "single", "description": "current"},
    {"number": 1, "type": "single", "date": "2026-10-24 19:02:11", "description": "Fresh DeckOS install"},
    {"number": 14, "type": "pre", "date": "2026-10-26 21:40:03", "description": "pacman -Syu"},
    {"number": 15, "type": "post", "pre-number": 14, "date": "2026-10-26 21:43:57", "description": "linux mesa steam"},
    {"number": 16, "type": "pre", "date": "2026-10-28 18:12:30", "description": "pacman -S lutris"},
    {"number": 17, "type": "post", "pre-number": 16, "date": "2026-10-28 18:12:40", "description": "lutris"},
    {"number": 18, "type": "pre", "date": "2026-10-29 09:00:00", "description": "pacman -Syu"},  # interrupted: no post
]}


class UndoListTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bin = Path(self.temp.name) / 'bin'
        self.bin.mkdir()
        (self.bin / 'snapshots.json').write_text(json.dumps(SNAPSHOTS))
        snapper = self.bin / 'snapper'
        snapper.write_text(f'#!/bin/bash\ncat {self.bin / "snapshots.json"}\n')
        snapper.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def deckos(self, *args):
        return subprocess.run(['bash', str(DECKOS), 'undo', *args], capture_output=True, text=True, timeout=10,
                              env=dict(PATH=f'{self.bin}:/usr/bin:/bin', HOME=self.temp.name))

    def test_updates_newest_first_named_by_their_packages(self):
        result = self.deckos('--tsv')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            '18\t2026-10-29 09:00\tpacman -Syu',  # no post snapshot: the command line is all there is
            '16\t2026-10-28 18:12\tlutris',
            '14\t2026-10-26 21:40\tlinux mesa steam',
        ])

    def test_hub_reads_the_same_rows(self):
        import hub_system
        rows = hub_system.parse_undoable(self.deckos('--tsv').stdout)
        self.assertEqual(rows[1], (16, '2026-10-28 18:12', 'lutris'))
        self.assertEqual(hub_system.parse_undoable('garbage\n\n'), [])

    def test_no_updates_yet(self):
        (self.bin / 'snapshots.json').write_text(json.dumps({"root": SNAPSHOTS["root"][:2]}))
        self.assertIn('No updates to undo yet', self.deckos('list').stdout)

    def test_undo_needs_root(self):
        result = self.deckos('16')
        if result.returncode == 0:
            self.skipTest('running as root')
        self.assertIn('needs root', result.stderr)


if __name__ == '__main__':
    unittest.main()
