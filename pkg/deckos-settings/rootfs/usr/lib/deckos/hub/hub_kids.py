"""DecKoOS Hub's Kids card (System page): set up Kid mode per child (apps, time limit, bedtime, web) and start it.
Changes go through `deckos kids` with pkexec; kids.py (no Qt) reads the settings."""
import json
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog, QLineEdit,
                               QMessageBox, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kids"))
import hub_system as sysinfo  # noqa: E402
import kids  # noqa: E402
from hub_widgets import Card, RowItem, button, label  # noqa: E402

DEMO_KIDS = [{"name": "mia", "display": "Mia", "apps": "org.kde.kolourpaint,tuxpaint,deckos-kids-browser",
              "minutes": "60", "bedtime": "19:30", "web": "filtered"},
             {"name": "leo", "display": "Leo", "apps": "org.kde.gcompris,org.kde.ktuberling", "minutes": "0",
              "bedtime": "", "web": "off"}]
DEMO_APPS = {i: {"id": i, "name": n, "icon": "", "exec": "", "comment": ""} for i, n in (
    ("org.kde.kolourpaint", "KolourPaint"), ("tuxpaint", "Tux Paint"), ("org.kde.gcompris", "GCompris"),
    ("org.kde.ktuberling", "Potato Guy"), ("deckos-kids-browser", "The web"), ("steam", "Steam"),
    ("org.kde.dolphin", "Dolphin"))}
WEB = {"filtered": "Filtered web", "open": "Open web", "off": "No web"}


def summary(k):
    apps = len([a for a in k["apps"].split(",") if a])
    bits = [f"{apps} app{'s' if apps != 1 else ''}",
            f"{k['minutes']} min a day" if k["minutes"] not in ("", "0") else "no daily limit"]
    if k["bedtime"]:
        bits.append(f"bedtime {k['bedtime']}")
    bits.append(WEB.get(k["web"], k["web"]).lower())
    return ", ".join(bits)


class AppsDialog(QDialog):
    """Tick the apps a child gets: suggested (made for kids) first, then everything else installed."""

    def __init__(self, parent, kid, apps):
        super().__init__(parent)
        self.setWindowTitle(f"Apps for {kid['display'] or kid['name']}")
        self.resize(460, 560)
        v = QVBoxLayout(self)
        v.addWidget(label("Their tiles in Kid mode. Only what's ticked can be opened.", "sub"))
        chosen = [a for a in kid["apps"].split(",") if a]
        suggested = [i for i in kids.SUGGESTED if i in apps]
        order = list(dict.fromkeys(chosen + suggested + sorted(apps, key=lambda i: apps[i]["name"].lower())))
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setSpacing(2)
        self.boxes = {}
        for i in order:
            if i not in apps:
                continue
            tag = "  (made for kids)" if i in suggested else ""
            b = QCheckBox(apps[i]["name"] + tag)
            b.setChecked(i in chosen)
            self.boxes[i] = b
            lay.addWidget(b)
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        v.addWidget(scroll, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def ids(self):
        return [i for i, b in self.boxes.items() if b.isChecked()]


class LimitsDialog(QDialog):
    def __init__(self, parent, kid):
        super().__init__(parent)
        self.setWindowTitle(f"Limits for {kid['display'] or kid['name']}")
        f = QFormLayout(self)
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 1440)
        self.minutes.setSingleStep(15)
        self.minutes.setSpecialValueText("No limit")
        self.minutes.setSuffix(" min")
        self.minutes.setValue(int(kid["minutes"] or 0))
        f.addRow("Time a day", self.minutes)
        self.bedtime = QLineEdit(kid["bedtime"])
        self.bedtime.setPlaceholderText("none, or like 19:30")
        f.addRow("Bedtime", self.bedtime)
        self.web = QComboBox()
        for key, text in WEB.items():
            self.web.addItem(text, key)
        self.web.setCurrentIndex(max(0, self.web.findData(kid["web"])))
        f.addRow("The web", self.web)
        f.addRow(label("Filtered: a family filter blocks adult and unsafe sites in their Firefox. They get a warning "
                       "5 minutes before the time's up, then Kid mode logs out.", "muted"))
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.check)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def check(self):
        if self.bedtime.text().strip() and not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", self.bedtime.text().strip()):
            QMessageBox.warning(self, "Bedtime", "Write the bedtime like 19:30, or leave it empty.")
            return
        self.accept()


class KidsCard(Card):
    def __init__(self, hub):
        super().__init__("Kids", "Kid mode", "user")
        self.hub = hub
        self.body.addWidget(label("Each child gets their own account: only the apps you pick, a filtered web and, "
                                  "if you like, a time limit. Your session stays locked underneath, and your "
                                  "password brings it back.", "sub"))
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        self.body.addLayout(self.rows)
        self.start = button("Start Kid mode", "primary", self.start_kid_mode, icon="play",
                            tip="Locks your session and shows the login screen; tap a child's picture")
        self.body.addWidget(self.row_of(self.start, button("Add a child…", slot=self.add, icon="plus")))
        self.refresh()

    @staticmethod
    def row_of(*widgets):
        from hub_widgets import row
        return row(*widgets)

    def kids_list(self):
        if sysinfo.DEMO:
            return DEMO_KIDS
        try:
            return json.loads(subprocess.run([sysinfo.DECKOS, "kids", "list", "--json"], capture_output=True,
                                             text=True, timeout=10).stdout or "[]")
        except (OSError, ValueError, subprocess.SubprocessError):
            return []

    def refresh(self):
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        found = self.kids_list()
        self.start.setEnabled(bool(found))
        if not found:
            self.rows.addWidget(label("No children set up yet.", "muted"))
        for k in found:
            right = (button("Apps…", slot=lambda _=False, k=k: self.pick_apps(k), icon="grid"),
                     button("Limits…", slot=lambda _=False, k=k: self.limits(k), icon="clock"),
                     button("Remove", slot=lambda _=False, k=k: self.remove(k), icon="trash"))
            self.rows.addWidget(RowItem("user", k["display"] or k["name"], summary(k), right=right))

    def run(self, args, done_text):
        def done(ok):
            self.hub.toast(done_text if ok else "That didn't work (the password was cancelled?)", "ok" if ok else "warn")
            self.refresh()
        self.hub.privileged(["kids", *args], done)

    def add(self):
        display, ok = QInputDialog.getText(self, "Add a child", "Their name, as they'll see it:")
        if not ok or not display.strip():
            return
        name = re.sub(r"[^a-z0-9]", "", display.strip().lower())[:30]
        if not kids.valid_name(name):
            QMessageBox.warning(self, "Add a child", "Use a name that starts with a letter, like Mia.")
            return
        self.run(["add", name, display.strip()], f"{display.strip()} is set up: their picture is on the login screen")

    def pick_apps(self, k):
        apps = DEMO_APPS if sysinfo.DEMO else kids.installed_apps()
        d = AppsDialog(self, k, apps)
        if d.exec() == QDialog.Accepted:
            self.run(["apps", k["name"], ",".join(d.ids())], f"{k['display'] or k['name']}'s apps saved")

    def limits(self, k):
        d = LimitsDialog(self, k)
        if d.exec() != QDialog.Accepted:
            return
        name = k["name"]
        # One password prompt for all three (each value is checked above or comes from a fixed list)
        self.hub.privileged_cmd(["sh", "-c", f"{sysinfo.DECKOS} kids limit {name} {d.minutes.value()} && "
                                 f"{sysinfo.DECKOS} kids bedtime {name} '{d.bedtime.text().strip()}' && "
                                 f"{sysinfo.DECKOS} kids web {name} {d.web.currentData()}"],
                                lambda ok: (self.hub.toast(f"{k['display'] or name}'s limits saved" if ok else
                                                           "Limits not changed", "ok" if ok else "warn"),
                                            self.refresh()))

    def remove(self, k):
        if QMessageBox.question(self, "Remove a child", f"Remove {k['display'] or k['name']}'s Kid mode account? Their "
                                "drawings and saves go too.") != QMessageBox.Yes:
            return
        self.run(["remove", k["name"]], f"{k['display'] or k['name']}'s account is removed")

    def start_kid_mode(self):
        if sysinfo.DEMO:
            self.hub.toast("Would lock your session and show the login screen", "info")
            return
        QProcess.startDetached(sysinfo.DECKOS, ["kids", "start"])
