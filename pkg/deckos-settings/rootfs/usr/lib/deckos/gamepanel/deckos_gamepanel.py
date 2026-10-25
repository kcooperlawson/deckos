"""DecKoOS in Gaming Mode: a full-screen panel, in the Steam library as "DecKoOS", for what DecKoOS does that Steam
doesn't: back to the desktop, workload modes, power, the playing game's profile, Game Doctor, a checkup, and the
timeline. Made for a controller: D-pad or stick to move, A to choose, B to close (keyboard and mouse work too).

Steam doesn't turn the controller into keys for a non-Steam app, so the panel reads it itself (/dev/input, which
the active session may read): a few lines of evdev, no library.

    deckos-gamepanel                     the panel
    deckos-gamepanel --add-to-steam      adds it to Steam's library (gaming-session does, before Steam starts)
    deckos-gamepanel --demo [--screenshot FILE]
"""
import fcntl
import json
import os
import struct
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
sys.path[:0] = [str(LIB / "hub"), str(LIB / "pulse"), str(LIB / "profiles"), str(LIB / "gamedoctor")]

DEMO = "--demo" in sys.argv
STEAM_TAG = "DecKoOS"
EXE = '"/usr/bin/deckos-gamepanel"'


def add_to_steam():
    """Puts "DecKoOS" in every Steam user's library, once. Steam must be closed (it rewrites the file)."""
    import steamfiles
    if steamfiles.steam_running():
        return "Steam is running"
    added = 0
    for user in steamfiles.users():
        entries = steamfiles.read_shortcuts(user)
        if any(e.get("Exe") == EXE for e in entries):
            continue
        entries.append({"appid": steamfiles.shortcut_appid(EXE, "DecKoOS"), "AppName": "DecKoOS", "Exe": EXE,
                        "StartDir": '"/usr/bin/"', "icon": "", "ShortcutPath": "", "LaunchOptions": "", "IsHidden": 0,
                        "AllowDesktopConfig": 1, "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "",
                        "DevkitOverrideAppID": 0, "LastPlayTime": 0, "FlatpakAppID": "", "tags": {"0": STEAM_TAG}})
        steamfiles.write_shortcuts(user, entries)
        added += 1
    return f"added for {added} Steam user(s)" if added else "already there"


if "--add-to-steam" in sys.argv:
    print(add_to_steam())
    sys.exit(0)

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QFont, QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget  # noqa: E402

import hub_style as S  # noqa: E402
from hub_widgets import icon_label  # noqa: E402

# ---- the controller, straight from evdev

EV_KEY, EV_ABS = 0x01, 0x03
BTN_SOUTH, BTN_EAST = 0x130, 0x131
ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y = 0x00, 0x01, 0x10, 0x11
EVENT = struct.Struct("llHHi")  # struct input_event on 64-bit Linux: timeval, type, code, value


def eviocgabs(axis):
    return (2 << 30) | (24 << 16) | (ord("E") << 8) | (0x40 + axis)  # _IOR('E', 0x40 + axis, input_absinfo)


def has_key(bitmap, code):
    """Is `code` set in a /sys .../capabilities/key bitmap (hex words, most significant first)?"""
    words = bitmap.split()
    bits = 64 if any(len(w) > 8 for w in words) else 32
    i = len(words) - 1 - code // bits
    return 0 <= i < len(words) and bool(int(words[i], 16) >> (code % bits) & 1)


def gamepads(proc="/proc/bus/input/devices", sysfs="/sys/class/input"):
    """/dev/input/eventN of the gamepads: a joystick handler *and* an A button (LED controllers and wheels
    show up as joysticks too)."""
    out = []
    try:
        blocks = Path(proc).read_text().split("\n\n")
    except OSError:
        return out
    for b in blocks:
        handlers = next((line for line in b.splitlines() if line.startswith("H: Handlers=")), "")
        if " js" in handlers or "=js" in handlers:
            ev = next((h for h in handlers.split() if h.startswith("event")), None)
            try:
                keys = Path(f"{sysfs}/{ev}/device/capabilities/key").read_text()
            except (OSError, TypeError):
                continue
            if ev and has_key(keys, BTN_SOUTH):
                out.append(f"/dev/input/{ev}")
    return out


class Pad(QObject):
    """Turns gamepad events into the keys the panel already understands."""
    key = Signal(int)

    def start(self):
        for dev in gamepads():
            threading.Thread(target=self.read, args=(dev,), daemon=True).start()

    def read(self, dev):
        try:
            f = open(dev, "rb", buffering=0)
        except OSError:
            return
        centre = {}
        for axis in (ABS_X, ABS_Y):
            try:
                info = struct.unpack("6i", fcntl.ioctl(f, eviocgabs(axis), b"\0" * 24))
                centre[axis] = ((info[1] + info[2]) / 2, (info[2] - info[1]) / 2 * 0.6)  # middle, 60% of the way
            except OSError:
                pass
        held = {}
        while True:
            data = f.read(EVENT.size)
            if len(data) < EVENT.size:
                return
            _, _, kind, code, value = EVENT.unpack(data)
            if kind == EV_KEY and value == 1:
                if code == BTN_SOUTH:
                    self.key.emit(Qt.Key_Return)
                elif code == BTN_EAST:
                    self.key.emit(Qt.Key_Escape)
            elif kind == EV_ABS and code in (ABS_HAT0X, ABS_HAT0Y) and value:
                self.key.emit({(ABS_HAT0X, -1): Qt.Key_Left, (ABS_HAT0X, 1): Qt.Key_Right,
                               (ABS_HAT0Y, -1): Qt.Key_Up, (ABS_HAT0Y, 1): Qt.Key_Down}[(code, max(-1, min(1, value)))])
            elif kind == EV_ABS and code in centre:
                mid, reach = centre[code]
                way = -1 if value < mid - reach else 1 if value > mid + reach else 0
                if way and held.get(code) != way:  # one step per push, like the D-pad
                    self.key.emit({(ABS_X, -1): Qt.Key_Left, (ABS_X, 1): Qt.Key_Right,
                                   (ABS_Y, -1): Qt.Key_Up, (ABS_Y, 1): Qt.Key_Down}[(code, way)])
                held[code] = way


# ---- what the panel shows and does

def run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def mode_state():
    if DEMO:
        return {"auto": "1", "mode": "gaming", "game": "Cyberpunk 2077"}
    return dict(line.split("=", 1) for line in run(["deckos", "mode", "status"]).splitlines() if "=" in line)


def last_game():
    """(id, name) of the game playing now, or the one played last (from the timeline)."""
    if DEMO:
        return "1091500", "Cyberpunk 2077"
    import pulse
    for e in pulse.entries(50, kinds={"game-start"}):
        name = e["title"].removeprefix("Playing ")
        gid = next((k for k, v in __import__("profiles").load().items() if v.get("name") == name), name)
        return gid, name
    return "", ""


POWER = ["performance", "balanced", "power-saver"]


class Tile(QFrame):
    def __init__(self, icon, title, detail, action):
        super().__init__()
        self.action = action
        self.setObjectName("padtile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 22, 26, 22)
        v.setSpacing(10)
        v.addWidget(icon_label(icon, S.P.accent, 40))
        self.title = QLabel(title)
        self.title.setObjectName("padtitle")
        self.detail = QLabel(detail)
        self.detail.setObjectName("paddetail")
        self.detail.setWordWrap(True)
        v.addWidget(self.title)
        v.addWidget(self.detail)
        v.addStretch(1)

    def mousePressEvent(self, _e):
        self.setFocus()
        self.action(self)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.action(self)
        else:
            super().keyPressEvent(e)


class Panel(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("DecKoOS")
        self.setStyleSheet(S.qss() + f"""
            QFrame#padtile {{ background: {S.SURFACE}; border: 2px solid {S.BORDER}; border-radius: 18px; }}
            QFrame#padtile:focus {{ border-color: {S.P.accent}; background: {S.RAISED}; }}
            QLabel#padtitle {{ font-family: "Inter Display", "Inter"; font-size: 20pt; font-weight: 600; }}
            QLabel#paddetail {{ color: {S.SUBTEXT}; font-size: 13pt; }}
            QLabel#padhead {{ font-family: "Inter Display", "Inter"; font-size: 30pt; font-weight: 700; }}
            QLabel#padhint {{ color: {S.MUTED}; font-size: 12pt; }}
            QLabel#padrecent {{ color: {S.SUBTEXT}; font-size: 12pt; }}""")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(56, 40, 56, 32)
        outer.setSpacing(22)
        head = QHBoxLayout()
        head.addWidget(icon_label("gaming", S.P.accent, 44))
        title = QLabel("DecKoOS")
        title.setObjectName("padhead")
        head.addWidget(title, 1)
        hint = QLabel("Ⓐ choose    Ⓑ back to the game")
        hint.setObjectName("padhint")
        head.addWidget(hint)
        outer.addLayout(head)

        grid = QGridLayout()
        grid.setSpacing(18)
        self.status = QLabel("")
        self.status.setObjectName("padhint")
        modes = mode_state()
        gid, game = last_game()
        self.gid, self.game = gid, game
        power = (run(["powerprofilesctl", "get"]).strip() if not DEMO else "balanced") or "balanced"
        profile = __import__("profiles").load().get(gid, {}) if gid and not DEMO else {"power": "performance"}
        self.tiles = [
            Tile("display", "Back to the desktop", "Steam closes; the desktop opens", self.desktop),
            Tile("gauge", "Workload modes", "On: frees the graphics card for games" if modes.get("auto") == "1"
                 else "Off", self.toggle_modes),
            Tile("battery", f"Power: {power.replace('-', ' ')}", "Choose to change", self.cycle_power),
            Tile("sliders", f"{game or 'Game'}: profile",
                 f"Power while it runs: {profile.get('power', 'as usual')}" if game else "Play a game first",
                 self.cycle_profile),
            Tile("check", "Game Doctor", "Why the last game closed, and fixes", lambda _t: self.open(["deckos-gamedoctor"])),
            Tile("shield", "Checkup", "What's wrong with this PC, in plain words", lambda _t: self.open(["deckos-sysdoctor"])),
        ]
        self.power, self.profile = power, profile
        for i, t in enumerate(self.tiles):
            grid.addWidget(t, i // 3, i % 3)
        outer.addLayout(grid, 1)
        recent = QLabel(self.recent_text())
        recent.setObjectName("padrecent")
        recent.setWordWrap(True)
        outer.addWidget(recent)
        outer.addWidget(self.status)
        self.tiles[0].setFocus()
        self.pad = Pad()
        self.pad.key.connect(self.press)
        if not DEMO:
            self.pad.start()

    def recent_text(self):
        if DEMO:
            return "Recently: Playing Cyberpunk 2077 · Elden Ring: Turn off fast sync · Updated to DecKoOS 0.10.0"
        import pulse
        rows = [e["title"] for e in pulse.entries(4) if e["kind"] != "undo"]
        return "Recently: " + " · ".join(rows) if rows else ""

    # ---- input: the controller's keys go where the keyboard's would

    def press(self, key):
        target = QApplication.focusWidget() or self
        QApplication.postEvent(target, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            return
        moves = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -3, Qt.Key_Down: 3}
        if e.key() in moves:
            cur = next((i for i, t in enumerate(self.tiles) if t.hasFocus()), 0)
            self.tiles[max(0, min(len(self.tiles) - 1, cur + moves[e.key()]))].setFocus()
            return
        super().keyPressEvent(e)

    def eventFilter(self, obj, e):  # tiles hand arrows and Escape up to the panel
        if e.type() == QEvent.KeyPress and e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Escape):
            self.keyPressEvent(e)
            return True
        return False

    # ---- the tiles' actions

    def say(self, text):
        self.status.setText(text)

    def open(self, argv):
        if DEMO:
            self.say(f"Demo · would open {argv[0]}")
            return
        subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def desktop(self, _tile):
        self.say("Switching to the desktop…")
        if not DEMO:
            subprocess.Popen(["steamos-session-select", "desktop"], start_new_session=True)

    def toggle_modes(self, tile):
        on = tile.detail.text() == "Off"
        if not DEMO:
            run(["deckos", "mode", "on" if on else "off"])
        tile.detail.setText("On: frees the graphics card for games" if on else "Off")

    def cycle_power(self, tile):
        self.power = POWER[(POWER.index(self.power) + 1) % len(POWER)] if self.power in POWER else "balanced"
        if not DEMO:
            run(["powerprofilesctl", "set", self.power])
        tile.title.setText(f"Power: {self.power.replace('-', ' ')}")

    def cycle_profile(self, tile):
        if not self.game:
            return
        order = ["", *POWER]
        now = self.profile.get("power", "")
        nxt = order[(order.index(now) + 1) % len(order)] if now in order else ""
        self.profile["power"] = nxt
        if not DEMO:
            import profiles
            profiles.set_(self.gid, "power", nxt, self.game)
        tile.detail.setText(f"Power while it runs: {nxt or 'as usual'} (from the next start)")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS")
    app.setDesktopFileName("deckos-gamepanel")
    app.setFont(QFont("Inter", 12))
    p = Panel()
    for t in p.tiles:
        t.installEventFilter(p)
    if "--screenshot" in sys.argv[:-1]:
        p.resize(1280, 800)
        p.show()
        p.tiles[3].setFocus()
        app.processEvents()
        p.grab().save(sys.argv[sys.argv.index("--screenshot") + 1])
        sys.exit(0)
    p.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
