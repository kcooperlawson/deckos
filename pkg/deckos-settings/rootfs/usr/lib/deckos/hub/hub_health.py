"""DecKoOS Hub's Health page: the one place for "something's wrong". What used to be four places is here:
System Doctor's checkup (sysdoctor.py: crashes, failed services, slow start-up, missing programs, full disks),
games that closed right after starting (Game Doctor's window opens on one of them), DecKoOS's fixes and their
switches (hub_heal.py), and a report for whoever helps (deckos report). DecKoOS Care runs the same checks in the
background and its notifications open this page (`deckos-sysdoctor` is `deckos-hub --page health`).
"""
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

LIB = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(LIB / "sysdoctor"), str(LIB / "gamedoctor")]
import sysdoctor as sd  # noqa: E402

import hub_style as S  # noqa: E402
import hub_system as sysinfo  # noqa: E402
from hub_heal import HealCard  # noqa: E402
from hub_pages import Page  # noqa: E402
from hub_widgets import Card, Empty, RowItem, button, icon_label, label  # noqa: E402

DEMO = sysinfo.DEMO
COLORS = {sd.BAD: S.DANGER, sd.WARN: S.WARNING, sd.INFO: S.SUBTEXT}
ICONS = {sd.BAD: "alert", sd.WARN: "alert", sd.INFO: "info"}
OPEN_LABELS = {"deckos-gamedoctor": "Open Game Doctor", "deckos-hub": "Open in DecKoOS Hub",
               "filelight": "See what's using space"}
RECENT_GAMES = 7 * 86400  # quick exits older than this aren't shown


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
    """One thing the checkup found: what, why, the fixes, and the evidence (with the local AI to explain it)."""

    def __init__(self, page, f):
        super().__init__()
        self.page, self.f = page, f
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)
        h = QHBoxLayout()
        h.addWidget(icon_label(ICONS[f.level], COLORS[f.level], 20))
        h.addWidget(label(f"<b>{f.title}</b>", "cardTitle"), 1)
        v.addLayout(h)
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
        a = QHBoxLayout()
        a.setContentsMargins(0, 2, 0, 0)
        a.setSpacing(6)
        for i, fix in enumerate(f.fixes):
            a.addWidget(button(fix.title, "primary" if i == 0 else None,
                               lambda _=False, x=fix: self.page.run_fix(x), tip=fix.detail or " ".join(fix.cmd)))
        if f.open:
            a.addWidget(button(OPEN_LABELS.get(f.open[0], "Open"), icon="external",
                               slot=lambda: QProcess.startDetached(f.open[0], f.open[1:]) if not DEMO else None))
        if f.evidence:
            self.ev_btn = button("Show the evidence", slot=self.toggle_evidence, icon="list")
            a.addWidget(self.ev_btn)
            self.ai_btn = button("Explain", slot=self.explain, icon="ai", tip="Asks the local AI; nothing leaves this PC")
            a.addWidget(self.ai_btn)
        a.addStretch(1)
        v.addLayout(a)

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
            self.page.worker.start(("explain", self), sd.explain, self.f)

    def explained(self, text, error):
        self.ai.setText(text or f"Couldn't ask the local AI ({error}).")
        self.ai_btn.setEnabled(True)


def quick_exits():
    """[(appid, name, when)] of games that closed right after starting this past week, newest first, one per game."""
    if DEMO:
        now = time.time()
        return [("1091500", "Cyberpunk 2077", now - 3600), ("1245620", "Elden Ring", now - 2 * 86400)]
    import gamedoctor as gd
    import steamfiles as sf
    out, seen = [], set()
    for s in reversed(gd.sessions()):
        if s["seconds"] >= gd.QUICK or s["appid"] in seen or time.time() - s["end"] > RECENT_GAMES:
            continue
        seen.add(s["appid"])
        out.append((s["appid"], (sf.game(s["appid"]) or {}).get("name") or f"App {s['appid']}", s["end"]))
    return out[:4]


class HealthPage(Page):
    title = "Health"
    subtitle = "What's wrong with this PC, a game that won't start, and the fixes DecKoOS knows. DecKoOS Care checks " \
               "in the background and tells you when something needs a look."

    def build(self):
        self.worker = Worker(self)
        self.worker.done.connect(self.on_done)
        self.again = button("Check again", "primary", self.check, icon="refresh")
        self.head_actions.addWidget(self.again)

        self.checkup = Card("Checkup", "Checking…", "check")
        self.checkup.actions.addWidget(button("Full report in a terminal", slot=self.full_report, icon="terminal"))
        self.status = label("Reading the system log and services…", "sub")
        self.checkup.body.addWidget(self.status)
        self.lay.addWidget(self.checkup)
        self.findings = QVBoxLayout()
        self.findings.setSpacing(14)
        self.lay.addLayout(self.findings)

        self.games = Card("Games", "Closed right after starting", "gaming")
        self.games.body.addWidget(label("Game Doctor reads what the game printed as it closed and offers fixes for the "
                                        "common causes (Proton versions, shader caches, launch options). Each fix can "
                                        "be undone.", "sub"))
        self.game_rows = QVBoxLayout()
        self.game_rows.setSpacing(6)
        self.games.body.addLayout(self.game_rows)
        self.lay.addWidget(self.games)

        self.lay.addWidget(HealCard(self.hub.toast))

        help_ = Card("Getting help", "A report for whoever helps", "doc")
        help_.body.addWidget(label("One text file with this PC's hardware, drivers and recent errors, for a bug report "
                                   "or a friend. Names, serial numbers and addresses are taken out first, and it's "
                                   "shown to you before it goes anywhere: DecKoOS never sends it.", "sub"))
        help_.actions.addWidget(button("Make a report", slot=self.make_report, icon="doc"))
        self.lay.addWidget(help_)
        self.checked = False

    def refresh(self):
        if not self.checked:  # once when first opened; Check again after that
            self.checked = True
            self.check()
        self.fill_games()

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
        if tag == "games":
            self.show_games(result or [])
            return
        self.again.setEnabled(True)
        Page.clear(self.findings)
        findings = result or []
        serious = [f for f in findings if f.level != sd.INFO]
        title = self.checkup.findChild(QLabel, "cardTitle")
        if error:
            title.setText("Couldn't finish the checkup")
            self.status.setText(error)
        elif not serious:
            title.setText("All good")
            self.status.setText("No failed services, crashes, missing programs, full disks or graphics resets."
                                + (" A few notes below." if findings else "") + f" Checked at {time.strftime('%H:%M')}.")
        else:
            n = len(serious)
            title.setText(f"{n} thing{'s' if n > 1 else ''} need{'' if n > 1 else 's'} a look")
            self.status.setText("Worst first. Fixes ask for your password when they change the system. "
                                f"Checked at {time.strftime('%H:%M')}.")
        for f in findings:
            self.findings.addWidget(FindingCard(self, f))

    def fill_games(self):
        self.worker.start("games", quick_exits)

    def show_games(self, rows):
        Page.clear(self.game_rows)
        if not rows:
            self.game_rows.addWidget(Empty("check", "No game has closed early this week",
                                           "If one does, Steam's notification or this list opens Game Doctor on it."))
            return
        for appid, name, when in rows:
            why = button("Why?", slot=lambda _=False, a=appid: self.game_doctor(a), icon="arrow-right")
            self.game_rows.addWidget(RowItem("alert", name, time.strftime("Closed right after starting, %a %H:%M",
                                                                          time.localtime(when)), S.WARNING, (why,)))

    def game_doctor(self, appid):
        if not DEMO:
            QProcess.startDetached("deckos-gamedoctor", ["--appid", appid])

    def run_fix(self, fix):
        if DEMO:
            self.hub.toast(f"{fix.title}: done (demo).", "ok")
            return
        proc = QProcess(self)
        self.status.setText(f"{fix.title}…")

        def finished(code, _status):
            proc.deleteLater()
            self.hub.toast(f"{fix.title}: done." if code == 0 else f"{fix.title}: didn't finish (exit {code}).",
                           "ok" if code == 0 else "warn")
            if code == 0:
                self.check()  # the finding should be gone now
                if "heal" in fix.cmd and "apply" in fix.cmd:  # a vetted recipe: "Did that fix it?"
                    i = fix.cmd.index("apply")
                    finding = next((a.split("=", 1)[1] for a in fix.cmd if a.startswith("--finding=")), "")
                    QProcess.startDetached("deckos", ["heal", "ask", fix.cmd[i + 1], finding])
        proc.finished.connect(finished)
        proc.start(fix.cmd[0], fix.cmd[1:])

    def full_report(self):
        if not DEMO:
            self.hub.terminal("deckos doctor")

    def make_report(self):
        if DEMO:
            self.hub.toast("Report written to ~/deckos-report-….txt (demo)", "ok")
            return
        self.hub.toast("Making the report… it opens when it's ready.")
        proc = QProcess(self)

        def finished(code, _status):
            path = bytes(proc.readAllStandardOutput()).decode(errors="replace").strip().splitlines()
            proc.deleteLater()
            if code == 0 and path:
                QProcess.startDetached("xdg-open", [path[-1]])
            else:
                self.hub.toast("Couldn't make the report: run deckos report in a terminal to see why.", "warn")
        proc.finished.connect(finished)
        proc.start(sysinfo.DECKOS, ["report"])


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
        F("journal", sd.INFO, "Other errors in the system log", "Lines the system marked as errors this start-up. Many "
          "are harmless; Explain asks the local AI what they mean for you.",
          evidence=["4×  kwin_wayland: atomic commit failed: Invalid argument"]),
    ]
