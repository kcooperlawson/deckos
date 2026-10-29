# The installer's whole-disk erase and two-drive install on real disks (see vm.py): list_erase, disk_contents,
# make_space erase:…, and one btrfs over two devices. Make the disks and functions.bash first (the same
# functions.bash as partition_steps.py):
#   W=out/erasetest; mkdir -p $W/serve; truncate -s 80G $W/one.img $W/two.img; truncate -s 32G $W/small.img
#   printf 'label: gpt\nstart=1MiB, size=1GiB, type=U\nstart=2GiB, size=30GiB, type=L\n' | sfdisk -q $W/one.img
#   printf 'label: gpt\nstart=1MiB, size=40GiB, type=L\n' | sfdisk -q $W/two.img
#   printf 'label: gpt\nstart=1MiB, size=10GiB, type=L\n' | sfdisk -q $W/small.img
#   sed -n '/^MNT=/p; /^ESP_GUID=/p; /^MIN_GB=/p; /^mnt_disk() {/,/^}/p; /^list_free() {/,/^}/p; /^list_erase() {/,/^}/p; /^disk_contents() {/,/^}/p; /^make_space() {/,/^}/p' \
#     installer/deckos-install > $W/serve/functions.bash; cp tests/vm/partition_harness.bash $W/serve/
#   VM_TMP=out VM_EXTRA_DISKS=$W/one.img,$W/two.img,$W/small.img python3 tests/vm/vm.py DISK VARS $W/serve tests/vm/erase_steps.py

def dev(serial):
    return vm.run(f'readlink -f /dev/disk/by-id/virtio-{serial}')[1].strip()


vm.run(f'curl -fsS http://10.0.2.2:{vm.port}/functions.bash -o /tmp/functions.bash && '
       f'curl -fsS http://10.0.2.2:{vm.port}/partition_harness.bash -o /tmp/h.bash')
H = 'bash /tmp/h.bash'
one, two, small = dev('one'), dev('two'), dev('small')

# something on each: a FAT boot partition and a data partition with a file on one, a data partition on two
vm.sudo(f'sh -c "mkfs.fat -F 32 -n EFI {one}1 >/dev/null && mkfs.ext4 -q -L games {one}2 && mkfs.ext4 -q {two}1 '
        f'&& mkdir -p /mnt/data && mount {one}2 /mnt/data && echo keep > /mnt/data/file"')

# listed: both big disks; the one with a mounted partition is blocked and says where; the small one is too small
_, rows = vm.sudo(f'{H} erase-list')
lines = {r.split('\t')[0]: r.split('\t') for r in rows.splitlines() if '\t' in r}
assert 'mounted at /mnt/data' in lines[f'erase:{one}'][6], rows
assert lines[f'erase:{two}'][6] == '', rows
assert 'Too small' in lines[f'erase:{small}'][6], rows

# what's on a disk, before anyone erases it
_, contents = vm.sudo(f'{H} contents {one}')
assert f'{one}1\t1 GB\tvfat\tEFI\tboot' in contents and f'{one}2\t32 GB\text4\tgames\tdata' in contents, contents

# erasing a disk with something mounted: refused, and nothing on it changes
_, before = vm.sudo(f'sfdisk -d {one}')
code, out = vm.sudo(f'{H} make erase:{one} yes', ok=False)
assert code != 0 and 'is mounted' in out, out
_, after = vm.sudo(f'sfdisk -d {one}')
assert before == after, 'a refused erase must not touch the disk'
vm.run('cat /mnt/data/file')
vm.sudo('umount /mnt/data')

# erase with a boot partition: a new GPT, FAT32 EFI the firmware can read, DecKoOS; the old file systems are gone
_, out = vm.sudo(f'{H} make erase:{one} yes')
assert f'ESP={one}1' in out and f'TARGET={one}2' in out, out
_, fsck = vm.sudo(f'fsck.fat -n {one}1')
assert int(fsck.split('/')[-1].split()[0]) >= 65525, fsck
_, fs = vm.sudo(f'lsblk -lnpo PATH,FSTYPE,LABEL {one}')
assert 'games' not in fs and 'ext4' not in fs, fs

# erase without one (the second drive): a single DecKoOS partition
_, out = vm.sudo(f'{H} make erase:{two} no')
assert f'TARGET={two}1' in out and 'ESP= ' in out, out
_, parts = vm.sudo(f'lsblk -lnpo PATH,TYPE {two}')
assert parts.count('part') == 1, parts

# the small disk was never touched
_, small_parts = vm.sudo(f'sfdisk -d {small}')
assert f'{small}1' in small_parts, small_parts

# one btrfs over both, as the installer makes it: data single (all the space), metadata on both
vm.sudo(f'mkfs.btrfs -q -f -d single -m raid1 {one}2 {two}1')
vm.sudo('btrfs device scan')
vm.sudo(f'sh -c "mount {one}2 /mnt/data && echo both > /mnt/data/file && sync"')
_, show = vm.sudo('btrfs filesystem show /mnt/data')
assert show.count('devid') == 2, show
_, usage = vm.sudo('btrfs filesystem usage -b /mnt/data')
size = int([l for l in usage.splitlines() if 'Device size' in l][0].split()[-1])
assert size > 150e9, usage   # roughly 79 + 80 GB
vm.sudo('umount /mnt/data')
