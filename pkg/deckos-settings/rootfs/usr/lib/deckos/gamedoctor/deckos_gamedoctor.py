"""DecKoOS Game Doctor's window: a game that closed right after starting, what went wrong, and fixes.

    deckos-gamedoctor                  the most recent game that closed within 45 s of starting
    deckos-gamedoctor --appid 284160   that game's most recent launch
    deckos-gamedoctor --demo [--screenshot FILE]
"""
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub"), str(HERE.parent / "assistant")]

from PySide6.QtCore import QObject, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QFont, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,  # noqa: E402
                               QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)

import gamedoctor as gd  # noqa: E402
import hub_style as S  # noqa: E402
import steamfiles as sf  # noqa: E402
from hub_widgets import button, icon_label, label  # noqa: E402

DEMO = "--demo" in sys.argv

QSS = f"""
#finding {{ background: transparent; border: none; }}  /* a notched plate: hub_style */
#finding QLabel {{ background: transparent; }}
QLabel#big {{ font-family: "Inter Display", "Inter"; font-size: 17pt; font-weight: 600; }}
QLabel#header {{ border-radius: 10px; }}
"""


class Job(QObject):
    """Runs fn(*args) on a thread; done(result, error) arrives on the UI thread (bound slots only)."""
    done = Signal(object, str)

    def __init__(self, parent, fn, *args, on_done=None):
        super().__init__(parent)
        if on_done:
            self.done.connect(on_done)
        threading.Thread(target=self._run, args=(fn, args), daemon=True).start()

    def _run(self, fn, args):
        try:
            self.done.emit(fn(*args), "")
        except Exception as e:  # shown in the window, not a traceback
            self.done.emit(None, str(e) or type(e).__name__)


class FixButton(QWidget):
    """Apply, then Undo. Fixes that edit Steam's files ask before closing Steam."""

    def __init__(self, window, fix, appid):
        super().__init__()
        self.window_, self.fix, self.appid = window, fix, appid
        title, text = gd.describe_fix(fix, appid)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(f"<b>{title}</b>"))
        col.addWidget(label(text, "sub"))
        lay.addLayout(col, 1)
        self.button = button("Apply", "primary", self.toggle)
        lay.addWidget(self.button, 0, Qt.AlignTop)
        self.refresh()

    def is_applied(self):
        return any(e["fix"] == self.fix for e in gd.applied(self.appid))

    def refresh(self):
        self.button.setText("Undo" if self.is_applied() else "Apply")
        self.button.setObjectName("" if self.is_applied() else "primary")
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)

    def confirm(self):
        return QMessageBox.question(self, "Close Steam for a moment?",
                                    "Steam keeps this setting in files it rewrites when it closes, so it has to "
                                    "close while DecKoOS changes it. It reopens straight after.") == QMessageBox.Yes

    def toggle(self):
        if DEMO:
            self.window_.say(f"Demo: {gd.describe_fix(self.fix, self.appid)[0]}")
            return
        if self.fix not in ("verify", "prefix-reset", "prefix-home") and sf.steam_running() and not self.confirm():
            return
        self.button.setEnabled(False)
        fn = gd.undo if self.is_applied() else gd.apply
        self.job = Job(self, fn, self.fix, self.appid, lambda: True, on_done=self.finished)

    def finished(self, result, error):
        self.button.setEnabled(True)
        self.refresh()
        self.window_.say(error or result, bad=bool(error))


class Doctor(QWidget):
    def __init__(self, session, game, lines, findings):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle(f"Game Doctor: {game['name']}")
        self.setStyleSheet(S.qss() + QSS)
        self.resize(780, 820)
        self.session, self.game, self.lines = session, game, lines
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 16)
        lay.setSpacing(14)

        header = self.header_image(game["appid"])
        if header:
            lay.addWidget(header)
        lay.addWidget(label("GAME DOCTOR", "kicker"))
        secs = round(session["seconds"])
        lay.addWidget(label(f"{game['name']} closed {secs} second{'s' if secs != 1 else ''} after starting", "big"))
        tool = sf.compat_tool(game["appid"]) or "Steam's default Proton"
        opts = sf.launch_options(game["appid"])
        lay.addWidget(label(f"Runs with {gd.pretty_tool(tool)}" + (f" · launch options: {opts}" if opts else ""), "sub"))

        self.ai = label("", "sub")
        ai_card = self.card("ai", "In plain words", self.ai)
        lay.addWidget(ai_card)
        self.explain()

        for f in findings:
            card = QFrame()
            card.setObjectName("finding")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(18, 14, 18, 14)
            cl.setSpacing(8)
            head = QHBoxLayout()
            head.addWidget(icon_label("alert" if f["fixes"] else "shield", S.WARNING, 18))
            head.addWidget(label(f["title"], "cardTitle"), 1)
            cl.addLayout(head)
            cl.addWidget(label(f["text"], "sub"))
            if f["evidence"]:
                ev = QLabel("\n".join(l[-160:] for l in f["evidence"]))
                ev.setObjectName("evidence")
                ev.setWordWrap(True)
                ev.setTextInteractionFlags(Qt.TextSelectableByMouse)
                cl.addWidget(ev)
            for fix in f["fixes"]:
                cl.addWidget(FixButton(self, fix, game["appid"]))
            lay.addWidget(card)
        lay.addStretch(1)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(24, 10, 24, 18)
        self.status = label("Fixes can be undone here; the next start shows whether one worked.", "muted")
        foot.addWidget(self.status, 1)
        foot.addWidget(button("Show the log", slot=self.show_log, icon="doc"))
        foot.addWidget(button("Play again", "primary", self.play, icon="play"))
        outer.addLayout(foot)

    def card(self, icon, title, body):
        c = QFrame()
        c.setObjectName("finding")
        cl = QVBoxLayout(c)
        cl.setContentsMargins(18, 14, 18, 14)
        head = QHBoxLayout()
        head.addWidget(icon_label(icon, S.P.accent, 18))
        head.addWidget(label(title, "cardTitle"), 1)
        cl.addLayout(head)
        cl.addWidget(body)
        return c

    @staticmethod
    def header_image(appid):
        cache = sf.STEAM / "appcache/librarycache"
        for p in (cache / str(appid) / "header.jpg", cache / f"{appid}_header.jpg"):
            pm = QPixmap(str(p))
            if not pm.isNull():
                img = QLabel()
                img.setObjectName("header")
                img.setPixmap(pm.scaledToWidth(460, Qt.SmoothTransformation))
                return img
        return None

    def explain(self):
        """The local model's reading of the log, if it's free to run (not while a game holds the GPU)."""
        if DEMO:
            self.ai.setText("The game's DirectX-to-Vulkan layer (DXVK) couldn't create a device, so it quit before "
                            "showing a window. Switching to Proton-CachyOS, which ships a newer DXVK, usually fixes it.")
            return
        self.ai.setText("Reading the log on this PC…")

        def work():
            from assistant import pick_model, summarize
            if not pick_model():
                return "No local model to explain it (sudo deckos ai setup); the findings below come from known patterns."
            text = "\n".join(self.lines[-250:]) or "(no output)"
            return summarize(text, f"The game {self.game['name']} closed {round(self.session['seconds'])} seconds after "
                             "starting under Proton on Linux. In 2-3 plain sentences: what most likely went wrong, "
                             "quoting the one log line that shows it. Don't suggest commands.")
        self.ai_job = Job(self, work, on_done=self.explained)

    def explained(self, text, error):
        self.ai.setText(text or f"Couldn't ask the local model ({error}); the findings below still apply.")

    def say(self, text, bad=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {S.DANGER if bad else S.SUCCESS};")

    def play(self):
        if not DEMO:
            sf.start_steam(f"steam://rungameid/{self.game['appid']}")
        self.close()

    def show_log(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{self.game['name']}: what Steam's log caught")
        dlg.resize(900, 600)
        v = QVBoxLayout(dlg)
        text = QPlainTextEdit("\n".join(self.lines) or "(nothing)")
        text.setReadOnly(True)
        v.addWidget(text)
        dlg.exec()


def demo_case():
    session = {"appid": "1091500", "start": 0, "end": 4, "seconds": 4}
    game = {"appid": "1091500", "name": "Cyberpunk 2077"}
    lines = ["[2026-10-24 20:01:02] Proton: Upgrading prefix from None to CachyOS-11.0-100",
             "[2026-10-24 20:01:04] err:vulkan:vkCreateDevice failed VK_ERROR_INITIALIZATION_FAILED",
             "[2026-10-24 20:01:04] DXVK: D3D11CoreCreateDevice: failed to create device"]
    return session, game, lines, gd.diagnose(lines)


def main():
    args = sys.argv[1:]
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Game Doctor")
    app.setDesktopFileName("deckos-gamedoctor")
    app.setFont(QFont("Inter", 10))
    if DEMO:
        session, game, lines, findings = demo_case()
    else:
        appid = args[args.index("--appid") + 1] if "--appid" in args else None
        session = gd.last_failure(appid) or (next((s for s in reversed(gd.sessions()) if s["appid"] == str(appid)),
                                                  None) if appid else None)
        if not session:
            QMessageBox.information(None, "Game Doctor", "No game has closed early lately. Run it again from here "
                                    "the next time one does, or pass --appid.")
            return 0
        game = sf.game(session["appid"]) or {"appid": session["appid"], "name": f"App {session['appid']}"}
        lines = gd.game_output(session["start"], session["end"])
        findings = gd.diagnose(lines)
    w = Doctor(session, game, lines, findings)
    w.show()
    if "--screenshot" in args:
        out = args[args.index("--screenshot") + 1]

        def shoot():
            page = w.findChild(QScrollArea).widget()
            page.resize(page.width(), page.sizeHint().height())
            page.grab().save(out)
            app.exit(0)
        QTimer.singleShot(500, shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
