# DeckOS Work handoff — October 24, 2026

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

Validation: all 43 unit tests pass. Real gpt-oss:20b created code and ran its tests.
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

## Prior release work — paused for Work app

Claude's latest commit `af9b81e` contains Bench, experiments, Game Doctor, installer fix and 0.5.0
release notes. VERSION is still 0.4.0; v0.5.0 is not tagged. User asked us to pick up Claude's work,
then redirected to this app. Hold the release until validation is resolved.

30 existing tests pass. Real vkmark rerun and AI rerun passed. BeamNG JSON path fix worked
(533.36 MBeams/s, 40 realtime vehicles, the sweep's ceiling). Disk repeats had inconsistent read
layout after random writes. Modified Disk to refill sequentially before EVERY repetition and
check chattr errors; adjusted test. New real run `20261024-152752-Sequential-refill-validation`:
seq read 2539/2583/3034 MB/s; seq write 2380/2382/2373 MB/s; random rates stable. Those two source
changes are still uncommitted. Do not rerun long workloads without a concrete reason.

0.4.0 GitHub run 40121079581 passed package/publish/ISO but FAILED install-test: OVMF couldn't load
EFI/DeckOS/grubx64.efi, no FAT filesystem mapping visible on next boot. Live installer said GRUB
succeeded, then reported lazy unmount. Logs downloaded under Codex `work/release-review/install-logs`.
A minimal OVMF FAT probe ran in shell 85952; its serial log was empty (not diagnostic).
The package-repository installer fix in af9b81e is separate from this EFI boot failure.
Do not claim ISO validation or publish a tested release until this is understood.

Do not commit the unrelated `assets/quicksettings-preview.png`.
