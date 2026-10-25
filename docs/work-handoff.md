# DecKoOS Work handoff — October 24, 2026

The user wants a dedicated local alternative to Claude/Codex coding and coworking: persistent
project chats, files and code, terminal commands, office documents, and image generation.
It should use the installed Ollama models and require no paid API. Be honest that local models
will not match frontier-model reasoning or every hosted integration. Native PySide6/Hub styling.
The user is low on usage; keep updates brief and leave checkpoints.

## Current work — usable v1 installed

New source: `pkg/deckos-settings/rootfs/usr/lib/deckos/work/`.
Native PySide6 app includes persistent project chats, scoped file tools, diffs/undo,
approved terminal commands, attachments, office documents and an image studio.
Uses local Ollama models and SDXL; no paid API required. Launcher: `deckos-work`.
Production runtime and cached SDXL weights: `~/.local/share/deckos/work/runtime`.
Python 3.12, torch 2.10 ROCm 7.1, diffusers, and document libraries installed.
SDXL uses CPU offloading and sliced attention/VAE to fit the GPU with Ollama unloaded.
The next chat request reloads Ollama automatically.

Validation (at the time): all 43 unit tests pass. Real gpt-oss:20b created code and ran its tests.
DOCX/PDF/PPTX/XLSX creation and extraction passed. Real SDXL 1024px image generation
passed on AMD GPU. Native GUI integration passed model chat, file creation, command
approval, task save, cancellation and command process cleanup. Stop records stopped
status even if the child command exits before the worker handles its signal.
Logs are in the Codex chat workspace `work/`, including work-model-smoke.log,
work-image-smoke-2.log, and work-gui-smoke.log (first two lines are successful rerun;
old failed test process appended some stale errors after those lines).

Targeted system installation completed via outputs/install-deckos-work.sh.
Backup: /var/lib/deckos/repairs/work-5nwclGxc. Installed app modules, launcher,
desktop entry and icon. Source Hub/deckos command integration is ready for packaging
but those existing installed system files were deliberately not replaced.
No release, tag, push or commit done. Previous release remains paused.
Default allows reversible project edits and asks before shell commands; terminal
commands run with user permissions, not an OS sandbox. See docs/work.md for limits.

## Hardware

RX 9070 XT: 16 GiB; 32 GiB RAM. ROCm 7.2.4 installed. System Python 3.14; PySide6 installed.
Ollama at localhost:11434: `gpt-oss:20b` (tools), `gemma4:12b` (vision/tools), `qwen3:0.6b`.
Image/doc Python dependencies were initially absent. uv installed; runtime setup downloads wheels.
Do not require an API key or send project data to a hosted model. External web tools and first-time
model/package downloads naturally need internet. Use clear model-license links in image settings.

## Release status (updated October 24, 2026)

Work shipped: 0.5.0 (Work, Bench disk fix: the sequential refill before every repetition is in
`df8c829`) through 0.5.5 are tagged and published. VERSION is 0.5.5.

Install test: every ISO run from v0.3.15 to v0.5.5 failed install-test the same way (OVMF: no FAT
filesystem on the EFI partition, `grubx64.efi` "Not Found"). The cause was the test harness, not the
installer: `mkfs.fat --offset` on the 40 GB image sized clusters for the whole image (64 sectors),
leaving the 300 MiB partition 9600 clusters, too few for FAT32. Linux mounts that; UEFI firmware
decides the FAT type from the cluster count and can't read it. `tests/install-test.sh` now passes
`-S 512 -s 1`; checked locally in OVMF (old flags: Not Found, new flags: boots). Confirm on CI at the
next ISO build. A full local run of install-test.sh on the CI-built 0.5.5 ISO with the fix passed:
install PASS, first boot reached graphical.target with sddm active.

Publish now also waits for unit-tests. The Assistant's safety rules (`is_read_only`, `BLOCKED`,
shared with deckos-local and Work) have tests in `tests/test_assistant.py`; that closed holes where
`env CMD`, `rg --pre`, `git branch -D`, `find -fprint`, `sort -o`, `journalctl --vacuum-*` ran
unasked and `rm -rf --no-preserve-root /`, `rm -rf ~/*`, `shred /dev/...` weren't refused.

Do not commit the unrelated `assets/quicksettings-preview.png`.
