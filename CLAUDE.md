# DeckOS: notes for Claude Code

DeckOS is an Arch + CachyOS gaming/AI distro: KDE Plasma 6, Steam Gaming Mode, ROCm, btrfs snapshots,
its own installer, Hub, Store and theming. The maintainer (kcooperlawson) daily-drives it on the
reference machine (Ryzen 7 7800X3D, RX 9070 XT, Samsung Odyssey G70B; see docs/reference-machine.md)
and develops DeckOS from DeckOS. User-facing docs are in README.md; read it before big changes.

**Positioning:** tuned for the reference machine, but the repo and UI must read as installable by
anyone. Personal specifics (drive letters, BIOS paths, that PC's partition) go in
docs/reference-machine.md, not the README or UI text. Be honest about limitations (README's "Known
limitations") rather than implying support that isn't there (untested NVIDIA/Intel, whole-disk installs).

## Layout

- `installer/deckos-install`: the install script (bash). The window in `pkg/deckos-installer` drives it
  unattended through `DECKOS_*` env vars (see the comment near the top). `installer/*.tsv` are the
  language and keyboard lists both use.
- `pkg/deckos-settings/`: the main package; `rootfs/` mirrors `/`. Holds the `deckos` tool
  (`usr/bin/deckos`), DeckOS Hub (`usr/lib/deckos/hub/`), DeckOS Store (`usr/lib/deckos/store/`), DeckOS
  Welcome (`usr/lib/deckos/welcome/`, the first-login tour), the package lists per group
  (`usr/share/deckos/packages/*.txt`, shared by the installer and `deckos software add`; an optional
  second column limits a line to one GPU vendor, `amd`/`nvidia`/`intel`, from `deckos display vendors`), themes, icons,
  SDDM and Plasma styles, the signing public key. DeckOS Menu, the launcher, is a QML plasmoid
  (`usr/share/plasma/plasmoids/org.deckos.menu/`) on Plasma's kicker models and KRunner; its Store
  suggestions come from `usr/lib/deckos/store/store_find.py` (no Qt, a slim index the Store writes).
  Preview it with `assets/preview_menu.py` (stand-in Plasma modules in `assets/preview_menu/`). JS names
  like `escape` or `get` break QML method/signal declarations.
- Graphics: AMD is the tested path. The installer runs CachyOS's `chwd -a` only when an NVIDIA or Intel
  GPU is present (AMD-only PCs keep desktop.txt's Radeon packages) and falls back to NVIDIA's open driver
  if chwd fails. The display ladder, `deckos gpu` and the Hub's Graphics card / FSR 4 rows are
  amdgpu-only and step aside on other cards; the Hub demo takes `--demo-gpu=nvidia|intel` to check that.
- Gaming tuning: `deckos scheduler` (scx_loader; lavd Gaming is the one-time default from the .install),
  `deckos gpu` (power limit, voltage offset, fan curve via amdgpu sysfs from `/etc/deckos/gpu.conf`,
  re-applied by `deckos-gpu.service`; boot with `deckos.gpu=stock` to skip; stands aside when LACT's
  `lactd` runs), `deckos auto-update` (04:00 timer, skipped mid-game). Shader cache size is in
  `usr/lib/environment.d/60-deckos-gaming.conf`; the Hub writes the FSR 4 upgrade to
  `~/.config/environment.d/90-deckos-gaming.conf`; `gaming-session` sources both, since Gaming Mode
  doesn't go through environment.d. The Hub's Games page (`hub/hub_games.py`) reads Steam, Heroic and
  Lutris libraries from their files and caches ProtonDB tiers for a week.
- `pkg/deckos-settings/rootfs/usr/share/plasma/plasmoids/org.deckos.quicksettings/`: DeckOS Quick Settings,
  the panel popup (native QML). Plasma services through their own QML modules (plasma-nm, bluedevil,
  plasma-pa, powerdevil, KWin over `org.kde.plasma.workspace.dbus`), each in its own Loader so a missing
  one hides only its piece; DeckOS bits through `Backend.qml` → `deckos quick-status` / `deckos updates`.
  Optimisation first: no polling, timers only while open, the update check every 3 h.
- `apps/deckos-files/` + `pkg/deckos-files/`: DeckOS Files, the file manager (C++/Qt 6/KIO, design in
  `docs/files.md`). `deckos-settings` depends on it. No Linux here? Push a branch: the "DeckOS Files"
  workflow builds it and uploads offscreen screenshots (`deckos-files --demo --screenshot DIR`).
- `pkg/deckos-theme-tmpikes/`: optional TMpikes theme. `pkg/deckos-installer/`: live USB only, never
  published to the update repo.
- `build.sh`: ISO build (archiso releng + DeckOS + an on-USB repo of prebuilt DeckOS/AUR packages).
- `assets/`: generators whose output is committed into `pkg/` (brand, `icons.py`, `plasma_theme.py`)
  and previews (`preview_hub.py`, `preview_welcome.py`, `preview_sddm.py`, `preview_plasma.py`,
  `preview_quicksettings.py`: the real plasmoid QML on stand-ins from `assets/qml-stubs/`). Re-run a
  generator after changing it and commit both.
- `builder/`: DeckOS Builder (starts GitHub builds, downloads ISOs, copies to Ventoy, builds locally).
- `personal/`: git-ignored. Holds the package signing key backup and the TMpikes brand kit. Never
  commit anything from it, never print the private key.

## Conventions

- **Match the surrounding code**: naming, comment density (short "why" comments, not narration).
- **Bash**: `set -Eeuo pipefail` everywhere. Under pipefail, `grep … | while` dies when grep matches
  nothing: use `while …; done < <(grep … || true)`. `IFS=$'\t' read` collapses empty fields (keep
  optional columns last). Quote everything. CI runs `shellcheck -S warning` on the scripts.
- **Python UIs**: PySide6. The Hub, Store and installer share one look: `hub_style.py` (palette, QSS,
  `icon()`/`pixmap()` recolouring DeckOS line icons) and `hub_widgets.py` (Card, StatusTile, RowItem,
  Meter, Toast, Empty…). Reuse them; the Store and Welcome import them from `../hub`. Slow work goes
  through `hub_system.Job` / threads, never blocking the UI. Qt treats `&` in button text as a shortcut:
  escape as `&&`.
- **Every UI has `--demo`** (canned data, no system calls) so it runs and can be screenshotted on any
  OS, Windows included. Keep demo data working when adding features; render with
  `QT_QPA_PLATFORM=offscreen` (and `QT_QPA_FONTDIR` on Windows) to check layouts.
- **Design language**: slate `#0F1115` / `#171A21`, borders `#262B36`, text `#E8EAF0` / `#8C94A6`,
  accent `#4C8DFF` with a violet gradient partner, 10px radii, Inter / Inter Display, the DeckOS line
  icons (24px, 1.75 stroke, drawn in `#000` and recoloured; add new ones in `assets/icons.py`).
  "Bolted plates" (screw heads) is the brand motif.
- **User-facing text**: plain, friendly, specific ("Windows Fast Startup is probably on"), sentence
  case, no jargon where a word will do.
- **Changing the system**: UIs never write system files directly. They call `deckos …` (through
  `pkexec` when root is needed) or Plasma's own tools.

## Installer safety (don't regress)

The installer only erases the partition the user picks; the EFI partition is shared, never formatted.
`list_targets` blocks BitLocker/LUKS/RAID/mounted partitions; a partition that won't mount (so it can't
be checked for Windows) is refused. `CHANGED` (nothing → partition → boot) drives the failure message;
keep it accurate. Optional steps (drives, Flathub, themes, home snapshots, final unmount) must warn,
not die: a finished install must never be reported as failed.

## Versions and releases

- `VERSION` is the DeckOS release: it names the ISO and sets `deckos-settings`' pkgver.
- **Release**: bump `VERSION`, commit, `git tag -a vX.Y.Z -m …`, push `main` and the tag. CI checks the
  tag matches `VERSION`, signs `deckos-settings` and `deckos-theme-tmpikes` with the DeckOS key
  (fingerprint `F67E15FABF95D2DA72BE5D3F6322881773088C41`, secret `DECKOS_SIGNING_KEY`) and replaces the
  pacman repo in the `repo` release; installed systems get it via `deckos update` about 5 minutes after
  the tag. A tag only builds an ISO when the installer or live USB changed since the last tag (the
  workflow's `plan` job: `build.sh`, `installer/`, `iso/`, `pkg/deckos-installer/`, the package lists, the
  workflow), or when the tag/commit message has `[iso]` (DeckOS Builder's "Build an ISO too");
  Build ISO (workflow_dispatch) always builds one. The squashfs is zstd: the ISO job takes ~12 minutes.
- `deckos-theme-tmpikes` only reaches installed systems when its own `pkgver` goes up.
- Commit messages: `area: summary` (or `DeckOS X.Y.Z: summary` for releases), then a short body.

## Testing

- **Without Linux** (Windows): `--demo` modes and the `assets/preview_*.py` renders; `bash -n` and small
  harnesses for script logic; `python -m py_compile` for Python.
- **On DeckOS**: `deckos dev-install` builds and installs your checkout (Hub/Store/tool changes), then
  restart the app. `sudo ./build.sh` builds an ISO locally (work dir and `out/` are btrfs subvolumes, so
  snapshots don't keep them). Test installs in a VM (QEMU + OVMF) before real disks.
- **Install test (CI)**: the `install-test` job runs `tests/install-test.sh` on every ISO the workflow
  builds: QEMU + OVMF (KVM), a blank disk with an EFI partition and an empty one, the live kernel booted
  with `deckos.autoinstall`, then a first boot of the installed system until graphical.target with SDDM.
  Serial consoles are in the log and the `install-test-logs` artifact; runs locally on Arch too
  (`bash tests/install-test.sh out/deckos-*.iso`). The live side is `deckos-autoinstall` (service in
  `iso/airootfs`): it only acts with that kernel flag, in a VM, with answers from QEMU's fw_cfg and a
  disk with the serial `deckos-autotest`. Keep all four checks; the target is never taken from the answers.
- **Install test (CI)**: the `install-test` job runs `tests/install-test.sh` on every ISO the workflow
  builds: QEMU + OVMF (KVM), a blank disk with an EFI partition and an empty one, the live kernel booted
  with `deckos.autoinstall`, then a first boot of the installed system until graphical.target with SDDM.
  Serial consoles are in the log and the `install-test-logs` artifact; runs locally on Arch too
  (`bash tests/install-test.sh out/deckos-*.iso`). The live side is `deckos-autoinstall` (service in
  `iso/airootfs`): it only acts with that kernel flag, in a VM, with answers from QEMU's fw_cfg and a
  disk with the serial `deckos-autotest`. Keep all four checks; the target is never taken from the answers.
- Things verified only on real hardware so far are worth re-checking after touching them: SDDM theme,
  Plasma style, Store with the real AppStream catalogs, Spicetify theme, pkexec flows.

## Gotchas already hit

- gpg on Windows (Git Bash/MSYS) stamps keys ~4h in the future (timezone bug); CI's gpg then rejects
  them. Make keys on Linux, or pass `--faked-system-time <real epoch>!`.
- Processes started inside `arch-chroot` (gpg-agent from `pacman-key`) keep `/mnt` busy; the installer
  ends them before unmounting.
- Spotify's MPRIS reports position 0 and old art URLs (`open.spotify.com/image/…`): the Now Playing card
  keeps its own clock and rewrites them to `i.scdn.co/image/…`.
- `sed` with `|` as delimiter breaks on text containing `|` (usage strings): edit those directly.
- Don't name a page method after a QWidget one (`update`, `show`, `close`…): a Welcome step's `update()`
  ran `deckos update` every time an accent change repainted the window.
- DeckOS Welcome autostarts (`/etc/xdg/autostart/deckos-welcome.desktop`) until
  `~/.config/deckos/welcome-done` exists; the launcher checks that in shell, so later logins don't start
  Python. `welcome-startup` is the "Show at startup" opt-in. Welcome reuses the Hub's
  `Hub.terminal`/`privileged`/`write_gaming` and `HubData`, and the Store's `Jobs`/`Installed`: changing
  those changes it too.

## Open work

Hub "Controllers" card for xone (Xbox wireless dongle); an NVIDIA and an Intel test install (the chwd
path has only been checked with `bash -n`/shellcheck); free-space
and whole-disk install modes; why NTFS drives weren't detected on
the reference machine (likely BitLocker); a `LICENSE` file.
