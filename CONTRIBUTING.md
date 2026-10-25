# Contributing to DeckOS

Thanks for helping. DeckOS is a whole operating system that people install over their own disks and
update automatically, so a few rules keep a contribution from ever breaking someone's PC. They're all here,
and most of them are checked for you.

## How a change reaches people

1. You open a pull request. CI runs every check on it (below). Pull requests can't use the signing key,
   publish packages or build release ISOs: those only run for the maintainer's version tags.
2. The maintainer reviews it (every file has an owner in `.github/CODEOWNERS`) and merges it when the
   checks pass.
3. A release tag puts it on the **testing** channel first, which the maintainer's own PC runs.
4. Only after that does the maintainer promote the release to **stable**, where installs start. Nothing
   reaches stable without having run on testing.

So nothing you push can reach anyone's PC by itself.

## Getting set up

- On DeckOS: clone the repo, change things, and `deckos dev-install` builds and installs your checkout.
  Restart the app you changed. `sudo ./build.sh` builds an ISO; test installs in a VM (QEMU + OVMF),
  never on a disk you care about.
- Elsewhere (Windows, macOS, other Linux): every DeckOS window has a `--demo` mode with made-up data that
  runs anywhere PySide6 does, e.g. `python pkg/deckos-settings/rootfs/usr/lib/deckos/hub/deckos_hub.py --demo`.
  The C++ apps (Files, Terminal, Editor) build on their own GitHub workflow, which uploads screenshots.

## The checks

```bash
bash tests/check.sh
```

runs exactly what CI runs: shell and Python syntax, shellcheck, the data files (release notes, themes),
that no private file is committed, the unit and offscreen UI tests, and that generated files match their
generators (`assets/*.py`: re-run a generator after changing it and commit its output). Run one part with
`bash tests/check.sh lint`, `tests` or `generated`.

New behaviour needs a test (`tests/test_*.py`, using fake folders and stand-in commands, never the real
system) or, for something you see, a `--demo` screenshot in the pull request.

## How DeckOS code reads

`CLAUDE.md` has the full notes; the short version:

- **Match the code around you**: naming, short comments that say why, not what.
- **Bash** starts with `set -Eeuo pipefail` and quotes everything.
- **Windows** are PySide6 and use the shared look (`hub_style.py`, `hub_widgets.py`). Slow work goes on a
  thread. Every window keeps a working `--demo`.
- **Windows never change the system themselves.** They call `deckos …` (through `pkexec` when it needs
  root) or Plasma's own tools.
- **Words people read** are plain and specific, in sentence case: "Windows Fast Startup is probably on",
  not "Volume dirty flag set".
- **Be honest about what's tested.** If something only works on AMD graphics, or hasn't been tried on real
  hardware, say so.

## Parts that need extra care

These can erase a disk, run as root, or reach every DeckOS PC. Changes to them get a careful review,
and the pull request should say how you checked them:

- **The installer** (`installer/`, `pkg/deckos-installer/`). It only ever erases the partition the person
  picked; the EFI partition is shared and never formatted; in free space or on an empty disk it only adds.
  Nothing existing is moved, resized or deleted. `tests/vm/` checks this on real disk images: keep those
  checks passing and add to them.
- **Root**: `sudoers.d`, polkit rules, `pkexec` steps, the `.install` script, `session-switch`.
- **Gaming Mode's session** (`gaming-session`, `session-switch`): test with `tests/test_gaming_session.py`.
- **Packaging, CI and the update repo** (`PKGBUILD`s, `build.sh`, `.github/`).

Never commit anything from `personal/`, any key, or anything that downloads games, BIOS files or other
copyrighted material.

## Reporting problems

Use the issue templates. For security problems (a way around a password prompt, the installer touching the
wrong disk, unsigned packages), please use [SECURITY.md](SECURITY.md) instead.

By contributing you agree your work is released under the [MIT License](LICENSE).
