# Self-healing DecKoOS: the plan and its rules

The goal: problems are found on users' PCs, fixed there in one click, and fixes that work reach everyone. The rule
that makes it safe: **AI thinks, recipes act.** An AI (DecKoOS Assistant, System Doctor's explanations, a
maintainer model) can diagnose, explain, pick a fix and fill in its blanks. It never writes a command that runs.

## The walls (never removed, whatever the model)

1. **Recipes only.** Fixes are vetted recipes in `usr/lib/deckos/heal/heal.py`: fixed commands with a few blanks.
2. **Blanks are checked.** A package must be in the official repositories (never the AUR), a service must be on a
   short list, a number must be in range. Anything else is refused.
3. **A deny list behind that.** No fix may touch sudo, polkit, PAM, SSH, passwords or users, the firewall, the
   bootloader, pacman's keys or mirrors, or fetch anything from the internet; even a bad recipe added by mistake is
   refused (`tests/test_heal.py`).
4. **The person decides.** They see the exact commands and confirm. Fixes needing root take a snapshot first and go
   on the Timeline with Undo.
5. **People write recipes.** New recipes are reviewed and tested like any code, and signed with the release.

Snapshots undo a broken system, not a compromised one (data can leave, and `/home` isn't rolled back); that's why
the walls stop bad changes before they run rather than relying on Undo afterwards.

## Phases

1. **Done:** the recipe library, `deckos heal`, and the Assistant's `use_fix` tool.
2. **Done: reports, not patches.** Every fix is remembered on the PC (`deckos heal history`; the outcome with
   `deckos heal outcome ID worked|failed`). `deckos heal report` shows the whole report (the problem, the fix, the
   result, scrubbed processor and graphics names); `--open` opens it in the "DecKoOS fix report" form on GitHub
   (`.github/ISSUE_TEMPLATE/heal.yml`, label `heal-report`), where the person submits it themselves. DecKoOS sends
   nothing.
3. **Started: maintainer triage.** `deckos heal triage` (gh, maintainer) groups open reports by problem and fix: how
   many PCs, how often it worked, on which graphics vendors. Next: a maintainer model drafting candidate recipes from
   a group, for a person to review.
4. **Staged rollout.** New recipes reach the testing channel, then a share of stable PCs, and are pulled back
   automatically if Care sees crashes rise after them.

Bigger models make the thinking better; they don't make acting safe (prompt injection lives in the logs they
read, and "usually right" isn't a security property). Use the best model available for diagnosis and drafting;
keep the walls for anything that changes a PC.
