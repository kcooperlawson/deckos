# DeckOS Terminal: design and architecture

DeckOS Terminal (`deckos-terminal`) is DeckOS's own terminal and the default one (`kdeglobals`
TerminalApplication), replacing Konsole. It's a native C++20 / Qt 6 Widgets app like DeckOS Files.
`qtermwidget` (LXQt's terminal widget, Qt 6) does what's hard and already solved: the VT emulation,
text rendering, scrollback, selection, search, input methods. DeckOS Terminal adds the window, tabs,
splits, the DeckOS look, and what only DeckOS can know: which project a tab is in, what it's running,
and what the rest of the system is doing.

## Goals

1. **Fast.** A second window or a new tab costs nothing (one process, like DeckOS Files). Typing
   latency is qtermwidget's; DeckOS adds no work per keystroke.
2. **Knows your work.** A tab shows the project it's in (the git folder's name and branch), not
   `user@host:~/some/long/path`, and the command running in it.
3. **Part of DeckOS.** It reacts to workload modes as they happen (an `org.deckos.Mode` D-Bus signal,
   not polling) and is what "Open terminal here" opens everywhere.
4. **DeckOS look.** Slate surfaces, accent for the active pane, JetBrains Mono, a DeckOS colour scheme.

Non-goals for v1: profiles, a settings window (sensible defaults, a config file later), SSH
bookmarks, the Claude pane and "Snapshot first" (both next, below).

## v1 features

| Area | What it does | Built on |
|---|---|---|
| Tabs | Ctrl+Shift+T new tab in the current folder, Ctrl+Shift+W close, Ctrl+PgUp/PgDn or Ctrl+Tab to switch, Alt+1…9 to jump, middle-click closes, drag to reorder. A tab is named after its project and branch (`deckos ⎇ main`), or its folder, plus the running command (`cargo build`) | `QTabBar` |
| Splits | Ctrl+Shift+D splits right, Ctrl+Shift+E splits down, Alt+arrows move between panes, the active pane has an accent outline; closing the last pane closes the tab | nested `QSplitter` |
| Terminal | Copy/paste Ctrl+Shift+C/V, Ctrl+Shift+F find, Ctrl+= / Ctrl+- / Ctrl+0 zoom, links open with a click, 20,000 lines of scrollback, bell flashes the tab | `QTermWidget` |
| Project awareness | The shell's working folder (`/proc/PID/cwd`), its git root and branch (`.git/HEAD`, read directly: no `git` process), the foreground command (`/proc/PID/comm`). Checked when the shell's title changes and every 2 s for the visible tab only | `/proc`, `QFileInfo` |
| Workload modes | A strip in the window's corner while a game runs ("Playing Cyberpunk 2077 · 9.1 GB freed"), updated the moment the mode changes | `org.deckos.Mode.Changed` on the session bus, `$XDG_RUNTIME_DIR/deckos-mode` |
| Integration | `deckos-terminal --workdir DIR` / `-e CMD` (what `KTerminalLauncherJob`, DeckOS Files' Shift+F4 and Plasma's "Open terminal here" call), one process for every window | `KDBusService` |

## The shared DeckOS bus (first piece)

DeckOS apps learn about each other through the session bus instead of each asking `deckos` on a
timer. v1 has one signal: `deckos mode watch` emits

```
path /org/deckos/Mode   interface org.deckos.Mode   signal Changed(s mode, s game)
```

on every change, and the state itself stays in `$XDG_RUNTIME_DIR/deckos-mode` (key=value), so any app
can read it on start and listen for changes after. A signal needs no service name, so nothing has to
be running for an app to subscribe. Next on the bus: `org.deckos.Snapshots` (taken, restored),
`org.deckos.Updates` (finished), and a small `org.deckos` service that owns them once there's more
than the mode to keep.

## Next

- **Snapshot first:** before `sudo pacman -R…`, `rm -rf` under `$HOME` or `dd`, offer one click to
  take a snapshot, and "Undo" afterwards (shell integration through an OSC 133 prompt marker, so
  the terminal knows where a command starts).
- **Claude pane:** Claude Code in a split that sees the tab's folder; "Explain this error" sends the
  last command's output.
- **Build mode:** the foreground command tells workload modes a build is running in a tab, so it can
  slow it down for a game and speed it up after.
