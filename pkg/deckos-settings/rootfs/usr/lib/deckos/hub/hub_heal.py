"""DecKoOS's fixes (self-healing), said plainly up front with a switch for each part: DecKoOS Hub > System and Welcome's
privacy step show this same card. The switches run `deckos heal settings` (the person's own file); heal.py reads it."""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heal"))
import heal  # noqa: E402
import hub_style as S  # noqa: E402
import hub_system as sysinfo  # noqa: E402
from hub_widgets import Card, button, icon_label, label, row  # noqa: E402

FACTS = (
    ("check", "When something breaks, DecKoOS can suggest a fix from its own list of reviewed fixes. An AI may choose "
              "one; it can't write its own."),
    ("shield", "Nothing runs without you: you see the exact commands and say yes. Fixes that change the system take a "
               "snapshot first, so they can be undone from the Timeline."),
    ("eye", "It remembers which fixes it used and whether they worked, on this PC only."),
    ("globe", "Nothing is sent. To help others with the same problem, you can make a report, read every word of it, "
              "and submit it to GitHub yourself."),
)
SWITCHES = (("suggest", "Suggest fixes", "DecKoOS Assistant may offer its reviewed fixes (it always asks first)"),
            ("remember", "Remember fixes on this PC", "Kept on this PC; reports are made from it"),
            ("reports", "Offer to make fix reports", "You read each one and submit it yourself, or don't"))


class HealCard(Card):
    def __init__(self, toast=None):
        super().__init__("Fixes", "Self-healing: what DecKoOS does, and doesn't", "check")
        self.toast = toast or (lambda *_a: None)
        for ic, text in FACTS:
            h = QHBoxLayout()
            h.setSpacing(10)
            h.addWidget(icon_label(ic, S.SUBTEXT, 16), 0, Qt.AlignTop)
            h.addWidget(label(text, "sub"), 1)
            self.body.addLayout(h)
        now = {"suggest": "on", "remember": "on", "reports": "on"} if sysinfo.DEMO else heal.settings()
        for key, text, tip in SWITCHES:
            box = QCheckBox(text)
            box.setToolTip(tip)
            box.setChecked(now[key] == "on")
            box.toggled.connect(lambda on, k=key, t=text: self.switch(k, on, t))
            self.body.addWidget(box)
        self.body.addWidget(row(button("Forget everything", slot=self.forget, icon="trash",
                                       tip="Deletes the record of fixes on this PC")))

    def switch(self, key, on, text):
        if not sysinfo.DEMO:
            subprocess.run([sysinfo.DECKOS, "heal", "settings", key, "on" if on else "off"], capture_output=True)
        self.toast(f"{text}: {'on' if on else 'off'}", "ok")

    def forget(self):
        if QMessageBox.question(self, "Forget fixes", "Delete the record of which fixes were used on this PC?") \
                != QMessageBox.Yes:
            return
        if not sysinfo.DEMO:
            subprocess.run([sysinfo.DECKOS, "heal", "forget"], capture_output=True)
        self.toast("This PC no longer remembers any fixes", "ok")
