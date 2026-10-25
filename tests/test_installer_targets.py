"""deckos-install --list-targets: partitions, plus free space and empty disks DecKoOS could add its own
partition to. A fake lsblk describes the disks; nothing is read from or written to a real one."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'installer/deckos-install'
GB = 10 ** 9
S = 512  # lsblk START is in 512-byte sectors


def part(path, start_mib, size_gb, fstype='ntfs', parttype='ebd0a0a2-b9e5-4433-87c0-68b6b72699c7', label=None):
    return dict(path=path, name=path[5:], type='part', start=start_mib * 2048, size=size_gb * GB, fstype=fstype,
                label=label, parttype=parttype, model=None, mountpoints=[None], pttype=None)


def disk(path, size_gb, pttype='gpt', children=(), fstype=None, model='Test disk', mounts=(None,)):
    return dict(path=path, name=path[5:], type='disk', size=size_gb * GB, pttype=pttype, fstype=fstype, label=None,
                model=model, start=None, parttype=None, mountpoints=list(mounts), children=list(children))


DISKS = {"blockdevices": [
    disk('/dev/zram0', 16, pttype=None, mounts=['[SWAP]']),                      # RAM, never a target
    disk('/dev/sdz', 32, pttype='dos', model='Live USB',
         children=[part('/dev/sdz1', 1, 31, fstype='iso9660')]),                 # the live USB itself
    disk('/dev/sdb', 500, pttype=None),                                          # empty: whole disk
    disk('/dev/sdc', 20, pttype=None),                                           # empty but too small
    disk('/dev/sdd', 1000, fstype='ntfs', pttype=None),                          # a file system, no partitions
    disk('/dev/nvme0n1', 1000, children=[                                        # Windows, 300 GB unused after it
        part('/dev/nvme0n1p1', 1, 1, fstype='vfat', parttype='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'),
        part('/dev/nvme0n1p2', 1100, 500, label='Windows'),
        part('/dev/nvme0n1p3', 1100 + 500 * GB // 2 ** 20 + 300 * GB // 2 ** 20, 199)]),
    disk('/dev/sde', 100, pttype='dos', children=[part('/dev/sde1', 1, 20)]),    # MBR with 80 GB free
    disk('/dev/sdf', 200, children=[part('/dev/sdf1', 1, 170)]),                 # GPT, only ~30 GB free
]}


class ListTargets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        bin_ = Path(self.temp.name)
        (bin_ / 'disks.json').write_text(json.dumps(DISKS))
        # lsblk -J ... (the listings) prints the fake disks; lsblk -no PKNAME (the live USB's disk) says sdz
        (bin_ / 'lsblk').write_text(f'#!/bin/bash\n[[ $1 == -no ]] && {{ echo sdz; exit; }}\ncat {bin_ / "disks.json"}\n')
        (bin_ / 'findmnt').write_text('#!/bin/bash\necho /dev/sdz1\n')
        for f in ('lsblk', 'findmnt'):
            (bin_ / f).chmod(0o755)
        out = subprocess.run(['bash', str(INSTALLER), '--list-targets'], capture_output=True, text=True, timeout=20,
                             env=dict(PATH=f'{bin_}:/usr/bin:/bin', DECKOS_SRC=str(ROOT)))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.rows = {r.split('\t')[0]: r.split('\t') for r in out.stdout.splitlines()}

    def tearDown(self):
        self.temp.cleanup()

    def free(self, disk_path):
        return [r for p, r in self.rows.items() if p.startswith(f'free:{disk_path}:')]

    def test_ram_and_the_live_usb_are_never_offered(self):
        self.assertFalse([p for p in self.rows if 'zram' in p or 'sdz' in p])

    def test_an_empty_disk_is_offered_whole(self):
        row = self.rows['free:/dev/sdb:disk']
        self.assertEqual(row[2:4], ['free', 'Empty disk'])
        self.assertEqual(row[6], '')

    def test_too_small_and_formatted_disks_are_not(self):
        self.assertIn('needs 64 GB', self.rows['free:/dev/sdc:disk'][6])
        self.assertEqual(self.free('/dev/sdd'), [])  # whole-disk NTFS: not empty, and not a partition either

    def test_the_gap_after_windows_is_offered_exactly(self):
        gaps = self.free('/dev/nvme0n1')
        self.assertEqual(len(gaps), 1, gaps)
        _, disk_path, start, sectors = gaps[0][0].split(':')
        p2_end = (1100 * 2048) + 500 * GB // S
        p3_start = (1100 + 500 * GB // 2 ** 20 + 300 * GB // 2 ** 20) * 2048
        self.assertEqual(int(start) % 2048, 0)                     # 1 MiB aligned
        self.assertGreaterEqual(int(start), p2_end)                # after Windows...
        self.assertLessEqual(int(start) + int(sectors), p3_start)  # ...and before the next partition
        self.assertEqual(gaps[0][6], '')
        self.assertEqual(gaps[0][1], '299 GB')  # 286,102 MiB, rounded down

    def test_mbr_and_small_gaps_are_listed_but_blocked(self):
        (mbr,) = self.free('/dev/sde')
        self.assertIn('MBR', mbr[6])
        (small,) = self.free('/dev/sdf')
        self.assertIn('needs 64 GB', small[6])

    def test_partitions_are_still_listed(self):
        self.assertIn('/dev/nvme0n1p2', self.rows)
        self.assertNotIn('/dev/nvme0n1p1', self.rows)  # the EFI partition never is


if __name__ == '__main__':
    unittest.main()
