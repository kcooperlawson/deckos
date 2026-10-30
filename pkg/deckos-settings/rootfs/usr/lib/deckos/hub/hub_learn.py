"""DecKoOS Hub's "Made for you" card (Home): what DecKoOS has noticed about how you use this PC, and the small changes
it suggests from that (learn/learn.py: it reads what the PC already keeps, sends nothing). Each suggestion is yours:
Do it, or Not now (remembered, so it doesn't come back). Read in the background: a game library on a sleeping hard
drive can take a while to answer."""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import hub_style as S  # noqa: E402
import hub_system as sysinfo  # noqa: E402
from hub_widgets import Card, RowItem, button, icon_label, label  # noqa: E402

LEARN = Path(__file__).resolve().parent.parent / "learn/learn.py"

DEMO_NOTICED = [{"icon": "grid", "text": "Your most-used apps: DecKoOS Hub, Terminal, Spotify"},
                {"icon": "gaming", "text": "You usually play between 6 PM and 10 PM"},
                {"icon": "star", "text": "Your most-played game: BeamNG.drive (1273 h)"}]
DEMO_SUGGEST = [{"key": "pin:firefox.desktop", "icon": "plus", "title": "Pin Firefox to the taskbar",
                 "detail": "You open it most days, and it isn't on the taskbar.", "run": []},
                {"key": "space:1", "icon": "drives", "title": "Free 119 GB: uninstall Red Dead Redemption 2",
                 "detail": "Last played 7 months ago. Steam can reinstall it any time.", "run": []}]


class MadeForYouCard(Card):
    def __init__(self, hub):
        super().__init__("Made for you", "DecKoOS learning how you use this PC", "star")
        self.hub = hub
        self.actions.addWidget(button("Forget it all", slot=self.forget, icon="trash",
                                      tip="Clears the suggestions you turned down. It never stored anything else."))
        self.body.addWidget(label("Worked out on this PC from what it already keeps (the apps you open, your Steam "
                                  "library, your timeline). Nothing new is collected and nothing is sent.", "sub"))
        self.noticed = QVBoxLayout()
        self.noticed.setSpacing(4)
        self.body.addLayout(self.noticed)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        self.body.addLayout(self.rows)
        self.procs = []
        self.load()

    def run_learn(self, args, done):
        if sysinfo.DEMO:
            done(json.dumps(DEMO_NOTICED if args == ["noticed"] else DEMO_SUGGEST if args == ["suggest"] else []))
            return
        proc = QProcess(self)
        self.procs.append(proc)

        def finished(*_a):
            out = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            self.procs.remove(proc)
            proc.deleteLater()
            done(out)
        proc.finished.connect(finished)
        proc.start(sys.executable, [str(LEARN), *args])

    def load(self):
        self.run_learn(["noticed"], self.show_noticed)
        self.run_learn(["suggest"], self.show_suggestions)

    @staticmethod
    def clear(layout):
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def parse(self, out):
        try:
            return json.loads(out or "[]")
        except ValueError:
            return []

    def show_noticed(self, out):
        self.clear(self.noticed)
        for n in self.parse(out):
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setSpacing(9)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(icon_label(n.get("icon", "info"), S.P.accent, 16), 0, Qt.AlignTop)
            row.addWidget(label(n.get("text", ""), None), 1)
            self.noticed.addWidget(holder)

    def show_suggestions(self, out):
        self.clear(self.rows)
        items = self.parse(out)
        if not items:
            self.rows.addWidget(label("Nothing to suggest right now. As you use the PC, this fills in.", "muted"))
        for s in items:
            do = button("Do it", "primary", slot=lambda _=False, x=s: self.do(x))
            no = button("Not now", slot=lambda _=False, x=s: self.no(x))
            self.rows.addWidget(RowItem(s.get("icon", "star"), s["title"], s.get("detail", ""), S.P.accent, (do, no)))

    def do(self, s):
        if s.get("run") and not sysinfo.DEMO:
            QProcess.startDetached(s["run"][0], s["run"][1:])
        self.hub.toast(f"Done: {s['title']}" if s.get("kind") != "space" else "Steam asks before uninstalling", "ok")
        self.no(s, quiet=True)  # handled: it doesn't come back

    def no(self, s, quiet=False):
        self.run_learn(["dismiss", s["key"]], lambda _o: self.run_learn(["suggest"], self.show_suggestions))
        if sysinfo.DEMO:
            self.show_suggestions(json.dumps([x for x in DEMO_SUGGEST if x["key"] != s["key"]]))

    def forget(self):
        self.run_learn(["forget"], lambda _o: self.load())
        self.hub.toast("Forgotten: turned-down suggestions can come back", "ok")
