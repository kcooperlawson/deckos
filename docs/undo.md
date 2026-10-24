# Undo an update

`deckos undo` (and DeckOS Hub > System > Undo an update) takes the system back to how it was before
an update, from the next restart.

## How it works

snap-pac takes a snapper snapshot of `/` before ("pre") and after ("post") every pacman transaction.
`deckos undo N` takes pre snapshot N and, on the btrfs top level (`subvolid=5`):

1. makes a writable snapshot of `@snapshots/N/snapshot` as `@.undo-new`,
2. writes `/var/lib/deckos/undo` into it (what was undone, and where the old system is kept),
3. renames `@` to `@.undone-DATE` and `@.undo-new` to `@` (if the second rename fails, the first is
   put back, so there is always an `@`).

The running system doesn't change; the restart mounts the new `@` (fstab and GRUB name it by path).
`/boot` lives in `@`, so kernels, modules, the initramfs, GRUB's menu and pacman's database go back
together. `/home`, `/var/log` and `/var/cache/pacman/pkg` are their own subvolumes and stay as they are.
`deckos undo clean` deletes the `@.undone-*` systems (recursively, for nested subvolumes) and adds
`cleaned=` to the state file so the Hub stops offering it.

It refuses when: the snapshot isn't a pre snapshot, an update is running (`db.lck`), or `/` isn't
DeckOS's layout (`@` and `@snapshots` on btrfs). GRUB's "DeckOS snapshots" menu still works for
booting a snapshot read-only without changing anything.

## Limits

- Nested subvolumes inside `@` (Docker's images and containers, `/var/lib/machines`) aren't in snapshots,
  so they stay with the kept system. Docker starts empty after an undo until it's cleaned up or redone.
- GRUB's EFI core image isn't in a snapshot. DeckOS never re-runs `grub-install` after installing, so it
  matches `/boot/grub` in every snapshot; undoing past a `grub-install` someone ran by hand could not.
- The kept system takes the disk space of everything that changed since the snapshot until it's cleaned.

## Checked

`tests/test_undo.py` covers which updates are offered and how they're named (fake snapper).
`tests/vm/undo_steps.py` runs the whole thing on an installed DeckOS in QEMU (an install test disk):
an update (cowsay), a change to `/etc`, the refusals, the undo, a restart (cowsay and the `/etc` change
gone, a file in `/home` kept, `systemctl is-system-running` = running), then `undo clean`. It passed on
the 0.5.5 install test disk on October 24, 2026.
