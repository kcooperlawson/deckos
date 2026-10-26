"""NTFS drives that won't mount after the PC was cut off: deckos finds exactly the dirty (or Windows-hibernated) ones
that aren't mounted, System Doctor offers the vetted repair, and the repair is a recipe heal accepts. Nothing real is
read: a fake fstab, /dev/disk/by-uuid and kernel log."""
import os
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
sys.path.insert(0, str(LIB / 'heal'))
import heal  # noqa: E402
import sysdoctor as sd  # noqa: E402

FSTAB = """UUID=7ca4  /  btrfs  rw  0 0
UUID=4C3C  /mnt/SSD  ntfs3  uid=1000,nofail  0 0
UUID=2E76  /mnt/BIG  ntfs3  uid=1000,nofail,noauto,x-systemd.automount  0 0
UUID=E086  /mnt/Windows  ntfs3  uid=1000,nofail  0 0
UUID=AAAA  /mnt/Gone  ntfs3  nofail  0 0
"""
KERNEL = """ntfs3: Enabled Linux POSIX ACLs support
ntfs3(sda1): It is recommened to use chkdsk.
ntfs3(sda1): volume is dirty and "force" flag is not set!
ntfs3(sdb2): volume is dirty and "force" flag is not set!
ntfs3(nvme1n1p2): Windows is hibernated, so it's read-only
"""


class DirtyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        devs, uuids, stubs = self.tmp / 'dev', self.tmp / 'by-uuid', self.tmp / 'bin'
        for d in (devs, uuids, stubs):
            d.mkdir()
        for uuid, name in (('4C3C', 'sda1'), ('2E76', 'sdb2'), ('E086', 'nvme1n1p2')):  # AAAA isn't plugged in
            (devs / name).touch()
            (uuids / uuid).symlink_to(devs / name)
        (self.tmp / 'fstab').write_text(FSTAB)
        (stubs / 'journalctl').write_text(f"#!/bin/sh\ncat <<'EOF'\n{KERNEL}EOF\n")
        self.mounted = self.tmp / 'mounted'
        self.mounted.write_text('')
        (stubs / 'findmnt').write_text(f'#!/bin/sh\ngrep -qx "$2" {self.mounted}\n')
        for f in stubs.iterdir():
            f.chmod(0o755)
        self.env = {'PATH': f'{stubs}:/usr/bin:/bin', 'DECKOS_FSTAB': str(self.tmp / 'fstab'),
                    'DECKOS_BY_UUID': str(uuids), 'HOME': str(self.tmp)}

    def tearDown(self):
        subprocess.run(['rm', '-rf', str(self.tmp)])

    def dirty(self):
        out = subprocess.run(['bash', str(DECKOS), 'drives', 'dirty'], capture_output=True, text=True, env=self.env)
        return [line.split('\t')[:2] for line in out.stdout.splitlines()]

    def test_finds_the_refused_drives(self):
        self.assertEqual(self.dirty(), [['dirty', '/mnt/SSD'], ['dirty', '/mnt/BIG'], ['hibernated', '/mnt/Windows']])

    def test_a_mounted_drive_is_fine(self):
        # Repaired since (or mounted anyway): the old kernel lines don't count any more
        self.mounted.write_text('/mnt/SSD\n/mnt/Windows\n')
        self.assertEqual(self.dirty(), [['dirty', '/mnt/BIG']])

    def test_repair_needs_root(self):
        if os.geteuid() == 0:
            self.skipTest('running as root')
        out = subprocess.run(['bash', str(DECKOS), 'drives', 'repair'], capture_output=True, text=True, env=self.env)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('sudo deckos drives repair', out.stderr + out.stdout)


class DoctorTests(unittest.TestCase):
    def fake(self, outputs):
        def run(cmd, timeout=30):
            for prefix, text in outputs.items():
                if tuple(cmd[:len(prefix)]) == prefix:
                    return 0, text
            return 0, ''
        return run

    def test_dirty_drive_gets_the_vetted_repair(self):
        dirty = 'dirty\t/mnt/BIG\t/dev/disk/by-uuid/2E76\tnofail\nhibernated\t/mnt/Windows\t/dev/x\tnofail\n'
        with patch.object(sd, 'run', self.fake({('deckos', 'drives', 'dirty'): dirty})):
            found = {f.key: f for f in sd.ntfs_drives()}
        big, win = found['ntfs:/mnt/BIG'], found['ntfs:/mnt/Windows']
        self.assertEqual(big.level, sd.BAD)
        self.assertEqual(big.fixes[0].cmd, ['pkexec', 'deckos', 'heal', 'apply', 'repair-drives', '--finding=ntfs:/mnt/BIG'])
        self.assertEqual(win.fixes, [], 'only Windows can let go of a hibernated drive: no fix that would lose it')

    def test_no_double_finding_for_the_failed_mount(self):
        outputs = {('deckos', 'drives', 'dirty'): 'dirty\t/mnt/BIG\t/dev/x\tnofail\n',
                   ('systemctl', '--failed'): 'mnt-BIG.mount loaded failed failed /mnt/BIG\nsddm.service loaded failed failed x\n'}
        with patch.object(sd, 'run', self.fake(outputs)), patch.object(sd, 'CHECKS', [sd.ntfs_drives, sd.failed_units]):
            keys = [f.key for f in sd.checkup() if not f.key.startswith('journal')]
        self.assertIn('ntfs:/mnt/BIG', keys)
        self.assertNotIn('unit:system:mnt-BIG.mount', keys)
        self.assertIn('unit:system:sddm.service', keys)

    def test_the_recipe_passes_heals_walls(self):
        self.assertTrue(heal.check_recipe('repair-drives', heal.RECIPES['repair-drives']))
        p = heal.plan('repair-drives')
        self.assertEqual(p['steps'], [['deckos', 'drives', 'repair']])
        self.assertTrue(p['root'])
        self.assertFalse(p['snapshot'], 'a system snapshot holds none of the NTFS drives')


if __name__ == '__main__':
    unittest.main()
