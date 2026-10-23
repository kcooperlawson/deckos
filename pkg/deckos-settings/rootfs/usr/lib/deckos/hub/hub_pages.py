"""DeckOS Hub pages. Each page builds once; `refresh()` runs when it's shown, `tick(stats)` every
two seconds while it's on screen."""
import re
import shlex
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

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
        self.head_actions.addWidget(button("Gaming Mode", "primary", self.hub.to_gaming, icon="play"))

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
                                 button("Terminal", slot=lambda: QProcess.startDetached("konsole", []), icon="terminal"),
                                 button("Health check", slot=lambda: self.hub.terminal("deckos doctor"), icon="check"),
                                 button("Files", slot=lambda: QProcess.startDetached("dolphin", []), icon="folder"),
                                 button("Welcome tour", slot=lambda: QProcess.startDetached("deckos-welcome", []),
                                        icon="star", tip="DeckOS Welcome: the first-login setup, again")))
        self.lay.addWidget(quick)

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

        gpu = Card("Graphics", self.hub.gpu.name, "gpu")
        self.gpu_live = label("", "mono")
        gpu.body.addWidget(self.gpu_live)
        self.monitor_box = QVBoxLayout()
        self.monitor_box.setSpacing(6)
        gpu.body.addLayout(self.monitor_box)
        gpu.body.addWidget(row(button("Watch for blackouts", slot=lambda: self.hub.terminal("deckos display watch"),
                                      icon="eye", tip="Logs clock and display events; press Enter when it blinks"),
                               button("Display status", slot=lambda: self.hub.terminal("deckos display status"),
                                      icon="info")))
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

RESOLUTIONS = ["3840x2160", "3440x1440", "2560x1440", "2560x1080", "1920x1080"]
RATES = ["60", "100", "120", "144", "165", "240"]


class GamingPage(Page):
    title = "Gaming"
    subtitle = "Steam Gaming Mode: Big Picture full screen, like a Steam Deck."

    def build(self):
        if not sysinfo.installed("gamescope-session-plus"):
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
        self.vrr = QCheckBox("Variable refresh rate (FreeSync)")
        self.vrr.setChecked(conf.get("ADAPTIVE_SYNC") == "1")
        self.vrr.toggled.connect(lambda on: self.save("ADAPTIVE_SYNC", "1" if on else "0"))
        self.hdr = QCheckBox("HDR (turn it on in the monitor's menu too)")
        self.hdr.setChecked(conf.get("ENABLE_GAMESCOPE_HDR") == "1")
        self.hdr.toggled.connect(lambda on: self.save("ENABLE_GAMESCOPE_HDR", "1" if on else "0"))
        settings.body.addWidget(self.vrr)
        settings.body.addWidget(self.hdr)
        settings.body.addWidget(label("If a screen flickers with VRR on, turn it off; some monitors (the Samsung "
                                      "Odyssey G7 among them) blink with it.", "muted"))
        self.lay.addWidget(settings)

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
        self.head_actions.addWidget(button("Open in Files", slot=lambda: QProcess.startDetached("dolphin", ["/mnt"]),
                                           icon="folder"))
        self.card = Card("Mounted", "Drives", "drives")
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        self.card.body.addLayout(self.list)
        self.lay.addWidget(self.card)
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
            button("Open terminal", slot=lambda: QProcess.startDetached("konsole", []), icon="terminal")))
        self.lay.addWidget(claude)

        self.ollama_card = Card("Local AI", "Ollama on your graphics card", "ai")
        if ai:
            self.ollama_state = label("", "sub")
            self.ollama_card.body.addWidget(self.ollama_state)
            self.models = QVBoxLayout()
            self.models.setSpacing(6)
            self.ollama_card.body.addLayout(self.models)
            self.toggle = button("Start", slot=self.toggle_ollama, icon="play")
            self.ollama_card.body.addWidget(row(
                self.toggle, button("Try a model", slot=lambda: self.hub.terminal("ollama run qwen3"), icon="ai"),
                button("GPU compute check", slot=lambda: self.hub.terminal(
                    "rocminfo | grep -E 'Marketing|gfx' | head -n 6"), icon="gpu")))
        else:
            self.ollama_card.body.addWidget(Empty("ai", "Local AI isn't installed",
                                                  "Ollama with ROCm runs models on a Radeon RX 7000 / 9000.",
                                                  button("Add Local AI", "primary", lambda: self.hub.add_group("ai"),
                                                         icon="plus")))
        self.lay.addWidget(self.ollama_card)

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

    def show_models(self, out, code):
        rows = [ln.split() for ln in out.splitlines()[1:] if ln.strip()]
        if not rows:
            self.models.addWidget(label("No models yet. “Try a model” downloads one.", "muted"))
        for r in rows:
            size_ = " ".join(r[2:4]) if len(r) > 3 else ""
            self.models.addWidget(RowItem("ai", r[0], size_))


# ------------------------------------------------------------------ system

class SystemPage(Page):
    title = "System"
    subtitle = "Updates, snapshots, firewall and software."

    def build(self):
        self.head_actions.addWidget(button("Health check", slot=lambda: self.hub.terminal("deckos doctor"),
                                           icon="check"))
        up = Card("Updates", "Keep DeckOS current", "update")
        self.up_state = label("Checking…", "cardTitle")
        self.up_detail = label("", "sub")
        up.body.addWidget(self.up_state)
        up.body.addWidget(self.up_detail)
        self.channel = label("", "muted")
        up.body.addWidget(self.channel)
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
                             tip="Arch, CachyOS and Flatpak apps; a snapshot is taken first")
        self.up_btn.setEnabled(False)
        up.body.addWidget(row(self.up_btn,
                              button("Check again", slot=self.check_updates, icon="refresh"),
                              button("Full update in terminal", slot=lambda: self.hub.terminal("deckos update"),
                                     icon="terminal", tip="Includes AUR apps (paru)")))
        self.lay.addWidget(up)

        snaps = Card("System snapshots", "Roll back a bad update", "snapshot")
        snaps.body.addWidget(label("A snapshot is taken before and after every update. To go back, restart and pick "
                                   "<b>DeckOS snapshots</b> in the boot menu, then the one from before the problem.",
                                   "sub"))
        self.snap_list = QVBoxLayout()
        self.snap_list.setSpacing(6)
        snaps.body.addLayout(self.snap_list)
        self.lay.addWidget(snaps)

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

        sw = Card("Software", "Add what you skipped at install", "package")
        sw.actions.addWidget(button("Open DeckOS Store", slot=lambda: QProcess.startDetached("deckos-store", []),
                                    icon="store", tip="Every app from Arch, CachyOS, Flathub and the AUR"))
        self.sw_list = QVBoxLayout()
        self.sw_list.setSpacing(6)
        sw.body.addLayout(self.sw_list)
        self.lay.addWidget(sw)
        self.updating = None

    def refresh(self):
        self.check_updates()
        self.channel.setText(
            "DeckOS's own updates (the Hub, tools, themes) come from the signed DeckOS repo." if
            sysinfo.update_channel_on() else
            f"<span style='color:{S.WARNING}'>DeckOS's own updates aren't set up yet.</span> Run "
            "<b>deckos dev-install</b> once from a DeckOS checkout, or install a newer deckos-settings.")
        self.hub.data.snapshots(self.show_snapshots)
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
        self.hub.data.updates(self.show_updates, fresh=True)

    def show_updates(self, n, aur, err):
        if err:
            self.up_state.setText("Couldn't check for updates")
            self.up_detail.setText(err)
        elif n + aur == 0:
            self.up_state.setText("Everything is up to date")
            self.up_detail.setText("Arch, CachyOS and AUR packages.")
        else:
            self.up_state.setText(f"{n + aur} update{'s' if n + aur != 1 else ''} waiting")
            self.up_detail.setText(f"{n} from Arch and CachyOS" + (f", {aur} from the AUR (update those in the "
                                                                   "terminal)" if aur else "") + ".")
        self.up_btn.setEnabled(n > 0 and not err)

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
        self.up_detail.setText("Keep DeckOS running until this finishes.")
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
            self.hub.toast("DeckOS is up to date. Restart if the kernel was updated.", "ok", 7000)
        elif code in (126, 127):
            self.hub.toast("Update cancelled.", "warn")
        else:
            self.hub.toast("The update stopped with an error; see the log.", "bad", 7000)
        self.hub.data.invalidate()
        self.check_updates()
        self.hub.data.snapshots(self.show_snapshots, fresh=True)

    def show_snapshots(self, snaps):
        self.clear(self.snap_list)
        if snaps is None:
            self.snap_list.addWidget(label("Couldn't read the snapshot list (snapper).", "muted"))
            return
        if not snaps:
            self.snap_list.addWidget(label("No snapshots yet.", "muted"))
        for num, date, desc, important in snaps[:8]:
            right = [label(f"<span style='color:{S.P.accent}'>kept</span>", wrap=False)] if important else []
            self.snap_list.addWidget(RowItem("snapshot", desc or "Snapshot", f"#{num}  ·  {date}", right=right))
        if len(snaps) > 8:
            self.snap_list.addWidget(label(f"…and {len(snaps) - 8} older.", "muted"))

    def show_home(self):
        self.clear(self.home_box)
        self.clear(self.home_buttons)
        if sysinfo.home_snapshots_on():
            self.home_snap_row = RowItem("snapshot", "Hourly snapshots of /home", "Checking…", S.SUCCESS)
            self.home_box.addWidget(self.home_snap_row)
            self.hub.data.snapshots(self.show_home_snapshots, config="home")
            self.home_buttons.addWidget(button("Browse snapshots", slot=lambda: QProcess.startDetached(
                "dolphin", ["/home/.snapshots"]), icon="folder"))
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

ACCENTS = [("DeckOS blue", "#4C8DFF"), ("Violet", "#7A5CFF"), ("Teal", "#22C7B8"), ("Green", "#3DD68C"),
           ("Amber", "#F5B84B"), ("Orange", "#FF7A45"), ("Red", "#FF5C7A"), ("Pink", "#E86BD8")]


class AppearancePage(Page):
    title = "Appearance"
    subtitle = "Theme, accent colour, wallpaper and desktop style."

    def build(self):
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
        sw_row.addStretch(1)
        accent.body.addLayout(sw_row)
        self.lay.addWidget(accent)

        walls = Card("Wallpaper", "Desktop background", "image")
        self.wall_grid = QGridLayout()
        self.wall_grid.setSpacing(10)
        walls.body.addLayout(self.wall_grid)
        walls.body.addWidget(row(button("Choose an image…", slot=self.pick_wallpaper, icon="folder")))
        self.lay.addWidget(walls)

        style = Card("Desktop style", "Panel, menus and icons", "display")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.plasma = QComboBox()
        self.plasma.addItem("DeckOS", "deckos")
        self.plasma.addItem("Breeze", "default")
        self.plasma.setCurrentIndex(max(0, self.plasma.findData(sysinfo.current_plasma_style())))
        self.plasma.currentIndexChanged.connect(lambda _i: self.apply(
            ["plasma-apply-desktoptheme", self.plasma.currentData()], f"Plasma style: {self.plasma.currentText()}"))
        self.icons = QComboBox()
        for name, theme in (("DeckOS", "DeckOS"), ("Papirus Dark", "Papirus-Dark"), ("Breeze Dark", "breeze-dark")):
            self.icons.addItem(name, theme)
        self.icons.setCurrentIndex(max(0, self.icons.findData(sysinfo.current_icons())))
        self.icons.currentIndexChanged.connect(lambda _i: self.apply(
            ["/usr/lib/plasma-changeicons", self.icons.currentData()], f"Icons: {self.icons.currentText()}"))
        grid.addWidget(label("Plasma style", "sub", wrap=False), 0, 0)
        grid.addWidget(self.plasma, 0, 1)
        grid.addWidget(label("Icons", "sub", wrap=False), 1, 0)
        grid.addWidget(self.icons, 1, 1)
        grid.setColumnStretch(2, 1)
        style.body.addLayout(grid)
        style.body.addWidget(label("DeckOS icons are Papirus with folders in the DeckOS blue. The login screen uses the "
                                   "DeckOS theme.", "muted"))
        self.lay.addWidget(style)

        spotify = Card("Spotify", "The DeckOS look for Spotify", "music")
        spotify.body.addWidget(label("Restyles the official Spotify app with Spicetify: DeckOS colours, bordered panels "
                                     "and the gradient play buttons. Spotify updates undo it; apply it again after one.",
                                     "sub"))
        spotify.body.addWidget(row(button("Apply DeckOS look", "primary", lambda: self.hub.terminal("deckos spotify theme"),
                                          icon="appearance"),
                                   button("Back to stock", slot=lambda: self.hub.terminal("deckos spotify restore"),
                                          icon="refresh")))
        self.lay.addWidget(spotify)

    def apply(self, cmd, done_text):
        if sysinfo.DEMO:
            self.hub.toast(done_text, "ok")
            return
        ok = QProcess.startDetached(cmd[0], cmd[1:])
        self.hub.toast(done_text if ok else f"Couldn't run {Path(cmd[0]).name}.", "ok" if ok else "warn")

    def set_accent(self, color, name):
        self.apply(["plasma-apply-colorscheme", "--accent-color", color], f"Accent colour: {name}")
        self.hub.set_accent(color)

    def refresh(self):
        self.clear(self.theme_grid)
        current = sysinfo.current_look()
        for i, (tid, name, desc, preview) in enumerate(sysinfo.look_and_feels()):
            self.theme_grid.addWidget(self.preview_tile(preview, name, desc, tid == current,
                                                        lambda t=tid, n=name: self.apply(
                                                            ["plasma-apply-lookandfeel", "--apply", t], f"Theme: {n}")),
                                      0, i)
        self.theme_grid.setColumnStretch(4, 1)
        self.clear(self.wall_grid)
        for i, (path, name, preview) in enumerate(sysinfo.wallpapers()[:8]):
            self.wall_grid.addWidget(self.preview_tile(preview, name, "", False, lambda p=path, n=name: self.apply(
                ["plasma-apply-wallpaperimage", str(p)], f"Wallpaper: {n}"), small=True), i // 4, i % 4)
        self.wall_grid.setColumnStretch(4, 1)

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
        v.addWidget(label(f"<b>{name}</b>" + (f" &nbsp;<span style='color:{S.P.accent}'>in use</span>" if current
                                              else ""), wrap=False))
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
            self.apply(["plasma-apply-wallpaperimage", path], f"Wallpaper: {Path(path).name}")
