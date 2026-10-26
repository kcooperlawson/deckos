"""DecKoOS Hub pages. Each page builds once; `refresh()` runs when it's shown, `tick(stats)` every
two seconds while it's on screen."""
import re
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSlider,
                               QVBoxLayout, QWidget)

import hub_style as S
import hub_system as sysinfo
from hub_widgets import (Card, Empty, Meter, NowPlaying, RowItem, StatTile, StatusTile, button, icon_label, label,
                         restyle,
                         row)

DECKOS = sysinfo.DECKOS


class Page(QWidget):
    """Title, subtitle and header actions above a scrolling column of cards."""

    title, subtitle = "", ""

    def __init__(self, hub):
        super().__init__()
        self.hub = hub
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        inner = QWidget()
        scroll.setWidget(inner)
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(30, 26, 30, 26)
        self.lay.setSpacing(14)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = label(self.title, "title")
        titles.addWidget(self.title_label)
        self.subtitle_label = label(self.subtitle, "sub")
        titles.addWidget(self.subtitle_label)
        head.addLayout(titles, 1)
        self.head_actions = QHBoxLayout()
        self.head_actions.setSpacing(6)
        head.addLayout(self.head_actions)
        self.lay.addLayout(head)
        self.lay.addSpacing(4)
        self.build()
        self.lay.addStretch(1)

    def build(self):
        pass

    def refresh(self):
        pass

    def tick(self, stats):
        pass

    @staticmethod
    def clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                Page.clear(item.layout())


# ------------------------------------------------------------------ home

class HomePage(Page):
    title = "Home"

    def build(self):
        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        self.title_label.setText(f"Good {part}")
        self.subtitle_label.setText(f"{self.hub.gpu.name}  ·  {sysinfo.cpu_name()}  ·  {sysinfo.deckos_version()}")
        self.head_actions.addWidget(button("What's new", slot=lambda: QProcess.startDetached("deckos-whatsnew", []),
                                           icon="star", tip="What the latest DecKoOS release brought"))
        self.head_actions.addWidget(button("Gaming Mode", "primary", self.hub.to_gaming, icon="play"))

        snap = sysinfo.booted_snapshot()
        if snap:
            # Started from GRUB's snapshots menu, usually because an update broke start-up: say so, offer to keep it
            card = Card("Running a snapshot", f"DecKoOS started from snapshot {snap}", "snapshot")
            card.body.addWidget(label("Changes you make now are lost at the next restart. If this works and the normal "
                                      "start-up didn't, keep it: DecKoOS makes this snapshot the system from the next "
                                      "start, and keeps the one that didn't start in case you want it back.", "muted"))
            card.body.addWidget(row(button("Keep this system", "primary", lambda: self.hub.privileged(
                ["undo", "keep"], lambda ok: self.hub.toast("Kept. Restart to start this system for good." if ok else
                                                           "Couldn't keep this snapshot.", "ok" if ok else "error")),
                icon="snapshot"), button("Restart normally", slot=lambda: QProcess.startDetached("systemctl", ["reboot"]),
                                         icon="power")))
            self.lay.addWidget(card)

        stats = QGridLayout()
        stats.setSpacing(10)
        self.tiles = {}
        for i, (key, ic, name) in enumerate((("gpu_temp", "temp", "GPU"), ("gpu_power", "power", "GPU power"),
                                             ("vram", "gpu", "VRAM clock"), ("cpu_temp", "cpu", "CPU"),
                                             ("ram", "memory", "Memory"))):
            self.tiles[key] = StatTile(ic, name)
            stats.addWidget(self.tiles[key], 0, i)
            stats.setColumnStretch(i, 1)
        self.lay.addLayout(stats)

        self.lay.addWidget(label("STATUS", "kicker"))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.status = {}
        for i, (key, ic, title, page) in enumerate((
                ("updates", "update", "Updates", "system"), ("snapshots", "snapshot", "Snapshots", "system"),
                ("firewall", "shield", "Firewall", "system"), ("display", "display", "Display fix", "display"),
                ("drives", "drives", "Drives", "drives"), ("software", "package", "Software", "system"))):
            t = StatusTile(ic, title)
            t.clicked.connect(lambda p=page: self.hub.navigate(p))
            grid.addWidget(t, i // 3, i % 3)
            self.status[key] = t
        for c in range(3):
            grid.setColumnStretch(c, 1)
        self.lay.addLayout(grid)

        self.now = NowPlaying()
        self.now.control.connect(self.player_control)
        self.now.seek.connect(self.player_seek)
        self.lay.addWidget(self.now)
        self.np_busy, self.np_track, self.np_pos, self.np_last, self.np_status, self.np_key = \
            False, None, 0.0, 0.0, "", None

        quick = Card("Quick actions", None, None)
        quick.body.addWidget(row(button("Get apps", slot=lambda: QProcess.startDetached("deckos-store", []),
                                        icon="store"),
                                 button("Update now", slot=lambda: self.hub.navigate("system", "update"), icon="update"),
                                 button("Terminal", slot=lambda: QProcess.startDetached("deckos-terminal", []), icon="terminal"),
                                 button("Health check", slot=lambda: QProcess.startDetached("deckos-sysdoctor", []),
                                        icon="check", tip="System Doctor: what's wrong, in plain words, with fixes"),
                                 button("Files", slot=lambda: QProcess.startDetached("deckos-files", []), icon="folder"),
                                 button("Work", slot=lambda: QProcess.startDetached("deckos-work", []), icon="code",
                                        tip="DecKoOS Work: code, documents and images with your local AI"),
                                 button("Welcome tour", slot=lambda: QProcess.startDetached("deckos-welcome", []),
                                        icon="star", tip="DecKoOS Welcome: the first-login setup, again")))
        self.lay.addWidget(quick)
        from hub_timeline import RecentCard  # here: hub_timeline builds on this module's Page
        self.recent = RecentCard(self.hub)
        self.lay.addWidget(self.recent)

    def tick(self, stats):
        for key, tile in self.tiles.items():
            tile.set(*stats.get(key, ("—", None)))
        if self.isVisible():
            self.poll_player()

    # ---- now playing

    def poll_player(self):
        if self.np_busy:
            return
        if not sysinfo.have("playerctl"):
            return
        self.np_busy = True
        sysinfo.Job(self, ["playerctl", "-a", "metadata", "--format", sysinfo.PLAYERCTL_FORMAT], self.show_player,
                    demo=sysinfo.demo_playing())

    def show_player(self, out, code):
        self.np_busy = False
        rows = sysinfo.parse_players(out) if code == 0 else []
        if not rows:
            self.np_track = None
            self.now.show_nothing()
            return
        t = rows[0]
        t["label"] = sysinfo.player_label(t["player"])
        key, now = (t["player"], t["title"], t["artist"]), time.monotonic()
        # Some players (Spotify among them) report position 0; then keep our own clock.
        if t["position"] > 0 or key != self.np_key:
            pos = t["position"]
        else:
            pos = self.np_pos + (now - self.np_last if t["status"] == self.np_status == "Playing" else 0)
        self.np_pos = min(pos, t["length"]) if t["length"] else pos
        self.np_last, self.np_status, self.np_key, self.np_track = now, t["status"], key, t
        self.now.show_track(t, self.np_pos)

    def player_control(self, action):
        if self.np_track and not sysinfo.DEMO:
            QProcess.startDetached("playerctl", ["-p", self.np_track["player"], action])
        QTimer.singleShot(350, self.poll_player)

    def player_seek(self, frac):
        t = self.np_track
        if not t or not t["length"]:
            return
        self.np_pos = frac * t["length"]
        if not sysinfo.DEMO:
            QProcess.startDetached("playerctl", ["-p", t["player"], "position", f"{self.np_pos:.1f}"])
        self.now.show_track(t, self.np_pos)

    def show_snapshots(self, system):
        tile = self.status["snapshots"]
        if system is None:
            tile.set("Unavailable", "Couldn't read snapper", "info")
            return
        if not sysinfo.home_snapshots_on():
            tile.set(f"{len(system)} system", "Your files have no snapshots", "warn")
            return
        self.hub.data.snapshots(lambda home: tile.set(
            f"{len(system)} system · {len(home or [])} home",
            f"Newest: {home[0][1]}" if home else (f"Last: {system[0][1]}" if system else ""), "ok"), config="home")

    def refresh(self):
        lvl = sysinfo.display_level()
        self.status["display"].set(f"Level {lvl}", sysinfo.LEVELS[lvl][0], "ok" if lvl else "info")
        ds = sysinfo.drives()
        ro = [d for d in ds if d[3]]
        if ro:
            self.status["drives"].set(f"{len(ro)} read-only", "Windows Fast Startup is probably on", "warn")
        else:
            self.status["drives"].set(f"{len(ds)} mounted" if ds else "None", "All read/write" if ds else
                                      "No Windows drives found", "ok" if ds else "off")
        have = [g for g in sysinfo.GROUPS if sysinfo.installed(g[4])]
        self.status["software"].set(f"{len(have)} of {len(sysinfo.GROUPS)} groups",
                                    ", ".join(g[1] for g in have) or "Desktop only", "ok" if have else "info")
        self.hub.data.updates(lambda n, aur, err: self.status["updates"].set(
            "Couldn't check" if err else "Up to date" if n + aur == 0 else f"{n + aur} waiting",
            err or (f"{aur} from the AUR" if aur else "Arch + CachyOS"), "warn" if err or n + aur else "ok"))
        self.hub.data.snapshots(self.show_snapshots)
        self.hub.data.firewall(lambda on, svcs: self.status["firewall"].set(
            "On" if on else "Off", ("Open: " + ", ".join(svcs)) if on and svcs else
            ("Blocking incoming connections" if on else "Incoming connections allowed"), "ok" if on else "bad"))


# ------------------------------------------------------------------ display

class DisplayPage(Page):
    title = "Display"
    subtitle = "Fixes for monitors that blink black for a second or two on Radeon cards."

    def build(self):
        if not self.hub.gpu.amd:
            # The levels are amdgpu flags and clocks: nothing to pick on other cards.
            card = Card("Blackout fix", "For AMD Radeon cards", "display")
            card.body.addWidget(label(f"This fix is for AMD Radeon cards. Your {self.hub.gpu.name} doesn't need it.",
                                      "sub"))
            self.lay.addWidget(card)
            self.build_graphics()
            return
        self.recommended, self.why = sysinfo.display_recommend()
        card = Card("Blackout fix", "Pick a level", "display")
        card.body.addWidget(label("Each level removes another source of the memory-clock switches that can drop "
                                  "the DisplayPort signal. Start low; step up only if a screen still blinks. "
                                  "Changes need your password and a reboot.", "sub"))
        self.group = QButtonGroup(self)
        self.level_tiles = []
        for i, (name, desc, cost) in enumerate(sysinfo.LEVELS):
            t = QFrame()
            t.setObjectName("tile")
            t.setAttribute(Qt.WA_StyledBackground, True)
            t.setCursor(Qt.PointingHandCursor)
            h = QHBoxLayout(t)
            h.setContentsMargins(14, 10, 14, 10)
            h.setSpacing(12)
            num = QLabel(str(i))
            num.setFixedSize(30, 30)
            num.setAlignment(Qt.AlignCenter)
            num.setObjectName("cardTitle")
            num.setStyleSheet(f"background: {S.BORDER}; border-radius: 15px;")
            h.addWidget(num)
            v = QVBoxLayout()
            v.setSpacing(0)
            top = f"<b>{name}</b>"
            if i == self.recommended:
                top += f" &nbsp;<span style='color:{S.P.accent}'>recommended for your setup</span>"
            v.addWidget(label(top))
            v.addWidget(label(f"{desc} <span style='color:{S.MUTED}'>Cost: {cost}.</span>", "sub"))
            h.addLayout(v, 1)
            rb = QPushButton()
            rb.setCheckable(True)
            rb.hide()
            self.group.addButton(rb, i)
            t.mousePressEvent = lambda _e, b=rb: b.setChecked(True)
            card.body.addWidget(t)
            self.level_tiles.append((t, num))
        self.group.idToggled.connect(self.picked)
        self.apply_btn = button("Apply level", "primary", self.apply, icon="check")
        self.note = label("", "muted", wrap=False)
        card.body.addWidget(row(self.apply_btn, self.note, spacing=12))
        self.lay.addWidget(card)
        self.build_graphics()

    def build_graphics(self):
        gpu = Card("Graphics", self.hub.gpu.name, "gpu")
        self.gpu_live = label("", "mono")
        gpu.body.addWidget(self.gpu_live)
        self.monitor_box = QVBoxLayout()
        self.monitor_box.setSpacing(6)
        gpu.body.addLayout(self.monitor_box)
        buttons = [button("Display status", slot=lambda: self.hub.terminal("deckos display status"), icon="info")]
        if self.hub.gpu.amd:  # it follows amdgpu's memory clock
            buttons.insert(0, button("Watch for blackouts", slot=lambda: self.hub.terminal("deckos display watch"),
                                     icon="eye", tip="Logs clock and display events; press Enter when it blinks"))
        gpu.body.addWidget(row(*buttons))
        self.lay.addWidget(gpu)

    def picked(self, i, on):
        t, num = self.level_tiles[i]
        t.setProperty("picked", on)
        restyle(t)
        num.setStyleSheet(f"background: {S.P.accent if on else S.BORDER}; border-radius: 15px; color: white;")
        cur = sysinfo.display_level()
        sel = self.group.checkedId()
        self.apply_btn.setEnabled(sel != cur)
        self.note.setText("This is the current level." if sel == cur else f"Currently level {cur}.")

    def apply(self):
        n = self.group.checkedId()
        self.hub.privileged(["display", "set", str(n)],
                            lambda ok: self.hub.toast(f"Display fix level {n} saved. Reboot to use it.", "ok")
                            if ok else self.hub.toast("Display fix not changed.", "warn"))

    def refresh(self):
        if hasattr(self, "group"):
            self.group.button(sysinfo.display_level()).setChecked(True)
            self.picked(self.group.checkedId(), True)
        self.clear(self.monitor_box)
        for conn, name in sysinfo.monitors() or [("", "No monitors detected on this card")]:
            self.monitor_box.addWidget(RowItem("display", name or "Unknown monitor", conn))

    def tick(self, stats):
        mode = self.hub.stats.vram_mode() or ("auto" if sysinfo.DEMO else "")
        self.gpu_live.setText(f"VRAM {stats['vram'][0]}   ·   {stats['gpu_temp'][0]}   ·   "
                              f"{stats['gpu_power'][0]}" + (f"   ·   power mode {mode}" if mode else ""))


# ------------------------------------------------------------------ gaming

class TryDialog(QDialog):
    """"Keep this?" with a 15-second countdown; anything but Keep (closing, waiting it out) reverts."""

    def __init__(self, parent, what, screen):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle(f"Try {what}")
        self.left = 15
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(10)
        v.addWidget(label(f"{what} is on for {screen}", "cardTitle"))
        v.addWidget(label("Watch the screen for a few seconds: flicker, blinking or black frames mean it's not for "
                          "this monitor.", "sub"))
        self.count = label("", "muted")
        v.addWidget(self.count)
        keep = button(f"Keep {what}", "primary", self.accept, icon="check")
        v.addWidget(row(keep, button("Turn it off", slot=self.reject, icon="undo")))
        self.timer = QTimer(self, interval=1000, timeout=self.tick)
        self.timer.start()
        self.tick()

    def tick(self):
        if self.left <= 0:
            self.reject()
            return
        self.count.setText(f"Turning it off in {self.left} s unless you keep it.")
        self.left -= 1


RESOLUTIONS = ["3840x2160", "3440x1440", "2560x1440", "2560x1080", "1920x1080"]
RATES = ["60", "100", "120", "144", "165", "240"]


class GamingPage(Page):
    title = "Gaming"
    subtitle = "Steam Gaming Mode: Big Picture full screen, like a Steam Deck."

    def build(self):
        self.head_actions.addWidget(button("Retro games", slot=lambda: QProcess.startDetached("deckos-retro", []),
                                           icon="gaming", tip="DecKoOS Retro: your retro games, set up and in Steam"))
        if not all(sysinfo.installed(cmd) for cmd in ("gamescope-session-plus", "steam", "gamescope", "steamos-session-select")):
            self.lay.addWidget(Empty("gaming", "Gaming isn't installed",
                                     "Add Steam, Gaming Mode, Proton, Lutris, Heroic, MangoHud and the rest.",
                                     button("Add Gaming", "primary", lambda: self.hub.add_group("gaming"), icon="plus")))
            return
        hero = Card("Gaming Mode", "Switch to Steam Big Picture", "play")
        hero.body.addWidget(label("Open apps close when you switch. Come back from Steam's Power menu › Switch to "
                                  "Desktop.", "sub"))
        hero.body.addWidget(row(button("Switch to Gaming Mode", "primary", self.hub.to_gaming, icon="play")))
        self.lay.addWidget(hero)

        conf = {**sysinfo.conf("/etc/deckos/gaming.conf"), **sysinfo.conf(Path.home() / ".config/deckos/gaming.conf")}
        settings = Card("Settings", "Gaming Mode screen", "display")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.res = QComboBox()
        cur = f"{conf.get('SCREEN_WIDTH', '3840')}x{conf.get('SCREEN_HEIGHT', '2160')}"
        self.res.addItems(RESOLUTIONS if cur in RESOLUTIONS else [cur, *RESOLUTIONS])
        self.res.setCurrentText(cur)
        self.res.currentTextChanged.connect(self.save_screen)
        self.rate = QComboBox()
        self.rate.addItems(RATES)
        self.rate.setCurrentText((conf.get("CUSTOM_REFRESH_RATES") or "144").split(",")[-1])
        self.rate.currentTextChanged.connect(self.save_screen)
        grid.addWidget(label("Resolution", "sub", wrap=False), 0, 0)
        grid.addWidget(self.res, 0, 1)
        grid.addWidget(label("Refresh rate", "sub", wrap=False), 1, 0)
        grid.addWidget(self.rate, 1, 1)
        grid.setColumnStretch(2, 1)
        settings.body.addLayout(grid)
        self.vrr = QCheckBox("Variable refresh rate (FreeSync, G-Sync)")
        self.vrr.setChecked(conf.get("ADAPTIVE_SYNC") == "1")
        self.vrr.toggled.connect(lambda on: self.save("ADAPTIVE_SYNC", "1" if on else "0"))
        self.hdr = QCheckBox("HDR (turn it on in the monitor's menu too)")
        self.hdr.setChecked(conf.get("ENABLE_GAMESCOPE_HDR") == "1")
        self.hdr.toggled.connect(lambda on: self.save("ENABLE_GAMESCOPE_HDR", "1" if on else "0"))
        settings.body.addWidget(row(self.vrr, button("Try it first", slot=lambda: self.try_display("vrr"),
                                                     tip="Turns VRR on for the desktop for 15 seconds")))
        settings.body.addWidget(row(self.hdr, button("Try it first", slot=lambda: self.try_display("hdr"),
                                                     tip="Turns HDR on for the desktop for 15 seconds")))
        settings.body.addWidget(label("Some monitors (the Samsung Odyssey G7 among them) flicker with VRR. Try it "
                                      "first switches it on for the desktop and back off by itself unless you keep "
                                      "it.", "muted"))
        self.lay.addWidget(settings)

        self.build_performance()
        self.build_gpu()
        self.build_controllers()
        self.build_extras()

        tools = Card("Tools", "Game helpers", "gaming")
        for title, detail, ic, cmd, launch in (
                ("Steam libraries on Windows drives", "Moves Proton prefixes off NTFS so Windows games run",
                 "drives", None, lambda: self.hub.terminal("deckos steam-ntfs")),
                ("LACT", "GPU clocks, fans and power limits", "gpu", "lact",
                 lambda: QProcess.startDetached("lact", ["gui"])),
                ("GOverlay", "Set up the MangoHud performance overlay", "eye", "goverlay",
                 lambda: QProcess.startDetached("goverlay", [])),
                ("ProtonUp-Qt", "Install Proton-GE and other compatibility tools", "download", "protonup-qt",
                 lambda: QProcess.startDetached("protonup-qt", []))):
            b = button("Open", slot=launch)
            b.setEnabled(cmd is None or sysinfo.installed(cmd))
            tools.body.addWidget(RowItem(ic, title, detail, right=[b]))
        self.lay.addWidget(tools)

    # ---- performance: CPU scheduler, FSR 4, shader cache, NTSYNC

    SCHEDULERS = [("Gaming (lavd)", "lavd", "Gaming"), ("Power saving (lavd)", "lavd", "PowerSave"),
                  ("Low latency (bpfland)", "bpfland", "Auto"), ("Off: the kernel's own", "off", "Auto")]

    def build_performance(self):
        perf = Card("Performance", "Smoother games", "cpu")
        self.sched = QComboBox()
        self.sched.addItems([s[0] for s in self.SCHEDULERS])
        self.sched_state = label("", "muted", wrap=False)
        self.sched.activated.connect(self.set_scheduler)
        perf.body.addWidget(RowItem("cpu", "CPU scheduler", "lavd keeps frame times steady while Discord, OBS or a "
                                    "browser run next to the game", right=[self.sched_state, self.sched]))
        if self.hub.gpu.amd:  # FSR 4 runs on Radeon RX 9000 cards only
            self.fsr4 = QCheckBox()
            self.fsr4.setChecked(sysinfo.gaming_env().get("PROTON_FSR4_UPGRADE") == "1")
            self.fsr4.toggled.connect(self.set_fsr4)
            perf.body.addWidget(RowItem("display", "FSR 4 in FSR 3.1 games", "RX 9000 cards: sharper upscaling at the "
                                        "same frame rate (proton-cachyos). Restart Steam after changing it",
                                        right=[self.fsr4]))
        size = sysinfo.shader_cache_size()
        perf.body.addWidget(RowItem("drives", "Shader cache", f"Up to {size.replace('G', ' GB')} of compiled shaders, so "
                                    "big games don't stutter rebuilding them" if size else "Mesa's default (1 GB)",
                                    S.SUCCESS if size else S.SUBTEXT))
        on = sysinfo.ntsync()
        perf.body.addWidget(RowItem("check" if on else "alert", "NTSYNC", "Windows-style sync for Proton games: fewer "
                                    "hitches" if on else "Not available in this kernel: Proton uses fsync instead",
                                    S.SUCCESS if on else S.WARNING))
        self.lay.addWidget(perf)

    def set_scheduler(self, i):
        _, sched, mode = self.SCHEDULERS[i]
        self.hub.privileged(["scheduler", "set", sched, mode], lambda ok: (
            self.hub.toast(f"CPU scheduler: {self.SCHEDULERS[i][0]}." if ok else "Couldn't change the scheduler.",
                           "ok" if ok else "bad"), self.refresh()))

    def set_fsr4(self, on):
        sysinfo.write_gaming_env({"PROTON_FSR4_UPGRADE": "1" if on else None})
        self.hub.toast("FSR 4 upgrade " + ("on" if on else "off") + ". Restart Steam (or log out and in) to apply.", "ok")

    # ---- graphics card: power limit, undervolt, fan curve (deckos gpu)

    GPU_PRESETS = [("Stock", 100, 0, "stock", "As AMD ships it"),
                   ("Quiet", 90, -50, "quiet", "Less power and noise, nearly the same speed"),
                   ("Cool", 100, -50, "cool", "Same power, lower voltage, fans earlier"),
                   ("Performance", 110, -60, "cool", "Higher power limit and a mild undervolt")]

    def build_gpu(self):
        if not self.hub.gpu.amd:
            return
        card = Card("Graphics card", "Power, voltage and fans", "gpu")
        self.gpu_state = label("Reading the card…", "sub")
        card.body.addWidget(self.gpu_state)
        self.gpu_presets = QButtonGroup(self)
        self.gpu_presets.setExclusive(True)
        prow = []
        for i, (name, *_rest, tip) in enumerate(self.GPU_PRESETS):
            b = button(name, tip=tip)
            b.setCheckable(True)
            self.gpu_presets.addButton(b, i)
            prow.append(b)
        self.gpu_presets.idClicked.connect(self.pick_gpu_preset)
        card.body.addWidget(row(*prow))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        self.power = QSlider(Qt.Horizontal)
        self.power.setRange(50, 110)
        self.power_val = label("", "value", wrap=False)
        self.power.valueChanged.connect(self.show_gpu_values)
        self.volt = QSlider(Qt.Horizontal)
        self.volt.setRange(-150, 0)
        self.volt.setSingleStep(5)
        self.volt.setPageStep(10)
        self.volt_val = label("", "value", wrap=False)
        self.volt.valueChanged.connect(self.show_gpu_values)
        self.fan = QComboBox()
        self.fan.addItems(["Stock", "Quiet", "Cool"])
        for r, (name, w, val) in enumerate((("Power limit", self.power, self.power_val),
                                            ("Voltage offset", self.volt, self.volt_val),
                                            ("Fan curve", self.fan, None))):
            grid.addWidget(label(name, "sub", wrap=False), r, 0)
            grid.addWidget(w, r, 1)
            if val:
                grid.addWidget(val, r, 2)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)
        self.gpu_apply = button("Apply", "primary", self.apply_gpu, icon="check")
        self.od_btn = button("Turn on overdrive", slot=self.enable_overdrive, icon="power",
                             tip="Lets DecKoOS undervolt and set fan curves (amdgpu.ppfeaturemask); needs a restart")
        card.body.addWidget(row(self.gpu_apply, button("Reset to stock", slot=lambda: self.pick_gpu_preset(0, apply=True),
                                                       icon="undo"), self.od_btn))
        self.gpu_note = label("", "muted")
        card.body.addWidget(self.gpu_note)
        self.lay.addWidget(card)
        self.gpu_info = {}

    def show_gpu(self, info):
        self.gpu_info = info
        if not info.get("card"):
            self.gpu_state.setText("No AMD graphics card found.")
            return
        cap, default, top = (int(info.get(k) or 0) for k in ("cap", "cap_default", "cap_max"))
        od, lact = info.get("od") == "1", info.get("lact") == "1"
        self.power.setMaximum(max(100, top * 100 // default) if default else 110)
        for w, key in ((self.power, "power_percent"), (self.volt, "voltage_offset")):
            w.blockSignals(True)
            w.setValue(int(info.get(key) or (100 if w is self.power else 0)))
            w.blockSignals(False)
        self.fan.setCurrentText(info.get("fan", "stock").capitalize())
        self.show_gpu_values()
        match = next((i for i, p in enumerate(self.GPU_PRESETS) if (p[1], p[2], p[3]) ==
                      (self.power.value(), self.volt.value(), info.get("fan", "stock"))), -1)
        for b in self.gpu_presets.buttons():
            b.setChecked(self.gpu_presets.id(b) == match)
        self.gpu_state.setText(f"{self.hub.gpu.name}  ·  power limit <b>{cap} W</b> (stock {default} W, up to {top} W)")
        self.volt.setEnabled(od and not lact)
        self.fan.setEnabled(od and not lact and info.get("fan_curve") == "1")
        for w in (self.power, self.gpu_apply, *self.gpu_presets.buttons()):
            w.setEnabled(not lact)
        self.od_btn.setVisible(not od and not lact)
        self.gpu_note.setText(
            "LACT is managing this card, so DecKoOS leaves it alone. Stop LACT's service (lactd) to tune it here." if lact
            else "Undervolting and fan curves need overdrive: turn it on, then restart." if not od
            else "Each card undervolts differently. If games crash, step back toward 0 mV or pick Stock. If DecKoOS ever "
                 "fails to start, press e in the boot menu and add deckos.gpu=stock to the linux line.")

    def show_gpu_values(self):
        default = int(self.gpu_info.get("cap_default") or 0)
        self.power_val.setText(f"{self.power.value()}%" + (f"  ·  {default * self.power.value() // 100} W" if default else ""))
        self.volt_val.setText(f"{self.volt.value()} mV")

    def pick_gpu_preset(self, i, apply=False):
        _, power, volt, fan, _tip = self.GPU_PRESETS[i]
        od = self.gpu_info.get("od") == "1" or sysinfo.DEMO
        self.power.setValue(min(power, self.power.maximum()))
        self.volt.setValue(volt if od else 0)
        self.fan.setCurrentText(fan.capitalize() if od else "Stock")
        if apply:
            self.apply_gpu()

    def apply_gpu(self):
        args = ["gpu", "set", f"POWER_PERCENT={self.power.value()}", f"VOLTAGE_OFFSET={self.volt.value()}",
                f"FAN={self.fan.currentText().lower()}"]
        self.hub.privileged(args, lambda ok: (
            self.hub.toast("Graphics card settings applied; they come back after every restart." if ok else
                           "The card didn't take those settings.", "ok" if ok else "bad", 6000),
            self.refresh()))

    def enable_overdrive(self):
        self.hub.privileged(["gpu", "overdrive", "on"], lambda ok: self.hub.toast(
            "Overdrive turns on at the next restart." if ok else "Couldn't turn on overdrive.", "ok" if ok else "bad"))

    # ---- controllers

    def build_controllers(self):
        card = Card("Controllers", "Batteries and pairing", "gaming")
        self.pad_list = QVBoxLayout()
        self.pad_list.setSpacing(6)
        card.body.addLayout(self.pad_list)
        self.pair_btn = button("Pair an Xbox controller", slot=self.pair_xbox, icon="plus",
                               tip="Puts the Xbox wireless dongle in pairing mode for 30 seconds")
        card.body.addWidget(row(self.pair_btn, button("Refresh", slot=self.show_controllers, icon="refresh"),
                                button("Bluetooth", slot=lambda: QProcess.startDetached("systemsettings", ["kcm_bluetooth"]),
                                       icon="bluetooth", tip="Pair PlayStation, Switch and Bluetooth Xbox controllers")))
        self.lay.addWidget(card)

    def show_controllers(self):
        self.clear(self.pad_list)
        devs = sysinfo.battery_devices()
        for name, pct, status in devs:
            col = S.DANGER if pct is not None and pct <= 20 else S.SUCCESS if status == "Charging" else S.SUBTEXT
            text = f"{pct}%" if pct is not None else status or "connected"
            self.pad_list.addWidget(RowItem("gaming", name, status if pct is not None else "", col,
                                            [label(f"<b>{text}</b>", wrap=False)]))
        if not devs:
            self.pad_list.addWidget(label("No wireless controllers connected. Wired ones work without setup.", "sub"))
        self.pair_btn.setVisible(sysinfo.xone_dongle())

    def pair_xbox(self):
        self.hub.privileged(["controllers", "pair"], lambda ok: self.hub.toast(
            "Pairing for 30 seconds: hold the pair button on the controller until the Xbox logo flashes fast." if ok
            else "No Xbox wireless dongle found.", "info" if ok else "bad", 8000))

    # ---- extras: Decky Loader, Sunshine

    def build_extras(self):
        card = Card("Extras", "Plugins and streaming", "plus")
        self.extras = QVBoxLayout()
        self.extras.setSpacing(6)
        card.body.addLayout(self.extras)
        self.lay.addWidget(card)

    def show_extras(self):
        self.clear(self.extras)
        decky = sysinfo.decky_installed()
        self.extras.addWidget(RowItem(
            "gaming", "Decky Loader", "Steam Deck plugins in Gaming Mode: per-game frame limits, ProtonDB badges, themes",
            S.SUCCESS if decky else S.SUBTEXT,
            [label(f"<span style='color:{S.SUCCESS}'>Installed</span>", wrap=False)] if decky else
            [button("Install", slot=lambda: self.hub.terminal("deckos decky install"), icon="download")]))
        sun = sysinfo.installed("sunshine")
        self.extras.addWidget(RowItem(
            "display", "Game streaming (Sunshine)", "Play on a TV, phone or Steam Deck with Moonlight",
            S.SUCCESS if sun else S.SUBTEXT,
            [button("Pair a device", slot=lambda: QProcess.startDetached("xdg-open", ["https://localhost:47990"]),
                    icon="external")] if sun else
            [button("Set up", slot=lambda: self.hub.terminal("deckos streaming setup"), icon="download")]))

    # ---- safe VRR/HDR test on the desktop

    def try_display(self, what):
        outs = [o for o in sysinfo.outputs() if (o[3] if what == "vrr" else o[4])]
        if not outs:
            self.hub.toast(f"No screen here reports {'VRR' if what == 'vrr' else 'HDR'} support.", "warn")
            return
        name, vrr, hdr, *_ = outs[0]
        on, off = ((f"output.{name}.vrrpolicy.automatic", f"output.{name}.vrrpolicy." +
                    {0: "never", 1: "always", 2: "automatic"}.get(vrr, "never")) if what == "vrr" else
                   (f"output.{name}.hdr.enable", f"output.{name}.hdr.{'enable' if hdr else 'disable'}"))
        if not sysinfo.DEMO:
            QProcess.execute("kscreen-doctor", [on])
        keep = TryDialog(self, "VRR" if what == "vrr" else "HDR", name).exec()
        if not keep:
            if not sysinfo.DEMO:
                QProcess.execute("kscreen-doctor", [off])
            self.hub.toast("Back to how it was.", "info")
            return
        (self.vrr if what == "vrr" else self.hdr).setChecked(True)  # saves it for Gaming Mode too
        self.hub.toast(f"{'VRR' if what == 'vrr' else 'HDR'} kept on the desktop and for Gaming Mode.", "ok")

    def refresh(self):
        if not hasattr(self, "sched"):
            return
        sysinfo.Job(self, [DECKOS, "scheduler", "status"], lambda out, _c: self.show_scheduler(sysinfo.kv(out)),
                    demo=(sysinfo.DEMO_SCHEDULER, 0))
        if hasattr(self, "gpu_state"):
            sysinfo.Job(self, [DECKOS, "gpu", "status"], lambda out, _c: self.show_gpu(sysinfo.kv(out)),
                        demo=(sysinfo.DEMO_GPU, 0))
        self.show_controllers()
        self.show_extras()

    def show_scheduler(self, st):
        i = next((i for i, s in enumerate(self.SCHEDULERS) if (s[1], s[2]) == (st.get("sched"), st.get("mode"))),
                 3 if st.get("sched") == "off" else 0)
        self.sched.setCurrentIndex(i)
        running = st.get("state") == "enabled" and st.get("running")
        self.sched_state.setText(f"<span style='color:{S.SUCCESS}'>● {st['running']}</span>" if running else
                                 "not supported" if st.get("state") == "unsupported" else "")

    def save(self, key, value):
        self.hub.write_gaming({key: value})
        self.hub.toast("Saved. Takes effect next time you enter Gaming Mode.", "ok")

    def save_screen(self):
        w, _, h = self.res.currentText().partition("x")
        top = int(self.rate.currentText())
        rates = ",".join(r for r in RATES if int(r) <= top)
        self.hub.write_gaming({"SCREEN_WIDTH": w, "SCREEN_HEIGHT": h, "CUSTOM_REFRESH_RATES": rates})
        self.hub.toast(f"Gaming Mode will use {w}×{h} at up to {top} Hz.", "ok")


# ------------------------------------------------------------------ drives

class DrivesPage(Page):
    title = "Drives"
    subtitle = "Your Windows (NTFS) drives, mounted as they are. Nothing was reformatted."

    def build(self):
        self.head_actions.addWidget(button("Rescan", slot=self.rescan, icon="refresh",
                                           tip="Adds new NTFS drives to /etc/fstab"))
        self.head_actions.addWidget(button("Open in Files", slot=lambda: QProcess.startDetached("deckos-files", ["/mnt"]),
                                           icon="folder"))
        self.card = Card("Mounted", "Drives", "drives")
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        self.card.body.addLayout(self.list)
        self.lay.addWidget(self.card)
        movein = Card("Coming from Windows?", "Bring your stuff over", "arrow-right")
        movein.body.addWidget(label("Your Windows folders in the sidebar, your wallpaper, Firefox and Edge bookmarks, "
                                    "your Steam games without downloading them again, and a DecKoOS match for your apps. "
                                    "Windows itself isn't changed.", "sub"))
        movein.body.addWidget(row(button("Move in from Windows", "primary",
                                         lambda: QProcess.startDetached("deckos-movein", []), icon="arrow-right")))
        self.lay.addWidget(movein)
        help_ = Card("If a drive is read-only", None, "alert")
        help_.body.addWidget(label("Windows leaves drives half-hibernated when Fast Startup is on, and Linux won't write "
                                   "to them. In Windows, open Terminal as administrator and run "
                                   "<b>powercfg /h off</b>, then shut down normally.", "sub"))
        help_.body.addWidget(row(button("Diagnose", slot=lambda: self.hub.terminal("deckos drives doctor"),
                                        icon="info")))
        self.lay.addWidget(help_)

    def rescan(self):
        self.hub.privileged(["drives", "rescan"], lambda ok: (self.refresh(), self.hub.toast(
            "Drives rescanned." if ok else "Rescan cancelled.", "ok" if ok else "warn")))

    def refresh(self):
        self.clear(self.list)
        ds = sysinfo.drives()
        if not ds:
            self.list.addWidget(Empty("drives", "No Windows drives mounted",
                                      "Plug in or connect a drive, then press Rescan."))
        for mount, used, total, ro, fs in ds:
            item = QFrame()
            item.setObjectName("rowItem")
            item.setAttribute(Qt.WA_StyledBackground, True)
            v = QVBoxLayout(item)
            v.setContentsMargins(12, 10, 12, 11)
            v.setSpacing(7)
            h = QHBoxLayout()
            h.setSpacing(11)
            h.addWidget(icon_label("drives", S.WARNING if ro else S.SUBTEXT, 18))
            h.addWidget(label(f"<b>{mount}</b> &nbsp;<span style='color:{S.SUBTEXT}'>{fs}</span>", wrap=False), 1)
            h.addWidget(label(f"<span style='color:{S.WARNING}'>read-only</span>" if ro else
                              f"<span style='color:{S.SUBTEXT}'>{sysinfo.size(used)} of {sysinfo.size(total)}</span>",
                              wrap=False))
            v.addLayout(h)
            m = Meter(6)
            frac = used / total if total else 0
            m.set(frac, S.WARNING if ro else (S.DANGER if frac > 0.92 else None))
            v.addWidget(m)
            self.list.addWidget(item)


# ------------------------------------------------------------------ AI & dev

class AiDevPage(Page):
    title = "AI & Development"
    subtitle = "Claude Code, local models and your dev tools."

    def build(self):
        ai, dev = (sysinfo.installed(g[4]) for g in sysinfo.GROUPS[1:])
        claude = Card("Claude Code", "AI coding agent in your terminal", "terminal")
        claude.body.addWidget(label("Run <b>claude</b> in any project folder.", "sub"))
        claude.body.addWidget(row(button("Install / update", "primary", lambda: self.hub.terminal(
            "curl -fsSL https://claude.ai/install.sh | bash"), icon="download"),
            button("Open terminal", slot=lambda: QProcess.startDetached("deckos-terminal", []), icon="terminal")))
        self.lay.addWidget(claude)

        desk = Card("Claude Desktop", "Chat, Cowork and Claude Code in a window (beta)", "ai")
        have = sysinfo.installed("claude-desktop")
        desk.body.addWidget(label("Anthropic's Linux app is built for Ubuntu and Debian. On DecKoOS it comes from the AUR "
                                  "package <b>claude-desktop</b>, which repackages that official build. Sign-in is kept "
                                  "in KDE Wallet.", "sub"))
        desk.body.addWidget(row(
            button("Open", "primary", lambda: QProcess.startDetached("claude-desktop", []), icon="external") if have else
            button("Install", "primary", lambda: self.hub.terminal("paru -S --needed claude-desktop"), icon="download"),
            *([button("Update", slot=lambda: self.hub.terminal("paru -S --needed claude-desktop"), icon="refresh")]
              if have else [])))
        self.lay.addWidget(desk)

        self.ollama_card = Card("Local AI", "Ollama on your graphics card", "ai")
        if ai:
            self.ollama_state = label("", "sub")
            self.ollama_card.body.addWidget(self.ollama_state)
            self.models = QVBoxLayout()
            self.models.setSpacing(6)
            self.ollama_card.body.addLayout(self.models)
            self.toggle = button("Start", slot=self.toggle_ollama, icon="play")
            self.installed_models = []
            self.ollama_card.body.addWidget(row(
                button("Choose a model…", slot=lambda: ModelDialog(self, self.installed_models).exec(), icon="sliders",
                       tip="Which local model, picked for what your graphics card can run")))
            # The Assistant's personality and its window on the web (searches leave the PC: off until turned on)
            persona = QComboBox()
            for key, text in (("friendly", "Friendly, a bit witty"), ("calm", "Calm and patient"),
                              ("direct", "Straight to the point"), ("gamer", "Gamer buddy")):
                persona.addItem(text, key)
            persona.setCurrentIndex(max(0, persona.findData(sysinfo.ai_setting("PERSONALITY", "friendly"))))
            persona.activated.connect(lambda _i: self.ai_set("personality", persona.currentData(),
                                                             f"Personality: {persona.currentText()}"))
            web = QCheckBox("Web search (DuckDuckGo)")
            web.setToolTip("The Assistant can look things up online. Your searches go to DuckDuckGo; it always says "
                           "when it searched.")
            web.setChecked(sysinfo.ai_setting("WEB_SEARCH", "off") == "on")
            web.toggled.connect(lambda on: self.ai_set("web", "on" if on else "off", f"Web search {'on' if on else 'off'}"))
            name = label("Personality")
            self.ollama_card.body.addWidget(row(name, persona, web))
            self.ollama_card.body.addWidget(row(
                button("Ask DecKoOS Assistant", "primary", lambda: QProcess.startDetached("deckos-assistant", []), icon="ai",
                       tip="Install and set things up by asking (Meta+Space anywhere)"),
                self.toggle,
                button("Link Claude Code", slot=lambda: self.hub.terminal("deckos ai claude-link"), icon="external",
                       tip="Claude Code hands long logs and files to the local model, which saves tokens"),
                button("GPU compute check", slot=lambda: self.hub.terminal(
                    "nvidia-smi" if self.hub.gpu.nvidia else "rocminfo | grep -E 'Marketing|gfx' | head -n 6"),
                    icon="gpu")))
        else:
            self.ollama_card.body.addWidget(Empty("ai", "Local AI isn't installed",
                                                  "Ollama runs models on a Radeon RX 7000 / 9000 (ROCm) or an "
                                                  "NVIDIA card (CUDA).",
                                                  button("Add Local AI", "primary", lambda: self.hub.add_group("ai"),
                                                         icon="plus")))
        self.lay.addWidget(self.ollama_card)

        work = Card("DecKoOS Work", "A local workspace for bigger jobs", "code")
        work.body.addWidget(label("Saved project chats with your local models: read and change code, run approved "
                                  "commands, make Word, PDF, PowerPoint and spreadsheet files, and create images on "
                                  "your graphics card. No API key, nothing leaves this PC.", "sub"))
        work.body.addWidget(row(button("Open DecKoOS Work", "primary", lambda: QProcess.startDetached("deckos-work", []),
                                       icon="code")))
        self.lay.addWidget(work)
        tools = Card("Tools", "What's installed", "code")
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (name, cmd, what) in enumerate(sysinfo.TOOLS):
            ok = sysinfo.installed(cmd)
            grid.addWidget(RowItem("check" if ok else "plus", name, what, S.SUCCESS if ok else S.MUTED), i // 2, i % 2)
        tools.body.addLayout(grid)
        if not dev:
            tools.body.addWidget(row(button("Add Development tools", "primary", lambda: self.hub.add_group("dev"),
                                            icon="plus")))
        self.lay.addWidget(tools)

    def toggle_ollama(self):
        on = sysinfo.service_active("ollama")
        self.hub.privileged_cmd(["systemctl", "disable" if on else "enable", "--now", "ollama"],
                                lambda ok: (self.refresh(), self.hub.toast(
                                    ("Ollama stopped." if on else "Ollama started.") if ok else "Not changed.",
                                    "ok" if ok else "warn")))

    def refresh(self):
        if not hasattr(self, "ollama_state"):
            return
        on = sysinfo.service_active("ollama")
        self.ollama_state.setText(f"<span style='color:{S.SUCCESS if on else S.MUTED}'>●</span> Ollama is "
                                  f"{'running' if on else 'stopped'}")
        self.toggle.setText("Stop" if on else "Start")
        self.toggle.setIcon(S.icon("stop" if on else "play", S.TEXT, 16))
        self.clear(self.models)
        if on:
            sysinfo.Job(self, ["ollama", "list"], self.show_models,
                        demo=("NAME ID SIZE MODIFIED\nqwen3:8b 500a1f067a9f 5.2 GB 2 days ago\n"
                              "llama3.2:3b a80c4f17acd5 2.0 GB 1 week ago", 0))

    def ai_set(self, key, value, text):
        if not sysinfo.DEMO:
            QProcess.execute(sysinfo.DECKOS, ["ai", "set", key, value])
        self.hub.toast(text + " (from the next conversation)", "ok")

    def show_models(self, out, code):
        rows = [ln.split() for ln in out.splitlines()[1:] if ln.strip()]
        self.installed_models = [r[0] for r in rows]
        if not rows:
            self.models.addWidget(label("No models yet. “Choose a model” downloads one that suits this PC.", "muted"))
        for r in rows:
            size_ = " ".join(r[2:4]) if len(r) > 3 else ""
            self.models.addWidget(RowItem("ai", r[0], size_))


class ModelDialog(QDialog):
    """The local models DecKoOS offers, each rated for this PC's graphics card (assistant/models.py)."""

    FIT = {"fits": ("Fits", S.SUCCESS), "tight": ("Tight fit", S.WARNING),
           "slow": ("Slower: partly on the processor", S.WARNING), "too big": ("Too big for this PC", S.DANGER)}

    def __init__(self, page, installed):
        super().__init__(page)
        self.page = page
        self.setObjectName("root")
        self.setWindowTitle("Choose a local model")
        self.setMinimumWidth(720)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assistant"))
        import models
        hw = ({"gpu": "GeForce RTX 5070 Ti", "vendor": "nvidia", "vram": 16 << 30, "accel": "cuda", "ram": 64 << 30}
              if sysinfo.DEMO else models.hardware())
        current = self.current_model()
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(10)
        v.addWidget(label("Choose a local model", "title"))
        v.addWidget(label(f"<b>{models.describe(hw)}</b>. Bigger models answer better but need more graphics memory; "
                          "one that doesn't fit runs partly on the processor, which is slow.", "sub"))
        for r in models.rows(hw, installed):
            text, color = self.FIT[r["fit"]]
            # The fit goes by the name, where it can't be cut off: it's what the choice turns on
            title = (f"{r['title']}  <span style='color:{color}'>{text}</span>"
                     + (f"  <span style='color:{S.P.accent}'>· recommended</span>" if r["recommended"] else ""))
            detail = f"{r['good_for']} · {r['download_gb']:.0f} GB · {r['tag']}"
            if r["tag"] == current:
                act = label(f"<span style='color:{S.SUCCESS}'>In use</span>", None, wrap=False)
            elif r["installed"]:
                act = button("Use", "primary" if r["recommended"] else None, lambda _=False, t=r["tag"]: self.use(t))
            else:
                act = button("Download and use", "primary" if r["recommended"] else None,
                             lambda _=False, t=r["tag"]: self.download(t), icon="download")
                act.setEnabled(r["fit"] != "too big")
            v.addWidget(RowItem("ai", title, detail,
                                S.P.accent if r["recommended"] else S.SUBTEXT, [act]))
        v.addWidget(label("Only models that use DecKoOS Assistant's tools reliably are listed. Any other Ollama model "
                          "works too: deckos ai setup NAME.", "muted"))

    @staticmethod
    def current_model():
        if sysinfo.DEMO:
            return "qwen3:8b"
        for f in (Path.home() / ".config/deckos/ai.conf", Path("/etc/deckos/ai.conf")):
            m = re.search(r"^MODEL=(\S+)", sysinfo.read(f), re.M)
            if m:
                return m.group(1)
        return ""

    def use(self, tag):
        if not sysinfo.DEMO:
            QProcess.startDetached("deckos", ["ai", "model", tag])
        self.page.hub.toast(f"DecKoOS Assistant uses {tag} now", "ok")
        self.accept()

    def download(self, tag):
        # In a terminal: a model is gigabytes, and the download shows its progress there
        self.page.hub.terminal(f"sudo deckos ai setup {tag} && deckos ai model {tag}")
        self.accept()


# ------------------------------------------------------------------ system

def _setup_run(page, args, done_text):
    """deckos setup ARGS, with the outcome as a toast (it's quick: small files only)."""
    if sysinfo.DEMO:
        page.hub.toast(done_text, "ok")
        return
    proc = QProcess(page)
    proc.finished.connect(lambda code, _s: (page.hub.toast(
        done_text if code == 0 else bytes(proc.readAllStandardError()).decode(errors="replace").strip()
        or "That didn't work.", "ok" if code == 0 else "warn", 9000), proc.deleteLater()))
    proc.start("deckos", ["setup", *args])


class SystemPage(Page):
    title = "System"
    subtitle = "Updates, snapshots, firewall and software."

    def export_setup(self):
        name = f"decko-setup-{datetime.now():%Y-%m-%d}.tar.gz"
        path, _ = QFileDialog.getSaveFileName(self, "Save your setup", str(Path.home() / name), "DecKoOS setup (*.tar.gz)")
        if path:
            _setup_run(self, ["export", path], f"Saved your setup to {Path(path).name}")

    def import_setup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Bring in a setup", str(Path.home()), "DecKoOS setup (*.tar.gz)")
        if path and QMessageBox.question(self, "Bring in this setup?",
                                         "Your look, panel and DecKoOS settings are replaced by the ones in the file. "
                                         "What's there now is kept: the Timeline's Undo puts it back.") == QMessageBox.Yes:
            _setup_run(self, ["import", path], "Setup brought in: log out and back in to see all of it")

    def build(self):
        self.head_actions.addWidget(button("Health check", slot=lambda: QProcess.startDetached("deckos-sysdoctor", []),
                                           icon="check", tip="System Doctor: what's wrong, in plain words, with fixes"))
        self.head_actions.addWidget(button("System monitor", slot=lambda: QProcess.startDetached("deckos-sysmon", []),
                                           icon="list", tip="What's running and what it uses (Ctrl+Shift+Esc)"))
        self.head_actions.addWidget(button("Benchmarks", slot=lambda: QProcess.startDetached("deckos-bench", []),
                                           icon="gauge"))
        up = Card("Updates", "Keep DecKoOS current", "update")
        self.up_state = label("Checking…", "cardTitle")
        self.up_detail = label("", "sub")
        up.body.addWidget(self.up_state)
        up.body.addWidget(self.up_detail)
        self.up_rows = QVBoxLayout()  # what's coming: DecKoOS, system packages, AUR; after updating, what's next
        self.up_rows.setSpacing(6)
        up.body.addLayout(self.up_rows)
        self.up_list = label("", "mono")
        self.up_list.setTextFormat(Qt.PlainText)
        self.up_list.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.up_list.hide()
        up.body.addWidget(self.up_list)
        self.pending, self.notices = ([], []), []
        self.up_meter = Meter(6)
        self.up_meter.hide()
        up.body.addWidget(self.up_meter)
        self.up_log = QPlainTextEdit()
        self.up_log.setReadOnly(True)
        self.up_log.setMaximumBlockCount(3000)
        self.up_log.setFixedHeight(160)
        self.up_log.hide()
        up.body.addWidget(self.up_log)
        self.up_btn = button("Update now", "primary", self.run_update, icon="update",
                             tip="DecKoOS, Arch, CachyOS and Flatpak apps; a snapshot is taken first")
        self.up_btn.setEnabled(False)
        up.body.addWidget(row(self.up_btn,
                              button("Check again", slot=self.check_updates, icon="refresh"),
                              button("Full update in terminal", slot=lambda: self.hub.terminal("deckos update"),
                                     icon="terminal", tip="Includes AUR apps (paru)")))
        self.auto = QCheckBox("Update automatically overnight (4 AM; skipped while a game or Gaming Mode runs)")
        self.auto.clicked.connect(self.set_auto_update)
        self.auto_state = label("", "muted")
        up.body.addWidget(self.auto)
        up.body.addWidget(self.auto_state)
        self.testing = QCheckBox("Get new DecKoOS releases first (the testing channel: everyone else gets them once tried)")
        self.testing.clicked.connect(self.set_channel)
        up.body.addWidget(self.testing)
        self.lay.addWidget(up)

        carry = Card("Take my setup with me", "For a new PC, or after a reinstall", "download")
        carry.body.addWidget(label("One file with your look, your panel and pinned apps, DecKoOS's settings, game "
                                   "profiles and Game Doctor's fixes. No passwords, games or system files.", "sub"))
        carry.body.addWidget(row(button("Save my setup…", "primary", self.export_setup, icon="download"),
                                 button("Bring in a setup…", slot=self.import_setup, icon="folder")))
        self.lay.addWidget(carry)

        snaps = Card("Undo an update", "If something broke after updating", "undo")
        snaps.body.addWidget(label("DecKoOS takes a snapshot before every update. Undo one and the system goes back to "
                                   "how it was before it, from the next restart. Your files and settings in your home "
                                   "folder stay as they are.", "sub"))
        self.undo_note = QVBoxLayout()  # restart to finish, or delete the system an undo replaced
        self.undo_note.setSpacing(6)
        snaps.body.addLayout(self.undo_note)
        self.snap_list = QVBoxLayout()
        self.snap_list.setSpacing(6)
        snaps.body.addLayout(self.snap_list)
        self.snap_first = QCheckBox("In the terminal, offer a snapshot before deleting a big folder (undo it with "
                                    "deckos restore)")
        self.snap_first.clicked.connect(self.set_snapshot_first)
        snaps.body.addWidget(self.snap_first)
        self.lay.addWidget(snaps)
        self.undo_pending = None  # (date, what) once an undo waits for the restart

        home = Card("Your files", "Home snapshots and backup", "folder")
        home.body.addWidget(label("Snapshots bring back a file you deleted or broke, from the last hours or days. A "
                                  "backup on another drive survives this disk failing.", "sub"))
        self.home_box = QVBoxLayout()
        self.home_box.setSpacing(6)
        home.body.addLayout(self.home_box)
        self.home_buttons = QHBoxLayout()
        self.home_buttons.setSpacing(6)
        home.body.addLayout(self.home_buttons)
        self.lay.addWidget(home)

        fw = Card("Firewall", "Incoming connections", "shield")
        self.fw_row = QVBoxLayout()
        fw.body.addLayout(self.fw_row)
        self.fw_btn = button("", slot=self.toggle_firewall)
        fw.body.addWidget(row(self.fw_btn, button("Firewall settings", slot=lambda: QProcess.startDetached(
            "systemsettings", ["kcm_firewall"]), icon="external")))
        self.lay.addWidget(fw)

        from hub_heal import HealCard  # self-healing, said up front with its switches
        self.lay.addWidget(HealCard(self.hub.toast))

        from hub_kids import KidsCard  # here: hub_kids builds on this module's widgets
        self.kids = KidsCard(self.hub)
        self.lay.addWidget(self.kids)

        sw = Card("Software", "Add what you skipped at install", "package")
        sw.actions.addWidget(button("Open DecKoOS Store", slot=lambda: QProcess.startDetached("deckos-store", []),
                                    icon="store", tip="Every app from Arch, CachyOS, Flathub and the AUR"))
        self.sw_list = QVBoxLayout()
        self.sw_list.setSpacing(6)
        sw.body.addLayout(self.sw_list)
        self.lay.addWidget(sw)
        self.updating = None

    def refresh(self):
        self.check_updates()
        sysinfo.Job(self, [DECKOS, "auto-update", "status"], lambda out, _c: self.show_auto_update(sysinfo.kv(out)),
                    demo=(sysinfo.DEMO_AUTO_UPDATE, 0))
        sysinfo.Job(self, [DECKOS, "channel"], lambda out, _c: self.show_channel(sysinfo.kv(out).get("channel", "")),
                    demo=("channel=stable\n", 0))
        sysinfo.Job(self, [DECKOS, "snapshot-first"],
                    lambda out, _c: self.snap_first.setChecked(sysinfo.kv(out).get("snapshot-first") != "off"),
                    demo=("snapshot-first=on\n", 0))
        self.hub.data.undoable(self.show_undoable)
        self.show_home()
        self.hub.data.firewall(self.show_firewall)
        self.clear(self.sw_list)
        for key, title, desc, ic, cmd in sysinfo.GROUPS:
            ok = sysinfo.installed(cmd)
            right = [label(f"<span style='color:{S.SUCCESS}'>Installed</span>", wrap=False)] if ok else \
                [button("Add", slot=lambda k=key: self.hub.add_group(k), icon="plus")]
            self.sw_list.addWidget(RowItem(ic, title, desc, S.SUCCESS if ok else S.SUBTEXT, right))

    def check_updates(self):
        if self.updating:
            return
        self.up_state.setText("Checking for updates…")
        self.up_detail.setText("")
        self.up_btn.setEnabled(False)
        self.hub.data.update_list(self.show_updates, fresh=True)

    DECKOS_PARTS = {"deckos-settings": "Hub, Menu, Quick Settings, deckos tool, themes",
                    "deckos-files": "DecKoOS Files", "deckos-terminal": "DecKoOS Terminal", "deckos-editor": "DecKoOS Editor",
                    "deckos-theme-tmpikes": "TMpikes theme"}

    def show_updates(self, repo, aur, err):
        self.pending = (repo, aur)
        self.clear(self.up_rows)
        for _kind, make in self.notices:
            self.up_rows.addWidget(make())
        deck = [p for p in repo if p[0] in sysinfo.DECKOS_PKGS]
        system = [p for p in repo if p[0] not in sysinfo.DECKOS_PKGS]
        settings = next((p for p in deck if p[0] == "deckos-settings"), None)
        total = len(repo) + len(aur)
        if err:
            self.up_state.setText("Couldn't check for updates")
            self.up_detail.setText(err)
        elif total == 0:
            self.up_state.setText("Everything is up to date")
            self.up_detail.setText("DecKoOS, Arch, CachyOS and AUR packages.")
        else:
            self.up_state.setText(f"DecKoOS {sysinfo.plain_version(settings[2])} is ready" if settings else
                                  f"{total} update{'s' if total != 1 else ''} waiting")
            self.up_detail.setText("Update now installs the DecKoOS and system updates below. A snapshot is taken "
                                   "first, so you can roll back." if repo else
                                   "Only AUR apps: update them in the terminal.")

        if not err:
            if deck:
                title = (f"DecKoOS {sysinfo.plain_version(settings[1])} → {sysinfo.plain_version(settings[2])}"
                         if settings else "DecKoOS apps")
                self.up_rows.addWidget(RowItem("update", title, "From the signed DecKoOS repo: " + "; ".join(
                    self.DECKOS_PARTS.get(p[0], p[0]) for p in deck), S.P.accent))
            elif sysinfo.update_channel_on():
                self.up_rows.addWidget(RowItem("check", sysinfo.deckos_version(),
                                               "Up to date with the signed DecKoOS repo", S.SUCCESS))
            else:
                self.up_rows.addWidget(RowItem("alert", "DecKoOS's own updates aren't set up",
                                               "Run deckos dev-install once from a DecKoOS checkout, or install a "
                                               "newer deckos-settings.", S.WARNING))
            if system:
                # Name what matters first: the kernel and desktop, then the rest.
                key = sorted(system, key=lambda p: not (sysinfo.REBOOT_RE.fullmatch(p[0]) or
                                                        sysinfo.DESKTOP_RE.fullmatch(p[0])))
                names = ", ".join(p[0] for p in key[:4]) + (f" and {len(key) - 4} more" if len(key) > 4 else "")
                restart = any(sysinfo.REBOOT_RE.fullmatch(p[0]) for p in system)
                toggle = button("Hide" if self.up_list.isVisible() else "Show all", slot=self.toggle_up_list,
                                icon="list")
                self.up_rows.addWidget(RowItem("package", f"{len(system)} system package{'s' if len(system) != 1 else ''}",
                                               f"Arch and CachyOS: {names}" + (" · needs a restart" if restart else ""),
                                               S.SUBTEXT, [toggle]))
            if aur:
                self.up_rows.addWidget(RowItem("terminal", f"{len(aur)} AUR app{'s' if len(aur) != 1 else ''}",
                                               ", ".join(p[0] for p in aur[:4]) + ": not in Update now, use Full "
                                               "update in terminal", S.SUBTEXT))
        width = max((len(p[0]) for p in repo + aur), default=0)
        self.up_list.setText("\n".join(f"{n:<{width}}  {sysinfo.plain_version(o)} → {sysinfo.plain_version(v)}"
                                       for n, o, v in deck + system + aur))
        if not repo + aur:
            self.up_list.hide()
        self.up_btn.setEnabled(bool(repo) and not err)

    def show_auto_update(self, st):
        self.auto.setChecked(st.get("enabled") == "1")
        when = st.get("when", "")
        if not when.isdigit():
            self.auto_state.setText("")
            return
        at = datetime.fromtimestamp(int(when)).strftime("%a %d %b, %H:%M")
        self.auto_state.setText({
            "ok": f"Last overnight update: {at}, {st.get('count', '0')} packages.",
            "skipped": f"Skipped on {at}: {st.get('why', '')}.",
        }.get(st.get("result"), f"<span style='color:{S.WARNING}'>Overnight update on {at} didn't finish:</span> "
                                f"{st.get('why', '')}"))

    def show_channel(self, channel):
        self.testing.setChecked(channel == "testing")
        # a hand-edited deckos-repo (another mirror, a USB) is left alone, here as in deckos channel
        self.testing.setEnabled(channel in ("stable", "testing"))

    def set_channel(self, on):
        self.hub.privileged(["channel", "testing" if on else "stable"], lambda ok: (
            self.hub.toast(("New releases come to this PC first now." if on else "Back on stable releases.") if ok else
                           "Couldn't switch: the testing channel may not be published yet.", "ok" if ok else "bad",
                           6000),
            ok or self.testing.setChecked(not on), ok and self.check_updates()))

    def set_snapshot_first(self, on):
        sysinfo.Job(self, [DECKOS, "snapshot-first", "on" if on else "off"], lambda _out, code: (
            self.hub.toast(("Snapshot first is on: terminals ask before big deletes." if on else
                            "Snapshot first is off.") if code == 0 else "Couldn't change Snapshot first.",
                           "ok" if code == 0 else "bad"),
            code == 0 or self.snap_first.setChecked(not on)), demo=("", 0))

    def set_auto_update(self, on):
        self.hub.privileged(["auto-update", "on" if on else "off"], lambda ok: (
            self.hub.toast(("Overnight updates on." if on else "Overnight updates off.") if ok else
                           "Couldn't change overnight updates.", "ok" if ok else "bad"),
            ok or self.auto.setChecked(not on)))

    def toggle_up_list(self):
        self.up_list.setVisible(not self.up_list.isVisible())
        b = self.sender()
        if b:
            b.setText("Hide" if self.up_list.isVisible() else "Show all")

    def restart_desktop(self):
        """The panel, Menu and Quick Settings are loaded once per login: restart plasmashell for the new ones.
        Open windows stay open (KWin keeps them)."""
        self.notices = [n for n in self.notices if n[0] != "desktop"]
        self.show_updates(*self.pending, "")
        if sysinfo.DEMO:
            self.hub.toast("Restarting the desktop (demo).", "info")
        elif not QProcess.startDetached("systemctl", ["--user", "restart", "plasma-plasmashell"]):
            QProcess.startDetached("plasmashell", ["--replace"])

    def run_update(self):
        self.updating = QProcess(self)
        self.updating.setProcessChannelMode(QProcess.MergedChannels)
        self.updating.readyReadStandardOutput.connect(self.update_output)
        self.updating.finished.connect(self.update_done)
        self.up_log.clear()
        self.up_log.show()
        self.up_meter.set(0)
        self.up_meter.show()
        self.up_btn.setEnabled(False)
        self.up_state.setText("Updating…")
        self.up_detail.setText("Keep DecKoOS running until this finishes.")
        if sysinfo.DEMO:
            self.updating.start("python", ["-c", "import time\nfor i in range(1,13):\n print(f'({i:2}/12) upgrading "
                                                 "package-{i}', flush=True); time.sleep(0.15)"])
        else:
            self.updating.start("pkexec", [DECKOS, "update", "--system"])

    def update_output(self):
        text = bytes(self.updating.readAllStandardOutput()).decode(errors="replace")
        for line in text.splitlines():
            if line.strip():
                self.up_log.appendPlainText(line)
            m = re.search(r"\(\s*(\d+)/(\d+)\)", line)
            if m:
                self.up_meter.set(int(m.group(1)) / int(m.group(2)))

    def update_done(self, code, _status):
        self.updating = None
        self.up_meter.set(1.0 if code == 0 else self.up_meter.value, None if code == 0 else S.DANGER)
        if code == 0:
            # a new DecKoOS release: its What's New, once (it checks the notes against the last one seen)
            if any(p[0] == "deckos-settings" for p in self.pending[0]) and not sysinfo.DEMO:
                QProcess.startDetached("deckos-whatsnew", ["--if-new"])
            self.notices = self.after_update(self.pending[0])
            needs = [k for k, _ in self.notices]
            self.hub.toast("Updated. Restart the PC to finish." if "reboot" in needs else
                           "Updated. Restart the desktop to load the new DecKoOS." if "desktop" in needs else
                           "DecKoOS is up to date.", "ok", 7000)
        elif code in (126, 127):
            self.hub.toast("Update cancelled.", "warn")
        else:
            self.hub.toast("The update stopped with an error; see the log.", "bad", 7000)
            tail = "\n".join(self.up_log.toPlainText().splitlines()[-40:])
            self.notices = [("error", lambda: RowItem(
                "alert", "The update stopped with an error", "The log shows where. The Assistant can read it with you.",
                S.DANGER, [button("Ask DecKoOS Assistant", slot=lambda: sysinfo.ask_assistant(
                    "A DecKoOS update (pacman -Syu through deckos update) stopped with an error. Explain what went "
                    "wrong and how to fix it. The end of its output:\n" + tail), icon="ai")]))]
            self.up_rows.insertWidget(0, self.notices[0][1]())
        self.hub.data.invalidate()
        self.check_updates()
        self.hub.data.undoable(self.show_undoable, fresh=True)

    def after_update(self, done):
        """What the update just installed needs next, as (kind, row factory) notices for the Updates card."""
        notes = []
        settings = next((p for p in done if p[0] == "deckos-settings"), None)
        desktop = [p[0] for p in done if sysinfo.DESKTOP_RE.fullmatch(p[0])]
        reboot = [p[0] for p in done if sysinfo.REBOOT_RE.fullmatch(p[0])]
        if desktop and not reboot:  # a restart covers the desktop too
            title = f"DecKoOS {sysinfo.plain_version(settings[2])} installed" if settings else "Plasma updated"
            notes.append(("desktop", lambda: RowItem(
                "refresh", title, "The Menu, panel and Quick Settings switch to the new version when the desktop "
                "restarts. Your open windows stay open.", S.SUCCESS,
                [button("Restart desktop", "primary", self.restart_desktop, icon="refresh")])))
        if reboot:
            names = ", ".join(reboot[:3]) + (f" and {len(reboot) - 3} more" if len(reboot) > 3 else "")
            notes.append(("reboot", lambda: RowItem(
                "power", "Restart to finish", f"{names} load at the next start" +
                (f"; so does DecKoOS {sysinfo.plain_version(settings[2])}" if settings else "") + ".", S.WARNING,
                [button("Restart now", slot=lambda: self.hub.toast("Restarting (demo).") if sysinfo.DEMO else
                        QProcess.startDetached("systemctl", ["reboot"]), icon="power")])))
        return notes

    def show_undoable(self, rows):
        self.show_undo_note()
        self.clear(self.snap_list)
        if rows is None:
            self.snap_list.addWidget(label("Couldn't read the snapshot list (snapper).", "muted"))
            return
        if not rows:
            self.snap_list.addWidget(label("Nothing to undo yet: the next update is the first one you can take back.",
                                           "muted"))
        for pre, date, what in rows[:6]:
            undo = button("Undo", slot=lambda _=False, p=pre, d=date, w=what: self.undo_update(p, d, w), icon="undo",
                          tip=f"Go back to snapshot #{pre}, from just before this update")
            undo.setEnabled(self.undo_pending is None)
            self.snap_list.addWidget(RowItem("package", what or "Update", f"{date}  ·  snapshot #{pre}", right=[undo]))
        if len(rows) > 6:
            self.snap_list.addWidget(label(f"…and {len(rows) - 6} older: deckos undo list shows them all.", "muted"))

    def show_undo_note(self):
        self.clear(self.undo_note)
        last = sysinfo.last_undo()
        if self.undo_pending:
            date, what = self.undo_pending
            self.undo_note.addWidget(RowItem(
                "power", "Restart to finish the undo", f"DecKoOS goes back to before {what} ({date}).", S.WARNING,
                [button("Restart now", "primary", slot=lambda: self.hub.toast("Restarting (demo).") if sysinfo.DEMO else
                        QProcess.startDetached("systemctl", ["reboot"]), icon="power")]))
        elif last and not last.get("cleaned"):
            self.undo_note.addWidget(RowItem(
                "check", f"Went back to before {last.get('what') or 'an update'}",
                "The system it replaced is kept, in case you change your mind. Delete it once everything works.",
                S.SUCCESS, [button("Delete old system", slot=self.clean_undo, icon="trash",
                                   tip="Frees the space it takes; this can't be undone")]))

    def undo_update(self, pre, date, what):
        if QMessageBox.question(
                self, "Undo this update?",
                f"DecKoOS goes back to how it was before {what} ({date}).\n\n"
                "This happens when you restart; until then nothing changes. Apps and system settings changed since "
                "then go back too. Your files and settings in your home folder stay as they are.\n\n"
                "The system as it is now is kept, so you can change your mind.") != QMessageBox.Yes:
            return

        def done(ok):
            if not ok:
                self.hub.toast("The update couldn't be undone. Run 'sudo deckos undo' in a terminal to see why.",
                               "bad", 8000)
                return
            self.undo_pending = (date, what)
            self.hub.toast("Done: restart to go back.", "ok", 6000)
            self.hub.data.undoable(self.show_undoable, fresh=True)
        self.hub.privileged(["undo", str(pre)], done)

    def clean_undo(self):
        if QMessageBox.question(self, "Delete the old system?",
                                "The system an undo replaced is deleted for good. Only do this once everything "
                                "works.") != QMessageBox.Yes:
            return
        self.hub.privileged(["undo", "clean"], lambda ok: (
            self.hub.toast("Deleted." if ok else "Couldn't delete it: run 'sudo deckos undo clean' to see why.",
                           "ok" if ok else "bad", 6000), self.show_undo_note()))

    def show_home(self):
        self.clear(self.home_box)
        self.clear(self.home_buttons)
        if sysinfo.home_snapshots_on():
            self.home_snap_row = RowItem("snapshot", "Hourly snapshots of /home", "Checking…", S.SUCCESS)
            self.home_box.addWidget(self.home_snap_row)
            self.hub.data.snapshots(self.show_home_snapshots, config="home")
            self.home_buttons.addWidget(button("Browse snapshots", slot=lambda: QProcess.startDetached(
                "deckos-files", ["/home/.snapshots"]), icon="folder"))
        else:
            self.home_box.addWidget(RowItem("alert", "No snapshots of your files yet",
                                            "System snapshots don't include /home.", S.WARNING))
            self.home_buttons.addWidget(button("Turn on home snapshots", "primary", self.enable_home, icon="snapshot"))
        dest, last = sysinfo.backup_info()
        if dest:
            self.home_box.addWidget(RowItem("drives", f"Backup on {dest}", f"Last backup: {last or 'never'}",
                                            S.SUCCESS if last else S.SUBTEXT))
            self.home_buttons.addWidget(button("Back up now", slot=lambda: self.hub.terminal("deckos backup"),
                                               icon="download"))
            self.home_buttons.addWidget(button("Change drive", slot=self.pick_backup, icon="drives"))
        else:
            self.home_box.addWidget(RowItem("drives", "No backup yet", "Pick a drive or folder to copy your files to.",
                                            S.SUBTEXT))
            self.home_buttons.addWidget(button("Back up to…", slot=self.pick_backup, icon="download"))
        self.home_buttons.addStretch(1)

    def show_home_snapshots(self, snaps):
        if snaps is None:
            self.home_snap_row.detail.setText("Couldn't read the list (snapper).")
        else:
            self.home_snap_row.detail.setText(f"{len(snaps)} saved" + (f", newest {snaps[0][1]}" if snaps else "")
                                              + ". Kept: 12 hourly, 7 daily, 2 weekly.")
        self.home_snap_row.detail.show()

    def enable_home(self):
        self.hub.privileged(["home", "enable"], lambda ok: (self.hub.data.invalidate(), self.show_home(),
                                                             self.hub.toast("Home snapshots are on." if ok else
                                                                            "Home snapshots not changed.",
                                                                            "ok" if ok else "warn")))

    def pick_backup(self):
        dest = QFileDialog.getExistingDirectory(self, "Back up your files to…", "/mnt" if Path("/mnt").is_dir() else "")
        if dest:
            self.hub.terminal(f"deckos backup {shlex.quote(dest)}")
            self.hub.toast("Backing up in a terminal.", "info")

    def show_firewall(self, on, svcs):
        self.clear(self.fw_row)
        if on:
            self.fw_row.addWidget(RowItem("shield", "On: blocking incoming connections",
                                          "Open for: " + (", ".join(svcs) or "nothing"), S.SUCCESS))
        else:
            self.fw_row.addWidget(RowItem("shield-off", "Off: incoming connections are allowed",
                                          "Turn it back on unless you need it off for something specific.", S.DANGER))
        self.fw_on = on
        self.fw_btn.setText("Turn off" if on else "Turn on")
        self.fw_btn.setIcon(S.icon("shield-off" if on else "shield", S.TEXT, 16))

    def toggle_firewall(self):
        on = self.fw_on
        self.hub.privileged_cmd(["systemctl", "disable" if on else "enable", "--now", "firewalld"],
                                lambda ok: (self.hub.data.invalidate(), self.hub.data.firewall(self.show_firewall),
                                            self.hub.toast(("Firewall off." if on else "Firewall on.") if ok else
                                                           "Firewall not changed.", "ok" if ok else "warn")))


# ------------------------------------------------------------------ appearance

ACCENTS = [("DecKoOS blue", "#4C8DFF"), ("Violet", "#7A5CFF"), ("Teal", "#22C7B8"), ("Green", "#3DD68C"),
           ("Amber", "#F5B84B"), ("Orange", "#FF7A45"), ("Red", "#FF5C7A"), ("Pink", "#E86BD8")]


class AppearancePage(Page):
    title = "Appearance"
    subtitle = "Theme, accent colour, wallpaper and desktop style."

    def taskbar_colors(self, mode, text):
        if mode != "custom":
            self.apply(["deckos", "taskbar", "colors", mode], f"Taskbar colours: {text}")
            return
        from PySide6.QtWidgets import QColorDialog
        a = QColorDialog.getColor(QColor(S.P.accent), self, "Taskbar colour")
        if not a.isValid():
            return
        b = QColorDialog.getColor(a, self, "Second colour (for the gradient)")
        self.apply(["deckos", "taskbar", "colors", "custom", a.name().upper(), (b if b.isValid() else a).name().upper()],
                   "Taskbar colours: your own")

    def set_sounds(self, theme, name):
        if not sysinfo.DEMO:
            sysinfo.set_sound_theme(theme)
        self.hub.toast(f"System sounds: {name}", "ok")
        if theme != "off":
            self.play_sample()

    def play_sample(self):
        theme = sysinfo.sound_theme()
        if theme != "off" and not sysinfo.DEMO:
            sample = Path(f"/usr/share/sounds/{theme}/stereo/theme-demo.oga")
            if sample.exists():
                QProcess.startDetached("pw-play", [str(sample)])

    def set_style(self, key, value):
        S.save_style(**{key: value})
        self.hub.set_accent(S.P.accent)  # the same live restyle: stylesheet, logos, repaint

    def custom_accent(self):
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(QColor(S.P.accent), self, "Accent colour")
        if c.isValid():
            self.swatches.setExclusive(False)  # no preset is picked now
            for b in self.swatches.buttons():
                b.setChecked(False)
            self.swatches.setExclusive(True)
            self.set_accent(c.name().upper(), "Custom")

    def build(self):
        vibes = Card("Vibes", "A whole mood, in one go", "star")
        vibes.body.addWidget(label("Colours, an animated wallpaper and a music visualizer that dances to what's "
                                   "playing. It pauses during games and full-screen videos.", "sub"))
        self.vibe_grid = QGridLayout()
        self.vibe_grid.setSpacing(10)
        vibes.body.addLayout(self.vibe_grid)
        group = QButtonGroup(self)
        buttons = []
        shown = sysinfo.visualizer_style()
        for value, text in (("bars", "Bars"), ("wave", "Wave"), ("ring", "Ring"), ("none", "Off")):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(value == shown)
            b.clicked.connect(lambda _c, v=value, t=text: self.apply(["deckos", "vibe", "visualizer", v],
                                                                      f"Music visualizer: {t}"))
            group.addButton(b)
            buttons.append(b)
        name = label("Music visualizer")
        name.setFixedWidth(140)
        vibes.body.addWidget(row(name, *buttons))
        # Desktop widgets in the Vibe's look: on and off one by one (deckos vibe widget ID on|off)
        shown = sysinfo.desktop_widgets()
        toggles = []
        for wid, text in (("org.deckos.bigclock", "Clock"), ("org.deckos.nowplaying", "Now Playing"),
                          ("org.deckos.weather", "Weather"), ("org.deckos.focus", "Focus"), ("org.deckos.note", "Note")):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(wid in shown)
            b.toggled.connect(lambda on, w=wid, t=text: self.apply(["deckos", "vibe", "widget", w, "on" if on else "off"],
                                                                  f"{t} {'on' if on else 'off'} the desktop"))
            toggles.append(b)
        name = label("Desktop widgets")
        name.setFixedWidth(140)
        vibes.body.addWidget(row(name, *toggles, button("Weather town…", slot=self.weather_town, icon="globe")))
        self.lay.addWidget(vibes)

        themes = Card("Theme", "Global theme", "appearance")
        themes.body.addWidget(label("Sets colours, wallpaper and the desktop layout's look in one go.", "sub"))
        self.theme_grid = QGridLayout()
        self.theme_grid.setSpacing(10)
        themes.body.addLayout(self.theme_grid)
        self.lay.addWidget(themes)

        accent = Card("Accent colour", "Buttons, highlights and selections", "drop")
        self.swatches = QButtonGroup(self)
        sw_row = QHBoxLayout()
        sw_row.setSpacing(10)
        for name, color in ACCENTS:
            b = QPushButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setFixedSize(30, 30)
            b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton#swatch {{ background: {color}; }}")
            b.clicked.connect(lambda _c, c=color, n=name: self.set_accent(c, n))
            self.swatches.addButton(b)
            sw_row.addWidget(b)
            if color.lower() == S.P.accent.lower():
                b.setChecked(True)
        custom = button("Custom…", slot=self.custom_accent, icon="drop",
                        tip="Any colour: buttons, highlights and the DecKoOS logos in every app follow it")
        sw_row.addWidget(custom)
        sw_row.addStretch(1)
        accent.body.addLayout(sw_row)
        self.lay.addWidget(accent)

        style = Card("Style", "How DecKoOS apps look", "sliders")
        style.body.addWidget(label("For DecKoOS's own apps: the Hub, Store, Welcome, Assistant and the rest.", "sub"))
        for key, title, options in (("logo", "Logo", (("gradient", "Gradient"), ("flat", "One colour"))),
                                    ("corners", "Corners", (("sharp", "Sharp"), ("default", "Default"),
                                                            ("round", "Round"))),
                                    ("text", "Text size", (("small", "Small"), ("normal", "Normal"),
                                                           ("large", "Large")))):
            group = QButtonGroup(self)
            buttons = []
            for value, text in options:
                b = QPushButton(text)
                b.setObjectName("seg")
                b.setCheckable(True)
                b.setChecked(S.STYLE[key] == value)
                b.clicked.connect(lambda _c, k=key, v=value: self.set_style(k, v))
                group.addButton(b)
                buttons.append(b)
            name = label(title)
            name.setFixedWidth(90)
            style.body.addWidget(row(name, *buttons))
        self.lay.addWidget(style)

        bar = Card("Taskbar", "Size, colours and motion", "panel-right")
        tb = sysinfo.taskbar_settings()
        size = "small" if 0 < tb["height"] <= 42 else "large" if tb["height"] >= 56 else "medium"

        def segs(title, options, current, slot):
            group = QButtonGroup(self)
            buttons = []
            for value, text in options:
                b = QPushButton(text)
                b.setObjectName("seg")
                b.setCheckable(True)
                b.setChecked(value == current)
                b.clicked.connect(lambda _c, v=value, t=text: slot(v, t))
                group.addButton(b)
                buttons.append(b)
            name = label(title)
            name.setFixedWidth(140)
            return row(name, *buttons)
        bar.body.addWidget(segs("Height", (("small", "Small"), ("medium", "Medium"), ("large", "Large")), size,
                                lambda v, t: self.apply(["deckos", "taskbar", "height", v], f"Taskbar: {t.lower()}")))
        bar.body.addWidget(segs("Colours", (("accent", "Accent"), ("vibe", "Vibe"), ("custom", "Custom…")),
                                tb["colorMode"], self.taskbar_colors))
        bar.body.addWidget(segs("Motion", (("on", "On"), ("off", "Off")), "on" if tb["motion"] else "off",
                                lambda v, t: self.apply(["deckos", "taskbar", "motion", v], f"Taskbar motion: {v}")))
        bar.body.addWidget(label("Your own colours stay when you change Vibes. Motion: the active app's light "
                                 "breathes and icons lift as you point at them.", "muted"))
        self.lay.addWidget(bar)

        sounds = Card("Sounds", "System sounds", "volume")
        sounds.body.addWidget(label("Notifications, devices, errors and logging in. DecKoOS's own: glass tones, "
                                    "with a bolted-plate accent for the bigger moments.", "sub"))
        group = QButtonGroup(self)
        now = sysinfo.sound_theme()
        buttons = []
        for value, text in (("deckos", "DecKoOS"), ("ocean", "Plasma (Ocean)"), ("off", "Off")):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(now == value)
            b.clicked.connect(lambda _c, v=value, t=text: self.set_sounds(v, t))
            group.addButton(b)
            buttons.append(b)
        sounds.body.addWidget(row(*buttons, button("Play a sample", slot=self.play_sample, icon="play")))
        self.lay.addWidget(sounds)

        walls = Card("Wallpaper", "Desktop background", "image")
        self.wall_grid = QGridLayout()
        self.wall_grid.setSpacing(10)
        walls.body.addLayout(self.wall_grid)
        self.walls_all = False
        self.walls_more = button("Show all", slot=self.toggle_walls, icon="grid")
        walls.body.addWidget(row(self.walls_more, button("Choose an image…", slot=self.pick_wallpaper, icon="folder")))
        self.lay.addWidget(walls)

        layouts = Card("Desktop layout", "Where the panels go", "panel-right")
        layouts.body.addWidget(label("Replaces your panels with the layout you pick. Desktop icons and widgets stay.",
                                     "sub"))
        self.layout_grid = QGridLayout()
        self.layout_grid.setSpacing(10)
        layouts.body.addLayout(self.layout_grid)
        layouts.body.addWidget(row(button("Add performance graphs", slot=lambda: self.apply(
            ["deckos", "layout", "graphs"], "Performance graphs added to your desktop"), icon="gauge",
            tip="Live processor, graphics, memory and network graphs on the desktop")))
        self.lay.addWidget(layouts)

        style = Card("Desktop style", "Panel, menus and icons", "display")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.plasma = QComboBox()
        self.plasma.addItem("DecKoOS", "deckos")
        self.plasma.addItem("Breeze", "default")
        self.plasma.setCurrentIndex(max(0, self.plasma.findData(sysinfo.current_plasma_style())))
        self.plasma.currentIndexChanged.connect(lambda _i: self.apply(
            ["plasma-apply-desktoptheme", self.plasma.currentData()], f"Plasma style: {self.plasma.currentText()}"))
        self.icons = QComboBox()
        for name, theme in (("DecKoOS", "DeckOS"), ("Papirus Dark", "Papirus-Dark"), ("Breeze Dark", "breeze-dark")):
            self.icons.addItem(name, theme)
        self.icons.setCurrentIndex(max(0, self.icons.findData(sysinfo.current_icons())))
        self.icons.currentIndexChanged.connect(lambda _i: self.apply(
            ["/usr/lib/plasma-changeicons", self.icons.currentData()], f"Icons: {self.icons.currentText()}"))
        grid.addWidget(label("Plasma style", "sub", wrap=False), 0, 0)
        grid.addWidget(self.plasma, 0, 1)
        grid.addWidget(label("Icons", "sub", wrap=False), 1, 0)
        grid.addWidget(self.icons, 1, 1)
        self.cursors = QComboBox()
        for name, theme in (("DecKoOS", "DeckOS-cursors"), ("Breeze", "breeze_cursors"), ("Breeze Light", "Breeze_Light")):
            self.cursors.addItem(name, theme)
        self.cursors.setCurrentIndex(max(0, self.cursors.findData(sysinfo.current_cursor())))
        self.cursors.currentIndexChanged.connect(lambda _i: self.apply(
            ["plasma-apply-cursortheme", self.cursors.currentData()], f"Mouse pointer: {self.cursors.currentText()}"))
        grid.addWidget(label("Mouse pointer", "sub", wrap=False), 2, 0)
        grid.addWidget(self.cursors, 2, 1)
        grid.setColumnStretch(2, 1)
        style.body.addLayout(grid)
        style.body.addWidget(label("DecKoOS icons draw the everyday apps and file types in the DecKoOS style, with "
                                   "Papirus for the rest. The login screen uses the DecKoOS theme.", "muted"))
        self.lay.addWidget(style)

        spotify = Card("Spotify", "The DecKoOS look for Spotify", "music")
        spotify.body.addWidget(label("Restyles the official Spotify app with Spicetify: DecKoOS colours, bordered panels "
                                     "and the gradient play buttons. Spotify updates undo it; apply it again after one.",
                                     "sub"))
        spotify.body.addWidget(row(button("Apply DecKoOS look", "primary", lambda: self.hub.terminal("deckos spotify theme"),
                                          icon="appearance"),
                                   button("Back to stock", slot=lambda: self.hub.terminal("deckos spotify restore"),
                                          icon="refresh")))
        self.lay.addWidget(spotify)

    def apply(self, cmd, done_text, after=None):
        """Runs cmd; after() (a refresh, so the "in use" mark moves) once it has finished."""
        if sysinfo.DEMO:
            self.hub.toast(done_text, "ok")
            after and after()
            return
        proc = QProcess(self)
        proc.finished.connect(lambda code, _s: (
            self.hub.toast(done_text if code == 0 else f"Couldn't apply that ({Path(cmd[0]).name} failed).",
                           "ok" if code == 0 else "warn"), after and after(), proc.deleteLater()))
        proc.errorOccurred.connect(lambda e: e == QProcess.FailedToStart and (
            self.hub.toast(f"Couldn't run {Path(cmd[0]).name}.", "warn"), proc.deleteLater()))
        proc.start(cmd[0], cmd[1:])

    def weather_town(self):
        from PySide6.QtWidgets import QInputDialog
        town, ok = QInputDialog.getText(self, "Weather", "Your town or city:", text=sysinfo.weather_place())
        if ok and town.strip():
            self.apply(["deckos", "vibe", "weather", town.strip()], f"Weather for {town.strip()}")

    def apply_vibe(self, key, name):
        self.demo_vibe = key
        args = ["deckos", "vibe", "off"] if key == "off" else ["deckos", "vibe", "apply", key]
        self.apply(args, f"Vibe: {name}", self.after_theme)

    def apply_theme(self, tid, name):
        self.demo_look = tid
        self.demo_wall = None
        self.apply(["deckos", "theme", "apply", tid], f"Theme: {name}", self.after_theme)

    def after_theme(self):
        # The Hub follows the theme's accent like the rest of the desktop
        accent = sysinfo.kconfig("kdeglobals", "General", "AccentColor")
        if re.fullmatch(r"\d+,\d+,\d+", accent):
            self.hub.set_accent("#{:02X}{:02X}{:02X}".format(*map(int, accent.split(","))))
        self.refresh()

    def apply_wallpaper(self, path, name):
        self.demo_wall = Path(path)
        self.apply(["deckos", "wallpaper", str(path)], f"Wallpaper: {name}", self.refresh)  # lock screen too

    def set_accent(self, color, name):
        self.apply(["deckos", "accent", "apply", color], f"Accent colour: {name}")
        self.hub.set_accent(color)

    def columns(self, small=False):
        """Tiles per row for the page's width: a narrow window or large text wraps them, never scrolls sideways."""
        return max(1, (self.width() - 110) // ((176 if small else 232) + 26))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "_cols", None) not in (None, (self.columns(), self.columns(True))):
            self.refresh()

    def refresh(self):
        self._cols = (self.columns(), self.columns(True))
        big, small = self._cols
        self.clear(self.vibe_grid)
        current = sysinfo.current_vibe()
        for i, (key, name, summary, preview) in enumerate(sysinfo.vibes()):
            self.vibe_grid.addWidget(self.preview_tile(preview, name, summary, key == current,
                                                       lambda k=key, n=name: self.apply_vibe(k, n), small=True),
                                     i // small, i % small, Qt.AlignTop)
        self.vibe_grid.setColumnStretch(small, 1)
        self.clear(self.theme_grid)
        demo = sysinfo.DEMO and hasattr(self, "demo_look")
        current = self.demo_look if demo else sysinfo.current_look()
        for i, (tid, name, desc, preview) in enumerate(sysinfo.look_and_feels()):
            self.theme_grid.addWidget(self.preview_tile(preview, name, desc, tid == current,
                                                        lambda t=tid, n=name: self.apply_theme(t, n)),
                                      i // big, i % big)
        self.theme_grid.setColumnStretch(big, 1)
        self.clear(self.wall_grid)
        walls = sysinfo.wallpapers()
        wall = getattr(self, "demo_wall", None) if sysinfo.DEMO else sysinfo.current_wallpaper()
        shown = walls if self.walls_all else walls[:12]
        for i, (path, name, preview) in enumerate(shown):
            self.wall_grid.addWidget(self.preview_tile(preview, name, "", wall is not None and path.name == wall.name,
                                                       lambda p=path, n=name: self.apply_wallpaper(p, n), small=True),
                                     i // small, i % small)
        self.wall_grid.setColumnStretch(small, 1)
        self.walls_more.setVisible(len(walls) > 12)
        self.walls_more.setText("Show fewer" if self.walls_all else f"Show all {len(walls)}")
        self.clear(self.layout_grid)
        for i, (key, name, desc, preview) in enumerate(sysinfo.desktop_layouts()):
            self.layout_grid.addWidget(self.preview_tile(preview, name, desc, False,
                                                         lambda k=key, n=name: self.set_layout(k, n), small=True),
                                       i // small, i % small)
        self.layout_grid.setColumnStretch(small, 1)

    def toggle_walls(self):
        self.walls_all = not self.walls_all
        self.refresh()

    def set_layout(self, key, name):
        if QMessageBox.question(self, "Change the desktop layout?",
                                f"Your panels will be replaced with the {name} layout. Desktop icons and widgets "
                                "stay. You can switch back any time.") != QMessageBox.Yes:
            return
        self.apply(["deckos", "layout", "set", key], f"Desktop layout: {name}")

    @staticmethod
    def preview_tile(preview, name, desc, current, slot, small=False):
        t = QFrame()
        t.setObjectName("tile")
        t.setAttribute(Qt.WA_StyledBackground, True)
        t.setCursor(Qt.PointingHandCursor)
        t.setProperty("picked", current)
        t.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        v = QVBoxLayout(t)
        v.setContentsMargins(8, 8, 8, 10)
        v.setSpacing(6)
        w, h = (176, 99) if small else (232, 130)
        img = QLabel()
        img.setFixedSize(w, h)
        pm = QPixmap(str(preview)) if preview else QPixmap()
        if pm.isNull():
            img.setStyleSheet(f"background: {S.RAISED}; border-radius: 6px;")
        else:
            img.setPixmap(pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation).copy(0, 0, w, h))
        v.addWidget(img)
        title = label(f"<b>{name}</b>" + (f" &nbsp;<span style='color:{S.P.accent}'>in use</span>" if current else ""))
        title.setMaximumWidth(w)  # long names wrap instead of widening the tile
        v.addWidget(title)
        if desc:
            d = label(desc, "muted")
            d.setMaximumWidth(w)
            v.addWidget(d)
        t.mousePressEvent = lambda _e: slot()
        return t

    def pick_wallpaper(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a wallpaper", str(Path.home() / "Pictures"),
                                              "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.apply_wallpaper(path, Path(path).name)
