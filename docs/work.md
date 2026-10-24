# DeckOS Work

DeckOS Work is a native local workspace for coding, working with files and documents, and creating
images. It uses Ollama models and local creation tools. There are no hosted-model API keys or
per-request credits. Model quality and hardware limits still matter: it does not reproduce every
Claude/Codex feature or their reasoning quality.

## Start

Open `deckos-work`, or run `deckos work`. While developing from the checkout:

```bash
python3 pkg/deckos-settings/rootfs/usr/lib/deckos/work/work_app.py --workspace /path/to/project
```

1. Choose a project folder and a downloaded model. `gpt-oss:20b` is the tested coding/tool model;
   `gemma4:12b` also accepts images. Both are available through the existing DeckOS Assistant setup.
2. Describe the result you want. The agent reads files, edits them, runs approved commands and
   returns actual artifacts. A task saves automatically and can be reopened from the sidebar.
3. Review edits under **Changes**, outputs under **Outputs**, and tool/terminal details under
   **Activity**. Double-click an output to open it. Use **Undo selected edit** to restore a file;
   undo refuses to overwrite a later edit made outside the task.
4. Attach text/code, office documents, PDFs, or images. Image attachments require a vision model.
   Attached files are sent to the selected Ollama endpoint, which is local by default.

The three modes are starting contexts for the same tools; Work, Code and Create can all use them.
The tool loop has a configurable internal step limit and compacts older context into a local
summary. Original messages remain on disk. Send **Continue** to resume a saved task.

## How it keeps a local model on track

Local models lose the thread on long tasks more often than large hosted ones, so Work makes the
model follow a fixed routine and checks it before accepting an answer:

- **Project map.** `project_map` lists every source file with its classes, functions and line
  numbers, plus the detected test command, so the model doesn't search around blindly.
- **Checklist.** For multi-step work the model writes a checklist (`update_plan`). The list is
  shown under **Plan** and sent with every request, so it survives context compaction. Unfinished
  items send the model back to work (twice at most).
- **Verify before done.** After code changes it must pass a check: `run_checks` runs the project's
  own tests (npm, cargo, go, make, pytest/unittest, or `py_compile` as a last resort). Only a
  passing check-like command counts (`ls` doesn't). Without one it is sent back to verify, or to
  explain why it can't (twice at most).
- **Self-review.** The finished diff goes to a second, tool-free pass that is told to find bugs
  only. Problems it reports go back to the model to fix or rebut, once per request.
- **Tolerant edits.** `edit_file` accepts a block whose indentation drifted, as long as it matches
  exactly one place, and re-indents the replacement.

- **Line edits.** `replace_lines` edits by the line numbers `read_file` shows. Small models find
  this far easier than quoting a block exactly; diff-shaped `edit_file` calls (`-old`/`+new`) are
  accepted too, and repeated misses point the model at `replace_lines`.
- **Malformed tool calls** that Ollama can't parse are sent back to the model to retry instead of
  ending the task.

These prompts appear in the chat as *Quality check* lines. Both checks can be turned off under
Models & tools › Quality. They make tasks slower and catch many mistakes, but not all of them:
review the **Changes** tab before relying on a result.

### Measured (October 2026, RX 9070 XT)

Two graded tasks, checked by a separate script through the program's behaviour, not the model's own
tests. A: fix `median` and add empty-list errors with tests (7 checks). B: fix repeating ids in a
to-do app, add `done ID`, `[x]`/`[ ]` in `list` and `list --pending`, with tests (8 checks).

| Model | A | B | Speed |
|---|---|---|---|
| gpt-oss:20b, before the quality loop | deleted the failing test to pass | — | ~100 tokens/s |
| gpt-oss:20b, before `replace_lines` | 7/7 | 3/8 (26 failed edits, ran out of steps) | ~100 tokens/s |
| gpt-oss:20b, now | 7/7 | 8/8 | ~100 tokens/s |
| qwen3-coder:30b, now | 7/7 (65 s) | 8/8 (203 s) | ~46 tokens/s |

Both are good choices for code. gpt-oss:20b is faster and better for documents and general work;
qwen3-coder:30b plans more and reads less but runs at about half the speed (it doesn't fit fully in
16 GB of VRAM). Two small tasks are evidence the loop works, not a guarantee: review **Changes**.

## Permissions

Reversible file edits inside the chosen project are allowed by default and keep private backups.
Terminal commands ask first. Settings can disable automatic file edits or permit commands without
individual approval. Commands run as the logged-in Linux user and can access other directories;
this is an approval workflow, **not an operating-system sandbox**. Destructive disk/system command
patterns are refused, but those checks do not constitute comprehensive shell isolation.

Stop terminates the worker and its active command processes. Completed edits and conversation
checkpoints survive. A forced stop can interrupt an external program midway; inspect Activity and
the workspace before resuming. Closing the app asks before stopping an active task.

## Local creation runtime

Models & tools has separate setup actions for documents and images. Setup uses `uv` to create an
isolated Python 3.12 environment, leaving system Python packages alone. Documents use python-docx,
python-pptx, openpyxl, ReportLab and pypdf. The structured document tool supports headings/body
sections and tables; custom layouts or more advanced processing can be written as project scripts
and run through the approved terminal tool. Spreadsheet formulas must be explicit formula cells.
Creating a spreadsheet does not run an Excel/LibreOffice recalculation engine.

Images use PyTorch and Diffusers. AMD ROCm, NVIDIA CUDA and CPU runtimes are available in setup;
only the reference AMD system is under active validation. Default image model:
`stabilityai/stable-diffusion-xl-base-1.0`. First generation downloads several GB of weights; later
runs use the cache. See the model's [model card and license](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0).
The Image studio supports text-to-image and editing an input image. Generated PNGs include prompt,
model and seed metadata. Ollama models are unloaded before generating to release VRAM, and reload
when the next chat request needs them. Another simultaneously running AI app can still contend
for GPU memory.

After packages and models are downloaded, chat, file tools, document work and images can work
offline. Web search, URL fetching, package setup and initial model downloads need internet. Public
web search uses DuckDuckGo HTML and may be blocked or unavailable; a known source URL can still
be fetched. There is no browser automation, account integration or cloud-agent fallback in v1.

## Files and development

- Code: `pkg/deckos-settings/rootfs/usr/lib/deckos/work/`.
- Data: `~/.local/share/deckos/work` (respects XDG_DATA_HOME).
- Tasks/backups: `tasks/` and `backups/`; preferences: `preferences.json`.
- Optional runtime: `runtime/venv`, `runtime/python`, model cache: `runtime/models`.
- Overrides for tests: `DECKOS_WORK_HOME`, `DECKOS_WORK_RUNTIME`, `DECKOS_WORK_DIR` (launcher).
- Demo preview: `work_app.py --demo --screenshot DIR`.

Tests:

```bash
python3 -m unittest discover -s tests -p 'test_work*.py'
```

Validation so far: workspace/symlink boundaries, reversible edits, external-change protection,
command refusal/approval, task persistence, and offscreen UI behavior. A real gpt-oss:20b task
created a calculator module and unittest file, ran both tests successfully, and persisted the
conversation. Real DOCX, PDF, PPTX and XLSX files were created and read back through the runtime.
Hardware image validation and the complete installed GUI path are recorded in `work-handoff.md`.

API references: [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling),
[PyTorch setup](https://pytorch.org/get-started/locally/), and
[Diffusers SDXL](https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/stable_diffusion_xl).
