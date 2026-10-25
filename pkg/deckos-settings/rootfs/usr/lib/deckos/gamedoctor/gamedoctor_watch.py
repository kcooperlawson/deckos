"""deckos-gamedoctor.service: notices a game that closes right after starting and offers Game Doctor.

Follows Steam's console_log.txt as Steam writes it (tail -F: inotify, no polling). When a game's
"Game process removed" comes within gamedoctor.QUICK seconds of its "added", a notification offers
to look into it; choosing that opens the Game Doctor window. Steam's own tools (Proton, the runtimes,
the redistributables) also show up as "games" there and are left alone.
"""
import re
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gamedoctor as gd  # noqa: E402
import steamfiles as sf  # noqa: E402

TOOLS = re.compile(r"Proton|Steam Linux Runtime|Steamworks|SteamVR|Linux Runtime", re.I)


def offer(appid, seconds):
    g = sf.game(appid)
    if not g or TOOLS.search(g["name"]):
        return
    secs = round(seconds)
    # --wait: blocks until the notification is answered or dismissed; the chosen action is printed
    chosen = subprocess.run(
        ["notify-send", "--app-name=DecKoOS", "--icon=deckos-hub", "--wait", "--action=look=Look into it",
         f"{g['name']} closed {secs} second{'s' if secs != 1 else ''} after starting",
         "Game Doctor can read why and suggest a fix."],
        capture_output=True, text=True).stdout.strip()
    if chosen == "look":
        subprocess.Popen(["deckos-gamedoctor", "--appid", str(appid)], start_new_session=True)


def main():
    log = gd.LOGS / "console_log.txt"
    started = {}
    tail = subprocess.Popen(["tail", "-n", "0", "-F", str(log)], stdout=subprocess.PIPE, text=True,
                            errors="replace")
    for line in tail.stdout:
        m = gd.EVENT.match(line)
        if not m:
            continue
        when, kind, appid = gd.stamp(m.group(1)), m.group(2), m.group(3)
        if kind == "added":
            started.setdefault(appid, when)
        elif appid in started:
            seconds = when - started.pop(appid)
            if seconds < gd.QUICK:
                threading.Thread(target=offer, args=(appid, seconds), daemon=True).start()


if __name__ == "__main__":
    main()
