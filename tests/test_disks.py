"""DecKoOS Disks: what's on each disk, the start-up check (will each drive mount after a restart, and if not, why),
and changes that only touch DecKoOS's part of fstab and never keep an entry that didn't mount. Nothing real is read
or written: lsblk, fstab, the boot's log and every command are canned."""
import json
import os
import re
import shutil
import subprocess
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


# ------------------------------------------------------------------ partition editing

M = 1 << 20
GPT_DATA, LINUX = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7', '0fc63daf-8483-4772-8e79-3d69d8477de4'


def epart(name, n, size, start_mib, fstype='', label='', uuid='', ptype='', guid='', mounts=()):
    p = part(name, size, start_mib * 2048, fstype, label, uuid, ptype, mounts)
    p.update(partn=n, parttype=guid or None)
    return p


EDIT = json.dumps({'blockdevices': [
    disk('nvme0n1', 250 * G, 'Samsung SSD 970', 'nvme', [
        epart('nvme0n1p1', 1, 600 * M, 1, 'vfat', '', '61E1', 'EFI System', D.ESP, ['/boot/efi']),
        epart('nvme0n1p2', 2, 200 * G, 601, 'btrfs', 'DecKoOS', 'ROOT', 'Linux filesystem', LINUX, ['/', '/home']),
        epart('nvme0n1p3', 3, 40 * G, 200 * 1024 + 601, 'ext4', 'Spare', 'SPARE', 'Linux filesystem', LINUX)]),
    disk('sda', 1000 * G, 'Samsung SSD 870', 'sata', [
        epart('sda1', 1, 400 * 1024 * M, 1, 'ntfs', 'Games', 'GAMES', 'Microsoft basic data', GPT_DATA),
        epart('sda2', 2, 200 * 1024 * M, 600 * 1024, 'ext4', 'Old', 'OLD', 'Linux filesystem', LINUX)]),
    disk('sdb', 2000 * G, 'WD Elements', 'usb', [
        epart('sdb1', 1, 100 * G, 1, 'BitLocker', '', 'BL'),
        epart('sdb2', 2, 100 * G, 102401, 'crypto_LUKS', '', 'LUKS'),
        epart('sdb3', 3, 100 * G, 204801, 'linux_raid_member', '', 'RAID'),
        epart('sdb4', 4, 100 * G, 307201, 'exfat', 'Stick', 'MNT', mounts=['/run/media/me/Stick']),
        epart('sdb5', 5, 100 * G, 409601, 'exfat', 'Photos', 'PHOTOS'),
        epart('sdb6', 6, 100 * G, 512001, 'xfs', 'Hand', 'HAND'),
        epart('sdb7', 7, 100 * G, 614401, 'vfat', 'Music', 'MUSIC', 'Microsoft basic data', GPT_DATA)]),
    disk('sdc', 64 * G, 'Blank', 'usb', [], pttype=None),
    disk('sdd', 32 * G, 'Old stick', 'usb', [
        epart('sdd1', 1, 8 * G, 1, 'ext4', 'One', 'ONE', guid='0x83'),
        epart('sdd2', 2, 20 * G, 8193, '', '', '', guid='0x5'),
        epart('sdd5', 5, 8 * G, 8194, 'ext4', 'Five', 'FIVE', guid='0x83')], pttype='dos'),
    disk('sde', 128 * G, 'Ventoy stick', 'usb', [
        epart('sde1', 1, 120 * G, 1, 'exfat', 'Ventoy', 'VTOY')]),
]})
EDIT_FSTAB = f"""UUID=ROOT / btrfs rw 0 0
UUID=HAND /mnt/Hand xfs defaults 0 0
{D.BEGIN}
UUID=PHOTOS  /mnt/Photos  exfat  nofail  0 0
{D.END}
"""


class SafetyTests(unittest.TestCase):
    """Which partitions DecKoOS will change, and why not: the same answers the app shows and root enforces."""

    def setUp(self):
        self.disks = {d.name: d for d in D.inventory(EDIT)}
        self.parts = {p.name: (p, d) for d in self.disks.values() for p in d.parts}
        self.entries = D.fstab(EDIT_FSTAB)

    def why(self, name, action):
        p, d = self.parts[name]
        return D.why_not(p, d, self.entries, action)

    def test_never_touched(self):
        for name, words in (('nvme0n1p1', 'EFI'), ('nvme0n1p2', 'DecKoOS itself'), ('sdb1', 'BitLocker'),
                            ('sdb2', 'LUKS'), ('sdb3', 'RAID'), ('sdb4', 'mounted'), ('sdb5', 'start-up'),
                            ('sdb6', 'outside DecKoOS'), ('sdd2', 'extended'), ('sdd5', 'logical'), ('sde1', 'Ventoy')):
            for action in ('format', 'delete', 'resize'):
                with self.subTest(name=name, action=action):
                    self.assertIn(words, self.why(name, action))

    def test_the_system_disk_is_only_formatted(self):
        self.assertEqual(self.why('nvme0n1p3', 'format'), '', 'a spare partition on the system disk can be formatted')
        for action in ('delete', 'resize'):
            self.assertIn('running DecKoOS', self.why('nvme0n1p3', action))
        self.assertIn('running DecKoOS', D.why_not_create(self.disks['nvme0n1']))

    def test_what_may_change(self):
        for name in ('sda1', 'sda2', 'sdd1', 'sdb7'):
            for action in ('format', 'delete'):
                self.assertEqual(self.why(name, action), '', (name, action))
        self.assertEqual(self.why('sda1', 'resize'), '', 'NTFS resizes')
        self.assertEqual(self.why('sda2', 'resize'), '', 'ext4 resizes')
        self.assertIn("can't be resized", self.why('sdb7', 'resize'), 'FAT32 has no reliable resize tool')

    def test_where_partitions_can_be_made(self):
        self.assertEqual(D.why_not_create(self.disks['sda']), '')
        self.assertEqual(D.why_not_create(self.disks['sdc']), '', 'an empty disk gets GPT')
        self.assertIn('MBR', D.why_not_create(self.disks['sdd']))
        self.assertIn('Ventoy', D.why_not_create(self.disks['sde']))
        bare = D.Disk('sdf', '/dev/sdf', 64 * G, fstype='exfat')
        self.assertIn('no partition table', D.why_not_create(bare), 'a stick formatted whole holds files')

    def test_free_space_and_room_to_grow(self):
        sda = self.disks['sda']
        free = [item for kind, item in sda.layout() if kind == 'free']
        self.assertEqual([(f.start, f.size) for f in free],
                         [((400 * 1024 + 1) * M, (200 * 1024 - 1) * M),
                          (800 * 1024 * M, (1000 * G - 33 * 512) // M * M - 800 * 1024 * M)])
        self.assertTrue(all(f.start % M == 0 and f.size % M == 0 for f in free), 'MiB-aligned')
        self.assertEqual(sda.room_after(self.parts['sda1'][0]), (200 * 1024 - 1) * M)
        self.assertEqual(self.disks['nvme0n1'].room_after(self.parts['nvme0n1p1'][0]), 0)

    def test_fingerprint_and_confirmation(self):
        sda = self.disks['sda']
        self.assertEqual(D.fingerprint(sda), D.fingerprint(D.inventory(EDIT)[1]))
        moved = D.inventory(EDIT.replace('"OLD"', '"NEW"'))[1]
        self.assertNotEqual(D.fingerprint(sda), D.fingerprint(moved), 'a reformatted partition changes it')
        self.assertEqual(D.confirm_word(self.parts['sda1'][0]), 'Games')
        self.assertEqual(D.confirm_word(D.Part('sdx1', '/dev/sdx1', 1, 0)), 'sdx1', 'no label: its name')

    def test_labels(self):
        self.assertEqual(D.check_label('vfat', 'Music'), 'MUSIC')
        for fs, bad in (('vfat', 'TwelveLetter'), ('ext4', 'x' * 17), ('ntfs', 'a/b'), ('ext4', '-L'), ('zfs', 'x')):
            with self.subTest(fs=fs, label=bad), self.assertRaises(D.Refused):
                D.check_label(fs, bad)


class Fake:
    """Every command DecKoOS runs, answered from canned output; records (cmd, input)."""

    def __init__(self, fail=(), windows=False, free=None, minimum=1_000_000):
        self.calls, self.fail, self.windows = [], set(fail), windows
        self.free = free if free is not None else [((400 * 1024 + 1) * 2048, 600 * 1024 * 2048 - 1),
                                                   (800 * 1024 * 2048, 1000 * G // 512 - 34)]
        self.minimum = minimum

    def __call__(self, cmd, timeout=20, input=None):
        self.calls.append((cmd, input))
        key = ' '.join(cmd[:2])
        for f in self.fail:
            if ' '.join(cmd).startswith(f):
                return 1, 'it went wrong\n'
        if cmd[0] == 'lsblk':
            return 0, EDIT
        if cmd[0] == 'mount' and '-o' in cmd and self.windows:
            (Path(cmd[-1]) / 'Windows/System32').mkdir(parents=True)
        if key == 'sfdisk -F':
            return 0, 'Unpartitioned space\n\n Start End Sectors Size\n' + \
                ''.join(f'{a} {b} {b - a + 1} 1G\n' for a, b in self.free)
        if key == 'sfdisk --dump':
            return 0, 'label: gpt\n/dev/sda1 : start=2048\n'
        if key == 'sfdisk -J':
            return 0, json.dumps({'partitiontable': {'partitions': [
                {'node': '/dev/sda1', 'start': 2048}, {'node': '/dev/sda3', 'start': (401 * 1024 + 1) * 2048}]}})
        if cmd[0] == 'resize2fs' and cmd[1] == '-P':
            return 0, f'Estimated minimum size of the filesystem: {self.minimum}\n'
        if cmd[0] == 'dumpe2fs':
            return 0, 'Block size:               4096\n'
        if cmd[0] == 'blkid':
            return 0, 'NEW-UUID\n'
        return 0, ''

    def ran(self, *prefix):
        return [(c, i) for c, i in self.calls if c[:len(prefix)] == list(prefix)]

    def changes(self):
        """The commands that write to a disk (a read-only mount for the Windows check doesn't)."""
        writes = ('mkfs', 'wipefs', 'resize2fs', 'ntfsresize', 'sfdisk', 'partx')
        return [c for c, _ in self.calls if c[0].startswith(writes) and c[:2] not in (['sfdisk', '-F'], ['sfdisk', '-J'])
                and c[:2] != ['sfdisk', '--dump'] and c[:2] != ['resize2fs', '-P'] and '--no-action' not in c]


class EditTests(unittest.TestCase):
    """format, create, delete and resize with every command faked: the order of steps, and what a failed one leaves."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / 'fstab').write_text(EDIT_FSTAB)
        self.patches = [patch.object(D, 'FSTAB', self.tmp / 'fstab'), patch.object(D, 'TABLES', self.tmp / 'tables'),
                        patch.object(D, '_block', lambda path: True)]
        for p in self.patches:
            p.start()
        self.fp = {d.name: D.fingerprint(d) for d in D.inventory(EDIT)}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        import shutil
        shutil.rmtree(self.tmp)

    def go(self, fake, fn, *args):
        with patch.object(D, 'run', fake):
            return fn(*args)

    def refused(self, fake, fn, *args):
        with self.assertRaises(D.Refused) as e:
            self.go(fake, fn, *args)
        return str(e.exception)

    def test_format(self):
        fake = Fake()
        uuid = self.go(fake, D.format_part, '/dev/sda2', 'exfat', 'Shared', 'Old', self.fp['sda'])
        self.assertEqual(uuid, 'NEW-UUID')
        order = [c[0] for c in fake.changes()]
        self.assertEqual(order[:2], ['wipefs', 'mkfs.exfat'])
        self.assertEqual(fake.ran('mkfs.exfat')[0][0], ['mkfs.exfat', '-L', 'Shared', '/dev/sda2'])
        self.assertIn(['sfdisk', '--no-reread', '--part-type', '/dev/sda', '2', GPT_DATA], [c for c, _ in fake.calls],
                      'Windows sees it as a data partition')

    def test_format_on_the_system_disk_leaves_its_table(self):
        fake = Fake()
        self.go(fake, D.format_part, '/dev/nvme0n1p3', 'ext4', 'Spare', 'Spare', self.fp['nvme0n1'])
        self.assertFalse(fake.ran('sfdisk'), "the running system's partition table isn't written")

    def test_nothing_happens_without_the_right_name_or_a_fresh_look(self):
        for confirm, layout, words in (('Old?', self.fp['sda'], 'type Old'), ('Old', 'stale', 'changed since')):
            fake = Fake()
            msg = self.refused(fake, D.format_part, '/dev/sda2', 'ext4', '', confirm, layout)
            self.assertIn(words, msg)
            self.assertIn('Nothing was changed', msg)
            self.assertEqual(fake.changes(), [])

    def test_refused_partitions_are_never_touched(self):
        for path, fp in (('/dev/sdb1', 'sdb'), ('/dev/sdb4', 'sdb'), ('/dev/nvme0n1p2', 'nvme0n1')):
            fake = Fake()
            name = next(p for d in D.inventory(EDIT) for p in d.parts if p.path == path)
            self.refused(fake, D.format_part, path, 'ext4', '', D.confirm_word(name), self.fp[fp])
            self.assertEqual(fake.changes(), [], path)

    def test_windows_is_looked_for_inside_ntfs(self):
        fake = Fake(windows=True)
        msg = self.refused(fake, D.delete, '/dev/sda1', 'Games', self.fp['sda'])
        self.assertIn('holds Windows', msg)
        self.assertEqual(fake.changes(), [])
        self.assertTrue(fake.ran('umount'), 'the read-only look is unmounted again')
        unreadable = Fake(fail=['mount -t ntfs3'])
        self.assertIn("won't mount", self.refused(unreadable, D.delete, '/dev/sda1', 'Games', self.fp['sda']))

    def test_a_failed_format_says_what_is_left(self):
        msg = self.refused(Fake(fail=['mkfs.ext4']), D.format_part, '/dev/sda2', 'ext4', '', 'Old', self.fp['sda'])
        self.assertIn("It's empty now", msg)
        self.assertIn('partition itself is unchanged', msg)

    def test_create_in_free_space(self):
        fake = Fake()
        node, uuid = self.go(fake, D.create, '/dev/sda', 401 * 1024 * M + 5, 100 * G, 'ext4', 'Games2', self.fp['sda'])
        self.assertEqual((node, uuid), ('/dev/sda3', 'NEW-UUID'))
        (cmd, script), = fake.ran('sfdisk', '-q', '--append')
        self.assertEqual(script, f'start={(401 * 1024 + 1) * 2048}, size={(100 * G - M + 5) // M * M // 512}, type={LINUX}\n',
                         'starts on the next MiB, ends inside what was asked')
        self.assertIn('--no-reread', cmd, "the disk's other partitions may be in use")
        self.assertIn(['partx', '-a', '--nr', '3', '/dev/sda'], [c for c, _ in fake.calls])
        self.assertEqual(len(list((self.tmp / 'tables').iterdir())), 1, 'the table was saved first')

    def test_create_only_where_it_is_still_free(self):
        fake = Fake(free=[(800 * 1024 * 2048, 1000 * G // 512 - 34)])
        msg = self.refused(fake, D.create, '/dev/sda', 401 * 1024 * M + 5, 100 * G, 'ext4', '', self.fp['sda'])
        self.assertIn("isn't free any more", msg)
        self.assertEqual(fake.changes(), [])
        for disk in ('nvme0n1', 'sdd', 'sde'):
            fake = Fake()
            self.refused(fake, D.create, f'/dev/{disk}', M, 10 * G, 'ext4', '', self.fp[disk])
            self.assertEqual(fake.changes(), [], disk)

    def test_create_on_an_empty_disk_writes_gpt_first(self):
        fake = Fake(free=[(2048, 64 * G // 512 - 34)])
        self.go(fake, D.create, '/dev/sdc', M, 64 * G - 2 * M, 'exfat', 'Stick', self.fp['sdc'])
        tables = [i for c, i in fake.calls if c[:1] == ['sfdisk'] and i]
        self.assertEqual(tables[0], 'label: gpt\n')

    def test_create_says_when_formatting_failed(self):
        msg = self.refused(Fake(fail=['mkfs.ext4']), D.create, '/dev/sda', 401 * 1024 * M + 5, 10 * G, 'ext4', '',
                           self.fp['sda'])
        self.assertIn('/dev/sda3 was made', msg)
        self.assertIn('empty partition', msg)

    def test_delete(self):
        fake = Fake()
        out = self.go(fake, D.delete, '/dev/sda2', 'Old', self.fp['sda'])
        self.assertIn(['sfdisk', '-q', '--no-reread', '--delete', '/dev/sda', '2'], [c for c, _ in fake.calls])
        self.assertIn(str(self.tmp / 'tables'), out, 'says where the old table is')
        self.assertFalse(fake.ran('wipefs'), 'the data is left where it was')
        self.assertIn("wasn't written", self.refused(Fake(fail=['sfdisk -q --no-reread --delete']), D.delete,
                                                     '/dev/sda2', 'Old', self.fp['sda']))

    def test_shrink_ext4_file_system_first(self):
        fake = Fake(minimum=10_000_000)  # 40 GB of 4 KiB blocks
        self.go(fake, D.resize, '/dev/sda2', 100 * G, 'Old', self.fp['sda'])
        steps = [c[0] for c in fake.changes()]
        self.assertEqual(steps[:2], ['resize2fs', 'sfdisk'], 'the file system shrinks before the partition does')
        self.assertEqual(fake.ran('resize2fs', '/dev/sda2')[0][0], ['resize2fs', '/dev/sda2', f'{100 * G // M * M // 1024}K'])
        (_, script), = fake.ran('sfdisk', '-q', '--no-reread', '-N')
        self.assertEqual(script, f'start={600 * 1024 * 2048}, size={100 * G // M * M // 512}\n', 'the start never moves')
        self.assertTrue(fake.ran('e2fsck', '-f', '-p'), 'checked first')

    def test_shrink_refused_below_what_it_holds(self):
        fake = Fake(minimum=40_000_000)  # 160 GB
        msg = self.refused(fake, D.resize, '/dev/sda2', 100 * G, 'Old', self.fp['sda'])
        self.assertIn('smallest it can be', msg)
        self.assertEqual(fake.changes(), [])

    def test_a_failed_table_change_grows_the_file_system_back(self):
        fake = Fake(fail=['sfdisk -q --no-reread -N'])
        msg = self.refused(fake, D.resize, '/dev/sda2', 100 * G, 'Old', self.fp['sda'])
        self.assertIn('the disk is as it was', msg)
        self.assertEqual(fake.ran('resize2fs', '/dev/sda2')[-1][0], ['resize2fs', '/dev/sda2'], 'grown to fill again')

    def test_grow_ntfs_table_first_after_a_trial_run(self):
        fake = Fake()
        out = self.go(fake, D.resize, '/dev/sda1', 500 * G, 'Games', self.fp['sda'])
        writes = [c for c in fake.changes() if c[0] != 'partx']
        self.assertEqual(writes[0][:2], ['sfdisk', '-q'], 'the partition grows before the file system')
        self.assertEqual(writes[1][0], 'ntfsresize')
        self.assertTrue(fake.ran('ntfsresize', '--no-action', '/dev/sda1'), 'a trial run first')
        self.assertEqual(fake.ran('ntfsresize', '/dev/sda1')[0][1], 'y\n')
        self.assertIn('Windows checks it', out)

    def test_grow_only_into_the_free_space_after_it(self):
        fake = Fake()
        msg = self.refused(fake, D.resize, '/dev/sda1', 700 * G, 'Games', self.fp['sda'])
        self.assertIn("isn't that much free space", msg)
        self.assertEqual(fake.changes(), [])

    def test_a_failed_ntfs_trial_after_growing_puts_the_partition_back(self):
        fake = Fake(fail=['ntfsresize --no-action /dev/sda1'])
        msg = self.refused(fake, D.resize, '/dev/sda1', 500 * G, 'Games', self.fp['sda'])
        self.assertIn('the disk is as it was', msg)
        scripts = [i for c, i in fake.ran('sfdisk', '-q', '--no-reread', '-N')]
        self.assertEqual(scripts[-1], f'start=2048, size={400 * 1024 * 2048}\n', 'its old size again')

    def test_a_table_the_kernel_did_not_take(self):
        fake = Fake(fail=['partx -u'])
        msg = self.refused(fake, D.resize, '/dev/sda1', 500 * G, 'Games', self.fp['sda'])
        self.assertIn('as it was', msg, 'growing: the old table goes back before the file system is touched')
        self.assertFalse(fake.ran('ntfsresize', '/dev/sda1'))
        fake = Fake(fail=['partx -u'], minimum=10_000_000)
        msg = self.refused(fake, D.resize, '/dev/sda2', 100 * G, 'Old', self.fp['sda'])
        self.assertIn('Nothing is lost', msg)
        self.assertEqual(len(fake.ran('resize2fs', '/dev/sda2')), 1, 'shrunk once, never grown past the new partition')

    def test_shrink_ntfs_needs_its_trial_run(self):
        fake = Fake(fail=['ntfsresize --no-action'])
        msg = self.refused(fake, D.resize, '/dev/sda1', 100 * G, 'Games', self.fp['sda'])
        self.assertIn("trial run says no", msg)
        self.assertEqual(fake.changes(), [])

    def test_command_line(self):
        if os.geteuid() == 0:
            self.skipTest('running as root')
        self.assertEqual(D.main(['delete', '/dev/sda2', '--confirm', 'Old', '--layout', 'x']), 3, 'needs root')


TOOLS = all(shutil.which(t) for t in ('sfdisk', 'mkfs.ext4', 'resize2fs', 'e2fsck', 'dumpe2fs', 'mkfs.ntfs',
                                         'ntfsresize'))


@unittest.skipUnless(TOOLS, 'needs util-linux, e2fsprogs and ntfs-3g')
class RealToolTests(unittest.TestCase):
    """The commands DecKoOS runs, run for real against image files in a temp folder (never a real disk)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.img = self.tmp / 'disk.img'
        self.img.write_bytes(b'')
        os.truncate(self.img, 256 * M)
        self.disk = D.Disk('disk.img', str(self.img), 256 * M, table='gpt')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def table(self):
        return json.loads(D.run(['sfdisk', '-J', str(self.img)])[1])['partitiontable']['partitions']

    def test_partition_table_steps(self):
        self.assertEqual(D.run(['sfdisk', '-q', '--no-reread', str(self.img)], input='label: gpt\n')[0], 0)
        free = D._sectors_free(self.disk)
        self.assertEqual(free[0][0], 2048)
        code, _ = D.run(['sfdisk', '-q', '--append', '--no-reread', str(self.img)],
                        input=f'start=2048, size={64 * 2048}, type={LINUX}\n')
        self.assertEqual(code, 0)
        D.run(['sfdisk', '-q', '--append', '--no-reread', str(self.img)],
              input=f'start={128 * 2048}, size={32 * 2048}, type={GPT_DATA}\n')
        with patch.object(D, 'TABLES', self.tmp / 'tables'):
            saved = D._save_table(self.disk)
        self.assertIn('start=        2048', saved.read_text())
        p1 = D.Part('disk.img1', str(self.img) + '1', 64 * M, M, number=1)
        with patch.object(D, '_settle', lambda *cmd: True):
            self.assertEqual(D._table_size(self.disk, p1, 100 * 2048)[:2], (True, True))
        self.assertEqual([(p['start'], p['size']) for p in self.table()], [(2048, 100 * 2048), (128 * 2048, 32 * 2048)],
                         'grown in place: same start, the other partition untouched')
        D._set_type(self.disk, D.Part('disk.img2', '', 0, 0, number=2), 'ext4')
        self.assertEqual(self.table()[1]['type'].lower(), LINUX)
        self.assertEqual(D.run(['sfdisk', '-q', '--no-reread', '--delete', str(self.img), '1'])[0], 0)
        self.assertEqual([p['start'] for p in self.table()], [128 * 2048], 'only that one went')

    def test_ext4_shrink_and_grow(self):
        fs = self.tmp / 'ext4.img'
        fs.write_bytes(b'')
        os.truncate(fs, 128 * M)
        self.assertTrue(D._make_fs(str(fs), 'ext4', 'Test')[0])
        part = D.Part('ext4.img', str(fs), 128 * M, 0, 'ext4')
        self.assertEqual(D.run(['e2fsck', '-f', '-p', str(fs)])[0], 0)
        self.assertGreater(D._fs_min(part), 0)
        self.assertTrue(D._fs_resize(part, 64 * M)[0])
        head = D.run(['dumpe2fs', '-h', str(fs)])[1]
        blocks, bs = (int(re.search(rf'{k}:\s*(\d+)', head).group(1)) for k in ('Block count', 'Block size'))
        self.assertEqual(blocks * bs, 64 * M)
        self.assertTrue(D._fs_resize(part)[0], 'back to fill its (here: file) size')

    def test_ntfs_trial_and_shrink(self):
        fs = self.tmp / 'ntfs.img'
        fs.write_bytes(b'')
        os.truncate(fs, 128 * M)
        self.assertTrue(D._make_fs(str(fs), 'ntfs', 'Test')[0])
        part = D.Part('ntfs.img', str(fs), 128 * M, 0, 'ntfs')
        self.assertEqual(D.run(['ntfsresize', '--no-action', '-s', str(64 * M), str(fs)])[0], 0)
        self.assertNotEqual(D.run(['ntfsresize', '--no-action', '-s', str(M), str(fs)])[0], 0, 'too small: no')
        self.assertTrue(D._fs_resize(part, 64 * M)[0])
        self.assertNotEqual(D.run(['ntfsresize', '--no-action', str(fs)])[0], 0,
                            'after a resize Windows has to check it before the next one')
        self.assertTrue(D._fs_resize(part, again=True)[0], 'growing it back (the rollback) forces past that')

    def test_every_format(self):
        for fs in D.FORMATS:
            if not shutil.which(D.mkfs('x', fs, '')[0]):
                continue
            with self.subTest(fs=fs):
                img = self.tmp / f'{fs}.img'
                img.write_bytes(b'')
                os.truncate(img, 128 * M)
                ok, why = D._make_fs(str(img), fs, 'Test')
                self.assertTrue(ok, why)
                self.assertEqual(D.run(['blkid', '-o', 'value', '-s', 'TYPE', str(img)])[1].strip(), fs)


@unittest.skipUnless(TOOLS and os.geteuid() == 0 and shutil.which('losetup'), 'needs root (loop devices)')
class LoopDeviceTests(unittest.TestCase):
    """The whole of create, format, resize and delete on a loop device made from an image file: run as root
    (sudo python3 -m unittest tests.test_disks). Never a real disk: the device is made here and must be a loop."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        img = self.tmp / 'disk.img'
        img.write_bytes(b'')
        os.truncate(img, 512 * M)
        self.dev = subprocess.run(['losetup', '--find', '--show', '--partscan', str(img)], capture_output=True,
                                  text=True, check=True).stdout.strip()
        self.assertTrue(self.dev.startswith('/dev/loop'))
        self.patches = [patch.object(D, 'TABLES', self.tmp / 'tables'), patch.object(D, 'FSTAB', self.tmp / 'fstab')]
        (self.tmp / 'fstab').write_text('')
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        subprocess.run(['losetup', '-d', self.dev])
        import shutil
        shutil.rmtree(self.tmp)

    def disk(self):
        data = json.loads(D.run(['lsblk', '-J', '-b', '-o', D.LSBLK, self.dev])[1])
        for d in data['blockdevices']:
            d['name'] = d['name'].replace('loop', 'test')  # inventory() leaves loop devices out on purpose
        return D.inventory(json.dumps(data))[0]

    def test_whole_flow(self):
        with patch.object(D, 'inventory', lambda: [self.disk()]):
            node, _ = D.create(self.dev, M, 200 * M, 'ext4', 'First', D.fingerprint(self.disk()))
            self.assertEqual(node, self.dev + 'p1')
            p = self.disk().parts[0]
            self.assertEqual((p.fstype, p.label, p.start), ('ext4', 'First', M))
            D.resize(node, 300 * M, 'First', D.fingerprint(self.disk()))
            self.assertEqual(self.disk().parts[0].size, 300 * M)
            D.resize(node, 100 * M, 'First', D.fingerprint(self.disk()))
            self.assertEqual((self.disk().parts[0].size, self.disk().parts[0].start), (100 * M, M))
            self.assertEqual(D.run(['e2fsck', '-f', '-n', node])[0], 0, 'still a clean file system')
            D.format_part(node, 'ntfs', 'Second', 'First', D.fingerprint(self.disk()))
            self.assertEqual(self.disk().parts[0].fstype, 'ntfs')
            D.delete(node, 'Second', D.fingerprint(self.disk()))
            self.assertEqual(self.disk().parts, [])


if __name__ == '__main__':
    unittest.main()
