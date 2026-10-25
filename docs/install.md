# Installing DecKoOS

What you need, how to get the ISO and how to install it next to Windows or on its own disk.

## Requirements

| | |
|---|---|
| **CPU** | Any 64-bit x86 CPU. Packages are optimised for whatever level your CPU supports |
| **GPU** | **AMD Radeon** recommended: it's what DecKoOS is tested on. NVIDIA and Intel drivers are picked by CachyOS's hardware detection (`chwd`) but are untested so far ([limitations](../README.md#known-limitations)). Local AI needs a Radeon RX 7000 / 9000 (ROCm) or an NVIDIA card (CUDA) |
| **Firmware** | UEFI with **Secure Boot off** |
| **Disk** | **64 GB or more** (150 GB+ if games go on it too): unallocated space, an empty disk, or a spare partition |
| **Memory** | 8 GB minimum, 16 GB recommended |
| **Internet** | Wired or Wi-Fi during the install: packages are downloaded fresh |

## Get DecKoOS

The ISO is built on Arch Linux. Pick one:

**A. GitHub Actions (nothing to install).** Fork this repo, then go to *Actions › Build DecKoOS ISO ›
Run workflow*. When it finishes (~30 min), download the `deckos-iso` artifact.

**B. An Arch machine, or WSL on Windows.** On Windows, in an admin terminal:
`wsl --install -d archlinux`, reboot, then inside Arch:

```bash
sudo pacman -Syu --needed archiso git
```

```bash
sudo ./build.sh
```

The ISO lands in `out/`, named after the release in `VERSION` (for example `deckos-0.3.0-x86_64.iso`).

**Write it to a USB stick** with [Ventoy](https://www.ventoy.net) (copy the ISO onto the stick),
[Rufus](https://rufus.ie) (pick *DD Image mode* when asked) or `dd`. Boot it from your firmware's
boot menu (usually F11, F12 or F8 right after power-on) and pick the UEFI entry.

## Before you install

If DecKoOS is going next to Windows, do this in Windows first:

1. **Make room.** Open *Disk Management*, right-click a drive with free space › *Shrink Volume*, and leave
   the space unallocated: the installer makes DecKoOS's partition there itself. (A spare partition works
   too, and so does an empty second disk.)
2. **Turn off Fast Startup.** Open Terminal **as Administrator** and run `powercfg /h off`. Fast Startup
   leaves NTFS drives half-hibernated, and Linux will only mount them read-only.
3. **BitLocker.** Linux can't read BitLocker drives, and the installer won't offer a BitLocker partition
   as a target. Check *Settings › Privacy & security › Device encryption*.
4. **Secure Boot off** in your firmware settings (usually under *Security* or *Boot*).

## Install

The USB boots straight into the **DecKoOS desktop** (logged in as `liveuser`, no password). Try things
first (Wi-Fi, your monitors, DecKoOS Hub), then double-click **Install DecKoOS**:

1. **Welcome** checks UEFI mode, Secure Boot and internet. Connect to Wi-Fi from here if needed.
2. **Where** lists the partitions, free space and empty disks DecKoOS can go on. A partition you pick is
   erased; in free space (64 GB or more, on a GPT disk) or on an empty disk DecKoOS makes its own partition
   and erases nothing, and an empty disk gets its own boot partition too. Nothing existing is ever moved
   or resized. Partitions it can't safely check (BitLocker, encrypted, in use, part of a RAID) are shown
   greyed out with the reason, and a partition that holds Windows is always refused.
3. **You**: username, computer name, language, keyboard layout, password and time zone. The live
   desktop switches to your keyboard layout right away, so the password you type is the one that works
   at login.
4. **Software**: tick Gaming, Local AI and/or Development. The desktop, kernel, graphics drivers and
   snapshots are always installed. Local AI starts unticked if no Radeon RX 7000/9000 or NVIDIA card is
   found.
5. **Confirm**: read the summary, tick the box, *Erase and install* (just *Install* in free space or on an empty disk).
6. **Install** shows progress and the live log. It takes 20–60 minutes, depending on your internet.

Behind the scenes it installs Arch from mirrors in your time zone's country, switches to the CachyOS repos for your CPU, installs the desktop and
the groups you picked (the DecKoOS package and AUR apps come prebuilt on the USB), mounts your NTFS drives under
`/mnt/<drive label>`, takes a "fresh install" snapshot and sets up GRUB with DecKoOS, Windows and a
snapshots menu. The EFI partition is shared with Windows and never formatted. It also picks the
[display fix level](guide.md#display-blackouts-on-radeon-cards) for your GPU and monitors, and keeps the
hardware clock in local time only if it finds Windows, so the clock is right in both. The firewall
(firewalld) is on, blocking incoming connections except KDE Connect and, with Gaming, Steam Remote Play.
If an install fails, the message says exactly what was changed so far. The log is saved to `/var/log/deckos-install.log`. If the install fails, the log is copied to
the live desktop. A text-mode installer (`sudo deckos-install`) is in the app menu as a backup.

## First login: DecKoOS Welcome

The first time you log in, **DecKoOS Welcome** walks through what most people change right away. Every
step is optional and applies as you go:

| Step | What's there |
|---|---|
| **Look** | global theme (DecKoOS, TMpikes), light or dark, accent colour, wallpaper, Plasma style and icons |
| **Display** | scale per screen, a shortcut to arranging them, and the [blackout fix](guide.md#display-blackouts-on-radeon-cards) level with the one recommended for your setup picked |
| **Software** | add Gaming, Local AI or Development if you skipped them, and one-click Spotify, Discord, OBS, VS Code and more |
| **Gaming** | Gaming Mode's resolution and refresh rate (matched to your screen in one click), VRR and HDR, Steam libraries on Windows drives, the Xbox Wireless Adapter |
| **Your files** | hourly snapshots of your home folder, a backup drive, your Windows drives |
| **Privacy & updates** | the update channel, checking for updates, the firewall |
| **Extras** | the DecKoOS look for Spotify, Claude Code, KDE Connect and a keyboard shortcut cheat sheet |

It ends with a summary of what changed (and whether a restart is needed). After that it stays out of
the way: open it again from the app menu, **DecKoOS Hub › Home › Welcome tour**, or `deckos-welcome`.
Tick *Show at startup* to have it back at every login.
