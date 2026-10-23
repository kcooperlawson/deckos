# Reference machine

DeckOS is developed and tested on this PC. Its defaults (the installer's preselected partition, the
display fix level, Gaming Mode's resolution) come from here.

| | |
|---|---|
| **CPU** | Ryzen 7 7800X3D (Zen 4: gets the CachyOS `znver4` packages) |
| **GPU** | Radeon RX 9070 XT (Navi 48, `0x7550`); the CPU's iGPU is ignored |
| **Board** | ASRock B850M-C |
| **RAM** | 32 GB DDR5-6000 (EXPO) |
| **Monitors** | Samsung Odyssey G70B (4K 144 Hz) + LG UltraGear |
| **Disks** | Samsung 970 EVO Plus 250 GB (Windows EFI partition + the DeckOS partition), plus NTFS drives for Windows, games and storage |
| **USB** | Ventoy on the SSK stick (F: in Windows) |

## Before installing (once, on Windows)

1. **Fast Startup off:** Terminal as Administrator, `powercfg /h off`.
2. **BitLocker:** C:, D: and E: must not be encrypted
   (*Settings › Privacy & security › Device encryption*).
3. **BIOS:** *Security › Secure Boot* → **Disabled**. Optional: *Advanced › AMD CBS › NBIO ›
   GFX Configuration › iGPU* → **Disabled** (DeckOS ignores the iGPU anyway). Make sure EXPO is on.
4. **H: will disappear from Windows.** DeckOS replaces the empty 232 GB "NVME" partition on the
   970 EVO Plus. The installer preselects it. The EFI partition on that disk is reused, not formatted.

## Installing

Copy `deckos-*.iso` onto the Ventoy stick, press **F11** at power-on for the boot menu, pick the stick,
then DeckOS. In the installer, keep the preselected **NVME** partition and the America/New_York time zone.

## What you get on this machine

- NTFS drives mounted at `/mnt/Windows`, `/mnt/SSD` and `/mnt/BIG`.
- Display fix **level 1**, which stops the G70B's blackouts on the 9070 XT. `deckos display watch` is the
  tool if they come back.
- Gaming Mode on the Odyssey at 3840×2160 / 144 Hz, VRR off (the G7 flickers with Adaptive-Sync).
- A Steam library on `D:\SteamLibrary`: run `deckos steam-ntfs` once after adding it in Steam.
