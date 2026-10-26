# DecKoOS Bench

Bench has a system suite that needs no games, plus a separate game suite. It saves every
repetition and CPU/GPU sensor readings, and writes self-contained HTML reports that work offline.

## The DecKoOS Score

One number for the whole PC, like 3DMark's (`score.py`). Each part scores its key measurements against a fixed
reference PC that scores 5,000 in every part:

| Part | Measurements (weight) | Share of the score |
|---|---|---|
| CPU | 7-Zip all cores (70%), one core (30%) | 25% |
| Graphics | vkmark (100%) | 30% |
| Local AI | writing (70%) and reading (30%) tokens/s on `qwen3:0.6b` | 20% |
| Memory | bandwidth (60%), latency (40%) | 12.5% |
| Storage | sequential read/write, random 4K read/write at QD32, random 4K read at QD1 | 12.5% |

Parts and the total are weighted geometric means: twice as fast is twice the points, and no measurement can hide
behind another. Each measurement is the median of three repetitions; the range shown is the score of the lowest and
highest repetition. A full score needs all five parts: the local AI part only counts with the score's own model
(tokens per second can't be compared across models), so other runs show a *partial* score. The reference values are
fixed estimates for a mid-range 2024 gaming PC, not one measured machine. The formula is versioned (`score.VERSION`):
scores of one version compare across PCs and over time, and a new version is a new scale, never a quiet rescoring.
Saved runs carry their score; older runs are scored when shown.

## Native application

Open **DecKoOS Bench** from the application launcher, `deckos-bench`, `deckos bench app`,
or the **Benchmarks** button on the Hub's System page after installing the updated package.
It shares the Hub's PySide6 widgets, palette, typography and icons.

- **Score:** the DecKoOS Score (below): your latest, the change since the last one, your best, each part's
  score, and every score so far. **Run DecKoOS Score** runs it; so does `deckos bench score`.
- **History:** search saved sessions (with their scores), inspect individual measurements and environment details,
  choose a baseline and export a standalone HTML report.
- **Lab:** system/game presets or individual tests, repetition count, a session name, the A/B experiment,
  availability checks, progress, elapsed time and a stop button.
- **Compare:** choose a baseline and candidate, see changes and confidence-based verdicts,
  inspect recorded environment differences and export the comparison.

The UI stays responsive while a separate worker probes the hardware or runs a benchmark.
Stopping signals the worker's process group, saves completed repetitions when cleanup finishes,
and escalates to a forced stop after five seconds. A forced stop may prevent a report from being
saved. Failed or incomplete runners are excluded from trends and comparison verdicts, while
partial values remain visible in run details. Unreadable history files are skipped with a notice.
The app does not change system tuning settings.

To launch directly from this checkout without installing:

```bash
python3 pkg/deckos-settings/rootfs/usr/lib/deckos/bench/bench_app.py
```

`--demo` uses labeled sample data without starting hardware workers. To render all four screens:

```bash
python3 pkg/deckos-settings/rootfs/usr/lib/deckos/bench/bench_app.py --screenshot /tmp/bench-preview
```

## Terminal commands

```bash
deckos bench list
deckos bench system --repeat 3 --label baseline
deckos bench run cpu-7z,memory --repeat 3 --label after-change
deckos bench compare last-1 last
```

Use `--no-open` on a run or comparison to save the report without opening a browser.
`deckos bench --help` and `deckos bench run --help` show the command options.

The system runners use optional tools: `7zip` for CPU, `gcc` (with OpenMP) for memory,
`fio` for disk, `vkmark` for graphics, and a configured Ollama model for local AI.
Missing tools are reported as skipped; Bench does not install them. Install optional system
tools with `sudo pacman -S --needed 7zip gcc fio vkmark`, then use **Refresh tools** in the app. The memory workload
allocates about 1.5 GiB. The disk test writes a private 2 GiB temporary file in the Bench
cache and removes it afterwards; it requires over 6 GB free. It measures the filesystem
holding that cache, which may be changed with `XDG_CACHE_HOME`.

Results live under `$XDG_DATA_HOME/deckos/bench/runs`, or
`~/.local/share/deckos/bench/runs` by default. Each folder contains `result.json` and
`report.html`. Comparisons accept folder names, paths, `last`, and `last-N`.

For a manual settings comparison, record a baseline, change one setting, then repeat the same
runner selection and repetition count. Close other workloads and keep the power profile and
AI model consistent. Compare the two saved runs; the report lists recorded environment changes.
The engine briefly waits for the CPU to settle between repetitions, with a 45-second limit.

At least three repetitions per side are required for a comparison verdict. Bootstrap intervals
summarize variation in the samples; a range crossing zero does not prove equal performance.
Three repetitions are a starting point, and results can still be affected by background work,
thermal drift, caching, or a change the environment record does not capture.

## Current validation and remaining work

- CPU and memory ran successfully on the reference machine in the initial two-repetition smoke test.
- Automated engine and offscreen UI tests cover cleanup, argument validation, disk-file ownership,
  corrupt history, non-finite measurements, comparison compatibility, unique saves, the BeamNG JSON
  schema, navigation, filtering, baseline selection, demo start/stop, and report exports.
  Run them with `python3 -m unittest discover -s tests -p 'test_bench*.py'`.
- A real memory benchmark was run through the native app's worker, saved and loaded into History;
  stopping another run was verified to save a cancelled session. Smoke-test outputs were isolated
  from the user's benchmark history.
- Disk and graphics need end-to-end testing with fio and vkmark installed.
- BeamNG is experimental. The JSON parser now follows the installed game's actual `bench.physics`
  schema (peak MBeams/s and realtime vehicles), with a fresh explicit output path per repetition.
  The complete Proton invocation still needs a finished hardware run; these scores measure physics,
  not graphical FPS. Game updates may change the schema or output-path behavior.
- Automated settings experiments and a packaged release are still pending. The native UI, launcher,
  Hub shortcut, icon generation and packaging entries are implemented.

To use the checkout before installing it:

```bash
DECKOS_BENCH_DIR="$PWD/pkg/deckos-settings/rootfs/usr/lib/deckos/bench" \
  bash pkg/deckos-settings/rootfs/usr/bin/deckos bench list
```

The `deckos-settings` package copies the Bench Python modules and memory-test source from
`rootfs`; the memory executable is compiled into the user's cache on first use.

The vkmark invocation follows its [upstream command-line options](https://github.com/vkmark/vkmark/blob/master/src/options.cpp).
It may open a rendering window and uses the default Vulkan device.
