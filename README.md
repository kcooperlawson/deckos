# DeckOS

**D E C K ⚙ S** · Decko clan systems. An Arch-based, CachyOS-accelerated gaming + AI distro built for one
machine: Ryzen 7 7800X3D · RX 9070 XT · ASRock B850M-C · 32 GB DDR5-6000 · Samsung Odyssey G70B + LG UltraGear.

Same design language as Steady Downloader (slate `#0F1115` / `#171A21`, `#262B36` borders, `#4C8DFF` accent),
reworked mechanically: stencil letters, a gear for the O, bolted plates, hazard stripes.

| | |
|---|---|
| **Base** | Arch Linux + CachyOS **znver4** repos (packages compiled for Zen 4), `linux-cachyos` 7.x (BORE) + `linux-cachyos-lts` fallback |
| **Desktop** | KDE Plasma 6 (Wayland), DeckOS look-and-feel, Papirus, Inter + JetBrains Mono |
| **Gaming** | Steam, **Gaming Mode** (gamescope session, SteamOS-style switching), Proton-CachyOS, MangoHud, GameMode, LACT, Lutris, Heroic, `xone` for the Xbox Wireless Adapter, NTSync |
| **AI / dev** | Claude Code, ROCm + Ollama on the 9070 XT, VS Code, JetBrains Toolbox, Docker, Node, Python/uv, .NET, Java, gh |
| **Disks** | DeckOS on btrfs with snapshots (boot an older snapshot from GRUB). Your NTFS drives stay NTFS, mounted read/write |
| **Fixes** | Samsung G7 blackout ladder (`deckos display`), GPU pinned to the 9070 XT, Windows dual-boot clock |

## Before you install (once, on Windows)

1. **Turn off Fast Startup.** Open Terminal **as Administrator** and run `powercfg /h off`. Fast Startup
   leaves NTFS drives half-hibernated, and Linux will only mount them read-only.
2. **BitLocker:** if C:, D: or E: are BitLocker-encrypted, Linux can't read them. Check in
   *Settings › Privacy & security › Device encryption*.
3. **BIOS (ASRock):** *Security › Secure Boot* → **Disabled**. Optional: *Advanced › AMD CBS › NBIO ›
   GFX Configuration › iGPU* → **Disabled** (DeckOS ignores the iGPU anyway). Make sure EXPO is on.
4. **H: will disappear from Windows.** DeckOS replaces the empty 232 GB "NVME" partition on the
   Samsung 970 EVO Plus. The EFI partition on that disk (Windows' boot files) is reused, not formatted.

## Build the ISO

The ISO has to be built on Arch Linux. Pick one:

**A. GitHub (no setup on this PC beyond git).** Push this folder to a GitHub repo, then go to
*Actions › Build DeckOS ISO › Run workflow*. When it finishes (~20 min), download the `deckos-iso` artifact.
The same workflow lints the scripts and test-builds the DeckOS package on every push.

**B. WSL on this PC.** In an admin terminal: `wsl --install -d archlinux`, reboot, then inside Arch:

```bash
sudo pacman -Syu --needed archiso git
```

```bash
sudo ./build.sh
```

The ISO lands in `out/`.

**Then** copy `deckos-*.iso` onto your Ventoy USB (the SSK drive, **F:**), boot it (F11 on ASRock for
the boot menu) and pick DeckOS.

## Install

The installer starts by itself on the USB. It:

- preselects **the 970 EVO's "NVME" partition**, shows what's on it, and refuses any partition containing Windows;
- needs you to type `ERASE`. **Only that partition** is formatted (btrfs: `@ @home @snapshots @log @pkg`);
- reuses the existing EFI partition, so the GRUB menu offers **DeckOS, Windows and snapshots**;
- enables the CachyOS repos with CachyOS's own script, then installs everything above;
- mounts your NTFS drives by label: **`/mnt/Windows`** (C:), **`/mnt/SSD`** (D:), **`/mnt/BIG`** (E:, mounts when opened);
- builds the `deckos-settings` package (theme, tools, fixes) and takes a **"Fresh DeckOS install"** snapshot.

Log: `/var/log/deckos-install.log` (copied into the installed system too).

## The Samsung G7 blackouts

The likely cause: the RX 9070 XT saves power at idle by changing its VRAM clock, using firmware-assisted
switching (FAMS). With a 4K144 G70B plus a second monitor, those switches can drop the DisplayPort signal
for 1–2 seconds. DeckOS ships **level 1** by default and lets you climb the ladder if it still happens:

| Level | What it does | Cost |
|---|---|---|
| 0 | stock AMD behaviour | — |
| **1** (default) | `amdgpu.dcdebugmask=0x20000`: no SubVP/FAMS memory-clock switching | small idle power |
| 2 | + VRAM clock pinned to max at boot | ~15–30 W idle |
| 3 | + no multi-monitor clock switching, no PSR / Panel Replay | same |
| 4 | + every GPU clock forced high | most idle power / heat |

```bash
sudo deckos display set 2
```

Or use **DeckOS Hub › Display**, then reboot. To find out what's happening, run `deckos display watch`
(also a button in the Hub) and press Enter each time the screen blinks. It logs VRAM clock changes, kernel
display messages and hotplugs, so the cause shows up right next to your marker.

If it's still flickering on level 3+, it's probably the monitor/cable rather than the GPU:
- In the G70B menu: update the firmware, turn **Adaptive-Sync/FreeSync off**, turn **Auto Source Switch+ off**.
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
| `deckos steam-ntfs` | run once after adding `D:\SteamLibrary` in Steam. Games stay on NTFS, Proton prefixes move to Linux |
| `deckos drives` | `list`, `rescan` (new drives), `doctor` (read-only/Fast Startup problems) |
| `deckos update` | full update; snap-pac snapshots before and after |
| broken update? | reboot › *DeckOS snapshots* › pick the one before the update |
| `claude` | Claude Code, installed for your user (`~/.local/bin`) |
| `ollama run qwen3` | local models on the 9070 XT via ROCm |

## Layout

```
assets/generate.py        brand generator (wordmark, gear, wallpaper, GRUB bg) — run after design tweaks
build.sh                  ISO build (releng profile + DeckOS)
iso/                      live-USB additions
installer/deckos-install  the installer; installer/packages/*.txt = what gets installed
pkg/deckos-settings/      Arch package: theme, Hub, deckos tool, fixes (rootfs/ mirrors /)
.github/workflows/        lint + package test + ISO build
```

## Status

Written and partly checked on Windows: the Python compiles, the brand renders, and the package names
were verified against the Arch, CachyOS and AUR repos (Oct 2026). **Not yet run on Linux.** The first
GitHub Actions run (shellcheck + makepkg + ISO) is the next check. After that, test the ISO in a VM
before installing it on the real H: partition.
