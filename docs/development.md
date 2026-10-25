# Developing DecKoOS

The reference machine, building from source, and how updates reach installed systems. See also
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Reference machine

Every default in DecKoOS was chosen and tested on this machine:

Ryzen 7 7800X3D · Radeon RX 9070 XT · ASRock B850M-C · 32 GB DDR5-6000 · Samsung Odyssey G70B + LG UltraGear,
dual-booting Windows 11.

[docs/reference-machine.md](reference-machine.md) has the exact setup for it (BIOS settings, which
partition DecKoOS goes on, the drive layout).

## Development

The look grew out of the design language of the MES and logging system its author built for work
(slate `#0F1115` / `#171A21`, `#262B36` borders, `#4C8DFF` accent), reworked for a gaming PC: blocky
letters, the oO as a controller (a thumbstick and the face buttons), bolted plates, hazard stripes.

**DecKoOS Builder** (`builder/`) is a desktop app that starts GitHub builds, downloads ISOs and copies them
to a Ventoy stick. See [builder/README.md](../builder/README.md).

```
VERSION                   the DecKoOS release: names the ISO, shows in os-release, the Hub and deckos doctor
builder/                  DecKoOS Builder app (GitHub builds, downloads, Ventoy USB)
apps/                     DecKoOS Files and DecKoOS Terminal (C++/Qt 6); pkg/deckos-files, pkg/deckos-terminal package them
assets/generate.py        brand generator (wordmark, gear, wallpaper, GRUB bg)
assets/icons.py           the DecKoOS line icons (Hub, Store, login screen) and the Store's app icon
assets/plasma_theme.py    the DecKoOS Plasma style (panel, popups, tooltips, widgets)
assets/preview_*.py       render the Hub, Welcome, login screen, Plasma style or Quick Settings on any OS
assets/qml-stubs/         stand-ins for Plasma's QML modules, so plasmoid previews run without Plasma
build.sh                  ISO build (Arch releng profile + DecKoOS)
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

DecKoOS's own packages (`deckos-settings` with the Hub, `deckos` tool, themes and fixes, plus
`deckos-theme-tmpikes`) are published as a signed pacman repo, on two channels:

- **Stable**, the [`repo` release](https://github.com/kcooperlawson/deckos/releases/tag/repo): where every
  install starts. It only gets a release once that release has been tried on the testing channel.
- **Testing**, the [`repo-testing` release](https://github.com/kcooperlawson/deckos/releases/tag/repo-testing):
  every release, minutes after it's tagged. `sudo deckos channel testing` switches a PC to it,
  `sudo deckos channel stable` back (`deckos channel` shows which one a PC is on).

Installed systems have the repo as `[deckos]` in `pacman.conf`, so `deckos update` and the Hub's Update
button pick up new versions like any other package.

**What's New:** a feature release (0.4.0, 0.5.0…) ships release notes in
`pkg/deckos-settings/rootfs/usr/share/deckos/releases/X.Y.Z.toml`: a name, a tagline, highlights with a screenshot
and a *Try it* button, and the fixes. After the update, DecKoOS shows them once, at the next login or straight after
updating from the Hub (`deckos whatsnew` any time). Someone who skipped a release sees everything since the last one
they saw. Patch releases (0.4.1…) have no notes file, so they update quietly; their fixes go in the next notes.

**To release:** bump `VERSION`, commit, then tag and push (`git tag v0.3.1 && git push origin v0.3.1`).
CI checks that the tag matches `VERSION`, signs the packages with the DecKoOS key (fingerprint
`F67E15FABF95D2DA72BE5D3F6322881773088C41`, kept as the `DECKOS_SIGNING_KEY` secret) and replaces the
testing repo's contents. Once it has run well on a testing PC, run **Promote to stable** from the Actions
tab with that version: stable gets exactly the packages testing had. It refuses when testing holds a
different version (a newer tag landed in between), so nothing reaches stable untried. `deckos-theme-tmpikes` only updates on installed systems when its own `pkgver` goes up.

**Working on DecKoOS from DecKoOS:** clone the repo into your home folder (not a Windows drive: NTFS loses
file permissions and symlinks), then `deckos dev-install` builds and installs your checkout. A later
release replaces it as a normal update. Installs from 0.3.0 or earlier don't have the update channel or
`dev-install` yet; run `makepkg -si` once in `pkg/deckos-settings` to get both.

`build.sh` and DecKoOS Builder keep their work folder and `out/` as btrfs subvolumes of their own on DecKoOS,
so system and `/home` snapshots don't hold on to old builds and ISOs.

The generators write into `pkg/` and their output is committed; run them again after changing a
design. The installer, Hub, Store and Welcome all have a demo mode for working on the UI anywhere, including
Windows: run `deckos_installer.py --demo`, `deckos_hub.py --demo`, `deckos_store.py --demo` or `deckos_welcome.py --demo` from their folders in `pkg/`.
