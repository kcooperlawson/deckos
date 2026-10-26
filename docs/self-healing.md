# Self-healing DecKoOS: the plan and its rules

The goal: problems are found on users' PCs, fixed there in one click, and fixes that work reach everyone. The rule
that makes it safe: **AI thinks, recipes act.** An AI (DecKoOS Assistant, System Doctor's explanations, a
maintainer model) can diagnose, explain, pick a fix and fill in its blanks. It never writes a command that runs.

## The walls (never removed, whatever the model)

1. **Recipes only.** Fixes are vetted recipes in `usr/lib/deckos/heal/heal.py`: fixed commands with a few blanks.
2. **Blanks are checked.** A package must be in the official repositories (never the AUR), a service must be on a
   short list, a number must be in range. Anything else is refused.
3. **Programs and what they may do.** A fix runs one of a few programs, each only for listed purposes (pacman only
   installs from the repos: never `-U` from a file or URL, never `-R`).
4. **A deny list behind that.** No fix may touch sudo, polkit, PAM, SSH, passwords or users, the firewall, the
   bootloader, pacman's keys or mirrors, or fetch anything from the internet; even a bad recipe added by mistake is
   refused (`tests/test_heal.py`).
5. **The person decides.** They see the exact commands and confirm. Fixes needing root take a snapshot first and go
   on the Timeline with Undo.
6. **People approve recipes.** New recipes are reviewed and tested like any code, and signed with the release.

Snapshots undo a broken system, not a compromised one (data can leave, and `/home` isn't rolled back); that's why
the walls stop bad changes before they run rather than relying on Undo afterwards.

## In daily use

- **System Doctor's buttons run recipes** (`sysdoctor.recipe()`): restarting a listed service, not waiting for the
  network, installing a missing package, clearing package downloads, the NVIDIA driver, Intel microcode. Fixes no
  recipe covers yet (Undo's clean-up, keeping a snapshot, restarting an unlisted service) stay as they were.
- **Care offers the fix** in its notification when a check finds something a recipe fixes, if suggestions are on;
  otherwise its button opens System Doctor.
- **"Did that fix it?"**: after a recipe fix (System Doctor, Care or the Assistant), a notification with "Yes, fixed"
  and "Not really" puts the answer in the history (`deckos heal ask`), unless remembering is off.

## Your say

Said up front, in Welcome's privacy step on first login and in DecKoOS Hub > System > Fixes, with a switch for each
part (`~/.config/deckos/heal.conf`, or `deckos heal settings KEY on|off`):

- **Suggest fixes**: the Assistant may offer the reviewed fixes. Off: it isn't given them at all.
- **Remember fixes on this PC**: which fixes ran and whether they worked. Off: nothing is written. "Forget
  everything" (`deckos heal forget`) deletes what's there.
- **Offer to make fix reports**. Off: `deckos heal report` makes none.

Whatever the switches say, nothing runs without a yes, and nothing is ever sent by DecKoOS itself.

## Phases

1. **Done:** the recipe library, `deckos heal`, and the Assistant's `use_fix` tool.
2. **Done: reports, not patches.** Every fix is remembered on the PC (`deckos heal history`; the outcome with
   `deckos heal outcome ID worked|failed`). `deckos heal report` shows the whole report (the problem, the fix, the
   result, scrubbed processor and graphics names); `--open` opens it in the "DecKoOS fix report" form on GitHub
   (`.github/ISSUE_TEMPLATE/heal.yml`, label `heal-report`), where the person submits it themselves. DecKoOS sends
   nothing.
3. **Started: maintainer triage.** `deckos heal triage` (gh, maintainer) groups open reports by problem and fix: how
   many PCs, how often it worked, on which graphics vendors. `deckos heal draft N` asks the local model for a recipe
   for group N; the draft must pass `check_recipe` (listed programs and what each may do, whole-word blanks of known
   kinds, the deny list with sample values) and is saved for a person to review and paste in. Drafts are never added
   by themselves. The tests feed it malicious drafts; the first run of them found `pacman -U URL` getting through,
   which is why each program now has a list of what it may do.
4. **Staged rollout.** New recipes reach the testing channel, then a share of stable PCs, and are pulled back
   automatically if Care sees crashes rise after them.

Bigger models make the thinking better; they don't make acting safe (prompt injection lives in the logs they
read, and "usually right" isn't a security property). Use the best model available for diagnosis and drafting;
keep the walls for anything that changes a PC.
