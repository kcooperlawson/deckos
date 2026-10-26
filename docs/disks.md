# DecKoOS Disks

Every disk and partition on the PC, each drive's health, and above all whether the drives meant to be there after a
restart actually will be. Open it from the menu ("disks"), DecKoOS Hub > System > Disks, or `deckos-disks`.

## The start-up check

The banner at the top is green when every drive set to mount at start-up will. When one won't, it names it, says
why, and offers the fix. DecKoOS checks each entry in `/etc/fstab` against what's really there:

| What it finds | What it means | The fix |
|---|---|---|
| Marked dirty | The PC was cut off while the drive was in use; NTFS drives then refuse to mount at every start | **Repair** clears the mark (then run `chkdsk /f` in Windows when you can) |
| Held by Windows | Windows hibernated on it (Fast Startup) | In Windows: `powercfg /h off` as Administrator, then Shut Down |
| Wrong file system | fstab names a different file system than the drive has (often after reformatting it) | For drives DecKoOS set up: **Don't mount at start-up**, then **Mount at start-up** again |
| Didn't mount at this start-up | systemd tried and failed; the journal's reason is shown | **Repair** |
| Folder missing | The mount point doesn't exist | **Repair** makes it |
| Waits for a missing drive | An entry without `nofail` for a drive that isn't connected: start-up stalls 90 seconds | Remove it |
| Read-only | It mounted, but only for reading | Usually Windows Fast Startup |

Partitions that could hold files but aren't in fstab are offered with **Mount at start-up**.

## Mount at start-up

DecKoOS writes the entry by UUID, with `nofail` and a short device timeout so a missing drive never holds start-up
up, and for external drives `x-systemd.automount` so they mount when first opened. Then it **mounts the drive to
test it before keeping the entry**: if the test mount fails, `/etc/fstab` is restored exactly as it was (a copy is
also kept in `/etc/fstab.deckos-bak`) and you see the reason. Entries go in the same DecKoOS block as `deckos drives`;
entries outside it (the system's `/`, `/home`, EFI, anything set up by hand) are shown but never changed.

**Don't mount at start-up** removes DecKoOS's entry and unmounts the drive; **Mount for now** and **Unmount** use
udisks, like DecKoOS Files, and last until you restart or unplug it.

## Health

**Check health** asks each drive for its own SMART report (it needs your password) and keeps the result, so System
Doctor can warn when a drive reports failing, has damaged sectors, or has used most of its rated writes. USB
enclosures often hide the report; then there's simply none.

## From a terminal

`deckos disks list` and `deckos disks verify` read; `sudo deckos disks startup add UUID`, `startup remove UUID`,
`repair UUID` and `health` change things. The Assistant may run the reading ones without asking.

## Not yet

Creating, deleting, resizing and formatting partitions. They erase data, so they'll come with the installer's safety
rules: nothing in use, BitLocker or holding Windows, and nothing existing changed without an explicit choice.
