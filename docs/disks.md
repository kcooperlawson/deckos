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

## Changing partitions

Pick a partition to see **Format…**, **Resize…** and **Delete…**; pick free space (the hatched part of the map) for
**New partition…**. Each asks for your password, and each refuses rather than guesses:

| | What it does | What it never does |
|---|---|---|
| **Format** | Erases one partition and makes a new file system on it: ext4 or btrfs (Linux), NTFS (Windows and Linux), exFAT (any computer), FAT32 (old devices) | Move or resize it |
| **New partition** | Adds one partition in free space and formats it. An empty disk (no partition table, no file system) gets GPT first | Touch any partition that's already there; add to an MBR disk |
| **Resize** | Grows an ext4 or NTFS partition into the free space straight after it, or shrinks it down to what it holds. Only its end moves | Move its start, or copy data around. btrfs, XFS, exFAT and FAT32 aren't resized (the first two only resize while mounted; the others have no dependable tool) |
| **Delete** | Takes one partition out of the partition table; its space becomes free | Wipe it: the data stays on the disk until something overwrites it, but nothing in DecKoOS brings it back |

**What DecKoOS won't change**, and says why when you pick it: a partition that's mounted or in `/etc/fstab` (choose
Don't mount at start-up first), DecKoOS itself, the boot (EFI) partition, Windows (an NTFS partition is mounted
read-only first to look for it; one that won't mount can't be checked, so it's refused, as in the installer),
Windows' reserved and recovery partitions, swap, BitLocker, LUKS, RAID, LVM or ZFS members, extended and logical
partitions on MBR disks, and Ventoy sticks. On the disk DecKoOS runs from, partitions can be formatted but the
partition table is never changed.

**Every change is confirmed.** Format, Resize and Delete name the partition, its label and size, and stay greyed out
until you type its name (its label, or `sdb2` when it has none). The window also sends the disk as it saw it; if
anything on that disk changed since (a partition added, reformatted, plugged into another port), the change is
refused and nothing is touched.

**Before anything is written** the partition table is saved to `/var/lib/deckos/disks/tables/` (`sudo sfdisk
/dev/sdX < FILE` puts it back), a Linux file system gets a full `e2fsck`, an NTFS shrink gets an `ntfsresize`
trial run, and a shrink is refused below what the file system says it can give up. Shrinking resizes the file system
first, then the partition; growing does it the other way round. If a step fails, the one before it is undone where it
can be, and the message says exactly what state the disk is in ("the disk is as it was", or which part changed).

After an NTFS resize, `ntfsresize` asks Windows to check the drive at its next start, as it should. Until then Linux
sees it as marked dirty: without Windows, **Repair** clears the mark.

After a format or a new partition, DecKoOS offers **Mount at start-up**, which test-mounts it like any other drive.
Every change is in the timeline (Pulse).

## From a terminal

`deckos disks list` and `deckos disks verify` read; `sudo deckos disks startup add UUID`, `startup remove UUID`,
`repair UUID` and `health` change things. The Assistant may run the reading ones without asking. Partition changes
take the same confirmation as the window:

    sudo deckos disks format /dev/sdb1 exfat Photos --confirm NAME --layout FP
    sudo deckos disks create /dev/sdb START BYTES ext4 Games --layout FP
    sudo deckos disks resize /dev/sdb1 BYTES --confirm NAME --layout FP
    sudo deckos disks delete /dev/sdb1 --confirm NAME --layout FP

`NAME` is the partition's label (or name) and `FP` the disk's fingerprint (`disks.fingerprint()`), so a typo or a
stale look is refused, not acted on.
