# Handoff: getting ready to reinstall (item 1 done and merged 2026-10-29: all five install tests pass) (two-drive install, live USB, boot menu, quality pass)

Written 2026-10-28 when the previous session ran out of room. Work in progress is on the branch
`wip/two-drive-install` (not `main`). Read CLAUDE.md first, especially "Installer safety".

## What the maintainer asked for

They will wipe Windows and move to DecKoOS full time. Before that:
1. **Install on two drives as one system**, like Bazzite: their 250 GB Samsung 970 EVO Plus (`nvme0n1`, DecKoOS now,
   holds the EFI partition Windows boots from) + 500 GB Micron 2400 (`nvme1n1`, Windows) = one ~700 GB system.
2. **Live USB introduction and welcome**: make them "perfect" (not started).
3. **Redo the boot menu** (GRUB, with the grub-btrfs snapshots submenu) in the new DecKo look (not started).
4. **A quality pass** so everything is ready to move over (not started).

Keep the 1 TB SSD (`sda1`, NTFS, `/mnt/SSD`) and 7.3 TB BIG (`sdb2`, NTFS, `/mnt/BIG`) game drives untouched.

## Done on the branch (not tested yet)

`installer/deckos-install`:
- `list_erase` lists `erase:DISK` rows (whole disks to erase; never the live USB; blocked if mounted, swap,
  RAID/LVM/ZFS member, under 64 GB). `--list-targets` includes them. `--disk-contents DISK` (root) prints
  `PART\tSIZE\tFS\tLABEL\tWHAT` (WHAT: Windows, Windows boot, Windows recovery, encrypted, boot, data, empty).
- `make_space SPEC WANT_ESP` replaces `make_partition`: gap, empty disk, or erase (wipefs every partition + disk,
  new GPT, EFI only when WANT_ESP=yes). Sets MADE_PART/MADE_ESP/MADE_PARTNO. Refuses an erase if anything on the
  disk is mounted.
- `check_partition`, `choice_disk`, `kind_of` (partition|gap|disk|erase), `describe_choice`.
- Second drive: `DECKOS_EXTRA` (GUI) or a `gum confirm` + `choose_space` (text). Must be on another disk.
  `mkfs.btrfs -d single -m raid1 TARGET EXTRA`; `btrfs device scan`; initramfs HOOKS get `btrfs` when spanning.
- Whole-disk erase needs the disk's name typed: `DECKOS_ERASE_DISKS="nvme0n1 nvme1n1"` (GUI) or a prompt (text).
- ESP: a disk being erased can't provide the shared ESP; Windows detection ignores erased disks.

`iso/airootfs/usr/local/bin/deckos-autoinstall`: second test disk (serial `deckos-autotest2`) becomes DECKOS_EXTRA;
a partition labelled `deckos-erase` marks a disk to erase whole (and fills DECKOS_ERASE_DISKS); `btrfs device scan`
before the post-install mount.

`tests/install-test.sh`: layouts `span` (two blank 80 GB disks) and `erase` (two 80 GB disks with partitions, both
erased). `.github/workflows/build-iso.yml` and `iso-version.yml` matrices include them.

`pkg/deckos-installer/.../deckos_installer.py`: `space_disk`, `erases`; disk page lists "Or erase a whole disk"
cards with their contents (`contents_text`, via `sudo -n deckos-install --disk-contents`); a "Second drive" card
(`extra_on`, `extra_pick`, `fill_extra`, `extra()`); confirm page has one typed-name box per erased disk
(`erase_edits`, `erase_typed`), summary rows via `what_row`; env passes DECKOS_EXTRA and DECKOS_ERASE_DISKS.

## Progress (second session, 2026-10-28)

- Fixed: the window crashed building the disk page (`disk_group` now made first; `update_nav` waits for all pages).
  Walked through in `--demo`: erase + second drive, typed name and consent enable Install, env is right.
- Fixed (found by the VM test): `list_targets`/`list_erase` ignored every mount under /mnt, so a drive mounted at
  /mnt/SSD looked free. Now only mounts on the disk /mnt itself comes from (`mnt_disk`) are skipped.
- `tests/vm/erase_steps.py` (new) and `partition_steps.py` pass in a VM on real disks: listing, contents, refused
  erase while mounted, erase with/without EFI, FAT32 clusters, one btrfs over two devices (~159 GB).
- Docs: CLAUDE.md Installer safety, README Known limitations, docs/install.md.
- Next: the five CI install-test layouts on an ISO built from this branch (Build ISO workflow_dispatch), then the
  GRUB-on-two-devices boot (`span`), then merge. Then items 2-4 and the backup.

## Known bug to fix first (fixed)

The demo crashes: `build_disk` creates the second-drive card (and calls `extra_changed`, which ends in
`update_nav` → `self.target()`) before `self.disk_group` exists. Create `disk_group` before the extra card, or
guard `target()`. Then render the pages: the throwaway script that was being used, `scratchpad/inst/shot.py`, did
`go(WHERE)`, picked `erase:/dev/nvme1n1` plus extra `erase:/dev/nvme0n1`, filled the account fields, went to
CONFIRM, typed the names and checked the Next button. Run the window with `--demo` under `QT_QPA_PLATFORM=offscreen`.

## Still to do for (1)

- Run `bash tests/check.sh lint` (shellcheck runs in CI; it isn't installed locally) and `tests`.
- Test the disk functions in a VM: `tests/vm/partition_steps.py` style (see its header; KVM works without root
  here). Add steps for `list_erase`, `disk_contents`, `make_space erase:… yes/no`, and mkfs over two devices.
- Full installs: the CI install-test (now 5 layouts) runs when an ISO builds (Build ISO workflow_dispatch on the
  branch, or `[iso]`). All five must pass before merging. Never test on the maintainer's real disks.
- Update CLAUDE.md's "Installer safety" (whole-disk erase is now allowed only when picked and its name typed) and
  README's "Known limitations" (erasing a whole used disk is now supported) and the install docs.
- GRUB on multi-device btrfs: expected to work (GRUB reads btrfs across devices), but confirm in the `span` boot.

## Before the maintainer reinstalls: back up (their home is wiped)

- Their Proton prefixes now live in their home: `~/.local/share/deckos/proton-prefixes/mnt-SSD-SteamLibrary`
  (linked from `/mnt/SSD/SteamLibrary/steamapps/compatdata`) and `.../mnt-BIG-SteamLibrary` (bind-mounted at
  `/mnt/BIG/SteamLibrary/steamapps/compatdata` through an fstab block "DecKoOS Proton prefixes", managed by
  `deckos drives prefixes LIBRARY on|off`). After reinstalling, Game Doctor's "Keep Proton's files on your Linux
  drive" (or `deckos drives prefixes`) must be run again for both libraries, and the old prefixes copied back.
- The BIG NTFS drive refuses every symlink (ntfs3 answers EINVAL), even plain ones; the SSD accepts them. A Windows
  `chkdsk` might fix that, but Windows is going away.
- Offer a checked backup to the BIG drive first: `deckos setup export`, the prefixes, Steam's `userdata`, game
  saves, `~/.config/deckos`, `~/Documents`. The 250 GB NVMe was 91% full.

## Not released yet (on `main`, committed, after 0.19.0)

`084a6c9` Game Doctor opens from its service (desktopenv), NTFS prefix rule + fix, sync rule fix; `8730182` link
check before moving; `c830892` `deckos drives prefixes` + Game Doctor uses it via pkexec. The maintainer said to
hold them ("later"); ship as 0.19.1 when they say so (`release.py 0.19.1 "…" --hotfix` if within 12 h of 0.19.0).

## Context from this session

- The name is DecKoOS in anything people read (memory: decko-name-origin).
- 0.19.0 shipped "The DecKo look" (notched cards, Chakra Petch, islands dock, Vibe mode looks). The new boot menu
  should match it: the wordmark's notch, Chakra Petch (OFL, `usr/share/fonts/deckos`), the eyes logo, the blue to
  violet gradient. GRUB theme lives in `usr/share/deckos/branding/grub` / `usr/share/grub/themes/deckos`.
- Temporary test copies on the maintainer's PC were removed; Plasma runs the installed 0.19.0.
