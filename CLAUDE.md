# DeckOS: notes for Claude Code

DeckOS is an Arch + CachyOS gaming/AI distro: KDE Plasma 6, Steam Gaming Mode, ROCm, btrfs snapshots,
its own installer, Hub, Store and theming. The maintainer (kcooperlawson) daily-drives it on the
reference machine (Ryzen 7 7800X3D, RX 9070 XT, Samsung Odyssey G70B; see docs/reference-machine.md)
and develops DeckOS from DeckOS. User-facing docs are in README.md; read it before big changes.

**Positioning:** tuned for the reference machine, but the repo and UI must read as installable by
anyone. Personal specifics (drive letters, BIOS paths, that PC's partition) go in
docs/reference-machine.md, not the README or UI text. Be honest about limitations (README's "Known
limitations") rather than implying support that isn't there (untested NVIDIA/Intel, erasing a whole used disk).

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
  like `escape` or `get` break QML method/signal declarations. DeckOS Taskbar
  (`plasmoids/org.deckos.taskbar/`) is the panel's task manager on Plasma's `TasksModel` (launchers,
  grouping, order); every DeckOS layout uses it (`showLabels` for Classic). Preview with
  `assets/preview_taskbar.py` (stand-ins in `assets/preview_taskbar/`); lint against the real modules with
  `qmllint -I /usr/lib/qt6/qml`. In QML, `foo: foo` inside a child binds the child's own `foo` to itself:
  give ids names that no property uses (Quick Settings lost its backend that way).
  DeckOS Performance (`plasmoids/org.deckos.perfgraphs/`) is the desktop graphs widget on
  `org.kde.ksysguard.sensors` (ksystemstats; the GPU with the most VRAM, not gpu0, unless configured), one
  1 s clock while visible; default desktop and `deckos layout graphs` add it. Preview with
  `assets/preview_perfgraphs.py`. A `PathPolyline` starts its own subpath: close areas inside one polyline.
- Graphics: AMD is the tested path. The installer runs CachyOS's `chwd -a` only when an NVIDIA or Intel
  GPU is present (AMD-only PCs keep desktop.txt's Radeon packages) and falls back to NVIDIA's open driver
  if chwd fails. The display ladder, `deckos gpu` and the Hub's Graphics card / FSR 4 rows are
  amdgpu-only and step aside on other cards; the Hub demo takes `--demo-gpu=nvidia|intel` to check that.
  NVIDIA numbers (Hub tiles, System Monitor, the AI model pick) come from NVML in process (`usr/lib/deckos/gpu/nvml.py`,
  ctypes, no nvidia-smi). System Doctor flags nouveau/no driver and RTX 50 (Blackwell) on the closed module, and old
  Raptor Lake microcode. Tests: `tests/test_nvidia.py` (a simulated i9-14900K + RTX 5070 Ti).
- Gaming tuning: `deckos scheduler` (scx_loader; lavd Gaming is the one-time default from the .install),
  `deckos gpu` (power limit, voltage offset, fan curve via amdgpu sysfs from `/etc/deckos/gpu.conf`,
  re-applied by `deckos-gpu.service`; boot with `deckos.gpu=stock` to skip; stands aside when LACT's
  `lactd` runs), `deckos auto-update` (04:00 timer, skipped mid-game). Shader cache size is in
  `usr/lib/environment.d/60-deckos-gaming.conf`; the Hub writes the FSR 4 upgrade to
  `~/.config/environment.d/90-deckos-gaming.conf`; `gaming-session` sources both, since Gaming Mode
  doesn't go through environment.d. Gaming Mode's SDDM wrapper (`gaming-session`) checks for both
  gamescope-session-git and the gamescope-session-steam-git client profile before switching. The
  Steam service drop-in runs `gaming-service` to load DeckOS settings in the actual service process;
  `gaming-cleanup` removes shared display/portal environment and stops the graphical session target
  after failure/exit. Treat ADAPTIVE_SYNC=0 as unset for upstream (nonempty means enabled).
  Session changes need `tests/test_gaming_session.py`; never test by logging out the developer
  without coordinating first. Workload modes: `deckos mode watch` (user unit
  `deckos-modes.service`, enabled with `systemctl --global` from the .install) finds a game with an
  anchored `pgrep` every 5 s (Steam's reaper, lutris-wrapper, gamescope-session), then unloads Ollama
  models, pauses Docker and suspends Baloo, and records what to put back in `$XDG_RUNTIME_DIR/deckos-mode`
  (also what `quick-status` passes to Quick Settings' ModeRow). The Hub's Games page (`hub/hub_games.py`) reads Steam, Heroic and
  Lutris libraries from their files and caches ProtonDB tiers for a week.
- `pkg/deckos-settings/rootfs/usr/share/plasma/plasmoids/org.deckos.quicksettings/`: DeckOS Quick Settings,
  the panel popup (native QML). Plasma services through their own QML modules (plasma-nm, bluedevil,
  plasma-pa, powerdevil, KWin over `org.kde.plasma.workspace.dbus`), each in its own Loader so a missing
  one hides only its piece; DeckOS bits through `Backend.qml` → `deckos quick-status` / `deckos updates`.
  Optimisation first: no polling, timers only while open, the update check every 3 h.
- `apps/deckos-files/` + `pkg/deckos-files/`: DeckOS Files, the file manager (C++/Qt 6/KIO, design in
  `docs/files.md`). `deckos-settings` depends on it. No Linux here? Push a branch: the "DeckOS Files"
  workflow builds it and uploads offscreen screenshots (`deckos-files --demo --screenshot DIR`).
- `apps/deckos-terminal/` + `pkg/deckos-terminal/`: DeckOS Terminal, the default terminal (C++/Qt 6 on
  `qtermwidget`, design in `docs/terminal.md`). It compiles DeckOS Files' `style.cpp` for the shared look.
  Tabs are named from `/proc` and `.git/HEAD` (no git processes); the mode chip listens for
  `org.deckos.Mode.Changed`, which `deckos mode` emits with `busctl`. `--hold -e CMD` is what the Hub's
  terminal steps use. In Qt 6 `quit()` asks windows to close, and a running command makes the window
  ask: the screenshot mode uses `exit(0)`.
- `apps/deckos-editor/` + `pkg/deckos-editor/`: DeckOS Editor, the default text editor (C++/Qt 6 on KSyntaxHighlighting,
  design in `docs/editor.md`; `Document` keeps line endings/BOM/permissions and saves root files through pkexec cp).
  Its text defaults live in DeckOS Files' `mimeapps.list` (that package owns /etc/xdg/mimeapps.list). A new
  DeckOS app package goes in the same lists as deckos-terminal: build-iso.yml, build.sh, the installer's DeckOS
  layer, deckos-settings' depends, `deckos dev-install`, `hub_system.DECKOS_PKGS`. `unix` is a GCC macro.
- Local AI: `usr/lib/deckos/assistant/` (plain Python, no Qt). `assistant.py` has the Ollama client, the
  tools and their safety rules (`is_read_only`, `BLOCKED`: keep both tested), `Session` (the agent loop)
  and `summarize` (chunked, for deckos-local). `deckos_ask.py` is `deckos ask`; `deckos_assistant.py` is the chat box
  (`deckos-assistant`, Meta+Space via X-KDE-Shortcuts, one instance over a QLocalSocket, `--ask TEXT`,
  `--demo --screenshot DIR`; worker signals connect to bound methods: a lambda would run in the worker
  thread and build widgets there, which crashes); `deckos_local_mcp.py` is a hand-written MCP stdio
  server (`deckos ai claude-link`). Read-only pipelines (every part read-only) run without asking. Changes always go through `Tools.confirm`.
  `models.py` picks a model by graphics memory (`deckos ai models`, the Hub's "Choose a model", `deckos ai setup`'s
  default); "measured" means it passed `tests/eval/assistant_tools.py` (needs Ollama; results in docs/assistant-models.md). Model choice was measured, not guessed: gpt-oss:20b called the right tools where gemma4:12b asked in
  chat instead. `DECKOS_AI_DIR` points `deckos ask`/`deckos ai` at a checkout for testing.
  Web search (`web.py`, DuckDuckGo lite; `web_search`/`read_web_page` tools) only with WEB_SEARCH=on in ai.conf (off by
  default); pages from public addresses only (`web.public`: no localhost, LAN, link-local, file:); every result starts
  with the UNTRUSTED label. `PERSONALITIES` (PERSONALITY=friendly|calm|direct|gamer) prefix `system_prompt()`; the
  rules after it never change. `deckos ai set web|personality`; Hub > AI & Dev. Tests: `tests/test_assistant_web.py`.
- Game Doctor: `usr/lib/deckos/gamedoctor/`. `steamfiles.py` reads and writes Steam's KeyValues files
  (round-trips must stay exact; writes keep `.deckos-bak`; Steam must be closed: it rewrites them on exit),
  `gamedoctor.py` finds quick exits in `logs/console_log.txt`, takes the game's output from
  `logs/console-linux.txt`, matches `RULES`, and applies/undoes fixes (state per game in
  `~/.local/state/deckos/gamedoctor/`). `gamedoctor_watch.py` is the user service (tail -F, no polling).
  Tests: `tests/test_gamedoctor.py` (a fake Steam root via `DECKOS_STEAM_ROOT`; never the real one).
- DeckOS Retro: `usr/lib/deckos/retro/`. `retro.py` (no Qt): `SYSTEMS` (consoles: extensions, folder names,
  libretro core package or Flathub id, BIOS with known md5s), `scan()` (extension, then folder name, then disc
  header bytes; .cue/.gdi/.m3u claim their files; "(Disc N)" files merge; anything unidentified is left out,
  never guessed), `import_bios()` (by checksum), `sync_steam()` (non-Steam shortcuts tagged "DeckOS Retro" via
  steamfiles' binary KeyValues; other shortcuts untouched; Steam must be closed). `deckos retro install` installs
  only emulators (allow-listed). Never add game or BIOS downloads. Tests: `tests/test_retro.py`.
- System Doctor: `usr/lib/deckos/sysdoctor/`. `sysdoctor.py` (no Qt, read-only) runs `CHECKS` through `run()`
  (tests feed it canned output) into `Finding`s with evidence, `Fix`es (commands; root ones via pkexec) and
  `open` (a DeckOS app). `explain()` is deckos-local's `summarize` on one finding. Name crashes by command
  line (`PROGRAMS`), not by `python3`. `deckos_sysdoctor.py` is the window (the Hub's Health check).
- Move In: `usr/lib/deckos/movein/`. `movein.py` (no Qt) scans Windows on the mounted NTFS drives
  (`DECKOS_MOVEIN_ROOTS` for tests) into `Item`s and `apply()`s them: Windows is only read; Linux-side files
  keep `.deckos-bak`; Steam's libraryfolders.vdf goes through Game Doctor's `steamfiles`. Drives first: if
  they move to /mnt, `repoint()` moves the other items' paths. `deckos_movein.py` is the window. Build rows
  on their own widget (`QHBoxLayout(holder)`): a free layout added with addLayout crashed PySide on exit.
- `pkg/deckos-theme-tmpikes/`: optional TMpikes theme. `pkg/deckos-installer/`: live USB only, never
  published to the update repo.
- `build.sh`: ISO build (archiso releng + DeckOS + an on-USB repo of prebuilt DeckOS/AUR packages).
- `assets/`: generators whose output is committed into `pkg/` (brand, `icons.py`, `plasma_theme.py`)
  and previews (`preview_hub.py`, `preview_welcome.py`, `preview_sddm.py`, `preview_plasma.py`,
  `preview_quicksettings.py`: the real plasmoid QML on stand-ins from `assets/qml-stubs/`). Re-run a
  generator after changing it and commit both.
- Icons: `assets/icon_theme.py` draws DeckOS' own app (plates) and file type (sheets) icons into
  `usr/share/icons/DeckOS/scalable/` (aliases are symlinks; the generator refuses a name listed twice); the PKGBUILD
  adds Papirus' recoloured places and writes index.theme; colour variants inherit DeckOS. Never draw a brand's logo:
  those come from Papirus. `assets/cursors.py` draws DeckOS Pointers (`usr/share/icons/DeckOS-cursors`):
  Plasma 6 SVG cursors (`cursors_scalable/NAME/metadata.json`) plus Xcursor files 24-64 px written by hand
  (no xcursorgen), every CSS/X11/hash name a symlink. Both need PySide6; outputs are committed.
- DeckOS Builder: `usr/lib/deckos/builder/deckos_builder.py` (in deckos-settings, `deckos-builder`; `builder/` has
  the from-a-checkout launchers for Linux and Windows). It finds its checkout by walking up to `pkg/deckos-settings`,
  else uses the installed Hub/branding. Everyone signs in with their own GitHub (`gh auth login --web`); `github_role()`
  asks GitHub for the account's permission: admin/maintain see Release, Promote, Build on GitHub and merging,
  everyone else gets Contribute (fork + clone with gh, checks, `gh pr create --web`). GitHub enforces the same rules.
- DecKoOS Music: `usr/lib/deckos/music/` (`deckos-music`, Meta+M via X-KDE-Shortcuts) is Vibe mode. `library.py` (no Qt:
  scan with a size/mtime cache, mutagen tags else names, covers in folders or files, albums, search), `analysis.py` (no Qt:
  parec on the default monitor, 64 log bars, bass/mid/high, beats on the low end counted in audio time, a slow
  `intensity`), `sources.py` (MPRIS through `playerctl --follow`, `players="spotify,%any"`: no sign-in, no streaming of its
  own; local files with Qt Multimedia), `world.py` (no Qt: monitors laid out into one world, the cover on the middle
  screen, of two the one KDE ranks first: `kscreen-doctor -o` priority 1, since Qt's primaryScreen on Wayland is
  just the first), `deckos_music.py` (the `Engine` QObject every window reads, image provider, one instance over a
  QLocalSocket: a second launch toggles the stage; `--offer` is the notification Context sends when listening starts).
  QML in `qml/`: one `Stage` window per monitor, each drawing its slice of the world at -origin from the shared clock
  (`engine.startMs`; never per-window animations, or the screens drift apart); `stage.frag` is the sky (aurora, stars,
  beat shockwaves, the reveal), compiled to `stage.frag.qsb` (commit both; `tests/test_music.py` checks it's current).
  Esc leaves; your own files keep playing in `Mini`. Steps aside when workload modes says a game runs.
  `--demo [--demo-screens N] --screenshot DIR` stitches every screen's grab into one picture (offscreen renders without
  the shader: check the look on real screens). Tests: `tests/test_music.py`.
- DecKoOS Sounds: `assets/sounds.py` synthesises the sound theme (numpy + ffmpeg; glass tones, a metal-plate accent for
  big events) into `usr/share/sounds/deckos/` (`Inherits=ocean`); `kdeglobals.base` makes it the default; Hub > Appearance
  > Sounds switches it (kwriteconfig6). Not in check.sh's generated check: Vorbis output varies between ffmpeg versions.
- `site/`: the website (README.md there). `build.py` generates static pages from the README's features/limitations,
  the release TOMLs, `docs/` (`DOCS`/`DOC_META` pick and name them), SECURITY.md and the newest `out/deckos-X.Y.Z` ISO
  into git-ignored `site/public/`; its own small markdown renderer escapes everything. `serve.py` serves it (127.0.0.1,
  Range, no visitor addresses logged); `Caddyfile` for a server. Nothing loads from other sites (Inter is subset and
  served locally). `tests/test_site.py` checks every internal link and anchor. Builder's Website card publishes a
  release's ISO to it (`builder/site_publish.py`, no Qt; `tests/test_site_publish.py`): only from runs that passed,
  install tests included; missing ones come from `iso-version.yml`, which builds an old tag and never publishes
  (running build-iso.yml on an old tag would: its publish job follows the tag).
- DecKoOS Disks: `usr/lib/deckos/disks/` (`deckos-disks`, `deckos disks`; design in `docs/disks.md`). `disks.py` (no Qt)
  reads lsblk (NAME as a column: see Gotchas), fstab and this boot's log into `startup()` checks (will each drive mount
  after a restart, and why not); `add()` test-mounts before keeping an entry and restores fstab exactly if it fails;
  changes only inside the `deckos drives` block (rescan keeps non-NTFS entries there). `unit()` must match
  `systemd-escape -p --suffix=mount`. System Doctor's `startup_drives` uses it (`disks.run = run`). Partition editing
  (`format_part`/`create`/`delete`/`resize`, root): `why_not()` is the one rule list (the app offers only what it allows, else says why;
  root asks again on a fresh read and also mounts NTFS read-only to look for Windows); `--confirm` (label or name) and
  `--layout` (`fingerprint()`) must match; the table is `sfdisk --dump`ed to `TABLES` first; `--no-reread` + `partx` per
  partition; no table changes on the disk DecKoOS runs from; only the end of a partition moves. Tests fake every command,
  run the real tools on image files, and do the whole flow on a loop device only as root. Tests: `tests/test_disks.py`.
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
Free space and empty disks (`list_free`, `make_partition`) only ever add: one partition in a gap that
`sfdisk -F` still reports free, or GPT + a new EFI partition + DeckOS on a disk with no table and no file
system. Nothing existing is deleted, moved or resized; tests/vm/partition_steps.py checks that on real disks.
`list_targets` blocks BitLocker/LUKS/RAID/mounted partitions; a partition that won't mount (so it can't
be checked for Windows) is refused. `CHANGED` (nothing → partition → boot) drives the failure message;
keep it accurate. Optional steps (drives, Flathub, themes, home snapshots, final unmount) must warn,
not die: a finished install must never be reported as failed.

## Versions and releases

- `VERSION` is the DeckOS release: it names the ISO and sets `deckos-settings`' pkgver.
- Feature releases (X.Y.0) bundle features and get release notes: `usr/share/deckos/releases/X.Y.0.toml` (+ images in
  `X.Y.0/`), shown once by `deckos-whatsnew` (login autostart, after a Hub update, Hub > Home > What's new). Patch
  releases (X.Y.Z) are fixes only, no notes file: they update quietly. Write the notes as the features land.
- **Release** only through `pkg/deckos-settings/rootfs/usr/lib/deckos/builder/release.py X.Y.Z "summary" [--hotfix] [--iso]`
  (Builder's Release button runs the same): clean `main`, `check.sh lint` and `tests` here, the code pushed alone, the
  `checks.yml` workflow green on that exact commit, and only then VERSION bumped, tagged and pushed. One release per
  12 h (`RELEASE_GAP`); sooner only as `--hotfix`. Never tag by hand or push past failing checks. CI checks the
  tag matches `VERSION`, signs `deckos-settings` and `deckos-theme-tmpikes` with the DeckOS key
  (fingerprint `F67E15FABF95D2DA72BE5D3F6322881773088C41`, secret `DECKOS_SIGNING_KEY`) and replaces the
  pacman repo in the `repo-testing` release (`.github/publish-repo`); PCs on the testing channel
  (`deckos channel testing`, the reference machine) get it via `deckos update` about 5 minutes after
  the tag. Stable (`repo`, where installs start) only changes when the maintainer runs the "Promote to
  stable" workflow with that version, which refuses if testing holds a different one. Both jobs share
  the `deckos-repo` concurrency group. A tag only builds an ISO when the installer or live USB changed since the last tag (the
  workflow's `plan` job: `build.sh`, `installer/`, `iso/`, `pkg/deckos-installer/`, the package lists, the
  workflow), or when the tag/commit message has `[iso]` (DeckOS Builder's "Build an ISO too");
  Build ISO (workflow_dispatch) always builds one. The squashfs is zstd: the ISO job takes ~12 minutes.
- `deckos-theme-tmpikes` only reaches installed systems when its own `pkgver` goes up.
- Commit messages: `area: summary` (or `DecKoOS X.Y.Z: summary` for releases), then a short body. The name is
  DecKoOS in anything people read; `deckos` only for commands, packages and paths.

## Testing

- **Without Linux** (Windows): `--demo` modes and the `assets/preview_*.py` renders; `bash -n` and small
  harnesses for script logic; `python -m py_compile` for Python.
- **On DeckOS**: `deckos dev-install` builds and installs your checkout (Hub/Store/tool changes), then
  restart the app. `sudo ./build.sh` builds an ISO locally (work dir and `out/` are btrfs subvolumes, so
  snapshots don't keep them). Test installs in a VM (QEMU + OVMF) before real disks.
- **Install test (CI)**: the `install-test` job runs `tests/install-test.sh` on every ISO the workflow
  builds: QEMU + OVMF (KVM), a blank disk with an EFI partition and an empty one, the live kernel booted
  with `deckos.autoinstall`, then a first boot of the installed system until graphical.target with SDDM.
  Three layouts (`DECKOS_TEST_LAYOUT`, a matrix in CI): `partition` (an EFI partition + an empty one),
  `empty` (a blank 80 GB disk the installer takes whole) and `free` (EFI + a 20 GB ext4 to keep + free space; the
  harness fails if a partition or file system that was there changed).
  Serial consoles are in the log and the `install-test-logs-LAYOUT` artifacts; runs locally on Arch too
  (`bash tests/install-test.sh out/deckos-*.iso`). The live side is `deckos-autoinstall` (service in
  `iso/airootfs`): it only acts with that kernel flag, in a VM, with answers from QEMU's fw_cfg and a
  disk with the serial `deckos-autotest`. Keep all four checks; the target is never taken from the answers.
- Things verified only on real hardware so far are worth re-checking after touching them: SDDM theme,
  Plasma style, Store with the real AppStream catalogs, Spicetify theme, pkexec flows.

## Contributions

`CONTRIBUTING.md` is the contributor guide; `bash tests/check.sh [lint|tests|generated]` is the single list of
checks, and CI's lint and unit-test jobs call it (add new scripts to its `BASH_SCRIPTS`, not to the workflow).
Workflows default to read-only tokens; only `plan` and `publish` write, and only tags publish. `.github/CODEOWNERS`
names the maintainer on everything, with the installer, root and packaging paths called out. DeckOS Builder's
Contributions card lists open pull requests (checks, `CAREFUL` paths flagged), opens Claude Code to review one
(review only: never merge, approve or push), and merges only after the checks pass and the maintainer confirms.

## How DecKoOS hangs together (0.10.0)

- **Pulse** (`usr/lib/deckos/pulse/pulse.py`, no Qt): the timeline. JSON lines in `~/.local/state/deckos/timeline.jsonl`
  (user) and root-owned `/var/lib/deckos/timeline.jsonl` (system); readers watch the files (no polling), user events
  also go out as `org.deckos.Pulse.Event`. Record with `pulse.emit(kind, title, undo=[...])` (Python) or the `pulse`
  function in `deckos`. An undo is a `deckos` command from `UNDOABLE`; only system entries undo via pkexec. pacman
  hooks (`zzz-deckos-pulse-*.hook`) record installs/updates/removals with `deckos undo N`. Tests must point
  `DECKOS_PULSE_USER`/`DECKOS_PULSE_SYSTEM` at temp files (check.sh does for the whole run).
- **Actions** (`usr/share/deckos/actions.toml` + `usr/lib/deckos/actions/actions.py`): everything DecKoOS can do, once.
  DecKoOS Menu's search (In DecKoOS, above the results; the cursor still starts on the first app), `deckos do ID`, and the
  Assistant's `do_action` read it. Add a feature's action there; `tests/test_actions.py` checks icons, commands, pages.
- **Care** (`usr/lib/deckos/care/care.py`, `deckos-care.service`): follows the journal's crash reports and both timelines;
  runs System Doctor's quick checks after system changes; says each thing once in a while.
- **Game profiles** (`usr/lib/deckos/profiles/`): per-game power, Do Not Disturb, AI/Docker freeing; workload modes apply
  them on game start (`mode_game` prints `ID<TAB>NAME`) and restore on stop. Hub > Games > sliders button.
- **Recovery**: GRUB's snapshots menu (grub-btrfs, overlayfs) starts a snapshot read-only; `deckos undo booted` names it
  (from `rootflags=…subvol=@snapshots/N/snapshot`), the Hub's Home banner and System Doctor offer `deckos undo keep`,
  which swaps it in as @ through the same `swap_in` as `deckos undo N`. Tests: `tests/test_recovery.py`.
- **Report** (`usr/lib/deckos/report/deckos_report.py`, `deckos report`): hardware, drivers, System Doctor, recent
  errors in one text file for whoever helps; `scrub()` takes out names, serials, UUIDs, ids and addresses (tested).
  Never sends it anywhere.
- **Settings** (`hub/hub_settings.py`, no Qt; `hub/hub_more.py`): the Hub is the one place for settings. One index of
  the Hub's pages, actions.toml and the Plasma panels DecKoOS uses as they are (`PLASMA`, plain names, hidden when the
  KCM isn't installed); the sidebar's search (Ctrl+F, Enter opens the first) and More settings read it. Plasma panels
  open in System Settings. Tests: `tests/test_settings.py`.
- **Lock screen**: Plasma 6 keeps the lock screen's QML in the plasma-workspace shell package (a theme can't replace it;
  don't overwrite its files). DecKoOS owns its wallpaper: `deckos wallpaper` sets the desktop and kscreenlockerrc together
  (Hub, Welcome, Move In and theme changes use it); `/etc/xdg/kscreenlockerrc` defaults it to the DecKoOS wallpaper.
- **Kid mode** (`usr/lib/deckos/kids/`): an account per child (no password, not wheel, group `deckos-kids`), settings
  root-owned in `/etc/deckos/kids/NAME.conf` (`kids.py`, no Qt; `deckos kids` does the root work). `kids.py seed` writes
  their home: KDE kiosk restrictions, the `deckos-kids --session` autostart (big tiles, minutes used, logout at the end of
  the time), and a Firefox profile with CleanBrowsing's family DoH (trr mode 3). The first login sets the `kids` panel
  layout (no menu; hidden from grown-up layout lists). `deckos kids start` locks the parent and shows the login screen
  (SDDM's SwitchToGreeter). Hub > System > Kids. Time is counted and enforced by `deckos-kids-time.service` (root, `kids.py watch`: one
  minute at a time for a child's session that's on screen and unlocked, `/var/lib/deckos/kids/NAME.json`, logout after a
  grace minute); the launcher only shows it. Retro games are shared as copies in `/srv/deckos-kids/games` (`deckos kids
  games`; children can't read a parent's home), each a tile straight into RetroArch. Steam games can't be tiles (Steam is
  per account). polkit `49-deckos-kids.rules` refuses shutdown/reboot/sleep to `deckos-kids`; the launcher caps volume
  (pactl subscribe, no polling) and takes a controller (the Gaming Mode panel's `Pad`). The login screen shows children
  under the card and keeps the card on a grown-up. Tests: `tests/test_kids.py`.
- **Vibes** (`usr/lib/deckos/vibes/`): `vibes.py` (no Qt) lists each Vibe: a DecKoOS theme, accent, scene, visualizer
  style, colours, corners. `deckos vibe apply|visualizer|off` applies them as the user and records undo. The look is the
  `org.deckos.vibe` Plasma wallpaper (QML scenes over CC0/public-domain photos credited in `contents/images/CREDITS.md`;
  only ship photos with a licence like that) with `Visualizer.qml` on top, so it's under every window and stops while
  a window is full screen. `visualizer.py serve` (user unit `deckos-visualizer`) reads the default output's monitor
  through parec, numpy FFT to 48 bars, sends bytes over a localhost-only WebSocket, only while the wallpaper is
  connected, silent after 3 s of quiet and off during games. `assets/preview_vibes.py` renders them (and the Hub's tile
  previews). Tests: `tests/test_vibes.py`. Scenes get the music themselves (`MusicFeed.qml`: bass/mid/high/energy/beats;
  the bars on top are optional, off by default) and live on the clock (hour, rare events); shared `Glow` (an ellipse that
  always fades out), `Vignette`, `Grain`. Your own Vibes: `~/.config/deckos/vibes/KEY.json` (photo copied to
  `~/.local/share/deckos/vibes`), the `photo` scene (`PhotoScene.qml`: lights at fractions of the 16:9 crop, each on
  bass/mid/high), made in the Hub's editor (`hub/hub_vibe_editor.py`: `find_lights`, `photo_colours`), shared as a
  `.deckos-look` zip (`deckos vibe export|import`). Every value passes `vibes.CHECKS` first: they go into a desktop
  script, and imported looks are untrusted (picture by magic bytes). Tests: `tests/test_vibe_custom.py`.
  `deckos vibe widgets arrange` (`vibes/arrange.py`): widgets in a column on the right, written to Plasma's
  ItemGeometries while the shell restarts (a running desktop ignores scripted positions).
- **Taskbar settings**: `deckos taskbar height|colors|motion` writes every DecKoOS taskbar (`colorMode` accent|vibe|custom;
  a Vibe never overrides custom). `deckos layout set` saves pins to `~/.config/deckos/pins` before replacing panels.
  A tile pulses while its app plays sound: `org.kde.plasma.private.volume`'s SinkInputModel (not corked), matched by pid,
  else by name/binary (Flatpak Spotify plays from pid 4 in its sandbox; browsers from helper processes).
- **Desktop widgets** (`plasmoids/org.deckos.{bigclock,nowplaying,weather,focus,note}`): share `org.deckos.vibes` (a QML
  module in `usr/lib/qt6/qml`: `Look`, `Plate`, `VibeText`); `deckos vibe apply` writes their style/colours, `deckos vibe
  widget ID on|off` places them, `deckos vibe weather TOWN` geocodes through Open-Meteo. `assets/preview_widgets.py
  --check` loads every one for real on stand-ins (it caught an infinite timer loop and names that clash with Item's own:
  `focus`, `left`, `running`). The real lint is `/usr/lib/qt6/bin/qmllint` (not on PATH).
- **Fixes / self-healing** (`usr/lib/deckos/heal/heal.py`, no Qt; design and rules in `docs/self-healing.md`): AI picks
  a vetted recipe and fills its blanks, never writes commands. Blanks are allow-listed (repo packages via `pacman -Si`,
  unit lists, int ranges), a DENY regex is the second wall, root fixes take a snapper pre snapshot and record Undo.
  `deckos heal`, the Assistant's `use_fix`. Never loosen the walls for a model, however big. `heal_report.py`: outcomes
  per fix (the asking user's file, even from pkexec), `report [--open]` (scrubbed; opens the heal.yml issue form, the
  person submits; DecKoOS sends nothing), `triage` (gh; groups `heal-report` issues), `draft N` (local model proposes; `heal.check_recipe` must pass: `PROGRAMS` and each
  one's allowed first argument, whole-word blanks, DENY; saved for review, never added). The person's switches: `heal.conf` (suggest/remember/reports, `heal.settings()`;
  root fixes read the asking user's), shown with the facts in `hub/hub_heal.py`'s card (Hub > System and Welcome's
  privacy step). Every part checks its switch. System Doctor's fixes use `sysdoctor.recipe()` where a recipe fits; Care
  offers those in its notification (suggest on); after a recipe fix `deckos heal ask` notifies "Did that fix it?".
  Bugs only: triage skips reports without a finding, `draft` refuses one without, and the prompt answers "none" for
  features/tweaks/looks. Tests: `tests/test_heal.py`.
- **Context** (`usr/lib/deckos/context/context.py`, no Qt; design in `docs/context.md`): what you're doing (gaming, watching,
  away, developing, listening, desktop) from /proc, playerctl (browser media: by address, else no album = video), logind
  idle and the workload mode's state. `classify(facts)` is pure and tested; `Steady` holds a change for two looks. User
  unit `deckos-context.service` (global from the .install) runs the reactions, each a switch in `context.json`: power while
  building, quiet while developing, Welcome back after a game (from Pulse), Moments (`moments.for_activity`). Quick
  Settings' `ContextRow` shows it and why, and corrects it (`deckos context set|auto`). Tests: `tests/test_context.py`.
- **Setup** (`usr/lib/deckos/setup/`): `deckos setup export|import|undo`; imports only write `WHAT`'s places.
- **Gaming Mode panel** (`usr/lib/deckos/gamepanel/`, `deckos-gamepanel`): in the Steam library as "DecKoOS" (added by
  gaming-session before Steam starts); reads gamepads from evdev itself (devices with BTN_SOUTH; LED controllers
  register as joysticks too). A Decky plugin is the next step once one can be tested.

## Gotchas already hit

- gpg on Windows (Git Bash/MSYS) stamps keys ~4h in the future (timezone bug); CI's gpg then rejects
  them. Make keys on Linux, or pass `--faked-system-time <real epoch>!`.
- Processes started inside `arch-chroot` (gpg-agent from `pacman-key`) keep `/mnt` busy; the installer
  ends them before unmounting.
- Spotify's MPRIS reports position 0 and old art URLs (`open.spotify.com/image/…`): the Now Playing card
  keeps its own clock and rewrites them to `i.scdn.co/image/…`.
- util-linux 2.42's `lsblk -J` nests partitions under disks only when NAME is a column; without it the list is
  flat and `.children` is empty (NTFS drives went missing at install). `tests/test_lsblk_tree.py` guards it.
- `sed` with `|` as delimiter breaks on text containing `|` (usage strings): edit those directly.
- `mkfs.fat --offset` into a big disk image sizes clusters for the whole image: a small EFI partition
  ends up with too few clusters for FAT32, which Linux mounts but UEFI can't read. Pass `-S 512 -s 1`.
- Don't name a page method after a QWidget one (`update`, `show`, `close`…): a Welcome step's `update()`
  ran `deckos update` every time an accent change repainted the window.
- DeckOS Welcome autostarts (`/etc/xdg/autostart/deckos-welcome.desktop`) until
  `~/.config/deckos/welcome-done` exists; the launcher checks that in shell, so later logins don't start
  Python. `welcome-startup` is the "Show at startup" opt-in. Welcome reuses the Hub's
  `Hub.terminal`/`privileged`/`write_gaming` and `HubData`, and the Store's `Jobs`/`Installed`: changing
  those changes it too.

## DeckOS System Monitor

`usr/lib/deckos/sysmon/`: `sysmon.py` (no Qt) reads /proc and /sys (`DECKOS_PROC`/`DECKOS_SYS` for tests:
`tests/test_sysmon.py`) into `Snapshot`s; rates and CPU shares are deltas between samples. Processes are
grouped by the program they run, named from .desktop files (so Firefox's tab processes stay with Firefox).
`deckos_sysmon.py` is the window (`deckos-sysmon`, Ctrl+Shift+Esc, `--demo --screenshot DIR`): Processes
(tree updated in place, numeric sort via `Row.__lt__`; other users' processes end through pkexec kill) and
Performance (fixed-scale `Sparkline`s and the big `Graph`, with a scale and a dot where it is now). Each resource has its
own colour everywhere (`KIND`: CPU blue, memory violet, graphics green, disks amber, network cyan; fixed, not the accent),
process cells are heat-shaded by use (`Heat` delegate), the headers carry the totals, and `sysmon.mode()` (the
`deckos mode` state file) shows Gaming mode. GPU figures are amdgpu (`gpu_busy_percent`) and NVIDIA (NVML); Intel cards are
left out rather than guessed. pci.ids has comments inside vendor blocks: skip them when scanning.

## DeckOS Bench

`usr/lib/deckos/bench/` has the plain-Python engine, runners, reports and the PySide6 native app.
`deckos-bench` opens the app; `deckos bench` remains the terminal interface. The Hub's System page
has a Benchmarks shortcut. `bench_worker.py` uses JSON-line events so probing and benchmarks run
outside the GUI thread; it creates a process group for cancellation. `bench_data.py` validates
history and filters failed/incompatible results out of trends and comparison verdicts.
`bench_app.py --demo --screenshot DIR` renders all four pages with sample data. The DecKoOS Score (`score.py`, no Qt,
`VERSION`, `tests/test_bench_score.py`) is the Score page, `deckos bench score` and the worker's `score` command
(`runners.score_runners()`: every system test, `PinnedAI` on `score.AI_MODEL`). Never change version 1's references or
weights: bump `VERSION` instead, since history and cross-PC comparisons depend on it. Tests and remaining
hardware validation are documented in `docs/bench.md`; do not present BeamNG, fio or vkmark as
validated on hardware yet. Nothing in Bench should silently change system tuning settings.

## DeckOS Work — active development

Read `docs/work-handoff.md` before continuing. The user redirected the pending 0.5.0 release work
into a dedicated local coworking/coding/image application and is low on usage. Source is in
`usr/lib/deckos/work/`; UI/agent/core/runtime/artifacts are separate modules. Uses existing Ollama
models; documents and images run in an isolated optional uv environment. No paid APIs. Never claim
frontier-model parity, a shell sandbox, or finished hardware validation without evidence.
Work's default model is the Assistant's `MODEL` (`/etc/deckos/ai.conf`, user override) until picked in
Work. Entry points: the Hub's AI & Dev card and Home quick action, the Assistant header's code button,
`deckos work`, the app menu. `work_app.py --demo --screenshot DIR` renders its three pages.
Quality loop (docs/work.md): `work_agent.follow_up` sends the model back for unfinished plan items,
unverified edits and self-review findings; `Tools._write` refuses edits that delete existing tests.
Measured on gpt-oss:20b: without the test guard it deleted a failing test to get a pass.
Ollama drop-in `ollama.service.d/10-deckos.conf` keeps 2 GiB of VRAM free (`LLAMA_ARG_FIT_TARGET`: the
llama.cpp engine ignores `OLLAMA_GPU_OVERHEAD`); a full card made KWin stall. Work unloads 1 min after a task.

## Open work

An NVIDIA and an Intel test install (the chwd
path has only been checked with `bash -n`/shellcheck); the free-space and empty-disk modes through
the whole installer on real hardware (CI installs into all three layouts: partition, empty, free).
