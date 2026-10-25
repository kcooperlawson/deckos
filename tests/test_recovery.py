"""Starting from a snapshot after an update broke start-up: DecKoOS notices and offers to keep it."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
DECKOS = ROOT / 'pkg/deckos-settings/rootfs/usr/bin/deckos'
sys.path.insert(0, str(LIB / 'sysdoctor'))
import sysdoctor as sd  # noqa: E402

SNAPSHOT = 'BOOT_IMAGE=/@snapshots/42/snapshot/boot/vmlinuz-linux-cachyos root=UUID=x rw ' \
           'rootflags=subvol=@snapshots/42/snapshot quiet splash\n'
NORMAL = 'BOOT_IMAGE=/@/boot/vmlinuz-linux-cachyos root=UUID=x rw rootflags=subvol=@ quiet splash\n'


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cmdline = Path(self.temp.name) / 'cmdline'

    def tearDown(self):
        self.temp.cleanup()

    def booted(self, text):
        self.cmdline.write_text(text)
        return subprocess.run(['bash', str(DECKOS), 'undo', 'booted'], capture_output=True, text=True,
                              env={'PATH': '/usr/bin:/bin', 'DECKOS_CMDLINE': str(self.cmdline)}).stdout.strip()

    def test_deckos_knows_the_snapshot(self):
        self.assertEqual(self.booted(SNAPSHOT), '42')
        self.assertEqual(self.booted(NORMAL), '')
        self.assertEqual(self.booted(SNAPSHOT.replace('subvol=', 'rw,subvol=/')), '42')
        self.assertEqual(self.booted(SNAPSHOT.replace('subvol=@snapshots/42/snapshot', 'subvol="@snapshots/42/snapshot"')), '42')

    def test_doctor_offers_to_keep_it(self):
        with patch.object(sd, 'PROC', Path(self.temp.name)):
            self.cmdline.write_text(SNAPSHOT)
            f = sd.snapshot_boot()
            self.assertEqual(len(f), 1)
            self.assertIn('42', f[0].title)
            self.assertEqual(f[0].fixes[0].cmd, ['pkexec', 'deckos', 'undo', 'keep'])
            self.cmdline.write_text(NORMAL)
            self.assertEqual(sd.snapshot_boot(), [])


if __name__ == '__main__':
    unittest.main()
