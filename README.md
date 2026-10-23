# DeckOS

**DeckOS** is an Arch-based, CachyOS-accelerated distro for gaming and local AI. It boots into a
KDE Plasma desktop or a console-style Steam **Gaming Mode**, keeps itself recoverable with btrfs
snapshots, and installs next to Windows without touching your Windows drives.

It's tuned on a Ryzen 7 7800X3D + Radeon RX 9070 XT machine (see [Reference machine](#reference-machine)),
and installs on any 64-bit UEFI PC that meets the [requirements](#requirements).

| | |
|---|---|
| **Base** | Arch Linux + CachyOS repos built for your CPU (x86-64-v3, v4 or Zen 4), `linux-cachyos` (BORE) + `linux-cachyos-lts` fallback |
| **Desktop** | KDE Plasma 6 (Wayland), DeckOS look-and-feel, Papirus, Inter + JetBrains Mono |
| **Gaming** | Steam, **Gaming Mode** (gamescope session, SteamOS-style switching), Proton-CachyOS, MangoHud, GameMode, LACT, Lutris, Heroic, `xone` for the Xbox Wireless Adapter, NTSync |
| **AI / dev** | Claude Code, ROCm + Ollama for local models, VS Code, JetBrains Toolbox, Docker, Node, Python/uv, .NET, Java, gh |
| **Disks** | btrfs with snapshots: boot an older snapshot from GRUB after a bad update. Existing NTFS drives stay NTFS and are mounted read/write |
| **Fixes** | Display blackout fix ladder for Radeon cards (`deckos display`), Windows dual-boot clock, Steam libraries on NTFS |

## Requirements

| | |
|---|---|
| **CPU** | Any 64-bit x86 CPU. Packages are optimised for whatever level your CPU supports |
| **GPU** | **AMD Radeon** recommended. Local AI (ROCm) needs an RX 7000 / 9000 series card. Intel and NVIDIA GPUs aren't set up by the installer yet ([limitations](#known-limitations)) |
| **Firmware** | UEFI with **Secure Boot off** |
| **Disk** | A partition of **64 GB or more** (150 GB+ if games go on it too), created beforehand, plus an existing EFI partition (any PC with Windows has one) |
| **Memory** | 8 GB minimum, 16 GB recommended |
| **Internet** | Wired or Wi-Fi during the install: packages are downloaded fresh |

## Get DeckOS

The ISO is built on Arch Linux. Pick one:

**A. GitHub Actions (nothing to install).** Fork this repo, then go to *Actions › Build DeckOS ISO ›
Run workflow*. When it finishes (~30 min), download the `deckos-iso` artifact.

**B. An Arch machine, or WSL on Windows.** On Windows, in an admin terminal:
`wsl --install -d archlinux`, reboot, then inside Arch:

```bash
sudo pacman -Syu --needed archiso git
```

```bash
sudo ./build.sh
```

The ISO lands in `out/`.

**Write it to a USB stick** with [Ventoy](https://www.ventoy.net) (copy the ISO onto the stick),
[Rufus](https://rufus.ie) (pick *DD Image mode* when asked) or `dd`. Boot it from your firmware's
boot menu (usually F11, F12 or F8 right after power-on) and pick the UEFI entry.

## Before you install

If DeckOS is going next to Windows, do this in Windows first:

1. **Make room.** Open *Disk Management*, right-click a drive with free space › *Shrink Volume*, then
   create a new partition in the free space (any format: the installer erases it). Skip this if you
   already have a spare partition.
2. **Turn off Fast Startup.** Open Terminal **as Administrator** and run `powercfg /h off`. Fast Startup
   leaves NTFS drives half-hibernated, and Linux will only mount them read-only.
3. **BitLocker.** Linux can't read BitLocker drives, and the installer won't offer a BitLocker partition
   as a target. Check *Settings › Privacy & security › Device encryption*.
4. **Secure Boot off** in your firmware settings (usually under *Security* or *Boot*).

## Install

The USB boots straight into the **DeckOS desktop** (logged in as `liveuser`, no password). Try things
first (Wi-Fi, your monitors, DeckOS Hub), then double-click **Install DeckOS**:

1. **Welcome** checks UEFI mode, Secure Boot and internet. Connect to Wi-Fi from here if needed.
2. **Where** lists the partitions DeckOS can go on. Only the one you pick is erased. Partitions it can't
   safely check (BitLocker, encrypted, in use, part of a RAID) are shown greyed out with the reason,
   and a partition that holds Windows is always refused.
3. **You**: username, computer name, password and time zone.
4. **Confirm**: read the summary, tick the box, *Erase and install*.
5. **Install** shows progress and the live log. It takes 20–60 minutes, depending on your internet.

Behind the scenes it installs Arch, switches to the CachyOS repos for your CPU, installs everything listed
above (the DeckOS package and AUR apps come prebuilt on the USB), mounts your NTFS drives under
`/mnt/<drive label>`, takes a "fresh install" snapshot and sets up GRUB with DeckOS, Windows and a
snapshots menu. The EFI partition is shared with Windows and never formatted. It also picks the
[display fix level](#display-blackouts-on-radeon-cards) for your GPU and monitors, and keeps the
hardware clock in local time only if it finds Windows, so the clock is right in both. The log is saved to `/var/log/deckos-install.log`. If the install fails, the log is copied to
the live desktop. A text-mode installer (`sudo deckos-install`) is in the app menu as a backup.

## Display blackouts on Radeon cards

Some Radeon cards (confirmed on the RX 9070 XT) save power at idle by switching their VRAM clock with
firmware help (FAMS). With a high-bandwidth monitor (the Samsung Odyssey G7 at 4K 144 Hz is the known
case), especially alongside a second screen, each switch can drop the DisplayPort signal for 1–2 seconds.
DeckOS has a fix ladder you can climb if it happens to you. The installer starts you at **level 1** if it
finds an RX 9070-series card driving a Samsung Odyssey or more than one monitor, and at level 0 otherwise
(the live USB always runs level 1):

| Level | What it does | Cost |
|---|---|---|
| 0 | stock AMD behaviour | — |
| 1 | `amdgpu.dcdebugmask=0x20000`: no SubVP/FAMS memory-clock switching | small idle power |
| 2 | + VRAM clock pinned to max at boot | ~15–30 W idle |
| 3 | + no multi-monitor clock switching, no PSR / Panel Replay | same |
| 4 | + every GPU clock forced high | most idle power / heat |

```bash
sudo deckos display set 2
```

Or use **DeckOS Hub › Display**, then reboot. If you're on level 1 and never see blackouts,
`sudo deckos display set 0` gets the idle power back. `deckos display recommend` shows what the installer
would pick for your setup. To find the cause, run `deckos display watch` (also a button in the Hub) and
press Enter each time the screen blinks. It logs VRAM clock changes, kernel display messages and
hotplugs, so the cause shows up right next to your marker.

Still flickering on level 3+? It's probably the monitor or cable:
- In the monitor's menu: update the firmware, turn **Adaptive-Sync/FreeSync off**, turn off automatic
  source switching.
- Use the DisplayPort cable that came with the monitor (or a VESA-certified DP 1.4 one).
- Gaming Mode ships with VRR **off** for the same reason. Turn it on in the Hub once things are stable.

Sources: [Bazzite #4934](https://github.com/ublue-os/bazzite/issues/4934),
[Arch BBS 311159](https://bbs.archlinux.org/viewtopic.php?id=311159),
[`amd_shared.h` DC_DEBUG_MASK](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/include/amd_shared.h).

## Using it

| | |
|---|---|
| `deckos` / **DeckOS Hub** | everything below in one place |
| **Gaming Mode** | panel launcher, or pick *DeckOS Gaming Mode* on the login screen. Back: Steam › Power › *Switch to Desktop* |
| `deckos steam-ntfs` | run once after adding a Steam library that lives on a Windows drive. Games stay on NTFS, Proton prefixes move to Linux |
| `deckos drives` | `list`, `rescan` (new drives), `doctor` (read-only/Fast Startup problems) |
| `deckos update` | full update; snap-pac snapshots before and after |
| broken update? | reboot › *DeckOS snapshots* › pick the one before the update |
| `deckos doctor` | health check: kernel, display fix, drives, snapshots, AI |
| `claude` | Claude Code, installed for your user (`~/.local/bin`) |
| `ollama run qwen3` | local models on your Radeon via ROCm |

**Gaming Mode resolution:** it defaults to 3840×2160 at up to 144 Hz. For a different screen, set
`SCREEN_WIDTH`, `SCREEN_HEIGHT` and `CUSTOM_REFRESH_RATES` in `~/.config/deckos/gaming.conf`
(system defaults and comments are in `/etc/deckos/gaming.conf`).

## Known limitations

DeckOS is early, and these are on the list:

- **Intel and NVIDIA GPUs:** the installer only sets up AMD graphics drivers. On an Intel CPU, add
  microcode after installing: `sudo pacman -S intel-ucode` then
  `sudo grub-mkconfig -o /boot/grub/grub.cfg`.
- **Disk layout:** DeckOS installs onto one existing partition and reuses an existing EFI partition.
  Installing to free space or an empty disk isn't supported yet.
- **Software choices:** everything in the table at the top is installed, including ROCm, Docker and the
  dev tools.
- **Language and keyboard** are set to English (US) and a US layout, and mirrors are ranked from the US.
  Change the language and keyboard after installing in *System Settings*.
- **Secure Boot** has to stay off.

Bug reports are welcome. Please attach the output of `deckos doctor` and, for install problems,
`deckos-install.log`.

## Reference machine

Every default in DeckOS was chosen and tested on this machine:

Ryzen 7 7800X3D · Radeon RX 9070 XT · ASRock B850M-C · 32 GB DDR5-6000 · Samsung Odyssey G70B + LG UltraGear,
dual-booting Windows 11.

[docs/reference-machine.md](docs/reference-machine.md) has the exact setup for it (BIOS settings, which
partition DeckOS goes on, the drive layout).

## Development

The look shares its design language with Steady Downloader (slate `#0F1115` / `#171A21`, `#262B36`
borders, `#4C8DFF` accent), reworked mechanically: stencil letters, a gear for the O, bolted plates,
hazard stripes.

**DeckOS Builder** (`builder/`) is a desktop app that starts GitHub builds, downloads ISOs and copies them
to a Ventoy stick. See [builder/README.md](builder/README.md).

```
builder/                  DeckOS Builder app (GitHub builds, downloads, Ventoy USB)
assets/generate.py        brand generator (wordmark, gear, wallpaper, GRUB bg) — run after design tweaks
build.sh                  ISO build (Arch releng profile + DeckOS)
iso/                      live-USB additions (packages, live user, autologin)
installer/deckos-install  the install script; installer/packages/*.txt = what gets installed
pkg/deckos-installer/     the graphical installer (drives deckos-install)
pkg/deckos-settings/      Arch package: theme, Hub, deckos tool, fixes (rootfs/ mirrors /)
docs/                     the reference machine's setup
.github/workflows/        lint + package test + ISO build
```

The installer window has a demo mode for working on the UI anywhere, including Windows:
`python pkg/deckos-installer/rootfs/usr/lib/deckos/installer/deckos_installer.py --demo`
(set `DECKOS_BRANDING` to `pkg/deckos-settings/rootfs/usr/share/deckos/branding`).
