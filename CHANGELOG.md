# DecKoOS changelog

What each release brought, newest first. Feature releases (X.Y.0) have the notes DecKoOS shows in What's New;
patch releases (X.Y.Z) are fixes. Generated from the release notes by `assets/changelog.py`.

## 0.14.0: Fixes you can trust (2026-10-26)

DecKoOS fixes common problems itself, safely and with Undo, and Deck can look things up on the web.

- **Fixes you can trust**: When something breaks, DecKoOS Assistant, System Doctor and Care can pick a fix from DecKoOS's own library of checked fixes: restart a stuck service, reinstall a damaged package, clear a full drive. The AI picks a fix and you see the exact commands; it never writes them. Bigger fixes take a snapshot first, so Undo puts everything back, and afterwards DecKoOS asks "Did that fix it?". It's all yours to switch off in Hub > System.
- **Deck, with the web if you want it**: DecKoOS Assistant is Deck now, with a personality you pick: friendly, calm, direct or gamer. Turn on web search and Deck can look things up and read pages, from public sites only, never your PC or home network, and it shows you the sites it used. Web search is off until you turn it on.
- **Fix reports you choose to send**: If a fix didn't work, DecKoOS can make a report: you see exactly what's in it, with your names and serial numbers taken out, and you send it on GitHub yourself. DecKoOS never sends anything on its own.

Fixes:

- System Doctor's fix buttons run the same checked fixes, so every one can be undone from the timeline.
- Kid mode has its own page in DecKoOS Hub.
- Community (AUR) apps in the Store no longer look like the safe pick.
- DecKoOS Files: tabs sit over your folders, long names break in sensible places, and photos show bigger.

### 0.13.1 (2026-10-25)

Fixes and polish.

## 0.13.0: Make it yours (2026-10-25)

Vibes for your desktop, Kid mode for the family, DecKoOS's own sounds, and every setting in one place.

- **Vibes**: One click for a whole mood: Lo-fi, Neon, Midnight or Cozy. An animated wallpaper with a music visualizer that dances to whatever's playing (it pauses in games), matching colours, and a taskbar that follows along. Add the new desktop widgets too: a big clock, Now Playing, the weather, a focus timer and a note.
- **Kid mode**: Each child gets their own account with big tiles for only the apps you pick, a filtered web, games from your Retro library, and if you like, a time limit and bedtime. Your session stays locked underneath, and your password brings it back. A tap on their picture on the login screen and they're in.
- **Every setting in one place**: Search DecKoOS Hub for anything: "bluetooth", "night light", "vrr". More settings has the rest of Plasma's settings, named for what they do.
- **DecKoOS sounds**: DecKoOS has its own system sounds now: glass tones for everyday things, a metal-plate tap for the big moments. Switch them in Appearance > Sounds.

Fixes:

- Your pinned apps stay when you change the desktop layout.
- Apps' logos follow your accent colour, and Appearance has a Custom colour.
- DecKoOS apps hold together with large text, and Store cards no longer cut words in half.
- The lock screen shows your DecKoOS wallpaper instead of Plasma's.

### 0.12.2 (2026-10-25)

Fixes and polish.

### 0.12.1 (2026-10-25)

Fixes and polish.

## 0.12.0: Ready for more PCs (2026-10-25)

Getting back from a bad update, NVIDIA cards, picking an AI model that fits, and help when something goes wrong.

- **Back from a bad update**: If DecKoOS won't start after an update, pick a snapshot from the boot menu's DecKoOS snapshots. It starts as it was before, and DecKoOS Hub says so on Home: keep it, and that snapshot becomes your system from the next start. The one that didn't start is kept too, in case you want it back.
- **A local AI model that fits your PC**: Choose a model in DecKoOS Hub > AI & Dev. Each one says whether it fits your graphics card, runs slower, or is too big, and the best fit is marked. gpt-oss 20B and Qwen3 Coder 30B passed every everyday task in DecKoOS's own test; setting up local AI now picks the right size by itself.
- **NVIDIA cards, seen properly**: DecKoOS Hub, System Monitor and the AI setup now read NVIDIA cards directly: temperature, power, graphics memory and load, like Radeon cards. System Doctor knows what an NVIDIA PC needs and fixes it in one click. NVIDIA and Intel are still new on DecKoOS: tell us how it goes.
- **A report for whoever helps**: One command makes a single file with your PC's hardware, drivers, screens and recent errors, with your names, serial numbers and addresses taken out. Send it to whoever helps you; DecKoOS never sends it anywhere itself. Search the menu for "report", or run deckos report.

Fixes:

- Windows (NTFS) drives are found again while installing: a change in a disk tool had hidden them.
- When an install stops, the installer says what most likely went wrong and what to do, and saves its log on the USB stick.
- With an NVIDIA card and Secure Boot on, the installer warns before the screen would stay black.
- System Doctor spots an NVIDIA card without its driver, RTX 50 cards on the wrong driver, and old Intel 13th/14th gen microcode.

## 0.10.0: Everything together (2026-10-25)

DecKoOS now knows what happens on your PC, shows it in one place, and lets you take any change back.

- **The timeline, with Undo**: Everything DecKoOS does is in one place: updates and installs, game fixes, theme changes, drives, the games you play. Most of it has an Undo: an update goes back to the snapshot taken just before it, a theme to the one you had. Home shows the last few.
- **Just type what you want**: Search in the DecKoOS Menu now finds DecKoOS itself: type "drives", "fix game", "task manager" or "flicker" and the right thing is at the top, under In DecKoOS. DecKoOS Assistant can do the same things (it asks first), and it can see what changed recently when something stops working.
- **Game profiles**: Give a game its own settings: performance power, Do Not Disturb, and whether your local AI and Docker make room for it. They switch on when the game starts and back when it stops. The profile also shows the game's Game Doctor fixes and launch options, so everything about a game is in one place.
- **DecKoOS in Gaming Mode**: DecKoOS is in your Steam library now. Open it from Gaming Mode for what Steam doesn't do: back to the desktop, workload modes, power, the profile of the game you're playing, Game Doctor and a checkup. It's made for a controller.
- **Care in the background**: When a program crashes, or after an update, DecKoOS checks for you and says so once, calmly: "Restart to finish the update", or why an app closed, with a button that shows what to do. Games stay Game Doctor's.
- **Take your setup with you**: Save your look, panel and pinned apps, DecKoOS settings, game profiles and Game Doctor's fixes to one file, and bring it to a new PC or back after a reinstall. Never passwords, games or system files, and bringing one in can be undone from the timeline.

Fixes:

- Installing DecKoOS on an empty drive no longer fails while writing the boot menu.

### 0.9.3 (2026-10-25)

Fixes and polish.

### 0.9.2 (2026-10-25)

Fixes and polish.

### 0.9.1 (2026-10-25)

Fixes and polish.

## 0.9.0: DecKoOS (2026-10-25)

A new name and logo, eyes on the boot screen, and a taskbar that keeps your apps where you put them.

- **Meet DecKoOS**: DeckOS is now written DecKoOS, and has a new logo: the oO is a controller, a thumbstick and the face buttons. On the boot screen, the login screen and Gaming Mode's startup they glance around and blink. Your apps, settings and the deckos command are unchanged.
- **Pin any app, the easy way**: Click + on the taskbar for a list of everything installed: type to search, click an app to pin it, click again to unpin.

Fixes:

- The taskbar keeps an open app in its pinned spot instead of moving it to the end (the browser, the file manager and apps like Discord).
- Switching desktop layouts keeps your pinned apps.
- Windows you move to another screen, and minimized windows, stay on the taskbar. Right-click the taskbar to show only this screen's windows.

### 0.8.3 (2026-10-25)

Fixes and polish.

### 0.8.2 (2026-10-25)

Fixes and polish.

### 0.8.1 (2026-10-25)

Fixes and polish.

## 0.8.0: Made here (2026-10-25)

DecKoOS's own taskbar, editor, system monitor, icons and pointers, retro games, and a way for anyone to help build DecKoOS.

- **DecKoOS Taskbar**: A taskbar made for DecKoOS: your pinned apps and open windows in the DecKoOS look, with the accent glow under the app you're using and a dot for each one that's open. Click an app with several windows to go through them, middle-click for a new window, drag to reorder, and right-click to pin or close. New desktops get it; to switch yours, pick a desktop layout in DecKoOS Hub.
- **Performance graphs on your desktop**: Live graphs of your processor, graphics card, video memory, memory and network, on a DecKoOS plate on the desktop. Each shows the last minute; hover a graph to see any moment. It reads the same sensors as Plasma's System Monitor, once a second.
- **DecKoOS System Monitor**: What's running and what it uses, one row per app with its processes inside, sorted by processor, memory or disk. End an app that's stuck, or force it to stop. Performance shows the processor (every core), memory, graphics cards, disks and network with a minute of live graphs. Ctrl+Shift+Esc opens it.
- **DecKoOS Editor**: A text editor made for DecKoOS, with colours for over 300 languages. Tabs come back next time, find and replace lights every match, and Ctrl+/ comments lines in any language. It keeps a file's line endings and permissions, and a system file like /etc/fstab saves with your password instead of failing.
- **DecKoOS icons and mouse pointers**: The everyday apps (files, terminal, settings, calculator, screenshots, archives and 70 more) and over 80 kinds of file now have DecKoOS's own icons: plates in each app's colour, and file sheets that say what they are (PY, JSON, PDF, ZIP). New mouse pointers match, sharp at any size, with the thumbstick ring while you wait. Brand apps like Firefox and Steam keep their own logos.
- **DecKoOS Retro**: Your retro games in one place, from the NES to the PlayStation 2. DecKoOS Retro finds the games you have (by file, folder or the disc itself), installs the emulators they need in one click, checks for the BIOS files some consoles need and recognises yours by their contents, and adds everything to Steam, so your games are in Gaming Mode. It doesn't download games or BIOS files: it works with your own.
- **DecKoOS Builder, for everyone**: DecKoOS Builder now comes with DecKoOS. Sign in with your GitHub account to watch DecKoOS being built, build an ISO on your own PC and put it on a USB stick, or send a change: Builder makes your own copy of DecKoOS, checks your change and opens a pull request, which the maintainer reviews before anything goes in.

Fixes:

- DecKoOS Hub names your graphics card again (some cards showed as "Graphics card").

## 0.7.0: Smooth switch (2026-10-25)

One animation from the desktop into Gaming Mode, and a round of fixes for things that quietly didn't work.

- **A smooth switch to Gaming Mode**: Switching to Gaming Mode no longer flashes the closing desktop. The DecKoOS logo fades in and keeps turning while the desktop closes, and Steam opens with the same animation as its startup movie. A startup movie you picked yourself stays.

Fixes:

- Windows (NTFS) drives stay connected after a restart again: Rescan was finding no drives on the newest system tools, so they were never added.
- Picking a theme in DecKoOS Hub or Welcome now changes the colours, accent and wallpaper too, and the wallpaper you pick shows as the one in use.
- Quick Settings: Gaming Mode, display fixes, updates, workload modes and the Hub and Assistant buttons work again.
- DecKoOS Assistant: New chat starts a fresh conversation every time, not just the first.
- DecKoOS Work: delete a task from the list with right-click or the Delete key.
- Fewer CPU spikes: the file indexer skips game libraries, Wine prefixes and build folders, and DecKoOS Hub stops reading sensors while it's minimized.

### 0.6.1 (2026-10-24)

Fixes and polish.

## 0.6.0: Safe to try (2026-10-24)

Move in from Windows, a doctor for the whole PC, undo for updates and big deletes, and room for DecKoOS on any spare disk.

- **Move in from Windows**: Coming from Windows on the same PC? Move In finds it and brings over what's worth having: your folders in the sidebar, your wallpaper, your Firefox profile and Edge bookmarks, your Steam games without downloading them again, and a DecKoOS match for your apps. Windows itself isn't changed.
- **System Doctor**: What's wrong with your PC, in plain words: services that failed, programs that crashed, a slow start-up, a missing program, a full disk. Each comes with the evidence and a fix, and Explain asks your local AI what it means, on your own graphics card.
- **Undo an update**: Something broke after updating? DecKoOS Hub lists your recent updates, each with an Undo button. After a restart the system is back as it was before that update: apps, drivers and the kernel. Your files and settings in your home folder stay as they are, and the system you left is kept until you say it can go.
- **Snapshot first**: Before a big delete, like a whole folder in your home or a git repository, or system files with sudo, the terminal asks whether to take a snapshot first. If it was a mistake, the Undo bar in DecKoOS Terminal puts the files back straight away. Everyday deletes like a build folder don't ask, and it works in any terminal.
- **Install anywhere there's room**: The installer now also offers unallocated space and empty disks, not just a partition you made beforehand. In free space it adds DecKoOS's own partition and erases nothing; an empty disk gets its own boot partition, so it starts without any other disk. Nothing you have is ever moved or resized.

Fixes:

- DecKoOS Terminal: Ctrl+C copies when text is selected (and still stops the program when nothing is), Ctrl+V pastes, and right-click has Copy, Paste, Find and Ask DecKoOS Assistant.
- Hard drives get their power settings again: hdparm, which a CachyOS rule runs for them, was missing.
- A failed update in the Hub, or a failed install in the Store, offers to ask DecKoOS Assistant about it.
- DecKoOS Assistant and DecKoOS Work ask before more commands that change things (env, rg --pre, git branch -D, find -fprint and others ran without asking), and refuse more disasters outright.
- DecKoOS Work only reads the public web, and asks before opening an address it made up itself.
- A fresh install no longer says "deckos: missing required signature" on every pacman command until the first update.
- The installer refuses an EFI partition the PC's firmware can't read, before changing anything.
- deckos dev-install won't replace a newer DecKoOS with an older checkout by accident.

### 0.5.5 (2026-10-24)

Fixes and polish.

### 0.5.4 (2026-10-24)

Fixes and polish.

### 0.5.3 (2026-10-24)

Fixes and polish.

### 0.5.2 (2026-10-24)

Fixes and polish.

### 0.5.1 (2026-10-24)

Fixes and polish.

## 0.5.0: Know your machine (2026-10-24)

Benchmarks you can trust, games that tell you why they won't start, and a local AI workspace.

- **Game Doctor**: When a game closes right after starting, DecKoOS offers to look into it: it reads what the game printed, says in plain words what went wrong, and offers fixes you can undo: another Proton version, the OpenGL path, a fresh Proton prefix, or checking the game files.
- **DecKoOS Bench**: Your CPU, memory, disk, graphics card and local AI, measured the same way every time, with the spread of every result and a history to look back on. Compare two runs and it tells you whether a difference is real or just noise.
- **Experiments**: Does a setting actually help? Bench runs your tests both ways, taking turns (A B B A) so warming up can't favour one side, puts your setting back, and gives a verdict. Start with the power profile, or the local AI model loaded against unloaded.
- **DecKoOS Work (preview)**: A workspace for bigger jobs with the local AI models you already have: saved project chats, code changes you can undo, terminal commands you approve, Word, PDF, PowerPoint and spreadsheet files, and images made on your graphics card. No API key, and your files stay on this PC.

Fixes:

- Gaming Mode checks it's ready before closing the desktop, cleans up after itself, and VRR off now means off.
- A fresh install from the USB installs the TMpikes theme and the AUR apps again.
- DecKoOS Bench: the disk test measures the drive on btrfs, the graphics test runs on Radeon, and AI prompt speed is measured fresh every run.

## 0.4.0: Make it yours (2026-10-24)

Eight themes, a terminal and an assistant of its own, and games that get the whole graphics card.

- **Themes and wallpapers**: Six new themes: Midnight Violet, Ember, Aurora, Crimson, Graphite and Paper (a light one), each with its own colours, folder icons and wallpaper, and 28 new wallpapers to mix and match.
- **Five desktop layouts**: Move the panels around in one click, and back again. Desktop icons and widgets stay where they are.
- **DecKoOS Assistant**: Press Meta+Space anywhere and ask: "install OBS and set it up for streaming", "why is my Wi-Fi slow". It runs on your own graphics card, looks around on its own, and shows you every change before it makes it. Also in DecKoOS Menu, Quick Settings and DecKoOS Terminal (Ctrl+Shift+A).
- **DecKoOS Terminal**: The new default terminal. Tabs are named after the project you're in, with its git branch and what's running; split with Ctrl+Shift+D, and select an error and press Ctrl+Shift+A to ask the assistant about it.
- **Games get the graphics card**: When a game starts, DecKoOS moves the local AI model out of graphics memory, pauses Docker and file indexing, and puts it all back when you quit. Quick Settings shows what it freed.
- **Claude Code saves tokens**: `deckos ai claude-link` lets Claude Code hand long logs and big files to the local model and read back only the lines that matter.

Fixes:

- Switching to Gaming Mode happens within a couple of seconds, and a second click can't cancel it any more.
- DecKoOS Files: drag and drop works again, in and out of the window, and Cut + Paste moves files.
- deckos doctor counts snapshots correctly and warns when there are none.
- A tidier panel: the tray no longer repeats what Quick Settings shows, and DecKoOS Hub has its own icon.
- The TMpikes theme uses the shield crest.

### 0.3.16 (2026-10-24)

Fixes and polish.

### 0.3.15 (2026-10-24)

Fixes and polish.

### 0.3.14 (2026-10-24)

Fixes and polish.

### 0.3.13 (2026-10-24)

Fixes and polish.

### 0.3.12 (2026-10-23)

Fixes and polish.

### 0.3.11 (2026-10-23)

Fixes and polish.

### 0.3.10 (2026-10-23)

Fixes and polish.

### 0.3.9 (2026-10-23)

Fixes and polish.

### 0.3.8 (2026-10-23)

Fixes and polish.

### 0.3.7 (2026-10-23)

Fixes and polish.

### 0.3.6 (2026-10-23)

Fixes and polish.

### 0.3.5 (2026-10-23)

Fixes and polish.

### 0.3.4 (2026-10-23)

Fixes and polish.

### 0.3.3 (2026-10-23)

Fixes and polish.

### 0.3.2 (2026-10-23)

Fixes and polish.

### 0.3.1 (2026-10-23)

Fixes and polish.
