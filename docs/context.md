# Context: DecKoOS follows what you're doing

DecKoOS works out one thing, all the time, on this PC only: what you're doing right now. Every part that wants to
react reads that instead of guessing on its own. It's never a mode you have to switch.

## Activities

| Activity     | When                                                                    |
|--------------|-------------------------------------------------------------------------|
| `gaming`     | Workload modes found a game (`$XDG_RUNTIME_DIR/deckos-mode`)            |
| `watching`   | A video player is playing (mpv, VLC, a streaming site in a browser)     |
| `away`       | The session has been idle 10 minutes (logind's IdleHint) and no video   |
| `developing` | A build or test run is going, or you're working in an editor (it uses the CPU) |
| `listening`  | Music is playing and nothing above applies                              |
| `desktop`    | Anything else                                                           |

In that order: the first that applies wins. A new activity has to hold for two looks in a row (about 30 s) before it
counts, so a short pause doesn't flip anything; a game or your own choice counts at once.

## How it senses (`usr/lib/deckos/context/context.py`, no Qt)

Every 15 s: process names and CPU time from `/proc` (an editor counts only when it used CPU since the last look, so
one left open in the background doesn't), MPRIS players through `playerctl`, logind's idle hint, the workload mode's
state file. `classify(facts)` is a plain function from those facts to (activity, confidence, why), so tests feed it
made-up facts. The "why" is always shown: you can see what it saw.

## What it changes

Each reaction is a switch in `~/.config/deckos/context.json`, and every change it makes goes on the timeline:

- **Moments**: your Vibe for the activity (Moments' `work` and `watching` join `game` and `music`).
- **Power while building** (on by default): performance while a build runs, put back when it ends.
- **Quiet while developing** (off by default): Do Not Disturb while you develop, put back after.
- **Welcome back** (on by default): after a game, one notification with what happened while you played (updates,
  crashes, a build that finished), from Pulse's timeline.

## You're in charge

Quick Settings shows the activity and why. Pick another to correct it (`deckos context set ACTIVITY [MINUTES]`,
an hour by default); `deckos context auto` hands it back. Gaming is never chosen by hand: workload modes own it.

State: `$XDG_RUNTIME_DIR/deckos-context` (key=value, for `quick-status`), the D-Bus signal
`org.deckos.Context.Changed` on each change. The user unit is `deckos-context.service`. Tests:
`tests/test_context.py`.
