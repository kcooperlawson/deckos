# The installer's free-space and empty-disk modes on real disks (see vm.py): real sfdisk, real kernel
# partition handling. Make the disks and functions.bash first:
#   W=out/parttest; mkdir -p $W/serve; truncate -s 80G $W/empty.img; truncate -s 200G $W/gpt.img
#   truncate -s 100G $W/mbr.img
#   printf 'label: gpt\nstart=1MiB, size=20GiB, type=L\nstart=150GiB, size=40GiB, type=L\n' | sfdisk -q $W/gpt.img
#   printf 'label: dos\nstart=1MiB, size=20GiB, type=83\n' | sfdisk -q $W/mbr.img
#   sed -n '/^MNT=/p; /^ESP_GUID=/p; /^MIN_GB=/p; /^mnt_disk() {/,/^}/p; /^list_free() {/,/^}/p; /^list_erase() {/,/^}/p; /^disk_contents() {/,/^}/p; /^make_space() {/,/^}/p' installer/deckos-install \
#     > $W/serve/functions.bash; cp tests/vm/partition_harness.bash $W/serve/
#   VM_EXTRA_DISKS=$W/empty.img,$W/gpt.img,$W/mbr.img python3 tests/vm/vm.py DISK VARS $W/serve tests/vm/partition_steps.py

def dev(serial):
    return vm.run(f'readlink -f /dev/disk/by-id/virtio-{serial}')[1].strip()


vm.run(f'curl -fsS http://10.0.2.2:{vm.port}/functions.bash -o /tmp/functions.bash && '
       f'curl -fsS http://10.0.2.2:{vm.port}/partition_harness.bash -o /tmp/h.bash')
H = 'bash /tmp/h.bash'
empty, gpt, mbr = dev('empty'), dev('gpt'), dev('mbr')

# a disk in use: its first partition mounted, with a file on it
vm.sudo(f'sh -c "mkfs.ext4 -q {gpt}1 && mkdir -p /mnt/data && mount {gpt}1 /mnt/data && echo keep > /mnt/data/file"')
_, before = vm.sudo(f'sfdisk -d {gpt}')

_, rows = vm.sudo(f'{H} list')
lines = {r.split('\t')[0]: r.split('\t') for r in rows.splitlines() if '\t' in r}
assert lines[f'free:{empty}:disk'][6] == '', rows
gpt_gaps = [r for p, r in lines.items() if p.startswith(f'free:{gpt}:')]
assert len(gpt_gaps) == 2, rows                       # between the partitions, and the end
usable = [r for r in gpt_gaps if r[6] == '']
assert len(usable) == 1 and usable[0][1].startswith('139 GB'), gpt_gaps
small = [r for r in gpt_gaps if r[6]]
assert 'needs 64 GB' in small[0][6], small
assert 'MBR' in [r for p, r in lines.items() if p.startswith(f'free:{mbr}:')][0][6], rows

# free space: one new partition, exactly in the gap; nothing else moves, the mounted one keeps working
free = usable[0][0]
_, out = vm.sudo(f'{H} make {free}')
start = free.split(':')[2]
target = out.split('TARGET=')[1].split()[0]
_, after = vm.sudo(f'sfdisk -d {gpt}')
old_lines = [l for l in before.splitlines() if l.startswith('/dev/')]
new_lines = [l for l in after.splitlines() if l.startswith('/dev/')]
assert all(l in new_lines for l in old_lines), (before, after)   # every old partition exactly as it was
added = [l for l in new_lines if l not in old_lines]
assert len(added) == 1 and f'start= {start:>12}'.replace(' ', '') in added[0].replace(' ', ''), added
vm.run('cat /mnt/data/file')
vm.sudo(f'mkfs.btrfs -q -f {target}')
vm.sudo(f'lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS {gpt}')

# the same gap again: it's gone now, so nothing happens
code, out = vm.sudo(f'{H} make {free}', ok=False)
assert code != 0 and 'changed since it was listed' in out, out
_, again = vm.sudo(f'sfdisk -d {gpt}')
assert again == after, 'a refused make must not touch the disk'

# an empty disk: GPT, a FAT32 EFI partition the firmware can read, DecKoOS
_, out = vm.sudo(f'{H} make free:{empty}:disk')
assert f'ESP={empty}1' in out and f'TARGET={empty}2' in out, out
vm.sudo(f'sfdisk -l {empty}')
_, fsck = vm.sudo(f'fsck.fat -n {empty}1')
clusters = int(fsck.split('/')[-1].split()[0])
assert clusters >= 65525, f'FAT32 needs 65525+ clusters for UEFI, got {clusters}'
code, out = vm.sudo(f'{H} make free:{empty}:disk', ok=False)
assert code != 0 and "isn't empty any more" in out, out
vm.sudo('umount /mnt/data')
