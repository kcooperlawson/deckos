"""DeckOS System Doctor's window: what's wrong with this PC, in plain words, with fixes and the evidence.

    deckos-sysdoctor
    deckos-sysdoctor --demo [--screenshot FILE]
"""
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

from PySide6.QtCore import QObject, QProcess, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget  # noqa: E402

import hub_style as S  # noqa: E402
import sysdoctor as sd  # noqa: E402
from hub_widgets import Card, Empty, button, icon_label, label  # noqa: E402

DEMO = "--demo" in sys.argv
COLORS = {sd.BAD: S.DANGER, sd.WARN: S.WARNING, sd.INFO: S.SUBTEXT}
ICONS = {sd.BAD: "alert", sd.WARN: "alert", sd.INFO: "info"}
OPEN_LABELS = {"deckos-gamedoctor": "Open Game Doctor", "deckos-hub": "Open in DeckOS Hub", "filelight": "See what's using space"}
QSS = f"""
QLabel#big {{ font-family: "Inter Display", "Inter"; font-size: 17pt; font-weight: 600; }}
QLabel#evidence {{ font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 8.5pt;
    color: {S.SUBTEXT}; background: {S.SIDEBAR}; border: 1px solid {S.BORDER}; border-radius: 8px; padding: 8px; }}
"""


class Worker(QObject):
    """fn on a thread; the result (or the error) arrives on the UI thread."""
    done = Signal(object, object, str)  # tag, result, error

    def start(self, tag, fn, *args):
        def go():
            try:
                self.done.emit(tag, fn(*args), "")
            except Exception as e:  # shown, not a traceback
                self.done.emit(tag, None, str(e) or type(e).__name__)
        threading.Thread(target=go, daemon=True).start()


class FindingCard(QFrame):
    def __init__(self, doctor, f):
        super().__init__()
        self.doctor, self.f = doctor, f
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)
        head = QWidget()
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(icon_label(ICONS[f.level], COLORS[f.level], 20))
        h.addWidget(label(f"<b>{f.title}</b>", "cardTitle"), 1)
        v.addWidget(head)
        v.addWidget(label(f.text, "sub"))
        self.ai = label("", "sub")
        self.ai.setTextFormat(Qt.MarkdownText)  # the local model answers in Markdown
        self.ai.hide()
        v.addWidget(self.ai)
        self.evidence = QLabel("\n".join(f.evidence))
        self.evidence.setObjectName("evidence")
        self.evidence.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.evidence.setWordWrap(True)
        self.evidence.hide()
        v.addWidget(self.evidence)
        actions = QWidget()
        a = QHBoxLayout(actions)
        a.setContentsMargins(0, 2, 0, 0)
        a.setSpacing(6)
        for i, fix in enumerate(f.fixes):
            b = button(fix.title, "primary" if i == 0 else None, lambda _=False, x=fix: self.doctor.run_fix(self, x),
                       tip=fix.detail or " ".join(fix.cmd))
            a.addWidget(b)
        if f.open:
            a.addWidget(button(OPEN_LABELS.get(f.open[0], "Open"), icon="external",
                               slot=lambda: QProcess.startDetached(f.open[0], f.open[1:]) if not DEMO else None))
        if f.evidence:
            self.ev_btn = button("Show the evidence", slot=self.toggle_evidence, icon="list")
            a.addWidget(self.ev_btn)
            self.ai_btn = button("Explain", slot=self.explain, icon="ai", tip="Asks the local AI; nothing leaves this PC")
            a.addWidget(self.ai_btn)
        a.addStretch(1)
        v.addWidget(actions)

    def toggle_evidence(self):
        self.evidence.setVisible(not self.evidence.isVisible())
        self.ev_btn.setText("Hide the evidence" if self.evidence.isVisible() else "Show the evidence")

    def explain(self):
        self.ai_btn.setEnabled(False)
        self.ai.setText("Asking the local AI…")
        self.ai.show()
        if DEMO:
            QTimer.singleShot(300, lambda: self.explained("The desktop's programs lost their display when Gaming Mode "
                                                          "closed; nothing is wrong with them themselves.", ""))
        else:
            self.doctor.worker.start(("explain", self), sd.explain, self.f)

    def explained(self, text, error):
        self.ai.setText(text or f"Couldn't ask the local AI ({error}).")
        self.ai_btn.setEnabled(True)


class Doctor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Doctor")
        self.resize(820, 860)
        self.setStyleSheet(S.qss() + QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        self.lay = QVBoxLayout(page)
        self.lay.setContentsMargins(28, 24, 28, 24)
        self.lay.setSpacing(14)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        foot = QFrame()
        foot.setStyleSheet(f"background: {S.SURFACE}; border-top: 1px solid {S.BORDER};")
        f = QHBoxLayout(foot)
        f.setContentsMargins(28, 12, 28, 12)
        self.status = label("", "sub")
        f.addWidget(self.status, 1)
        f.addWidget(button("Full report in a terminal", slot=self.full_report, icon="terminal"))
        self.again = button("Check again", "primary", self.check, icon="refresh")
        f.addWidget(self.again)
        outer.addWidget(foot)
        self.worker = Worker(self)
        self.worker.done.connect(self.on_done)
        self.check()

    def clear(self):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.deleteLater()

    def header(self, title, sub):
        head = QWidget()
        h = QVBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 4)
        h.setSpacing(4)
        h.addWidget(label("SYSTEM DOCTOR", "kicker"))
        h.addWidget(label(title, "big"))
        h.addWidget(label(sub, "sub"))
        self.lay.addWidget(head)

    def check(self, *_):
        self.again.setEnabled(False)
        self.status.setText("Reading the system log and services…")
        if DEMO:
            QTimer.singleShot(200, lambda: self.on_done("checkup", demo(), ""))
        else:
            self.worker.start("checkup", sd.checkup)

    def on_done(self, tag, result, error):
        if isinstance(tag, tuple):  # an Explain
            tag[1].explained(result, error)
            return
        self.again.setEnabled(True)
        self.clear()
        findings = result or []
        serious = [f for f in findings if f.level != sd.INFO]
        if error:
            self.header("Couldn't finish the checkup", error)
        elif not serious:
            self.header("All good", "No failed services, crashes, missing programs, full disks or graphics resets."
                        + (" A few notes below." if findings else ""))
        else:
            self.header(f"{len(serious)} thing{'s' if len(serious) > 1 else ''} need{'' if len(serious) > 1 else 's'} a look",
                        "Worst first. Fixes ask for your password when they change the system.")
        for f in findings:
            self.lay.addWidget(FindingCard(self, f))
        if not findings and not error:
            self.lay.addWidget(Empty("check", "Nothing to report", "Check again any time, or after something odd."))
        self.lay.addStretch(1)
        self.status.setText(f"Checked at {time.strftime('%H:%M')}.")

    def run_fix(self, card, fix):
        if DEMO:
            self.status.setText(f"{fix.title}: done (demo).")
            return
        proc = QProcess(self)
        self.status.setText(f"{fix.title}…")

        def finished(code, _status):
            proc.deleteLater()
            self.status.setText(f"{fix.title}: done." if code == 0 else f"{fix.title}: didn't finish (exit {code}).")
            if code == 0:
                self.check()  # the finding should be gone now
        proc.finished.connect(finished)
        proc.start(fix.cmd[0], fix.cmd[1:])

    def full_report(self):
        if not DEMO:
            QProcess.startDetached("deckos-terminal", ["--hold", "-e", "deckos", "doctor"])


def demo():
    F, X = sd.Finding, sd.Fix
    return [
        F("crash:desktop-burst", sd.BAD, "The desktop crashed and restarted", "At 11:41, 6 desktop programs stopped at the "
          "same moment. That usually means the display they ran on went away (switching from Gaming Mode, a graphics "
          "driver reset), not a fault in each of them.", evidence=["11:41:32 plasmashell (SIGABRT)",
          "11:41:32 ksplashqml (SIGABRT)", "11:41:32 kdeconnectd (SIGABRT)", "11:41:32 ksecretd (SIGABRT)"],
          fixes=[X("Restart the desktop panel", [])]),
        F("missing:/usr/bin/hdparm", sd.WARN, "hdparm is needed but not installed", "Something on this PC runs "
          "/usr/bin/hdparm (29 times this start-up) and it isn't there, so what it's for doesn't happen. It comes with "
          "the hdparm package.", evidence=['sdb: Failed to find and pin callout binary "/usr/bin/hdparm"'],
          fixes=[X("Install hdparm", [])]),
        F("boot:wait-online", sd.WARN, "Starting up waits 6 s for the network", "NetworkManager-wait-online holds the "
          "start until the network is up. Nothing on a desktop needs that, so it can go.",
          evidence=["NetworkManager-wait-online.service: 6.5 s of 9.5 s"], fixes=[X("Don't wait for the network", [])]),
        F("crash:A game", sd.WARN, "A game crashed twice", "Last at Sat 20:10. Game Doctor reads what the game printed "
          "and has fixes for the common causes.", evidence=["20:10:02 Cyberpunk2077.exe (SIGSEGV)"],
          open=["deckos-gamedoctor"]),
        F("journal", sd.INFO, "Other errors in the system log", "Lines the system marked as errors this start-up. Many "
          "are harmless; Explain asks the local AI what they mean for you.",
          evidence=["4×  kwin_wayland: atomic commit failed: Invalid argument"]),
    ]


def main():
    args = sys.argv[1:]
    app = QApplication(sys.argv)
    app.setApplicationName("DeckOS System Doctor")
    app.setDesktopFileName("deckos-sysdoctor")
    app.setFont(QFont("Inter", 10))
    w = Doctor()
    w.show()
    if "--screenshot" in args:
        out = args[args.index("--screenshot") + 1]

        def shoot():
            page = w.findChild(QScrollArea).widget()
            page.resize(page.width(), page.sizeHint().height())
            page.grab().save(out)
            app.exit(0)
        QTimer.singleShot(700, shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
