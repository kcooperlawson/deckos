"""DecKoOS Assistant, the chat box: Meta+Space anywhere, or from DecKoOS Menu, Quick Settings, the Hub.

Same assistant as `deckos ask` (assistant.py), in a window: the conversation, a line for each thing it
looks at, and a card with the exact command and Do it / Not now whenever it wants to change something.
One process: launching it again shows or hides the window (Meta+Space toggles), and the conversation
stays until "New chat".

    deckos-assistant                     show or hide the chat box
    deckos-assistant --ask "TEXT"        show it and ask TEXT (DecKoOS Menu's "Ask DecKoOS Assistant")
    deckos-assistant --demo [--screenshot DIR]
"""
import os
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]

from PySide6.QtCore import QObject, QProcess, QSize, QThread, QTimer, Qt, Signal  # noqa: E402
from PySide6.QtGui import QFont, QKeyEvent  # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,  # noqa: E402
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

import assistant  # noqa: E402
import hub_style as S  # noqa: E402
from hub_widgets import button, icon_label, label  # noqa: E402

DEMO = "--demo" in sys.argv
SOCKET = f"deckos-assistant-{os.getuid()}"
SUGGESTIONS = ["Install OBS for streaming", "What's using my graphics card?", "Set me up for Docker",
               "Why did my last update fail?"]

QSS_EXTRA = f"""
#root {{ background: {S.BG}; border: 1px solid {S.BORDER}; border-radius: 14px; }}
#header {{ background: transparent; }}
#you {{ background: {S.P.tint}; border: 1px solid {S.P.accent}; border-radius: 12px; }}
#bot {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 12px; }}
#ask {{ background: {S.SURFACE}; border: 1px solid #5C4A22; border-radius: 12px; }}
#composer {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 12px; }}
#composer QPlainTextEdit {{ background: transparent; border: none; padding: 2px; font-family: "Inter";
    font-size: 10.5pt; color: {S.TEXT}; }}
QPushButton#chip {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; border-radius: 14px; padding: 6px 12px;
    color: {S.SUBTEXT}; }}
QPushButton#chip:hover {{ color: {S.TEXT}; border-color: {S.P.accent}; }}
QPushButton#flat {{ background: transparent; border: none; padding: 4px; border-radius: 7px; }}
QPushButton#flat:hover {{ background: {S.RAISED}; }}
QLabel#cmd {{ font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 9pt; color: {S.TEXT};
    background: {S.SIDEBAR}; border: 1px solid {S.BORDER}; border-radius: 8px; padding: 8px; }}
QLabel#step {{ color: {S.SUBTEXT}; font-size: 9pt; }}
QLabel#out {{ font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; font-size: 8.5pt; color: {S.MUTED}; }}
#banner {{ background: #2A2416; border: 1px solid #5C4A22; border-radius: 9px; }}
"""


def gaming():
    state = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "deckos-mode"
    try:
        values = dict(l.split("=", 1) for l in state.read_text().splitlines() if "=" in l)
    except OSError:
        return None
    return values.get("game") or "a game" if values.get("mode") == "gaming" else None


# ------------------------------------------------------------------ the assistant, off the UI thread

class Worker(QObject):
    """Runs Session.ask in a thread. Changes wait on the UI: confirm() blocks until Do it / Not now."""
    step = Signal(str)
    output = Signal(str)
    confirm_request = Signal(str, str)
    answered = Signal(str)
    failed = Signal(str)

    def __init__(self, model):
        super().__init__()
        from assistant import Session, Tools
        self._answer = threading.Event()
        self._yes = False
        self.session = Session(model, Tools(self._confirm, self.step.emit, self.output.emit))

    def _confirm(self, title, detail):
        self._answer.clear()
        self.confirm_request.emit(title, detail)
        self._answer.wait()
        return self._yes

    def reply(self, yes):
        self._yes = yes
        self._answer.set()

    def ask(self, text):
        try:
            self.answered.emit(self.session.ask(text))
        except OSError as e:
            self.failed.emit(f"Couldn't reach Ollama ({e}). Is it running? Try: systemctl start ollama")
        except Exception as e:  # anything else still ends the turn, with the reason
            self.failed.emit(f"Something went wrong: {e}")


class DemoWorker(Worker):
    """Canned answers, no Ollama, for working on the window anywhere."""

    def __init__(self):
        QObject.__init__(self)
        self._answer = threading.Event()
        self._yes = False

    def ask(self, text):
        import time
        self.step.emit("Searching the Store for “obs”")
        time.sleep(0.4)
        self.step.emit("Looking: pacman -Q obs-studio")
        time.sleep(0.4)
        if self._confirm("Install OBS Studio from Arch/CachyOS repos?",
                         "pkexec pacman -S --noconfirm --needed obs-studio"):
            for line in ("resolving dependencies...", "installing obs-studio...", "(1/1) Arming ConditionNeedsUpdate..."):
                self.output.emit(line)
                time.sleep(0.3)
            self.answered.emit("**OBS Studio is installed.** Open it from the app menu. For streaming, its first-run "
                               "wizard sets the encoder: pick **Hardware (AMD)** so the graphics card does the work.")
        else:
            self.answered.emit("OK, I didn't install it. When you want it: `pkexec pacman -S obs-studio`.")


# ------------------------------------------------------------------ the window

class Bubble(QFrame):
    def __init__(self, text, mine):
        super().__init__()
        self.setObjectName("you" if mine else "bot")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        self.text = QLabel(text)
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.PlainText if mine else Qt.MarkdownText)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.text.setOpenExternalLinks(True)
        lay.addWidget(self.text)
        if mine:  # a wrapped label asks for its narrowest width; a short message shouldn't wrap
            self.setMinimumWidth(min(self.fontMetrics().horizontalAdvance(text) + 30, 420))


class AskCard(QFrame):
    """Do it / Not now for one change: what and why, and the exact command."""

    def __init__(self, title, detail, on_answer):
        super().__init__()
        self.setObjectName("ask")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(icon_label("alert", S.WARNING, 16))
        head.addWidget(label(f"<b>{title}</b>"), 1)
        lay.addLayout(head)
        cmd = QLabel(detail if len(detail) < 1200 else detail[:1200] + "…")
        cmd.setObjectName("cmd")
        cmd.setWordWrap(True)
        cmd.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(cmd)
        self.buttons = QHBoxLayout()
        self.yes = button("Do it", "primary", lambda: self.answer(True), icon="check")
        self.no = button("Not now", slot=lambda: self.answer(False))
        self.buttons.addWidget(self.yes)
        self.buttons.addWidget(self.no)
        self.buttons.addStretch(1)
        lay.addLayout(self.buttons)
        self.on_answer = on_answer

    def answer(self, yes):
        self.yes.hide()
        self.no.hide()
        self.buttons.insertWidget(0, label("You said yes" if yes else "You said no: skipped", "sub"))
        self.on_answer(yes)


class Composer(QFrame):
    sent = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("composer")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 6, 6)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Ask Deck to install, fix or set up anything…")
        self.edit.setFixedHeight(46)
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit, 1)
        self.send = QPushButton()
        self.send.setObjectName("primary")
        self.send.setIcon(S.icon("arrow-up", "white", 16))
        self.send.setFixedSize(36, 36)
        self.send.setCursor(Qt.PointingHandCursor)
        self.send.setToolTip("Send (Enter)")
        self.send.clicked.connect(self.submit)
        lay.addWidget(self.send, 0, Qt.AlignBottom)

    def eventFilter(self, obj, event):
        # Enter sends, Shift+Enter is a new line
        if isinstance(event, QKeyEvent) and event.type() == QKeyEvent.KeyPress \
                and event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.submit()
            return True
        return False

    def submit(self):
        text = self.edit.toPlainText().strip()
        if text and self.send.isEnabled():
            self.edit.clear()
            self.sent.emit(text)

    def set_busy(self, busy):
        self.send.setEnabled(not busy)
        self.edit.setPlaceholderText("Working on it…" if busy else "Ask Deck to install, fix or set up anything…")


class ChatBox(QWidget):
    ask_in_thread = Signal(str)

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("DecKoOS Assistant")
        self.resize(660, 600)
        self.setStyleSheet(S.styled(S._qss() + QSS_EXTRA))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        root = QFrame()
        root.setObjectName("root")
        outer.addWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)

        # header: drag to move (Wayland lets the compositor do it)
        self.header = QWidget()
        self.header.setObjectName("header")
        h = QHBoxLayout(self.header)
        h.setContentsMargins(0, 0, 0, 0)
        tile = QLabel()
        tile.setPixmap(S.pixmap("ai", "white", 18))
        tile.setAlignment(Qt.AlignCenter)
        tile.setFixedSize(32, 32)
        tile.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {S.P.accent}, "
                           f"stop:1 {S.P.grad_b}); border-radius: 9px;")
        h.addWidget(tile)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("Deck", "cardTitle"))
        self.model_label = label("", "muted")
        names.addWidget(self.model_label)
        h.addLayout(names, 1)
        for name, tip, slot in (("code", "Bigger job? Open the workspace for code, documents and images",
                                 lambda: QProcess.startDetached("deckos-work", [])),
                                ("refresh", "New chat", self.new_chat), ("close", "Hide (Esc). Meta+Space brings it back", self.hide)):
            b = QPushButton()
            b.setObjectName("flat")
            b.setIcon(S.icon(name, S.SUBTEXT, 18))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(slot)
            h.addWidget(b)
        lay.addWidget(self.header)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(10, 7, 10, 7)
        bl.addWidget(icon_label("gaming", S.WARNING, 16))
        self.banner_text = label("", "sub")
        bl.addWidget(self.banner_text, 1)
        self.banner.hide()
        lay.addWidget(self.banner)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.feed_host = QWidget()
        self.feed = QVBoxLayout(self.feed_host)
        self.feed.setContentsMargins(0, 0, 4, 0)
        self.feed.setSpacing(8)
        self.feed.addStretch(1)
        self.scroll.setWidget(self.feed_host)
        self.scroll.verticalScrollBar().rangeChanged.connect(lambda _a, b: self.scroll.verticalScrollBar().setValue(b))
        lay.addWidget(self.scroll, 1)

        self.composer = Composer()
        self.composer.sent.connect(self.ask)
        lay.addWidget(self.composer)

        self.thinking = QTimer(self)
        self.thinking.setInterval(400)
        self.thinking.timeout.connect(self._tick)
        self._dots = 0
        self.status = None
        self.output = None
        self.thread = None
        self.worker = None
        self.answering = False
        self.new_chat()

    # -- window behaviour

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.geometry().contains(event.position().toPoint()) \
                and self.windowHandle():
            self.windowHandle().startSystemMove()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def summon(self, text=None):
        game = gaming()
        self.banner.setVisible(bool(game))
        if game:
            self.banner_text.setText(f"{game} is running. Asking loads the model back into graphics memory, "
                                     "which can make the game stutter.")
        self.show()
        self.raise_()
        self.activateWindow()
        self.composer.edit.setFocus()
        if text:
            self.ask(text)

    def shutdown(self):
        """The worker's thread stops before Qt tears down (a running QThread aborts the process)."""
        if self.worker:
            self.worker.reply(False)  # a question still waiting is a no
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)

    def toggle(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.summon()

    # -- the conversation

    def new_chat(self):
        if self.answering:
            return  # finish the current answer first (the worker thread itself runs until the window closes)
        while self.feed.count() > 1:
            w = self.feed.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.start_worker()
        intro = QWidget()
        il = QVBoxLayout(intro)
        il.setContentsMargins(4, 20, 4, 4)
        il.setSpacing(10)
        hello, about = assistant.greeting()
        if assistant.web_on():
            about += " Web search is on: I can look things up online too, and I'll show you the sites."
        il.addWidget(label(f"<b>{hello}</b>", "big"))
        il.addWidget(label(about, "sub"))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for s in SUGGESTIONS[:2]:
            chips.addWidget(self._chip(s))
        chips.addStretch(1)
        chips2 = QHBoxLayout()
        chips2.setSpacing(6)
        for s in (SUGGESTIONS[2:3] + ["Any fixes for my game crashing?"] if assistant.web_on() else SUGGESTIONS[2:]):
            chips2.addWidget(self._chip(s))
        chips2.addStretch(1)
        il.addLayout(chips)
        il.addLayout(chips2)
        self.intro = intro
        self._add(intro)

    def _chip(self, text):
        b = QPushButton(text)
        b.setObjectName("chip")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.ask(text))
        return b

    def start_worker(self):
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        if self.worker:
            self.ask_in_thread.disconnect(self.worker.ask)
            self.worker.deleteLater()
        if DEMO:
            self.worker, model = DemoWorker(), "gpt-oss:20b (demo)"
        else:
            from assistant import pick_model
            model = pick_model()
            if not model:
                self.model_label.setText("no model downloaded")
                self.worker = None
                self._add(label("No local model is downloaded yet. In a terminal: <b>sudo deckos ai setup</b>", "sub"))
                self.composer.set_busy(True)
                return
            self.worker = Worker(model)
        self.model_label.setText(f"DecKoOS Assistant · {model} · on this PC"
                                 + (" · web search on" if assistant.web_on() else ""))
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.ask_in_thread.connect(self.worker.ask)
        self.worker.step.connect(self.on_step)
        self.worker.output.connect(self.on_output)
        self.worker.confirm_request.connect(self.on_confirm)
        # bound methods, not lambdas: a lambda would run in the worker's thread and build widgets there
        self.worker.answered.connect(self.finish)
        self.worker.failed.connect(self.finish_failed)
        self.thread.start()
        self.composer.set_busy(False)

    def _add(self, widget, align=None):
        if align is not None:
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            if align == Qt.AlignRight:
                wl.addStretch(1)
            widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            widget.setMaximumWidth(520)
            wl.addWidget(widget)
            if align == Qt.AlignLeft:
                wl.addStretch(1)
            widget = wrap
        self.feed.insertWidget(self.feed.count() - 1, widget)

    def ask(self, text):
        if not self.worker or (self.thread and not self.composer.send.isEnabled()):
            return
        if self.intro:
            self.intro.hide()
            self.intro = None
        self._add(Bubble(text, True), Qt.AlignRight)
        self.status = label("thinking", "step")
        self._add(self.status)
        self.output = None
        self.composer.set_busy(True)
        self.answering = True
        self.thinking.start()
        self.ask_in_thread.emit(text)

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        if self.status:
            self.status.setText("thinking" + "." * self._dots)

    def _settle_status(self):
        """The 'thinking…' line moves to the end of the feed, under the newest step."""
        if self.status:
            self.feed.removeWidget(self.status)
            self._add(self.status)

    def on_step(self, text):
        step = label(f"› {text}", "step")
        if "<a href" in text:  # web sources: open in the browser
            step.setTextFormat(Qt.RichText)
            step.setOpenExternalLinks(True)
        self._add(step)
        self.output = None
        self._settle_status()

    def on_output(self, line):
        if self.output is None:
            self.output = label("", "out")
            self.output.setWordWrap(True)
            self._add(self.output)
            self._lines = []
        self._lines = (self._lines + [line])[-6:]  # the last few lines: enough to see it's moving
        self.output.setText("\n".join(self._lines))
        self._settle_status()

    def on_confirm(self, title, detail):
        self.thinking.stop()
        if self.status:
            self.status.hide()
        self._add(AskCard(title, detail, self._answered))
        self.summon()  # it may have been hidden while it worked

    def _answered(self, yes):
        if self.status:
            self.status.show()
            self._settle_status()
        self.thinking.start()
        self.worker.reply(yes)

    def finish_failed(self, text):
        self.finish(text, failed=True)

    def finish(self, text, failed=False):
        self.answering = False
        self.thinking.stop()
        if self.status:
            self.status.deleteLater()
            self.status = None
        bubble = Bubble(text or "(no answer)", False)
        if failed:
            bubble.text.setStyleSheet(f"color: {S.DANGER};")
        self._add(bubble)  # answers use the full width: they're where the reading is
        self.composer.set_busy(False)
        self.composer.edit.setFocus()


# ------------------------------------------------------------------ one instance

def main():
    args = sys.argv[1:]
    ask_text = args[args.index("--ask") + 1] if "--ask" in args and args.index("--ask") + 1 < len(args) else None
    message = ("ask:" + ask_text) if ask_text else "toggle"

    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Assistant")
    app.setDesktopFileName("org.deckos.assistant")
    app.setFont(QFont("Inter", 10))
    app.setQuitOnLastWindowClosed(False)  # hidden keeps the conversation; Meta+Space brings it back

    if not DEMO:
        sock = QLocalSocket()
        sock.connectToServer(SOCKET)
        if sock.waitForConnected(300):
            sock.write(message.encode())
            sock.waitForBytesWritten(300)
            return 0
        QLocalServer.removeServer(SOCKET)  # a stale one from a crash

    box = ChatBox()
    app.aboutToQuit.connect(box.shutdown)
    if not DEMO:
        server = QLocalServer()
        server.listen(SOCKET)

        def incoming():
            conn = server.nextPendingConnection()
            conn.waitForReadyRead(300)
            msg = bytes(conn.readAll()).decode(errors="replace")
            conn.close()
            if msg.startswith("ask:"):
                box.summon(msg[4:])
            else:
                box.toggle()

        server.newConnection.connect(incoming)
    box.summon(ask_text)

    if DEMO and "--screenshot" in args:
        out = Path(args[args.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)
        box.composer.edit.setPlainText("")

        def shoot(name, then=None):
            box.grab().save(str(out / f"{name}.png"))
            print(f"deckos-assistant screenshot: {name}.png")
            if then:
                then()

        QTimer.singleShot(500, lambda: shoot("1-start", lambda: box.ask("Install OBS for streaming")))
        QTimer.singleShot(2200, lambda: shoot("2-confirm", lambda: box.findChild(AskCard).answer(True)))
        QTimer.singleShot(4200, lambda: (shoot("3-done"), app.exit(0)))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
