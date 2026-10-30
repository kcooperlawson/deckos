# Using DecKoOS

The DecKoOS apps and tools, one by one.

## DecKoOS Bench

DecKoOS Bench is a native app for running system and game benchmarks, browsing historical
performance charts, and comparing saved sessions. Open `deckos-bench` for the interface or use
`deckos bench` in a terminal. Reports export as self-contained HTML files. See [Bench usage and validation status](bench.md).

## Game Doctor

When a game closes within 45 seconds of starting, a notification offers to look into it. **Game Doctor**
reads what the game printed in Steam's log (its Proton and Wine output), tells you in plain words what
went wrong (the local model explains it, and known problems are matched: anti-cheat, a missing Windows
library, the DirectX-to-Vulkan layer failing, a crash, sync problems, .NET, memory) and offers fixes that
fit, each one click and each undoable:

- run the game with another Proton version (DecKoOS's Proton-CachyOS, or Proton Experimental)
- the OpenGL path (`PROTON_USE_WINED3D=1`) or no fast sync (`PROTON_NO_FSYNC=1 PROTON_NO_NTSYNC=1`)
- a fresh Proton prefix (the old one is kept and can come back)
- Steam checking the game files

Fixes that change Steam's settings close Steam for a moment (it rewrites those files when it exits) and
reopen it. Open it any time from Hub › Games › Game Doctor, or `deckos game doctor [APPID]`. Anti-cheat
that blocks Linux is said plainly: no setting on the PC changes that.

## DecKoOS Work (in development)

A dedicated local workspace for code, files, documents and images, using the models already in
DecKoOS Assistant. Saved project chats, reversible edits, approved terminal commands, office-format
outputs and Stable Diffusion image generation. No hosted-model credits; setup downloads models and
an isolated creation runtime. See [usage, setup and current limits](work.md).

## Health

**Health** (DecKoOS Hub › Health, or `deckos sysdoctor`) is the one place for something wrong. Its checkup says what's wrong with the PC right now,
worst first, in plain words: services that failed, programs that crashed (named by what ran, and a burst of
desktop crashes recognised as one event), graphics card resets, programs a system rule needs but that
aren't installed, a slow start-up, a full disk, a restart an update is waiting for. Each finding shows the
log lines it's based on, offers its fix (asking for your password when it changes the system) or the
DecKoOS app that handles it (Game Doctor, the Hub's display fix), and **Explain** asks the local AI what it
means, on your graphics card, so nothing leaves the PC. Below the checkup: games that closed right after starting
this week (each opens Game Doctor), DecKoOS's fixes and their switches, and **Make a report** for whoever helps.
`deckos doctor` is still the full report.

## Move in from Windows

**Move in from Windows** (DecKoOS Hub › Drives, the Welcome tour, or `deckos movein`) finds the Windows
on this PC and brings over what's worth having, in one go:

- your Windows **folders** (Documents, Pictures, Downloads, OneDrive…) in DecKoOS Files' sidebar, read
  straight from the Windows drive, nothing copied;
- your **wallpaper**; your **Firefox** profile (bookmarks, history, passwords, add-ons) as Firefox's
  profile here; **Edge or Chrome bookmarks** as a file Firefox imports;
- your **Steam games** as libraries in Steam here, so nothing downloads again (and Proton's files go on
  the Linux drive); other launchers' game folders, with how to add them to Heroic or Lutris;
- a DecKoOS match for **your apps**, each with a Get button; fonts you installed;
- and it makes your Windows drives mount at every start, so none of that vanishes after a restart.

Windows itself is never changed; anything changed on the DecKoOS side keeps a `.deckos-bak`. Wi-Fi
passwords can't come over: Windows encrypts them.

## Display blackouts on Radeon cards

Some Radeon cards (confirmed on the RX 9070 XT) save power at idle by switching their VRAM clock with
firmware help (FAMS). With a high-bandwidth monitor (the Samsung Odyssey G7 at 4K 144 Hz is the known
case), especially alongside a second screen, each switch can drop the DisplayPort signal for 1–2 seconds.
DecKoOS has a fix ladder you can climb if it happens to you. The installer starts you at **level 1** if it
finds an RX 9070-series card driving a Samsung Odyssey or more than one monitor, and at level 0 otherwise
(the live USB always runs level 1):

| Level | What it does | Cost |
|---|---|---|
| 0 | stock AMD behaviour | — |
| 1 | `amdgpu.dcdebugmask=0x20000`: no SubVP/FAMS memory-clock switching | small idle power |
| 2 | + VRAM clock pinned to max at boot | ~15–30 W idle |
| 3 | + no multi-monitor clock switching, no PSR / Panel Replay | same |
| 4 | + every GPU clock forced high | most idle power / heat |

```bash
sudo deckos display set 2
```

Or use **DecKoOS Hub › Display**, then reboot. If you're on level 1 and never see blackouts,
`sudo deckos display set 0` gets the idle power back. `deckos display recommend` shows what the installer
would pick for your setup. To find the cause, run `deckos display watch` (also a button in the Hub) and
press Enter each time the screen blinks. It logs VRAM clock changes, kernel display messages and
hotplugs, so the cause shows up right next to your marker.

Still flickering on level 3+? It's probably the monitor or cable:
- In the monitor's menu: update the firmware, turn **Adaptive-Sync/FreeSync off**, turn off automatic
  source switching.
- Use the DisplayPort cable that came with the monitor (or a VESA-certified DP 1.4 one).
- Gaming Mode ships with VRR **off** for the same reason. Turn it on in the Hub once things are stable.

Sources: [Bazzite #4934](https://github.com/ublue-os/bazzite/issues/4934),
[Arch BBS 311159](https://bbs.archlinux.org/viewtopic.php?id=311159),
[`amd_shared.h` DC_DEBUG_MASK](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/include/amd_shared.h).

## DecKoOS Hub

The DecKoOS Hub (in the panel, or `deckos hub`) is where DecKoOS's own settings live:

| Page | What's there |
|---|---|
| **Home** | live GPU, VRAM, CPU and memory graphs; status of updates, snapshots, firewall, display fix, drives and software, each a click away; **Now Playing** with album art, seek and controls for Spotify, Firefox or any media player |
| **Display** | the blackout fix ladder with the level recommended for your setup, your monitors, and the blackout watcher |
| **Gaming** | Gaming Mode, its resolution, refresh rate, VRR and HDR, plus LACT, GOverlay, ProtonUp-Qt and the Steam-on-NTFS fix |
| **Drives** | your Windows drives with how full they are, and help when one is read-only |
| **AI & Dev** | Claude Code, Ollama (start/stop, your models) and which dev tools are installed |
| **System** | updates with a progress bar (AUR apps in the terminal), system and home snapshots, backup to another drive, the firewall, and adding Gaming, Local AI or Development later |
| **Appearance** | global theme (DecKoOS, TMpikes), accent colour, wallpaper, Plasma style, icons, and the DecKoOS look for Spotify |

**Spotify in the DecKoOS look:** install Spotify from the DecKoOS Store, open it once and log in, then
press *Apply DecKoOS look* in **Hub › Appearance** (or run `deckos spotify theme`). It uses
[Spicetify](https://spicetify.app) to restyle the official app with DecKoOS colours, bordered panels and
the gradient play buttons; everything Spotify does keeps working. Spotify updates undo it, so apply it
again after one; `deckos spotify restore` puts the stock look back.

## Quick Settings

The sliders button in the panel opens **DecKoOS Quick Settings**, the everyday controls in one popup:

- **Wi-Fi, Bluetooth, Do not disturb and Night light** tiles (the arrow on a tile opens its settings page)
- **Volume** for your default output, or every output with the arrow; **brightness** for each screen
  that can be dimmed (laptop panels, and monitors that support DDC/CI)
- **Now playing** with controls for Spotify, Firefox or any media player
- **DecKoOS**: Gaming Mode, the [display fix level](#display-blackouts-on-radeon-cards) (pick a new one
  right there; it applies after a restart), the firewall, the power profile and, on laptops, the battery
- **Updates**: how many are waiting, with *Update now* (opens Hub › System and starts the update). The
  panel button shows the count as a badge; the check runs in the background every few hours

It uses Plasma's own services for Wi-Fi, sound and the rest, so it opens instantly and does nothing
while it's closed. On an existing install, add it with right-click on the panel › *Add or Manage Widgets*.

## Workload modes

A PC that games, builds code and runs local AI has them fighting over the same graphics card. When a
game starts (Steam, Lutris, or Gaming Mode), DecKoOS gets out of its way:

- **Ollama's models leave graphics memory**, so the game gets all of it. Ollama loads them again the
  next time something asks for one.
- **Docker containers pause**, and carry on where they were when the game ends. Label a container
  `deckos.keep=true` (a game server, say) to keep it running.
- **File indexing pauses** until the game ends.

A notification says what was freed, and Quick Settings shows it while you play. `deckos mode off` turns
it off (`deckos mode on` brings it back). To keep one part running, set `OLLAMA=keep`,
`DOCKER=leave` or `BALOO=leave` in `~/.config/deckos/modes.conf`.

## DecKoOS Assistant (local AI)

Ask your PC to install or set something up, in plain words. It runs on your own graphics card with
Ollama: no account, nothing leaves the PC.

**Press Meta+Space anywhere** for the chat box. It's also in DecKoOS Menu (type a question, then *Ask
DecKoOS Assistant*), the ✦ button in Quick Settings, DecKoOS Hub › AI & Dev, and DecKoOS Terminal (select
an error, press Ctrl+Shift+A). Esc hides it and the conversation stays; ↻ starts a new one. In a
terminal, `deckos ask "install OBS and set it up for streaming"` does the same, and `deckos ask` on its
own starts a conversation. It looks around by itself (what's installed, your
hardware, logs, `deckos doctor`), installs from the same places as DecKoOS Store (repos first, then
Flathub, then the AUR), and adds DecKoOS's Gaming, Local AI and Development groups. **Every change is
shown to you first** with the exact command (in the chat box, a card with *Do it* / *Not now*), and only runs if you say yes; root still asks for your
password. Wiping disks or home folders is refused outright.

First time (after adding Local AI): `sudo deckos ai setup` downloads the model (gpt-oss:20b, 13 GB:
the one that handled DecKoOS's tools best on a 16 GB card; gemma4:12b is the lighter choice) and keeps
models out of system snapshots. `deckos ai` shows what's running; `deckos ai model gemma4:12b` switches.

**With Claude Code:** `deckos ai claude-link` gives Claude Code a `deckos-local` tool that hands long
logs, build output and big files to the local model and gets back only the lines that matter, so
those cost Claude a few hundred tokens instead of the whole file. While a game runs, the model stays
unloaded and Claude reads things itself.

## DecKoOS Menu

The app launcher at the left of the dock (or press **Meta**) is DecKoOS Menu. Start typing right away:
results cover apps, files, settings, a calculator and commands (Plasma's own search), and when a search
matches apps you don't have yet, they're listed from the DecKoOS Store with a **Get it** button. Arrows
move, Enter opens, Escape clears or closes.

Without a search it shows your pinned apps (right-click any app to pin, unpin or move it), your recent
apps and files, **All apps** by category, and a footer with Gaming Mode, lock, log out, sleep, restart
and shut down. On an older install that still has Plasma's launcher, right-click it › *Show
Alternatives…* › *DecKoOS Menu*.

## DecKoOS Store

The DecKoOS Store (in the app menu, or `deckos-store`) installs apps without the command line, from all
three places DecKoOS gets software:

- **Arch and CachyOS repos**: installed with pacman, updated with the rest of the system. Preferred
  when an app is available from more than one place.
- **Flathub**: apps that aren't in the repos (Spotify, Bottles…), sandboxed, updated by `deckos update`.
- **AUR**: community packages, searched live and built with paru. Labelled, since Arch doesn't check them.

It has editor's picks and categories on the home page, one search across all three sources, app pages
with screenshots and a choice of source, and an Installed list. App details come from the AppStream
catalogs Arch and Flathub publish; repo installs ask for your password, Flathub ones don't.

## DecKoOS Terminal

DecKoOS Terminal (in the dock, or `deckos-terminal`) is the default terminal. Each tab is named after
the project it's in, with its git branch and whatever is running (`deckos ⎇ main · cargo build`), and
while a game runs a chip in the corner says what workload modes freed for it.

| | |
|---|---|
| Ctrl+Shift+T / Ctrl+Shift+W | new tab in the same folder / close the pane (the tab, when it's the last one) |
| Ctrl+Shift+D / Ctrl+Shift+E | split right / split down; Alt+arrows move between the panes |
| Ctrl+PgUp/PgDn, Alt+1…9 | switch tabs |
| Ctrl+C / Ctrl+V | copy (when text is selected; otherwise Ctrl+C stops the program, as always) / paste |
| Ctrl+Shift+C / V / F | copy / paste / find; right-click has them too, plus Open link and Ask DecKoOS Assistant |
| Ctrl+Shift+A | ask DecKoOS Assistant about the selected text (an error, a command) |
| Ctrl+= / Ctrl+- / Ctrl+0 | bigger / smaller / normal text |

**Snapshot first:** before a big delete (`rm -rf ~/Documents`, a whole git repository, `sudo rm -r` of
system files), the shell asks whether to take a snapshot first, in any terminal. Afterwards it says how
to undo it: `deckos restore N` puts the files back straight away; a system delete goes back with
`sudo deckos undo N` and a restart. In DecKoOS Terminal an Undo bar under the pane does either for you. `rm -rf build/` and other everyday deletes don't ask.
`deckos snapshot-first off` turns it off.

Konsole stays installed for anyone who prefers it (System Settings › Default Applications › Terminal).

## Using it

| | |
|---|---|
| `deckos` / **DecKoOS Hub** | everything below in one place |
| `deckos software add gaming` | add a software group you skipped at install (`gaming`, `ai` or `dev`) |
| **Gaming Mode** | panel launcher, or pick *DecKoOS Gaming Mode* on the login screen. Back: Steam › Power › *Switch to Desktop* |
| `deckos steam-ntfs` | run once after adding a Steam library that lives on a Windows drive. Games stay on NTFS, Proton prefixes move to Linux |
| `deckos drives` | `list`, `rescan` (new drives), `doctor` (read-only/Fast Startup problems) |
| `deckos update` | full update; snap-pac snapshots before and after |
| `deckos updates` | how many updates are waiting (cached; `--max-age 0` checks now) |
| broken update? | reboot › *DecKoOS snapshots* › pick the one before the update |
| deleted a file? | `/home` has hourly snapshots: copy it back from `/home/.snapshots/<number>/snapshot/` (Hub › System › Browse snapshots). Older installs: `sudo deckos home enable` |
| `deckos backup /mnt/BIG` | copy your home folder (minus caches, Steam games, ISOs) to another drive; remembered for next time |
| `deckos doctor` | health check: kernel, display fix, drives, snapshots, AI |
| `claude` | Claude Code, installed for your user (`~/.local/bin`) |
| `ollama run qwen3` | local models on your graphics card (ROCm on Radeon, CUDA on NVIDIA) |

**Gaming Mode resolution:** it defaults to 3840×2160 at up to 144 Hz. For a different screen, pick yours in
**DecKoOS Hub › Gaming** (it's saved in `~/.config/deckos/gaming.conf`; system defaults are in
`/etc/deckos/gaming.conf`).
