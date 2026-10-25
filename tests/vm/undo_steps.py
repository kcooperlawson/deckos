# deckos undo, end to end on an installed DecKoOS: an update, its undo, a restart, then clean (see vm.py).
D = '/usr/local/bin/deckos-new'
get = f'curl -fsS http://10.0.2.2:{vm.port}/deckos -o /tmp/deckos && echo deckos-test | sudo -S -p "" install -m755 /tmp/deckos {D}'

vm.run(get)
vm.run('findmnt -no FSROOT /; pacman -Q deckos-settings')
vm.run('echo kept > ~/keep.txt')
# an update: snap-pac takes the pre/post pair
vm.sudo('pacman -Sy --noconfirm cowsay', timeout=900)
vm.run('pacman -Q cowsay')
vm.sudo('sh -c "echo after-update > /etc/deckos-undo-marker"')  # a change to / after the update: undone too
_, rows = vm.run(f'{D} undo --tsv')
pre = rows.splitlines()[0].split('\t')[0]
assert 'cowsay' in rows.splitlines()[0], rows
vm.run(f'{D} undo list')
# refusals first: not a pre snapshot, not a number, not root
code, out = vm.sudo(f'{D} undo 1', ok=False); assert code != 0 and "isn't the 'before'" in out, out
code, out = vm.run(f'{D} undo {pre}', ok=False); assert code != 0 and 'needs root' in out, out
code, out = vm.sudo(f'{D} undo abc', ok=False); assert code == 2, out
vm.sudo(f'{D} undo {pre}')
vm.run('pacman -Q cowsay')  # nothing changes before the restart
vm.reboot()
vm.run('findmnt -no FSROOT /')
code, _ = vm.run('pacman -Q cowsay', ok=False); assert code != 0, 'cowsay still installed after undo'
code, _ = vm.run('cat /etc/deckos-undo-marker', ok=False); assert code != 0, '/etc change made after the update survived the undo'
vm.run('cat ~/keep.txt')
vm.run('cat /var/lib/deckos/undo')
vm.run('systemctl is-system-running --wait || systemctl --failed --no-legend', ok=False)
_, top = vm.sudo('sh -c "mount -o subvolid=5 $(findmnt -no SOURCE / | sed s/\\\\[.*//) /mnt && ls /mnt && umount /mnt"')
assert '@.undone-' in top, top
vm.run(get)
vm.sudo(f'{D} undo clean')
vm.sudo('sh -c "mount -o subvolid=5 $(findmnt -no SOURCE / | sed s/\\\\[.*//) /mnt && ls /mnt && umount /mnt"')
_, state = vm.run('cat /var/lib/deckos/undo'); assert 'cleaned=' in state, state
_, top = vm.sudo('sh -c "mount -o subvolid=5 $(findmnt -no SOURCE / | sed s/\\\\[.*//) /mnt && ls /mnt && umount /mnt"')
assert '@.undone' not in top, top
code, out = vm.sudo(f'{D} undo clean'); assert 'nothing to clean' in out, out
