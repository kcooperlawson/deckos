# Gaming Mode session lifecycle

Gaming Mode requires both `gamescope-session-git` (the framework) and
`gamescope-session-steam-git` (the Steam client profile and desktop-return hook).
Installing only the framework is insufficient: its `CLIENTCMD` is otherwise empty.
The Steam package is already in the optional gaming AUR list; a failed AUR installation must
not make the Hub or session switch report Gaming Mode as ready.

DeckOS uses the upstream Steam session, with these local integration points:

- `gaming-session --check` validates required commands and the installed Steam profile without
  starting or stopping anything. The root `session-switch` helper checks it before arming
  autologin or closing the desktop. The Hub also checks it before offering the switch dialog.
- `gaming-service` loads DeckOS's system and per-user gaming settings in the systemd service's
  process, rather than in an unrelated SDDM shell. `ADAPTIVE_SYNC=0` is unset, since upstream tests
  for a nonempty value and would otherwise enable VRR.
- The Steam service drop-in conflicts with the previous Plasma workspace, stops the entire
  session control group on exit, and limits shutdown to ten seconds.
- `gaming-cleanup` clears stale display and portal overrides and queues stopping
  `graphical-session.target`. The nonblocking stop is required inside `ExecStopPost` to avoid
  waiting on the service that is currently stopping.
- The SDDM wrapper waits instead of using `exec`, so its exit trap performs cleanup on normal
  exit, startup failure and termination. It refuses to run inside a normal desktop shell.
- If scheduling an SDDM restart fails, `session-switch` removes its one-shot autologin file.

The wrapper keeps the latest attempt in `~/.local/state/deckos/gaming-session.log` and the
previous attempt in `gaming-session.log.previous` (or under `$XDG_STATE_HOME`). Service logs:

```bash
journalctl --user -u gamescope-session-plus@steam.service --no-pager
```

## Validation

```bash
python3 -m unittest discover -s tests -p test_gaming_session.py
```

The tests fake all session commands. They cover missing-component preflight, refusal to run
inside Plasma, configuration overrides and VRR conversion, normal/failure cleanup, nonblocking
stop-post handling, and failure to schedule autologin. They never restart the display manager.

The October 24 repair was prompted by a missing Steam session package, settings absent from the
Gamescope process, and a retained Gamescope SIGABRT report involving libseat/libsystemd. The old
boot's journal was unavailable. The crash report alone does not establish whether the abort was
the initial startup failure or a secondary failure during teardown. A real Gaming Mode login
and return to Plasma must still be tested after applying the repair.

## Recover without rebooting

If a graphical session is stuck, switch to a text console with Ctrl+Alt+F3 and log in as the
same user. The following ends that user's graphical session; save work first when possible:

```bash
systemctl --user stop gamescope-session-plus@steam.service graphical-session.target
systemctl --user unset-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY XDG_DESKTOP_PORTAL_DIR
sudo /usr/lib/deckos/session-switch --clear
sudo systemctl restart sddm
```

Then select Plasma at the login screen. If that still fails, retain the log above before rebooting.

Upstream documents the separate client requirement in its
[session framework README](https://github.com/ChimeraOS/gamescope-session/blob/main/README.md).
