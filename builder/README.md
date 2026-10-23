# DeckOS Builder

A desktop app for building DeckOS and getting it onto a USB stick, in the DeckOS/Steady style. It runs on
Windows and on DeckOS.

- **Build ISO** starts the GitHub build, then shows each step live with an estimate based on GitHub's clock.
- **Builds** lists history with result and duration, plus **Download ISO** and **Log** (failed steps only, for failures).
- **USB** finds your Ventoy drive and copies the newest ISO with a SHA256 check. It can also remove older DeckOS ISOs.
- **Build on this PC** (DeckOS/Arch only) runs `build.sh` locally and streams the output.

Needs the GitHub CLI signed in (`gh auth login`) and a GitHub copy of the repo (your fork works).

- **Windows:** double-click `DeckOS Builder.bat`. The first run sets up its own Python environment in `.venv`.
- **DeckOS:** run `./deckos-builder`, or add it to the app menu with `./deckos-builder --install`.
