# DeckOS

**DeckOS** is an Arch-based, CachyOS-accelerated distro for gaming and local AI. It boots into a
KDE Plasma desktop or a console-style Steam **Gaming Mode**, keeps itself recoverable with btrfs
snapshots, and installs next to Windows without touching your Windows drives.

It's tuned on a Ryzen 7 7800X3D + Radeon RX 9070 XT machine (see [Reference machine](#reference-machine)),
and installs on any 64-bit UEFI PC that meets the [requirements](#requirements).

| | |
|---|---|
| **Base** | Arch Linux + CachyOS repos built for your CPU (x86-64-v3, v4 or Zen 4), `linux-cachyos` (BORE) + `linux-cachyos-lts` fallback |
| **Desktop** | KDE Plasma 6 (Wayland) with the DeckOS look: its own Plasma style, login screen and icons (Papirus with DeckOS-blue folders), Inter + JetBrains Mono. An optional TMpikes theme comes along |
| **DeckOS Hub** | one app for live stats, the display fix, Gaming Mode, drives, AI and dev tools, updates, snapshots, the firewall, adding software and changing the look |
| **DeckOS Store** | one app store for the Arch and CachyOS repos, Flathub and the AUR: browse, search and install with a click |
| **Gaming** (optional) | Steam, **Gaming Mode** (gamescope session, SteamOS-style switching), Proton-CachyOS, MangoHud, GameMode, LACT, Lutris, Heroic, `xone` for the Xbox Wireless Adapter, NTSync, Discord, OBS |
| **Local AI** (optional) | Ollama + ROCm for running models on a Radeon |
| **Development** (optional) | Claude Code, VS Code, JetBrains Toolbox, Docker, Node, Python/uv, .NET, Java, gh |
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

The ISO lands in `out/`, named after the release in `VERSION` (for example `deckos-0.3.0-x86_64.iso`).

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
3. **You**: username, computer name, language, keyboard layout, password and time zone. The live
   desktop switches to your keyboard layout right away, so the password you type is the one that works
   at login.
4. **Software**: tick Gaming, Local AI and/or Development. The desktop, kernel, graphics drivers and
   snapshots are always installed. Local AI starts unticked if no Radeon RX 7000/9000 is found.
5. **Confirm**: read the summary, tick the box, *Erase and install*.
6. **Install** shows progress and the live log. It takes 20–60 minutes, depending on your internet.

Behind the scenes it installs Arch from mirrors in your time zone's country, switches to the CachyOS repos for your CPU, installs the desktop and
the groups you picked (the DeckOS package and AUR apps come prebuilt on the USB), mounts your NTFS drives under
`/mnt/<drive label>`, takes a "fresh install" snapshot and sets up GRUB with DeckOS, Windows and a
snapshots menu. The EFI partition is shared with Windows and never formatted. It also picks the
[display fix level](#display-blackouts-on-radeon-cards) for your GPU and monitors, and keeps the
hardware clock in local time only if it finds Windows, so the clock is right in both. The firewall
(firewalld) is on, blocking incoming connections except KDE Connect and, with Gaming, Steam Remote Play.
If an install fails, the message says exactly what was changed so far. The log is saved to `/var/log/deckos-install.log`. If the install fails, the log is copied to
the live desktop. A text-mode installer (`sudo deckos-install`) is in the app menu as a backup.

## First login: DeckOS Welcome

The first time you log in, **DeckOS Welcome** walks through what most people change right away. Every
step is optional and applies as you go:

| Step | What's there |
|---|---|
| **Look** | global theme (DeckOS, TMpikes), light or dark, accent colour, wallpaper, Plasma style and icons |
| **Display** | scale per screen, a shortcut to arranging them, and the [blackout fix](#display-blackouts-on-radeon-cards) level with the one recommended for your setup picked |
| **Software** | add Gaming, Local AI or Development if you skipped them, and one-click Spotify, Discord, OBS, VS Code and more |
| **Gaming** | Gaming Mode's resolution and refresh rate (matched to your screen in one click), VRR and HDR, Steam libraries on Windows drives, the Xbox Wireless Adapter |
| **Your files** | hourly snapshots of your home folder, a backup drive, your Windows drives |
| **Privacy & updates** | the update channel, checking for updates, the firewall |
| **Extras** | the DeckOS look for Spotify, Claude Code, KDE Connect and a keyboard shortcut cheat sheet |

It ends with a summary of what changed (and whether a restart is needed). After that it stays out of
the way: open it again from the app menu, **DeckOS Hub › Home › Welcome tour**, or `deckos-welcome`.
Tick *Show at startup* to have it back at every login.

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

## DeckOS Hub

The DeckOS Hub (in the panel, or `deckos hub`) is where DeckOS's own settings live:

| Page | What's there |
|---|---|
| **Home** | live GPU, VRAM, CPU and memory graphs; status of updates, snapshots, firewall, display fix, drives and software, each a click away; **Now Playing** with album art, seek and controls for Spotify, Firefox or any media player |
| **Display** | the blackout fix ladder with the level recommended for your setup, your monitors, and the blackout watcher |
| **Gaming** | Gaming Mode, its resolution, refresh rate, VRR and HDR, plus LACT, GOverlay, ProtonUp-Qt and the Steam-on-NTFS fix |
| **Drives** | your Windows drives with how full they are, and help when one is read-only |
| **AI & Dev** | Claude Code, Ollama (start/stop, your models) and which dev tools are installed |
| **System** | updates with a progress bar (AUR apps in the terminal), system and home snapshots, backup to another drive, the firewall, and adding Gaming, Local AI or Development later |
| **Appearance** | global theme (DeckOS, TMpikes), accent colour, wallpaper, Plasma style, icons, and the DeckOS look for Spotify |

**Spotify in the DeckOS look:** install Spotify from the DeckOS Store, open it once and log in, then
press *Apply DeckOS look* in **Hub › Appearance** (or run `deckos spotify theme`). It uses
[Spicetify](https://spicetify.app) to restyle the official app with DeckOS colours, bordered panels and
the gradient play buttons; everything Spotify does keeps working. Spotify updates undo it, so apply it
again after one; `deckos spotify restore` puts the stock look back.

## DeckOS Store

The DeckOS Store (in the panel, or `deckos-store`) installs apps without the command line, from all
three places DeckOS gets software:

- **Arch and CachyOS repos**: installed with pacman, updated with the rest of the system. Preferred
  when an app is available from more than one place.
- **Flathub**: apps that aren't in the repos (Spotify, Bottles…), sandboxed, updated by `deckos update`.
- **AUR**: community packages, searched live and built with paru. Labelled, since Arch doesn't check them.

It has editor's picks and categories on the home page, one search across all three sources, app pages
with screenshots and a choice of source, and an Installed list. App details come from the AppStream
catalogs Arch and Flathub publish; repo installs ask for your password, Flathub ones don't.

## Using it

| | |
|---|---|
| `deckos` / **DeckOS Hub** | everything below in one place |
| `deckos software add gaming` | add a software group you skipped at install (`gaming`, `ai` or `dev`) |
| **Gaming Mode** | panel launcher, or pick *DeckOS Gaming Mode* on the login screen. Back: Steam › Power › *Switch to Desktop* |
| `deckos steam-ntfs` | run once after adding a Steam library that lives on a Windows drive. Games stay on NTFS, Proton prefixes move to Linux |
| `deckos drives` | `list`, `rescan` (new drives), `doctor` (read-only/Fast Startup problems) |
| `deckos update` | full update; snap-pac snapshots before and after |
| broken update? | reboot › *DeckOS snapshots* › pick the one before the update |
| deleted a file? | `/home` has hourly snapshots: copy it back from `/home/.snapshots/<number>/snapshot/` (Hub › System › Browse snapshots). Older installs: `sudo deckos home enable` |
| `deckos backup /mnt/BIG` | copy your home folder (minus caches, Steam games, ISOs) to another drive; remembered for next time |
| `deckos doctor` | health check: kernel, display fix, drives, snapshots, AI |
| `claude` | Claude Code, installed for your user (`~/.local/bin`) |
| `ollama run qwen3` | local models on your Radeon via ROCm |

**Gaming Mode resolution:** it defaults to 3840×2160 at up to 144 Hz. For a different screen, pick yours in
**DeckOS Hub › Gaming** (it's saved in `~/.config/deckos/gaming.conf`; system defaults are in
`/etc/deckos/gaming.conf`).

## Known limitations

DeckOS is early, and these are on the list:

- **Intel and NVIDIA GPUs:** the installer only sets up AMD graphics drivers. On an Intel CPU, add
  microcode after installing: `sudo pacman -S intel-ucode` then
  `sudo grub-mkconfig -o /boot/grub/grub.cfg`.
- **Disk layout:** DeckOS installs onto one existing partition and reuses an existing EFI partition.
  Installing to free space or an empty disk isn't supported yet.
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
borders, `#4C8DFF` accent), reworked mechanically: stencil letters, a thumbstick for the O (gate ring
and tilted cap), bolted plates, hazard stripes.

**DeckOS Builder** (`builder/`) is a desktop app that starts GitHub builds, downloads ISOs and copies them
to a Ventoy stick. See [builder/README.md](builder/README.md).

```
VERSION                   the DeckOS release: names the ISO, shows in os-release, the Hub and deckos doctor
builder/                  DeckOS Builder app (GitHub builds, downloads, Ventoy USB)
assets/generate.py        brand generator (wordmark, gear, wallpaper, GRUB bg)
assets/icons.py           the DeckOS line icons (Hub, Store, login screen) and the Store's app icon
assets/plasma_theme.py    the DeckOS Plasma style (panel, popups, tooltips, widgets)
assets/preview_*.py       render the Hub, Welcome, login screen or Plasma style on any OS
build.sh                  ISO build (Arch releng profile + DeckOS)
iso/                      live-USB additions (packages, live user, autologin)
installer/                the install script, plus the language and keyboard lists it offers
pkg/deckos-settings/      Arch package: Hub, Store, deckos tool, themes, icons, fixes (rootfs/ mirrors /);
                          usr/share/deckos/packages/*.txt = what gets installed, per group
pkg/deckos-theme-tmpikes/ the optional TMpikes theme
pkg/deckos-installer/     the graphical installer (drives deckos-install)
docs/                     the reference machine's setup
.github/workflows/        lint + package test + ISO build
```

### Updates for installed systems

DeckOS's own packages (`deckos-settings` with the Hub, `deckos` tool, themes and fixes, plus
`deckos-theme-tmpikes`) are published as a signed pacman repo in this repo's
[`repo` release](https://github.com/kcooperlawson/deckos/releases/tag/repo). Installed systems have it as
`[deckos]` in `pacman.conf`, so `deckos update` and the Hub's Update button pick up new versions like
any other package.

**To release:** bump `VERSION`, commit, then tag and push (`git tag v0.3.1 && git push origin v0.3.1`).
CI checks that the tag matches `VERSION`, signs the packages with the DeckOS key (fingerprint
`F67E15FABF95D2DA72BE5D3F6322881773088C41`, kept as the `DECKOS_SIGNING_KEY` secret) and replaces the
repo's contents. `deckos-theme-tmpikes` only updates on installed systems when its own `pkgver` goes up.

**Working on DeckOS from DeckOS:** clone the repo into your home folder (not a Windows drive: NTFS loses
file permissions and symlinks), then `deckos dev-install` builds and installs your checkout. A later
release replaces it as a normal update. Installs from 0.3.0 or earlier don't have the update channel or
`dev-install` yet; run `makepkg -si` once in `pkg/deckos-settings` to get both.

`build.sh` and DeckOS Builder keep their work folder and `out/` as btrfs subvolumes of their own on DeckOS,
so system and `/home` snapshots don't hold on to old builds and ISOs.

The generators write into `pkg/` and their output is committed; run them again after changing a
design. The installer, Hub, Store and Welcome all have a demo mode for working on the UI anywhere, including
Windows: run `deckos_installer.py --demo`, `deckos_hub.py --demo`, `deckos_store.py --demo` or `deckos_welcome.py --demo` from their folders in `pkg/`.
