"""DeckOS Hub — one window for the things DeckOS adds: the display fix, drives, Gaming Mode, AI tools.

Same visual language as Steady Downloader: slate background, rounded 10px cards with a
1px border, Inter type, one blue accent and the blue-violet gradient for the brand tile.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

BRANDING = Path(os.environ.get("DECKOS_BRANDING", "/usr/share/deckos/branding"))
USER_GAMING_CONF = Path.home() / ".config/deckos/gaming.conf"

BG, SURFACE, BORDER, HOVER, PRESSED = "#0F1115", "#171A21", "#262B36", "#2A2F3B", "#353B49"
TEXT, SUBTEXT, MUTED = "#E8EAF0", "#8C94A6", "#5A6172"
ACCENT, ACCENT_HOVER = "#4C8DFF", "#6AA2FF"
GRAD_A, GRAD_B = "#4C8DFF", "#7A5CFF"  # brand tile gradient
SUCCESS, WARNING, DANGER = "#3DD68C", "#F5B84B", "#FF6B6B"

QSS = f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: "Inter", "Noto Sans"; font-size: 10pt; }}
#root {{ background: {BG}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; border: none; }}
QLabel#title {{ font-family: "Inter Display", "Inter"; font-size: 16.5pt; font-weight: 600; }}
QLabel#sub {{ color: {SUBTEXT}; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 600; }}
QLabel#cardKicker {{ color: {SUBTEXT}; font-size: 8.5pt; font-weight: 600; }}
QLabel#value {{ color: {SUBTEXT}; font-size: 9.5pt; }}
#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#card QLabel, #card QCheckBox {{ background: transparent; }}
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 12px; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {PRESSED}; }}
QPushButton#primary {{ color: white; font-weight: 600; border: none; padding: 8px 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {GRAD_A}, stop:1 {GRAD_B}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_HOVER}, stop:1 #8E75FF); }}
QPushButton#primary:pressed {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {GRAD_A}, stop:1 {GRAD_B}); }}
#stat {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#stat QLabel {{ background: transparent; }}
QLabel#statName {{ color: {SUBTEXT}; font-size: 8pt; font-weight: 600; }}
QLabel#statValue {{ font-family: "Inter Display", "Inter"; font-size: 15pt; font-weight: 600; }}
QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 10px; }}
QComboBox:hover {{ background: {HOVER}; }}
QComboBox QAbstractItemView {{ background: #22262F; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QToolTip {{ background: #22262F; color: {TEXT}; border: 1px solid {BORDER}; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {HOVER}; border-radius: 4px; margin: 2px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

LEVELS = [
    ("0 · Stock", "AMD defaults, no workarounds."),
    ("1 · No FAMS","Turns off firmware-assisted memory-clock switching — the usual cause of 1–2 s blackouts."),
    ("2 · Pinned VRAM clock", "Level 1 + VRAM clock locked to max at boot. A little more idle power."),
    ("3 · No multi-monitor switching", "Level 2 + no multi-monitor clock switching, PSR or Panel Replay."),
    ("4 · Locked high", "Every GPU clock forced high. Last resort; most idle power and heat."),
]


def run(cmd, timeout=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def terminal(command):
    """Runs a command in Konsole and keeps the window open so the output can be read."""
    QProcess.startDetached("konsole", ["--hold", "-e", "bash", "-lc", command])


def privileged(args):
    QProcess.startDetached("pkexec", ["/usr/bin/deckos", *args])


class Card(QFrame):
    """A Steady Downloader card: surface fill, 1px border, 10px radius, title + muted kicker."""

    def __init__(self, kicker, title):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(8)
        k = QLabel(kicker.upper())
        k.setObjectName("cardKicker")
        h = QLabel(title)
        h.setObjectName("cardTitle")
        lay.addWidget(k)
        lay.addWidget(h)
        lay.addSpacing(2)
        self.body = lay


class Meter(QWidget):
    """4px rounded track with a blue-violet fill; value is 0..1."""

    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(4)

    def set(self, v):
        self.value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.rect()
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(r, 2, 2)
        if self.value > 0:
            g = QLinearGradient(0, 0, r.width(), 0)
            g.setColorAt(0, QColor(GRAD_A))
            g.setColorAt(1, QColor(GRAD_B))
            p.setBrush(g)
            p.drawRoundedRect(0, 0, max(4, int(r.width() * self.value)), r.height(), 2, 2)


def label(text, cls=None, wrap=True):
    l = QLabel(text)
    l.setWordWrap(wrap)
    if cls:
        l.setObjectName(cls)
    return l


def button(text, primary=False, tip=None, slot=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    if primary:
        b.setObjectName("primary")
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    return b


def row(*widgets, stretch_first=False):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    if not stretch_first:
        h.addStretch(0)
    for x in widgets:
        h.addWidget(x)
    h.addStretch(1)
    return w


def read_conf(path):
    out = {}
    try:
        for line in Path(path).read_text().splitlines():
            m = re.match(r"\s*([A-Z_]+)=(.*)", line)
            if m:
                out[m.group(1)] = m.group(2).strip().strip('"')
    except OSError:
        pass
    return out


def write_user_gaming(key, value):
    conf = read_conf(USER_GAMING_CONF)
    conf[key] = value
    USER_GAMING_CONF.parent.mkdir(parents=True, exist_ok=True)
    USER_GAMING_CONF.write_text("# Written by DeckOS Hub\n" + "".join(f"{k}={v}\n" for k, v in conf.items()))


class Hub(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("DeckOS Hub")
        self.setWindowIcon(QIcon.fromTheme("deckos", QIcon(str(BRANDING / "logo.svg"))))
        self.resize(980, 760)
        self.setMinimumSize(640, 480)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        page = QWidget()
        scroll.setWidget(page)
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 20, 24, 16)
        v.setSpacing(18)

        head = QHBoxLayout()
        tile = QSvgWidget(str(BRANDING / "logo.svg"))
        tile.setFixedSize(44, 44)
        head.addWidget(tile)
        head.addSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.addWidget(label("DeckOS Hub", "title"))
        titles.addWidget(label("Display fix, Gaming Mode, drives, AI tools and updates — tuned for your 7800X3D + RX 9070 XT.", "sub"))
        head.addLayout(titles, 1)
        v.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stats = {}
        for key, name in (("gpu_temp", "GPU"), ("vram", "VRAM CLOCK"), ("gpu_power", "GPU POWER"),
                          ("cpu_temp", "CPU"), ("ram", "MEMORY")):
            chip = QFrame()
            chip.setObjectName("stat")
            chip.setAttribute(Qt.WA_StyledBackground, True)
            cl = QVBoxLayout(chip)
            cl.setContentsMargins(14, 10, 14, 10)
            cl.setSpacing(0)
            cl.addWidget(label(name, "statName"))
            val = label("—", "statValue", wrap=False)
            cl.addWidget(val)
            bar = Meter()
            cl.addSpacing(6)
            cl.addWidget(bar)
            self.stats[key] = (val, bar)
            stats.addWidget(chip, 1)
        v.addLayout(stats)

        grid = QGridLayout()
        grid.setSpacing(12)
        cards = [(self.display_plate(), 0, 0, 1, 1), (self.gaming_plate(), 0, 1, 1, 1), (self.drives_plate(), 1, 0, 1, 1),
                 (self.ai_plate(), 1, 1, 1, 1), (self.system_plate(), 2, 0, 1, 2)]
        for card, r, c, rs, cs in cards:
            card.body.addStretch(1)  # keep content at the top when a neighbour is taller
            grid.addWidget(card, r, c, rs, cs)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)
        v.addStretch(1)

        self.status = label("", "sub")
        v.addWidget(self.status)

        self.refresh()
        timer = QTimer(self)
        timer.timeout.connect(self.refresh_live)
        timer.start(2000)

    # ---- plates

    def display_plate(self):
        p = Card("Display", "Blackout fix")
        p.body.addWidget(label("If a screen flashes black for a second or two, step up one level, reboot, and use it "
                               "for a while. Higher levels trade a little idle power for stability.", "sub"))
        self.level_box = QComboBox()
        for name, _ in LEVELS:
            self.level_box.addItem(name)
        self.level_box.currentIndexChanged.connect(lambda i: self.level_desc.setText(LEVELS[i][1]))
        self.level_desc = label("", "sub")
        p.body.addWidget(row(self.level_box, button("Apply", True, "Needs your password, then a reboot", self.apply_level)))
        p.body.addWidget(self.level_desc)
        self.display_live = label("", "value")
        p.body.addWidget(self.display_live)
        p.body.addWidget(row(button("Watch for blackouts…", tip="Logs GPU clock + display events; press Enter when it blinks",
                                    slot=lambda: terminal("deckos display watch")),
                             button("Monitors", slot=lambda: terminal("deckos display status"))))
        return p

    def gaming_plate(self):
        p = Card("Gaming", "Steam Gaming Mode")
        installed = shutil.which("gamescope-session-plus") is not None
        p.body.addWidget(label("Console-style Steam Big Picture, full screen. "
                               "Use Steam’s Power menu › Switch to Desktop to come back." if installed else
                               "Gaming wasn’t picked when DeckOS was installed. To add it: sudo pacman -S steam "
                               "gamescope gamescope-session-git, then paru -S gamescope-session-steam-git.", "sub"))
        switch = button("Switch to Gaming Mode", True, slot=self.to_gaming)
        switch.setEnabled(installed)
        p.body.addWidget(row(switch))
        conf = {**read_conf("/etc/deckos/gaming.conf"), **read_conf(USER_GAMING_CONF)}
        self.vrr = QCheckBox("Variable refresh rate (FreeSync)")
        self.vrr.setChecked(conf.get("ADAPTIVE_SYNC") == "1")
        self.vrr.toggled.connect(lambda on: self.set_gaming("ADAPTIVE_SYNC", on))
        self.hdr = QCheckBox("HDR")
        self.hdr.setChecked(conf.get("ENABLE_GAMESCOPE_HDR") == "1")
        self.hdr.toggled.connect(lambda on: self.set_gaming("ENABLE_GAMESCOPE_HDR", on))
        p.body.addWidget(self.vrr)
        p.body.addWidget(self.hdr)
        p.body.addWidget(row(button("Fix Steam libraries on NTFS", tip="Moves Proton prefixes off NTFS so Windows games run",
                                    slot=lambda: terminal("deckos steam-ntfs")),
                             button("LACT (GPU)", slot=lambda: QProcess.startDetached("lact", ["gui"]))))
        return p

    def drives_plate(self):
        p = Card("Drives", "Your Windows drives")
        p.body.addWidget(label("NTFS drives from Windows mount read/write with the kernel’s ntfs3 driver — nothing "
                               "was reformatted. If one shows read-only, Windows Fast Startup is on.", "sub"))
        self.drive_list = QVBoxLayout()
        self.drive_list.setSpacing(4)
        holder = QWidget()
        holder.setLayout(self.drive_list)
        p.body.addWidget(holder)
        p.body.addWidget(row(button("Rescan drives", tip="Adds new NTFS drives to /etc/fstab", slot=lambda: privileged(["drives", "rescan"])),
                             button("Diagnose", slot=lambda: terminal("deckos drives doctor")),
                             button("Open in Dolphin", slot=lambda: QProcess.startDetached("dolphin", ["/mnt"]))))
        return p

    def ai_plate(self):
        p = Card("AI and development", "Claude Code, local models, tools")
        self.ai_live = label("", "value")
        p.body.addWidget(self.ai_live)
        p.body.addWidget(row(button("Install / update Claude Code", True,
                                    slot=lambda: terminal("curl -fsSL https://claude.ai/install.sh | bash")),
                             button("Terminal", slot=lambda: QProcess.startDetached("konsole", []))))
        ollama = button("Start Ollama", slot=lambda: terminal("sudo systemctl enable --now ollama && ollama list"))
        rocm = button("GPU compute check", slot=lambda: terminal("rocminfo | grep -E 'Marketing|gfx' | head -n 6"))
        ollama.setEnabled(shutil.which("ollama") is not None)
        rocm.setEnabled(shutil.which("rocminfo") is not None)
        p.body.addWidget(row(ollama, rocm))
        return p

    def system_plate(self):
        p = Card("System", "Updates and snapshots")
        p.body.addWidget(label("Updates take a btrfs snapshot first. If an update breaks something, pick "
                               "“DeckOS snapshots” in the boot menu to start the previous state.", "sub"))
        p.body.addWidget(row(button("Update everything", True, slot=lambda: terminal("deckos update")),
                             button("Health check", slot=lambda: terminal("deckos doctor")),
                             button("Snapshots", slot=lambda: terminal("sudo snapper -c root list"))))
        return p

    # ---- actions

    def apply_level(self):
        n = self.level_box.currentIndex()
        privileged(["display", "set", str(n)])
        self.status.setText(f"Display fix level {n} requested — reboot once it’s saved.")

    def to_gaming(self):
        r = QMessageBox.question(self, "Gaming Mode", "Switch to Gaming Mode?\n\nOpen apps will close — save your work first.")
        if r == QMessageBox.Yes:
            QProcess.startDetached("sudo", ["-n", "/usr/lib/deckos/session-switch", "gaming", "--delay", "1"])

    def set_gaming(self, key, on):
        write_user_gaming(key, "1" if on else "0")
        self.status.setText("Saved — takes effect next time you enter Gaming Mode.")

    # ---- state

    def refresh(self):
        level = read_conf("/etc/deckos/display.conf").get("LEVEL", "0")
        idx = int(level) if level.isdigit() and int(level) < len(LEVELS) else 0
        self.level_box.setCurrentIndex(idx)
        self.level_desc.setText(LEVELS[idx][1])
        self.refresh_drives()
        self.refresh_live()

    def refresh_drives(self):
        while self.drive_list.count():
            w = self.drive_list.takeAt(0).widget()
            if w:
                w.deleteLater()
        data = run(["findmnt", "-J", "-t", "ntfs3,fuseblk,exfat,vfat", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS,LABEL"])
        mounts = [m for m in json.loads(data or '{"filesystems": []}').get("filesystems", []) if m["target"].startswith(("/mnt", "/run/media"))]
        if not mounts:
            self.drive_list.addWidget(label("No NTFS drives mounted yet.", "sub"))
        for m in mounts:
            ro = ",ro," in f",{m['options']},"
            try:
                u = shutil.disk_usage(m["target"])
                use = f"{u.used / 1e12:.2f} / {u.total / 1e12:.2f} TB" if u.total > 1e12 else f"{u.used / 1e9:.0f} / {u.total / 1e9:.0f} GB"
            except OSError:
                use = ""
            dot = f'<span style="color:{WARNING if ro else SUCCESS}">●</span>'
            note = f' <span style="color:{WARNING}">read-only</span>' if ro else ""
            self.drive_list.addWidget(label(f'{dot}&nbsp; <b>{m["target"]}</b>&nbsp; <span style="color:{SUBTEXT}">{use}</span>{note}'))

    def refresh_stats(self, dev):
        def read(path):
            try:
                return Path(path).read_text().strip()
            except OSError:
                return ""

        def show(key, text, frac):
            val, bar = self.stats[key]
            val.setText(text)
            bar.set(frac)

        if dev:
            hw = next(iter(sorted((dev / "hwmon").glob("hwmon*"))), None)
            t = read(hw / "temp1_input") if hw else ""
            show("gpu_temp", f"{int(t) / 1000:.0f}°C" if t else "—", int(t) / 1000 / 100 if t else 0)
            w = read(hw / "power1_average") or read(hw / "power1_input") if hw else ""
            show("gpu_power", f"{int(w) / 1e6:.0f} W" if w else "—", int(w) / 1e6 / 340 if w else 0)
            lines = read(dev / "pp_dpm_mclk").splitlines()
            cur = next((l for l in lines if "*" in l), "")
            mhz = re.search(r"(\d+)\s*Mhz", cur, re.I)
            top = re.search(r"(\d+)\s*Mhz", lines[-1], re.I) if lines else None
            show("vram", f"{mhz.group(1)} MHz" if mhz else "—",
                 int(mhz.group(1)) / int(top.group(1)) if mhz and top else 0)
        cpu = ""
        for hw in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
            if read(hw / "name") == "k10temp":
                cpu = read(hw / "temp1_input")
        show("cpu_temp", f"{int(cpu) / 1000:.0f}°C" if cpu else "—", int(cpu) / 1000 / 95 if cpu else 0)
        mem = dict(re.findall(r"(\w+):\s+(\d+)", read("/proc/meminfo")))
        if "MemTotal" in mem:
            used = (int(mem["MemTotal"]) - int(mem.get("MemAvailable", 0))) / 1048576
            total = int(mem["MemTotal"]) / 1048576
            show("ram", f"{used:.1f} / {total:.0f} GB", used / total)
        else:
            show("ram", "—", 0)

    def refresh_live(self):
        card = run(["bash", "-c", "for c in /sys/class/drm/card[0-9]; do [ \"$(cat $c/device/device)\" = 0x7550 ] && echo $c; done"]).splitlines()
        self.refresh_stats(Path(card[0]) / "device" if card else None)
        if card:
            dev = Path(card[0]) / "device"
            try:
                mclk = next((l for l in (dev / "pp_dpm_mclk").read_text().splitlines() if "*" in l), "?")
                perf = (dev / "power_dpm_force_performance_level").read_text().strip()
                temp = ""
                for h in (dev / "hwmon").glob("hwmon*/temp1_input"):
                    temp = f"   {int(h.read_text()) / 1000:.0f}°C"
                self.display_live.setText(f"RX 9070 XT   VRAM {mclk.split(':')[-1].strip(' *')}   mode {perf}{temp}")
            except OSError:
                self.display_live.setText("RX 9070 XT")
        else:
            self.display_live.setText("RX 9070 XT not detected")
        claude = shutil.which("claude") or (Path.home() / ".local/bin/claude").exists()
        ollama = run(["systemctl", "is-active", "ollama"]) == "active"
        ok = lambda b: f'<span style="color:{SUCCESS if b else MUTED}">●</span>'
        self.ai_live.setText(f"{ok(claude)} Claude Code&nbsp;&nbsp; {ok(ollama)} Ollama (ROCm)&nbsp;&nbsp; "
                             f"{ok(shutil.which('code'))} VS Code&nbsp;&nbsp; {ok(shutil.which('docker'))} Docker")
        self.ai_live.setTextFormat(Qt.RichText)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DeckOS Hub")
    app.setDesktopFileName("deckos-hub")
    app.setStyleSheet(QSS)
    f = QFont("Inter", 10)
    app.setFont(f)
    w = Hub()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
