"""util-linux 2.42's lsblk -J only nests partitions under their disk when NAME is a column; without it the
list is flat and `.children` is never there (NTFS drives went missing on the reference machine that way).
Every script that reads `.children` from lsblk -J must ask for NAME."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [ROOT / 'installer/deckos-install', ROOT / 'pkg/deckos-settings/rootfs/usr/bin/deckos',
           ROOT / 'iso/airootfs/usr/local/bin/deckos-autoinstall']


class LsblkTreeTests(unittest.TestCase):
    def test_tree_reads_ask_for_name(self):
        for script in SCRIPTS:
            text = script.read_text()
            for m in re.finditer(r'lsblk ([^|\n]*-J[^|\n]*)\|[^\n]*(?:\n[^\n]*){0,6}', text):
                if 'children' not in m.group(0):
                    continue
                cols = re.search(r'-o\s+(\S+)', m.group(1))
                with self.subTest(script=script.name, call=m.group(1).strip()):
                    self.assertTrue(cols and 'NAME' in cols.group(1).split(','), 'lsblk -J without NAME is flat')


if __name__ == '__main__':
    unittest.main()
