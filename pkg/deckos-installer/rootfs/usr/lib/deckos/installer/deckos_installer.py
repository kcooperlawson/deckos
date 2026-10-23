"""DeckOS Installer — the graphical front end of deckos-install.

Runs as the live user like any other app (no root GUI, so it opens on the Wayland desktop),
collects the answers, then runs `sudo deckos-install` in its unattended mode (DECKOS_GUI=1)
and turns its output into a progress view. The install itself is the same script as the
text installer, so both behave identically.

Same visual language as DeckOS Hub and Steady Downloader: slate surfaces, 1px borders,
10px radii, Inter, and the blue-violet gradient on primary actions and progress.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QTextCursor
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QRadioButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

BRANDING = Path(os.environ.get("DECKOS_BRANDING", "/usr/share/deckos/branding"))
INSTALLER = os.environ.get("DECKOS_INSTALLER", "/usr/local/bin/deckos-install")
INSTALL_LOG = "/var/log/deckos-install.log"
DEFAULT_TZ = "America/New_York"
DEFAULT_LOCALE, DEFAULT_KEYMAP = "en_US.UTF-8", "us"
DEMO = "--demo" in sys.argv  # canned disks and a fake install, for working on the UI anywhere
# deckos-install's files on the USB (language and keyboard tables); the repo itself in demo mode.
SRC = Path(os.environ.get("DECKOS_SRC", "/opt/deckos"))
if not (SRC / "installer").is_dir():
    SRC = Path(__file__).resolve().parents[7]

BG, SURFACE, BORDER, HOVER, PRESSED = "#0F1115", "#171A21", "#262B36", "#2A2F3B", "#353B49"
TEXT, SUBTEXT, MUTED = "#E8EAF0", "#8C94A6", "#5A6172"
ACCENT, ACCENT_HOVER, GRAD_A, GRAD_B = "#4C8DFF", "#6AA2FF", "#4C8DFF", "#7A5CFF"
SUCCESS, WARNING, DANGER = "#3DD68C", "#F5B84B", "#FF6B6B"

QSS = f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: "Inter", "Noto Sans"; font-size: 10pt; }}
#root {{ background: {BG}; }}
#sidebar {{ background: #0B0D11; border-right: 1px solid {BORDER}; }}
QLabel#title {{ font-family: "Inter Display", "Inter"; font-size: 18pt; font-weight: 600; }}
QLabel#sub {{ color: {SUBTEXT}; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#step {{ color: {MUTED}; padding: 7px 12px; border-radius: 7px; font-weight: 600; }}
QLabel#stepDone {{ color: {SUBTEXT}; padding: 7px 12px; border-radius: 7px; font-weight: 600; }}
QLabel#stepNow {{ color: white; padding: 7px 12px; border-radius: 7px; font-weight: 600; background: {SURFACE};
    border: 1px solid {BORDER}; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 600; }}
QLabel#cardKicker {{ color: {SUBTEXT}; font-size: 8.5pt; font-weight: 600; }}
QLabel#now {{ font-family: "Inter Display", "Inter"; font-size: 13pt; font-weight: 600; }}
QLabel#error {{ color: {DANGER}; }}
#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#card QLabel, #card QCheckBox, #card QRadioButton {{ background: transparent; }}
#disk, #choice {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
#disk[picked="true"], #choice[picked="true"] {{ border: 1px solid {ACCENT}; background: #182033; }}
#disk[blocked="true"] {{ background: #13161C; }}
#disk QLabel, #disk QRadioButton, #choice QLabel, #choice QCheckBox {{ background: transparent; }}
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 8px 16px; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {PRESSED}; }}
QPushButton:disabled {{ color: {MUTED}; background: #13161C; }}
QPushButton#primary {{ color: white; font-weight: 600; border: none; padding: 9px 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {GRAD_A}, stop:1 {GRAD_B}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_HOVER}, stop:1 #8E75FF); }}
QPushButton#primary:disabled {{ color: {MUTED}; background: #1B1F27; }}
QPushButton#danger {{ color: white; font-weight: 600; border: none; padding: 9px 20px; background: #D9534F; }}
QPushButton#danger:hover {{ background: {DANGER}; }}
QPushButton#danger:disabled {{ color: {MUTED}; background: #1B1F27; }}
QLineEdit, QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 8px 10px;
    selection-background-color: {ACCENT}; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox QAbstractItemView {{ background: #22262F; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QPlainTextEdit {{ background: #0B0D11; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px;
    font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; color: {SUBTEXT}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 1px solid {MUTED}; background: {SURFACE}; }}
QRadioButton::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {HOVER}; border-radius: 4px; margin: 2px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

STEPS = ["Welcome", "Where", "You", "Software", "Confirm", "Install", "Done"]
WELCOME, WHERE, YOU, SOFTWARE, CONFIRM, INSTALL, DONE = range(len(STEPS))
# Optional software groups: deckos-install's DECKOS_GROUPS names, title, what's in it.
GROUPS = [
    ("gaming", "Gaming", "Steam with Gaming Mode, Proton, Lutris, Heroic, MangoHud, GameMode, LACT, Discord and OBS."),
    ("ai", "Local AI", "Ollama with ROCm, for running models on your graphics card. Needs a Radeon RX 7000 or "
                       "9000 series card, and it's a large download."),
    ("dev", "Development", "Claude Code, VS Code, JetBrains Toolbox, Docker, Node, Python, .NET, Java and the "
                           "GitHub CLI."),
]
# Where each section of deckos-install starts on the progress bar (Software is the long part).
PROGRESS = [("Preparing", 0.02), ("Base system", 0.05), ("CachyOS", 0.20), ("Software", 0.25),
            ("Your account", 0.70), ("DeckOS layer", 0.72), ("AUR", 0.78), ("Your drives", 0.88),
            ("Boot", 0.90), ("Services", 0.97), ("DeckOS is installed", 1.0)]
NET_URLS = ["https://geo.mirror.pkgbuild.com", "https://mirror.cachyos.org", "https://archlinux.org"]


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def table(name):
    """Rows of installer/NAME.tsv (the same file deckos-install reads), without comments."""
    try:
        lines = (SRC / "installer" / f"{name}.tsv").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [line.split("\t") for line in lines if line.strip() and not line.startswith("#")]


def label(text, cls=None, wrap=True, rich=False):
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.RichText if rich or "<" in text else Qt.PlainText)
    if cls:
        lab.setObjectName(cls)
    return lab


def button(text, kind=None, slot=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    if kind:
        b.setObjectName(kind)
    if slot:
        b.clicked.connect(slot)
    return b


class Card(QFrame):
    def __init__(self, kicker=None, title=None):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 14, 18, 16)
        self.body.setSpacing(8)
        if kicker:
            self.body.addWidget(label(kicker.upper(), "cardKicker"))
        if title:
            self.body.addWidget(label(title, "cardTitle"))


class Meter(QWidget):
    """6px rounded track with the blue-violet fill; value is 0..1."""

    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(6)

    def set(self, v):
        self.value = max(self.value, min(1.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.rect()
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(r, 3, 3)
        if self.value > 0:
            g = QLinearGradient(0, 0, r.width(), 0)
            g.setColorAt(0, QColor(GRAD_A))
            g.setColorAt(1, QColor(GRAD_B))
            p.setBrush(g)
            p.drawRoundedRect(0, 0, max(6, int(r.width() * self.value)), r.height(), 3, 3)


class Page(QWidget):
    def __init__(self, title, sub=None):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(36, 32, 36, 24)
        self.lay.setSpacing(14)
        self.lay.addWidget(label(title, "title"))
        if sub:
            self.lay.addWidget(label(sub, "sub"))
        self.lay.addSpacing(4)


class Installer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("Install DeckOS")
        self.setWindowIcon(QIcon.fromTheme("deckos", QIcon(str(BRANDING / "logo.svg"))))
        self.resize(1040, 700)
        self.proc = None
        self.finished_ok = False
        self.net_ok = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(18, 26, 18, 20)
        sl.setSpacing(4)
        logo = QSvgWidget(str(BRANDING / "wordmark.svg"))
        logo.setFixedSize(160, 40)
        logo.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        sl.addWidget(logo)
        sl.addWidget(label("INSTALLER", "cardKicker"))
        sl.addSpacing(22)
        self.step_labels = []
        for s in STEPS:
            lab = label(s, "step")
            self.step_labels.append(lab)
            sl.addWidget(lab)
        sl.addStretch(1)
        sl.addWidget(label("The text installer is in the app menu if you ever need it.", "muted"))
        outer.addWidget(side)

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.stack = QStackedWidget()
        main.addWidget(self.stack, 1)
        nav = QHBoxLayout()
        nav.setContentsMargins(36, 12, 36, 24)
        self.back_btn = button("Back", slot=self.back)
        self.next_btn = button("Next", "primary", slot=self.next)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        main.addLayout(nav)
        outer.addLayout(main, 1)

        self.build_welcome()
        self.build_disk()
        self.build_you()
        self.build_software()
        self.build_confirm()
        self.build_install()
        self.build_done()
        self.go(WELCOME)
        QTimer.singleShot(150, self.check_system)

    # ------------------------------------------------------------- pages

    def build_welcome(self):
        p = Page("Welcome to DeckOS",
                 "DeckOS installs next to Windows, on one partition you pick. Windows, its boot files and "
                 "your other drives are left exactly as they are.")
        hero = QSvgWidget(str(BRANDING / "installer-welcome.svg"))
        hero.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        hero.setMinimumHeight(170)
        p.lay.addWidget(hero, 1)
        card = Card("Before we start", "System check")
        self.checks = QGridLayout()
        self.checks.setHorizontalSpacing(12)
        self.checks.setVerticalSpacing(6)
        card.body.addLayout(self.checks)
        actions = QHBoxLayout()
        actions.addWidget(button("Wi-Fi and network settings", slot=self.open_network))
        actions.addWidget(button("Check again", slot=self.check_system))
        actions.addStretch(1)
        card.body.addLayout(actions)
        p.lay.addWidget(card)
        self.stack.addWidget(p)

    def build_disk(self):
        p = Page("Where should DeckOS go?",
                 "Pick the partition to install on. Only that partition is erased; the EFI boot partition is "
                 "shared with Windows and never formatted.")
        self.disk_area = QScrollArea()
        self.disk_area.setWidgetResizable(True)
        self.disk_box = QWidget()
        self.disk_list = QVBoxLayout(self.disk_box)
        self.disk_list.setContentsMargins(0, 0, 6, 0)
        self.disk_list.setSpacing(8)
        self.disk_area.setWidget(self.disk_box)
        p.lay.addWidget(self.disk_area, 1)
        row = QHBoxLayout()
        row.addWidget(button("Refresh", slot=self.load_disks))
        row.addStretch(1)
        p.lay.addLayout(row)
        self.disk_group = QButtonGroup(self)
        self.disk_group.buttonToggled.connect(self.disk_picked)
        self.disk_cards = {}
        self.stack.addWidget(p)

    def build_you(self):
        p = Page("About you", "Your account on DeckOS. You'll use this password to log in and for sudo. The "
                              "keyboard layout switches right away, so you type the password the way you will at login.")
        card = Card()
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        self.user = QLineEdit()
        self.user.setPlaceholderText("lowercase, e.g. keagan")
        self.host = QLineEdit("deckos")
        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.Password)
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.Password)
        self.tz = QComboBox()
        self.tz.setEditable(True)
        zones = [z for z in run(["timedatectl", "list-timezones"]).split() if "/" in z] or [DEFAULT_TZ]
        self.tz.addItems(zones)
        self.tz.setCurrentText(DEFAULT_TZ)
        self.tz.completer().setFilterMode(Qt.MatchContains)
        self.tz.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.lang = QComboBox()
        for locale, name, *_ in table("locales") or [[DEFAULT_LOCALE, "English (United States)"]]:
            self.lang.addItem(name, locale)
        self.kbd = QComboBox()
        for layout, _console, name, *_ in table("keyboards") or [[DEFAULT_KEYMAP, "us", "English (US)"]]:
            self.kbd.addItem(name, layout)
        self.lang.setCurrentIndex(max(0, self.lang.findData(DEFAULT_LOCALE)))
        self.kbd.setCurrentIndex(max(0, self.kbd.findData(DEFAULT_KEYMAP)))
        self.kbd.currentIndexChanged.connect(self.apply_keyboard)
        for i, (name, w) in enumerate([("Username", self.user), ("Computer name", self.host), ("Language", self.lang),
                                       ("Keyboard", self.kbd), ("Password", self.pw1), ("Password again", self.pw2),
                                       ("Time zone", self.tz)]):
            g.addWidget(label(name, "sub", wrap=False), i, 0)
            g.addWidget(w, i, 1)
        card.body.addLayout(g)
        self.you_error = label("", "error")
        card.body.addWidget(self.you_error)
        p.lay.addWidget(card)
        p.lay.addStretch(1)
        for w in (self.user, self.host, self.pw1, self.pw2):
            w.textChanged.connect(self.validate_you)
        self.tz.currentTextChanged.connect(self.validate_you)
        self.stack.addWidget(p)

    def apply_keyboard(self):
        """Switches the live desktop to the chosen layout, the way System Settings does, and clears
        the password fields so nothing typed on the old layout gets saved."""
        self.pw1.clear()
        self.pw2.clear()
        if DEMO:
            return
        layout = self.kbd.currentData()
        run(["kwriteconfig6", "--file", "kxkbrc", "--group", "Layout", "--key", "LayoutList", layout])
        run(["kwriteconfig6", "--file", "kxkbrc", "--group", "Layout", "--key", "Use", "true"])
        run(["dbus-send", "--session", "--type=signal", "/Layouts", "org.kde.keyboard.reloadConfig"])

    def build_software(self):
        p = Page("Choose your software",
                 "DeckOS always installs the CachyOS kernel, the KDE Plasma desktop, Firefox, graphics drivers and "
                 "snapshots. Add any of these now; you can install them later too.")
        radeon = DEMO or self.has_radeon()
        self.group_boxes = {}
        for key, title, desc in GROUPS:
            card = QFrame()
            card.setObjectName("choice")
            card.setAttribute(Qt.WA_StyledBackground, True)
            h = QHBoxLayout(card)
            h.setContentsMargins(16, 12, 16, 12)
            box = QCheckBox()
            h.addWidget(box, 0, Qt.AlignTop)
            info = QVBoxLayout()
            info.setSpacing(2)
            info.addWidget(label(title, "cardTitle"))
            info.addWidget(label(desc, "sub"))
            if key == "ai" and not radeon:
                info.addWidget(label(f"<span style='color:{WARNING}'>No Radeon RX 7000/9000 card found, so this "
                                     f"starts unticked.</span>"))
            h.addLayout(info, 1)
            box.toggled.connect(lambda on, c=card: self.set_picked(c, on))
            box.setChecked(key != "ai" or radeon)
            self.set_picked(card, box.isChecked())
            card.mousePressEvent = lambda _e, b=box: b.toggle()
            self.group_boxes[key] = box
            p.lay.addWidget(card)
        p.lay.addStretch(1)
        self.stack.addWidget(p)

    @staticmethod
    def set_picked(card, on):
        card.setProperty("picked", on)
        card.style().unpolish(card)
        card.style().polish(card)

    @staticmethod
    def has_radeon():
        """An AMD card with more than 4 GB of VRAM: a Radeon, not a Ryzen's built-in graphics."""
        for vram in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
            try:
                if (vram.parent / "vendor").read_text().strip() == "0x1002" and int(vram.read_text()) > 4 << 30:
                    return True
            except (OSError, ValueError):
                pass
        return False

    def groups(self):
        return [key for key, *_ in GROUPS if self.group_boxes[key].isChecked()]

    def build_confirm(self):
        p = Page("Ready to install", "Check this over. Nothing has been changed yet.")
        self.summary = Card("Summary")
        self.summary_text = label("", rich=True)
        self.summary.body.addWidget(self.summary_text)
        p.lay.addWidget(self.summary)
        sw = Card("Installed for you")
        self.software_text = label("", "sub")
        sw.body.addWidget(self.software_text)
        p.lay.addWidget(sw)
        self.agree = QCheckBox()
        self.agree.toggled.connect(lambda _: self.update_nav())
        p.lay.addWidget(self.agree)
        p.lay.addStretch(1)
        self.stack.addWidget(p)

    def build_install(self):
        p = Page("Installing DeckOS", "Keep the PC on and the USB plugged in. You can follow along below.")
        card = Card()
        self.now = label("Starting…", "now")
        card.body.addWidget(self.now)
        self.meter = Meter()
        card.body.addWidget(self.meter)
        self.now_sub = label("", "sub")
        card.body.addWidget(self.now_sub)
        p.lay.addWidget(card)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        p.lay.addWidget(self.log_view, 1)
        self.stack.addWidget(p)

    def build_done(self):
        self.done_page = Page("", None)
        self.done_title = self.done_page.lay.itemAt(0).widget()
        self.done_text = label("", "sub")
        self.done_page.lay.addWidget(self.done_text)
        self.done_card = Card()
        self.done_body = label("", rich=True)
        self.done_card.body.addWidget(self.done_body)
        self.done_page.lay.addWidget(self.done_card)
        self.done_page.lay.addStretch(1)
        self.stack.addWidget(self.done_page)

    # ------------------------------------------------------------- navigation

    def go(self, i):
        self.stack.setCurrentIndex(i)
        for n, lab in enumerate(self.step_labels):
            lab.setObjectName("stepNow" if n == i else "stepDone" if n < i else "step")
            lab.style().unpolish(lab)
            lab.style().polish(lab)
        if i == WHERE and not self.disk_cards:
            self.load_disks()
        if i == CONFIRM:
            self.fill_summary()
        self.update_nav()

    def update_nav(self):
        i = self.stack.currentIndex()
        self.back_btn.setVisible(i in (WHERE, YOU, SOFTWARE, CONFIRM))
        self.next_btn.setVisible(i != INSTALL)
        self.next_btn.setObjectName("danger" if i == CONFIRM else "primary")
        self.next_btn.style().unpolish(self.next_btn)
        self.next_btn.style().polish(self.next_btn)
        text = {CONFIRM: "Erase and install", DONE: "Restart now" if self.finished_ok else "Close"}.get(i, "Next")
        self.next_btn.setText(text)
        ok = {WELCOME: self.net_ok, WHERE: self.target() is not None, YOU: self.validate_you(),
              CONFIRM: self.agree.isChecked()}
        self.next_btn.setEnabled(ok.get(i, True))

    def back(self):
        self.go(max(WELCOME, self.stack.currentIndex() - 1))

    def next(self):
        i = self.stack.currentIndex()
        if i == CONFIRM:
            self.start_install()
        elif i == DONE:
            if self.finished_ok and not DEMO:
                QProcess.startDetached("systemctl", ["reboot"])
            self.close()
        else:
            self.go(i + 1)

    # ------------------------------------------------------------- welcome

    def set_check(self, row, ok, text, detail=""):
        for col in range(2):
            item = self.checks.itemAtPosition(row, col)
            if item:
                item.widget().deleteLater()
                self.checks.removeItem(item)
        color = {True: SUCCESS, False: DANGER, None: WARNING}[ok]
        mark = {True: "✓", False: "✕", None: "!"}[ok]
        self.checks.addWidget(label(f'<span style="color:{color}; font-weight:600">{mark}</span>', wrap=False), row, 0)
        self.checks.addWidget(label(f"{text}" + (f'<br><span style="color:{SUBTEXT}">{detail}</span>' if detail else "")),
                              row, 1)
        self.checks.setColumnStretch(1, 1)

    def check_system(self):
        uefi = DEMO or Path("/sys/firmware/efi/efivars").is_dir()
        self.set_check(0, uefi, "Started in UEFI mode" if uefi else "Started in legacy (BIOS) mode",
                       "" if uefi else "Restart and pick the USB's UEFI entry in the boot menu.")
        sudo_ok = DEMO or subprocess.call(["sudo", "-n", "true"], stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL) == 0
        self.set_check(1, sudo_ok, "Administrator access" if sudo_ok else "No administrator access",
                       "" if sudo_ok else "The live user should have passwordless sudo; this USB may be damaged.")
        sb = self.secure_boot()
        self.set_check(2, None if sb else True, "Secure Boot is on" if sb else "Secure Boot is off",
                       "Turn it off in the BIOS before you restart into DeckOS." if sb else "")
        self.set_check(3, None, "Checking internet…")
        self.uefi_sudo = uefi and sudo_ok
        self.net_ok = False
        self.update_nav()
        if DEMO:
            QTimer.singleShot(400, lambda: self.net_done(0))
            return
        script = " || ".join(f"curl -sS -o /dev/null --connect-timeout 5 --max-time 10 {u}" for u in NET_URLS)
        self.net_proc = QProcess(self)
        self.net_proc.setProcessChannelMode(QProcess.MergedChannels)
        self.net_proc.finished.connect(lambda code, _s: self.net_done(code))
        self.net_proc.start("bash", ["-c", script])

    def net_done(self, code):
        if code == 0:
            self.set_check(3, True, "Connected to the internet")
        else:
            err = bytes(self.net_proc.readAll()).decode(errors="replace").strip().splitlines()
            self.set_check(3, False, "No internet",
                           "Plug in Ethernet, or connect to Wi-Fi with the button below, then check again."
                           + (f"<br>{err[-1]}" if err else ""))
        self.net_ok = code == 0 and self.uefi_sudo
        self.update_nav()

    @staticmethod
    def secure_boot():
        try:
            f = next(Path("/sys/firmware/efi/efivars").glob("SecureBoot-*"))
            return f.read_bytes()[4] == 1
        except (OSError, StopIteration, IndexError):
            return False

    def open_network(self):
        for cmd in (["kcmshell6", "kcm_networkmanagement"], ["systemsettings", "kcm_networkmanagement"],
                    ["konsole", "-e", "nmtui"]):
            if shutil.which(cmd[0]) and QProcess.startDetached(cmd[0], cmd[1:]):
                return

    # ------------------------------------------------------------- disk

    def load_disks(self):
        for b in self.disk_group.buttons():
            self.disk_group.removeButton(b)
        while self.disk_list.count():
            item = self.disk_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.disk_cards = {}
        if DEMO:
            out = ("/dev/nvme1n1p3\t232 GB\tntfs\tNVME\tSamsung SSD 970 EVO Plus 250GB\t1\t\n"
                   "/dev/sda2\t1000 GB\tntfs\tBIG\tST1000DM010\t0\t\n"
                   "/dev/nvme0n1p3\t500 GB\tBitLocker\t-\tWD_BLACK SN850X\t0\tBitLocker-encrypted, so DeckOS cannot "
                   "check what is on it. Turn BitLocker off or delete this partition in Windows first.\n")
        else:
            out = run([INSTALLER, "--list-targets"], timeout=20)
        # path, size, fs, label, model, default, and why it's blocked (empty = usable)
        rows = [(line.split("\t") + [""])[:7] for line in out.splitlines() if line.count("\t") >= 5]
        if not any(not why for *_, why in rows):
            self.disk_list.addWidget(label("No partitions found that DeckOS can use. In Windows, shrink a drive in "
                                           "Disk Management to make free space, create a partition there, then "
                                           "press Refresh.", "sub"))
        default = None
        for path, size, fs, lab, model, is_default, why in rows:
            card = QFrame()
            card.setObjectName("disk")
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setProperty("blocked", bool(why))
            h = QHBoxLayout(card)
            h.setContentsMargins(16, 12, 16, 12)
            rb = QRadioButton()
            rb.setProperty("path", path)
            rb.setEnabled(not why)
            self.disk_group.addButton(rb)
            h.addWidget(rb)
            info = QVBoxLayout()
            info.setSpacing(2)
            name = html.escape(lab if lab not in ("-", "") else "No label")
            info.addWidget(label(f"<b>{name}</b> &nbsp;<span style='color:{SUBTEXT}'>{path} · {size} · "
                                 f"{'empty' if fs == 'empty' else fs}</span>"))
            note = html.escape(model)
            if why:
                note += f" · <span style='color:{DANGER}'>Can't install here: {html.escape(why)}</span>"
            elif fs == "ntfs":
                note += f" · <span style='color:{WARNING}'>Windows-format partition: everything on it will be erased</span>"
            elif fs != "empty":
                note += f" · <span style='color:{WARNING}'>has a {fs} file system: it will be erased</span>"
            info.addWidget(label(f"<span style='color:{SUBTEXT}'>{note}</span>"))
            h.addLayout(info, 1)
            if not why:
                card.mousePressEvent = lambda _e, r=rb: r.setChecked(True)
            self.disk_list.addWidget(card)
            self.disk_cards[path] = card
            if is_default == "1" and default is None and not why:
                default = rb
        self.disk_list.addStretch(1)
        if default:
            default.setChecked(True)
        self.update_nav()

    def disk_picked(self, rb, checked):
        card = self.disk_cards.get(rb.property("path"))
        if card:
            card.setProperty("picked", checked)
            card.style().unpolish(card)
            card.style().polish(card)
        self.update_nav()

    def target(self):
        b = self.disk_group.checkedButton()
        return b.property("path") if b else None

    # ------------------------------------------------------------- you

    def validate_you(self):
        u, h, p1, p2 = self.user.text(), self.host.text(), self.pw1.text(), self.pw2.text()
        err = ""
        if u and not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", u):
            err = "Username: lowercase letters, digits, - and _ only, starting with a letter."
        elif u in ("root", "liveuser", "bin", "daemon", "nobody", "http", "mail", "ftp"):
            err = "That username is reserved — pick another."
        elif h and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}", h):
            err = "Computer name: letters, digits and - only."
        elif p1 and len(p1) < 4:
            err = "Password: at least 4 characters."
        elif p2 and p1 != p2:
            err = "The passwords don't match."
        if hasattr(self, "you_error"):
            self.you_error.setText(err)
        ok = not err and bool(u and h and p1 and p1 == p2) and self.tz.currentText() in self.zone_names()
        if self.stack.currentIndex() == YOU:
            self.next_btn.setEnabled(ok)
        return ok

    def zone_names(self):
        return {self.tz.itemText(i) for i in range(self.tz.count())}

    # ------------------------------------------------------------- confirm

    def fill_summary(self):
        t = self.target()
        self.summary_text.setText(
            f"<table cellspacing=6>"
            f"<tr><td style='color:{SUBTEXT}'>Erase&nbsp;&nbsp;</td><td><b style='color:{DANGER}'>{t}</b> → DeckOS "
            f"(btrfs with snapshots)</td></tr>"
            f"<tr><td style='color:{SUBTEXT}'>Boot menu</td><td>Shared EFI partition, not formatted — DeckOS and Windows</td></tr>"
            f"<tr><td style='color:{SUBTEXT}'>Keep</td><td>Every other partition and drive</td></tr>"
            f"<tr><td style='color:{SUBTEXT}'>Account</td><td>{html.escape(self.user.text())} @ {html.escape(self.host.text())}</td></tr>"
            f"<tr><td style='color:{SUBTEXT}'>Time zone</td><td>{self.tz.currentText()}</td></tr>"
            f"<tr><td style='color:{SUBTEXT}'>Language</td><td>{self.lang.currentText()} · keyboard "
            f"{self.kbd.currentText()}</td></tr></table>")
        extras = [title for key, title, _ in GROUPS if key in self.groups()]
        self.software_text.setText(
            "CachyOS kernel, KDE Plasma desktop, Firefox, graphics drivers and snapshots"
            + (f", plus {', '.join(extras)}." if extras else ". Nothing extra: add software later with Discover or pacman.")
            + " Your NTFS drives are mounted as they are. It takes 20–60 minutes depending on your internet.")
        self.agree.setText(f"I understand everything on {t} will be erased")
        self.agree.setChecked(False)

    # ------------------------------------------------------------- install

    def start_install(self):
        self.go(INSTALL)
        self.log_view.clear()
        if DEMO:
            self.demo_lines = iter(["// Pre-flight", "  [ OK ] internet", "// Preparing /dev/nvme1n1p3",
                                    "  [ .. ] Wiping /dev/nvme1n1p3", "  [ OK ] Wiping /dev/nvme1n1p3",
                                    "// Base system", "  [ .. ] Ranking mirrors",
                                    "  [ !! ] Mirror ranking failed - using a standard mirror list",
                                    "  [ .. ] Installing Arch base", "  [ OK ] Installing Arch base", "// Software",
                                    "  [ .. ] Installing gaming (40 packages) - this can take a while",
                                    "// Services", "// DeckOS is installed"])
            self.demo_timer = QTimer(self, interval=250)
            self.demo_timer.timeout.connect(self.demo_step)
            self.demo_timer.start()
            return
        fd, pwfile = tempfile.mkstemp(prefix="deckos-pw-", dir="/tmp")
        with os.fdopen(fd, "w") as f:
            f.write(self.pw1.text())
        env = {"DECKOS_GUI": "1", "DECKOS_TARGET": self.target(), "DECKOS_HOSTNAME": self.host.text(),
               "DECKOS_USER": self.user.text(), "DECKOS_PASSWORD_FILE": pwfile, "DECKOS_TZ": self.tz.currentText(),
               "DECKOS_LOCALE": self.lang.currentData(), "DECKOS_KEYMAP": self.kbd.currentData(),
               "DECKOS_GROUPS": ",".join(self.groups()), "DECKOS_CONFIRM": "ERASE"}
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_output)
        self.proc.finished.connect(self.install_finished)
        self.buffer = ""
        self.proc.start("sudo", ["-n", "env", *[f"{k}={v}" for k, v in env.items()], INSTALLER])

    def demo_step(self):
        line = next(self.demo_lines, None)
        if line is None:
            self.demo_timer.stop()
            self.install_finished(0, None)
        else:
            self.handle_line(line)

    def read_output(self):
        self.buffer += bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        *lines, self.buffer = re.split(r"[\r\n]", self.buffer)
        for line in lines:
            self.handle_line(line)

    def handle_line(self, line):
        line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).rstrip()
        if not line.strip():
            return
        self.log_view.appendPlainText(line)
        self.log_view.moveCursor(QTextCursor.End)
        s = line.strip()
        if s.startswith("// "):
            title = s[3:]
            for key, frac in PROGRESS:
                if title.startswith(key):
                    self.meter.set(frac)
            self.now.setText(title)
            self.now_sub.setText("")
        elif s.startswith("[ .. ]"):
            self.now_sub.setText(s[6:].strip() + "…")
        elif s.startswith("[FAIL]"):
            self.fail_reason = s[6:].strip()

    def install_finished(self, code, _status):
        self.finished_ok = code == 0
        if self.finished_ok:
            self.meter.set(1.0)
            self.done_title.setText("DeckOS is installed")
            self.done_text.setText("Restart, take out the USB, and DeckOS will start. Windows is in the boot menu.")
            self.done_body.setText(
                "<b>Before you boot DeckOS</b><br>"
                "1. BIOS: Secure Boot off. DeckOS is now first in the boot order.<br>"
                "2. Windows: run <code>powercfg /h off</code> as admin once, or your NTFS drives open read-only.<br><br>"
                "<b>After you log in</b><br>"
                "DeckOS Hub (bottom panel) has the display fix level, Gaming Mode and your drives.")
        else:
            saved = self.save_log()
            reason = getattr(self, "fail_reason", "") or f"The installer stopped (exit code {code})."
            self.done_title.setText("The install didn't finish")
            self.done_text.setText(reason)
            tail = "<br>".join(html.escape(x) for x in self.log_view.toPlainText().splitlines()[-14:]).replace(" ", "&nbsp;")
            self.done_body.setText(f"<span style='color:{SUBTEXT}'>{saved}</span><br><br>"
                                   f"<span style='font-family:monospace; font-size:8.5pt'>{tail}</span>")
        self.go(DONE)

    def save_log(self):
        """Copies the full log to the desktop, where it survives a reboot onto the USB stick only if copied."""
        desk = Path.home() / "Desktop"
        desk.mkdir(exist_ok=True)
        (desk / "installer-output.txt").write_text(self.log_view.toPlainText() + "\n")
        full = run(["sudo", "-n", "cat", INSTALL_LOG], timeout=10)
        if full:
            (desk / "deckos-install.log").write_text(full)
        return "The full log is on the desktop: deckos-install.log and installer-output.txt."

    def closeEvent(self, e):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            if QMessageBox.warning(self, "Install DeckOS", "DeckOS is still installing. Stop it?\n\n"
                                   "The partition you picked will be left unusable until you install again.",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                e.ignore()
                return
            subprocess.call(["sudo", "-n", "pkill", "-TERM", "-f", INSTALLER])
            self.proc.kill()
        e.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Install DeckOS")
    app.setDesktopFileName("deckos-install")
    app.setStyleSheet(QSS)
    w = Installer()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
