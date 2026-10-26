"""DecKoOS Disks: what's on each disk, the start-up check (will each drive mount after a restart, and if not, why),
and changes that only touch DecKoOS's part of fstab and never keep an entry that didn't mount. Nothing real is read
or written: lsblk, fstab, the boot's log and every command are canned."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/disks'))
import disks as D  # noqa: E402

G = 1_000_000_000


def part(name, size, start, fstype='', label='', uuid='', ptype='', mounts=(), used=None, avail=None):
    return {'name': name, 'path': f'/dev/{name}', 'type': 'part', 'size': size, 'start': start, 'fstype': fstype or None,
            'label': label or None, 'uuid': uuid or None, 'partuuid': None, 'parttypename': ptype or None,
            'mountpoints': list(mounts) or [None], 'fsused': used, 'fsavail': avail}


def disk(name, size, model, tran, children, rota=False, rm=False, pttype='gpt'):
    return {'name': name, 'path': f'/dev/{name}', 'type': 'disk', 'size': size, 'log-sec': 512, 'model': model,
            'tran': tran, 'rota': rota, 'rm': rm, 'pttype': pttype, 'children': children}


LSBLK = json.dumps({'blockdevices': [
    disk('nvme0n1', 250 * G, 'Samsung SSD 970', 'nvme', [
        part('nvme0n1p1', 629145600, 2048, 'vfat', '', '61E1', 'EFI System', ['/boot/efi']),
        part('nvme0n1p2', 249 * G, 1230848, 'btrfs', 'DeckOS', 'ROOT', 'Linux filesystem', ['/', '/home'], 200 * G, 49 * G)]),
    disk('sda', 1000 * G, 'Samsung SSD 870', 'sata', [
        part('sda1', 1000 * G, 2048, 'ntfs', 'SSD', '4C3C', 'Microsoft basic data')]),
    disk('sdb', 8000 * G, 'HGST 8TB', 'usb', [
        part('sdb1', 16 << 20, 34, '', '', '', 'Microsoft reserved'),
        part('sdb2', 7000 * G, 32768, 'ntfs', 'BIG', '2E76', 'Microsoft basic data')], rota=True),
    disk('sdc', 128 * G, 'Ventoy stick', 'usb', [
        part('sdc1', 120 * G, 2048, 'exfat', 'Ventoy', '4E21', 'HPFS/NTFS/exFAT'),
        part('sdc2', 33554432, 250004144, 'vfat', 'VTOYEFI', 'EA6C', 'EFI (FAT-12/16/32)')], rm=True, pttype='dos'),
    disk('sdd', 2000 * G, 'WD Elements', 'usb', [
        part('sdd1', 2000 * G, 2048, 'ext4', 'Games', 'aaaa-bbbb', 'Linux filesystem')]),
    {'name': 'zram0', 'type': 'disk', 'size': 16 * G},
]})

FSTAB = f"""UUID=ROOT / btrfs rw,subvol=/@ 0 0
UUID=ROOT /home btrfs rw,subvol=/@home 0 0
UUID=61E1 /boot/efi vfat rw 0 2
UUID=9999 /mnt/Old ext4 defaults 0 0

{D.BEGIN}
# /dev/sda1 (1000 GB, sata)
UUID=4C3C  /mnt/SSD  ntfs3  uid=1000,nofail  0 0
# /dev/sdb2 (7000 GB, usb)
UUID=2E76  /mnt/BIG  ntfs3  uid=1000,nofail,noauto,x-systemd.automount  0 0
UUID=GONE  /mnt/Gone  exfat  nofail  0 0
{D.END}
"""


def ctx(mounted=('/', '/home', '/boot/efi', '/mnt/SSD'), failed=(), kernel=()):
    return {'mounted': {m: ['rw'] for m in mounted}, 'failed': set(failed), 'kernel': list(kernel)}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.disks = D.inventory(LSBLK)
        self.parts = {p.name: p for d in self.disks for p in d.parts}

    def test_disks_and_partitions(self):
        self.assertEqual([d.name for d in self.disks], ['nvme0n1', 'sda', 'sdb', 'sdc', 'sdd'])  # no zram
        self.assertEqual([d.kind for d in self.disks], ['nvme', 'ssd', 'usb', 'usb', 'usb'])
        self.assertEqual(self.parts['nvme0n1p2'].start, 1230848 * 512)

    def test_roles(self):
        roles = {n: p.role for n, p in self.parts.items()}
        self.assertEqual(roles['nvme0n1p1'], 'efi')
        self.assertEqual(roles['nvme0n1p2'], 'system')
        self.assertEqual(roles['sdb1'], 'reserved')
        self.assertEqual(roles['sdc2'], 'efi', "a USB stick's boot partition is never offered for start-up")
        self.assertFalse(self.parts['sdc2'].mountable)
        self.assertTrue(self.parts['sdd1'].mountable)
        self.assertFalse(self.parts['nvme0n1p2'].mountable, 'the system is never touched')

    def test_layout_shows_free_space(self):
        d = D.Disk('x', '/dev/x', 100 * G, parts=[D.Part('x1', '/dev/x1', 40 * G, 1 << 20)])
        kinds = [k for k, _ in d.layout()]
        self.assertEqual(kinds, ['part', 'free'])
        self.assertEqual(D.inventory('not json'), [])

    def test_unit_names(self):
        self.assertEqual(D.unit('/mnt/BIG'), 'mnt-BIG.mount')
        self.assertEqual(D.unit('/mnt/My Games'), 'mnt-My\\x20Games.mount')
        self.assertEqual(D.unit('/mnt/a-b'), 'mnt-a\\x2db.mount')
        self.assertEqual(D.unit('/'), '-.mount')


class StartupTests(unittest.TestCase):
    def check(self, **kw):
        with patch.object(D, 'run', return_value=(0, 'mount: wrong fs type, bad option\n')):
            checks = D.startup(D.inventory(LSBLK), D.fstab(FSTAB), ctx(**kw))
        return {c.target: c for c in checks}

    def test_a_healthy_pc(self):
        c = self.check()
        self.assertEqual(c['/'].state, D.GOOD)
        self.assertFalse(c['/'].managed, "the installer's entries are shown, never changed")
        self.assertEqual(c['/mnt/SSD'].state, D.GOOD)
        self.assertTrue(c['/mnt/SSD'].managed)
        self.assertEqual(c['/mnt/BIG'].state, D.GOOD, 'an automount waits to be opened: that is fine')

    def test_dirty_and_hibernated(self):
        c = self.check(mounted=('/',), kernel=['ntfs3(sda1): volume is dirty and "force" flag is not set!',
                                               'ntfs3(sdb2): Windows is hibernated, read-only'])
        self.assertEqual((c['/mnt/SSD'].state, c['/mnt/SSD'].fix), (D.BAD, 'repair'))
        self.assertEqual((c['/mnt/BIG'].state, c['/mnt/BIG'].fix), (D.WARN, ''), 'only Windows can let go of it')

    def test_missing_drives(self):
        c = self.check()
        self.assertEqual(c['/mnt/Gone'].state, D.INFO, 'nofail: start-up just skips it')
        self.assertEqual(c['/mnt/Old'].state, D.BAD, 'no nofail: start-up waits 90 s for it')
        self.assertEqual(c['/mnt/Old'].fix, '', 'not ours to remove')

    def test_wrong_file_system_and_failed_mount(self):
        text = FSTAB.replace('UUID=4C3C  /mnt/SSD  ntfs3', 'UUID=4C3C  /mnt/SSD  ext4')
        with patch.object(D, 'run', return_value=(0, '')):
            c = {x.target: x for x in D.startup(D.inventory(LSBLK), D.fstab(text), ctx(mounted=('/',)))}
        self.assertIn('wrong file system', c['/mnt/SSD'].title)
        self.assertEqual(c['/mnt/SSD'].fix, 'edit')
        failed = self.check(mounted=('/',), failed=['mnt-SSD.mount'])
        self.assertIn("didn't mount", failed['/mnt/SSD'].title)
        self.assertIn('wrong fs type', failed['/mnt/SSD'].text, "the journal's reason is shown")

    def test_offers_drives_not_in_fstab(self):
        c = self.check()
        games = c['/dev/sdd1']
        self.assertEqual((games.state, games.fix), (D.INFO, 'add'))
        self.assertNotIn('/dev/sdc2', c, "Ventoy's boot partition isn't offered")

    def test_worst_first(self):
        checks = list(self.check().values())
        order = [D.BAD, D.WARN, D.INFO, D.GOOD]
        self.assertEqual([c.state for c in checks], sorted((c.state for c in checks), key=order.index))


class FstabEditTests(unittest.TestCase):
    def test_adds_inside_the_block(self):
        out = D.with_entry(FSTAB, 'UUID=new  /mnt/New  ext4  defaults,nofail  0 0')
        lines = out.splitlines()
        self.assertLess(lines.index(D.BEGIN), lines.index('UUID=new  /mnt/New  ext4  defaults,nofail  0 0'),
                        lines.index(D.END))
        self.assertTrue(out.startswith('UUID=ROOT / btrfs'), 'nothing outside the block moves')
        fresh = D.with_entry('UUID=ROOT / btrfs rw 0 0\n', 'UUID=n /mnt/N ext4 nofail 0 0')
        self.assertIn(D.BEGIN, fresh)
        self.assertIn(D.END, fresh)

    def test_removes_only_inside_the_block(self):
        out = D.without_entry(FSTAB, '/mnt/SSD')
        self.assertNotIn('/mnt/SSD', out)
        self.assertNotIn('# /dev/sda1', out, 'its comment goes with it')
        self.assertIn('/mnt/BIG', out)
        self.assertEqual(D.without_entry(FSTAB, '/mnt/Old'), FSTAB, 'an entry outside the block is never removed')
        self.assertEqual(D.without_entry(FSTAB, '/'), FSTAB)

    def test_options(self):
        parts = {p.name: (p, d) for d in D.inventory(LSBLK) for p in d.parts}
        ntfs = D.options_for(*parts['sda1'], uid=1001, gid=1001)
        self.assertIn('uid=1001', ntfs)
        ext4 = D.options_for(*parts['sdd1'])
        self.assertIn('x-systemd.automount', ext4, 'an external waits to be opened')
        for opts in (ntfs, ext4):
            self.assertIn('nofail', opts, 'never holds start-up up')


class ChangeTests(unittest.TestCase):
    """add() and remove() against a throwaway fstab and /mnt, with every command faked."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fstab = self.tmp / 'fstab'
        self.fstab.write_text(FSTAB)
        self.mnt = self.tmp / 'mnt'
        self.mnt.mkdir()
        self.patches = [patch.object(D, 'FSTAB', self.fstab), patch.object(D, 'MNT', self.mnt)]
        for p in self.patches:
            p.start()
        self.calls = []

    def tearDown(self):
        for p in self.patches:
            p.stop()
        import shutil
        shutil.rmtree(self.tmp)

    def fake(self, mount_ok=True):
        def run(cmd, timeout=20):
            self.calls.append(cmd)
            if cmd[0] == 'lsblk':
                return 0, LSBLK
            if cmd[0] == 'mount':
                return (0, '') if mount_ok else (32, '')
            if cmd[0] == 'journalctl':
                return 0, 'ntfs3(sdd1): something\nEXT4-fs (sdd1): bad geometry\n'
            if cmd[0] == 'findmnt':
                return 0, ''
            return 0, ''
        return run

    def test_add_keeps_an_entry_that_mounts(self):
        with patch.object(D, 'run', self.fake()):
            target = D.add('aaaa-bbbb')
        self.assertEqual(target, str(self.mnt / 'Games'))
        text = self.fstab.read_text()
        self.assertIn(f'UUID=aaaa-bbbb  {self.mnt}/Games  ext4', text)
        self.assertTrue((self.mnt / 'Games').is_dir())
        self.assertIn(['systemctl', 'start', D.unit(target).replace('.mount', '.automount')], self.calls)
        self.assertTrue(self.fstab.with_name('fstab.deckos-bak').exists(), 'a backup first')

    def test_add_never_keeps_an_entry_that_didnt_mount(self):
        with patch.object(D, 'run', self.fake(mount_ok=False)):
            with self.assertRaises(D.Refused) as e:
                D.add('aaaa-bbbb')
        self.assertIn('bad geometry', str(e.exception))
        self.assertEqual(self.fstab.read_text(), FSTAB, 'fstab exactly as it was')
        self.assertFalse((self.mnt / 'Games').exists(), 'the folder it made is gone')

    def test_add_refuses(self):
        with patch.object(D, 'run', self.fake()):
            for uuid in ('ROOT', '61E1', 'EA6C', 'nope', '4C3C'):  # system, EFI, Ventoy's EFI, absent, already there
                with self.subTest(uuid=uuid), self.assertRaises(D.Refused):
                    D.add(uuid)

    def test_remove_only_its_own(self):
        with patch.object(D, 'run', self.fake()):
            self.assertEqual(D.remove('4C3C'), '/mnt/SSD')
            self.assertNotIn('/mnt/SSD', self.fstab.read_text())
            with self.assertRaises(D.Refused):
                D.remove('9999')  # /mnt/Old, set up by hand
            with self.assertRaises(D.Refused):
                D.remove('ROOT')


class HealthTests(unittest.TestCase):
    def test_reads_smart(self):
        self.assertEqual(D.health_of({'smart_status': {'passed': False}})['state'], D.BAD)
        bad = D.health_of({'smart_status': {'passed': True}, 'ata_smart_attributes': {'table': [
            {'id': 5, 'raw': {'value': 3}}, {'id': 197, 'raw': {'value': 5}}]}})
        self.assertEqual(bad['state'], D.WARN)
        self.assertIn('8 damaged', bad['text'])
        worn = D.health_of({'smart_status': {'passed': True}, 'nvme_smart_health_information_log': {'percentage_used': 93}})
        self.assertEqual(worn['state'], D.WARN)
        ok = D.health_of({'smart_status': {'passed': True}, 'power_on_time': {'hours': 6120}, 'temperature': {'current': 41}})
        self.assertEqual((ok['state'], ok['hours'], ok['temp']), (D.GOOD, 6120, 41))
        self.assertEqual(D.health_of({})['state'], D.INFO)

    def test_needs_root_to_change(self):
        if os.geteuid() == 0:
            self.skipTest('running as root')
        self.assertEqual(D.main(['startup', 'add', 'x']), 3)


if __name__ == '__main__':
    unittest.main()
