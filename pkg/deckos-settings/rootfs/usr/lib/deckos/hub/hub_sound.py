"""DecKoOS Hub's Sound page: outputs and microphones, every app that's playing sorted into kinds (games, music, voice
chat…) with a slider per kind, the equalizer and the crackle guard (PipeWire's buffer floor). sound.py (no Qt) does
the work through pactl; changes run as background jobs, so a slow sound server never freezes the Hub."""
import json
import re
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QSlider, QVBoxLayout, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sound"))
import hub_style as S  # noqa: E402
import hub_system as sysinfo  # noqa: E402
import sound  # noqa: E402
from hub_pages import Page  # noqa: E402
from hub_widgets import Card, button, icon_label, label  # noqa: E402

SOUND = str(Path(sound.__file__).resolve())


def slider(value, on_release):
    s = QSlider(Qt.Horizontal)
    s.setRange(0, 100)
    s.setValue(min(100, value))
    s.setFixedWidth(S.scaled(200))  # the same width everywhere, so kinds and their apps line up
    s.sliderReleased.connect(lambda: on_release(s.value()))
    s.setToolTip(f"{value}%")
    s.valueChanged.connect(lambda v: s.setToolTip(f"{v}%"))
    return s


def line(*widgets, stretch_at=1):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    for i, x in enumerate(widgets):
        h.addWidget(x, 1 if i == stretch_at else 0)
    if stretch_at >= len(widgets):
        h.addStretch(1)  # nothing grows: keep them together on the left
    return w


class SoundPage(Page):
    title = "Sound"
    subtitle = "What plays where, how loud each kind of sound is, the equalizer and no more crackles."

    def build(self):
        self.head_actions.addWidget(button("", slot=self.refresh, icon="refresh", tip="Read the sound setup again"))
        self.outputs = Card("Outputs", "Speakers and headsets", "volume")
        self.inputs = Card("Microphones", None, "mic")
        self.playing = Card("Playing now", "Each kind of sound, and the apps in it", "music")
        self.eq = Card("Equalizer", "Shape the sound of an output", "sliders")
        self.guard = Card("Crackle guard", "Steady sound while games load the CPU", "check")
        for c in (self.outputs, self.inputs, self.playing, self.eq, self.guard):
            self.lay.addWidget(c)
        self.parts = {c: [] for c in (self.outputs, self.inputs, self.playing, self.eq, self.guard)}
        self.state = None
        # Live while the page is on screen: pactl subscribe says when anything changes (no polling); a burst of
        # changes is read once, and not while a slider is held
        self.watch = None
        self.again = QTimer(self, singleShot=True, interval=400, timeout=self.changed)

    def showEvent(self, e):
        super().showEvent(e)
        if sysinfo.DEMO or self.watch:
            return
        self.watch = QProcess(self)
        self.watch.readyReadStandardOutput.connect(self.heard)
        self.watch.start("pactl", ["subscribe"])

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.watch:
            self.watch.kill()
            self.watch.deleteLater()
            self.watch = None

    def heard(self):
        text = bytes(self.watch.readAllStandardOutput()).decode(errors="replace")
        if re.search(r" on (sink-input|sink|source|server)\b", text):  # "Event 'change' on sink #71"
            self.again.start()

    def changed(self):
        if any(s.isSliderDown() for s in self.findChildren(QSlider)):
            self.again.start()  # someone is dragging: read after they let go
            return
        if any(c.view().isVisible() for c in self.findChildren(QComboBox)):
            self.again.start()  # a list is open
            return
        self.refresh()

    def refresh(self):
        sysinfo.Job(self, ["python3", SOUND, "status"], self.got, demo=(json.dumps(sound.demo_state()), 0))

    def got(self, out, code):
        try:
            self.state = json.loads(out) if code == 0 else None
        except ValueError:
            self.state = None
        self.render()

    # ---- running sound.py

    def do(self, *args, then=True, msg=None):
        def done(out, code):
            if msg and code == 0:
                self.hub.toast(msg, "ok")
            elif code != 0:
                self.hub.toast("That didn't work: " + (out.strip() or "the sound server didn't answer"), "bad")
            if then:
                self.refresh()
        sysinfo.Job(self, ["python3", SOUND, *args], done, demo=("", 0))

    def pactl(self, *args):
        sysinfo.Job(self, ["pactl", *args], lambda *_: self.refresh(), demo=("", 0))

    # ---- drawing

    def clear(self, card):
        for w in self.parts[card]:
            w.deleteLater()
        self.parts[card] = []

    def add(self, card, w):
        card.body.addWidget(w)
        self.parts[card].append(w)
        return w

    def render(self):
        for c in self.parts:
            self.clear(c)
        st = self.state
        if not st or not st.get("running"):
            self.add(self.outputs, label("The sound server isn't answering. Restarting the PC usually brings it back.",
                                         "sub"))
            return
        outs = [d for d in st["devices"] if d["kind"] == "output"]
        ins = [d for d in st["devices"] if d["kind"] == "input"]
        for d in outs:
            self.add(self.outputs, self.device_row(d))
        for d in ins:
            self.add(self.inputs, self.device_row(d))
        if not ins:
            self.add(self.inputs, label("No microphone is plugged in.", "sub"))
        self.render_playing(st, outs)
        self.render_eq(st, outs)
        self.render_guard(st)

    def device_row(self, d):
        kind = d["kind"]
        ic = icon_label("mic" if kind == "input" else "headphones" if any(w in d["label"].lower() for w in ("head", "astro", "arctis", "hyperx",
                                                                             "a50", "buds", "airpods"))
                        else "display" if "hdmi" in d["label"].lower() else "volume",
                        S.P.accent if d["default"] else S.SUBTEXT, 18)
        name = label(("<b>" + d["label"] + "</b>") if d["default"] else d["label"], wrap=False)
        name.setToolTip(d["label"])
        mute = button("", slot=lambda: self.pactl("set-sink-mute" if kind == "output" else "set-source-mute",
                                                  str(d["index"]), "toggle"),
                      icon="volume-mute" if d["mute"] else "volume", tip="Unmute" if d["mute"] else "Mute")
        vol = slider(d["volume"], lambda v: self.pactl("set-sink-volume" if kind == "output" else "set-source-volume",
                                                       str(d["index"]), f"{v}%"))
        use = label("In use", "muted", wrap=False) if d["default"] else button(
            "Use", slot=lambda: self.pactl("set-default-sink" if kind == "output" else "set-default-source", d["name"]),
            tip="Make this the one new sound uses")
        use.setFixedWidth(S.scaled(56))  # "In use" and "Use" take the same room, so the sliders line up
        if d["default"]:
            use.setAlignment(Qt.AlignCenter)
        return line(ic, name, vol, mute, use, stretch_at=1)

    def render_playing(self, st, outs):
        apps = st["apps"]
        if not apps:
            self.add(self.playing, label("Nothing is playing right now. Start a game or some music and press the "
                                         "refresh button.", "sub"))
            return
        for kind, title, icon in sound.KINDS:
            mine = [a for a in apps if a["kind"] == kind]
            if not mine:
                continue
            avg = round(sum(a["volume"] for a in mine) / len(mine))
            spacer = QWidget()
            spacer.setFixedWidth(S.scaled(260) + 10 + S.scaled(36) + 10)  # under the output picker and mute button
            head = line(icon_label(icon, S.P.accent, 18), label(f"<b>{title}</b>", wrap=False),
                        slider(avg, lambda v, k=kind: self.do("set-kind", k, str(v))), spacer, stretch_at=1)
            head.setToolTip(f"Sets every app in {title.lower()} at once")
            self.add(self.playing, head)
            for a in mine:
                self.add(self.playing, self.app_row(a, outs))
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {S.BORDER};")
            self.add(self.playing, sep)
        self.parts[self.playing][-1].hide()  # no line under the last kind

    def app_row(self, a, outs):
        name = label(("    " + a["name"]) + ("  <span style='color:%s'>(paused)</span>" % S.MUTED if a["corked"] else ""),
                     "sub", wrap=False)
        where = QComboBox()
        for d in outs:
            where.addItem(d["label"], d["index"])
        where.setCurrentIndex(max(0, where.findData(a["sink"])))
        where.setFixedWidth(S.scaled(260))
        where.activated.connect(lambda _i, w=where: self.pactl("move-sink-input", str(a["index"]), str(w.currentData())))
        where.setToolTip("Where this app plays")
        mute = button("", slot=lambda: self.pactl("set-sink-input-mute", str(a["index"]), "toggle"),
                      icon="volume-mute" if a["mute"] else "volume", tip="Unmute" if a["mute"] else "Mute")
        vol = slider(a["volume"], lambda v: self.pactl("set-sink-input-volume", str(a["index"]), f"{v}%"))
        return line(name, vol, where, mute, stretch_at=0)

    def render_eq(self, st, outs):
        now = st.get("eq") or ""
        self.eq_box = QComboBox()
        self.eq_box.addItem("Off", "off")
        for key, (title, _desc, _bands) in sound.EQ_PRESETS.items():
            self.eq_box.addItem(title, key)
        self.eq_box.setCurrentIndex(max(0, self.eq_box.findData(now or "off")))
        self.eq_target = QComboBox()
        for d in outs:
            if d["name"] != sound.EQ_NODE:
                self.eq_target.addItem(d["label"], d["name"])
        default = next((d["name"] for d in outs if d["default"] and d["name"] != sound.EQ_NODE), None)
        if default:
            self.eq_target.setCurrentIndex(max(0, self.eq_target.findData(default)))
        self.eq_desc = label("", "muted")
        self.eq_box.currentIndexChanged.connect(self.describe_eq)
        self.describe_eq()
        self.add(self.eq, line(label("Preset", "sub", wrap=False), self.eq_box, label("on", "sub", wrap=False),
                               self.eq_target,
                               button("Apply", "primary", self.apply_eq, icon="check"), stretch_at=99))
        self.add(self.eq, self.eq_desc)

    def describe_eq(self):
        key = self.eq_box.currentData()
        self.eq_desc.setText("Sound plays as it is." if key == "off" else
                             sound.EQ_PRESETS[key][1] + ". It becomes its own output, \"DecKoOS EQ\", in front of the "
                             "one you pick; turning it off goes back.")

    def apply_eq(self):
        key = self.eq_box.currentData()
        args = ["eq", key] + ([self.eq_target.currentData()] if key != "off" and self.eq_target.currentData() else [])
        self.do(*args, msg="Equalizer off" if key == "off" else f"Equalizer: {self.eq_box.currentText()}")

    def render_guard(self, st):
        box = QComboBox()
        for key, (q, title, _desc) in sound.BUFFERS.items():
            box.addItem(title, key)
        box.setCurrentIndex(max(0, box.findData(st.get("buffer") or sound.DEFAULT_BUFFER)))
        desc = label(sound.BUFFERS[box.currentData()][2], "muted")
        box.currentIndexChanged.connect(lambda _i: (desc.setText(sound.BUFFERS[box.currentData()][2]),
                                                    self.do("buffer", box.currentData(),
                                                            msg=f"Buffer: {box.currentText()}")))
        self.check_btn = button("Listen for crackles", slot=self.check, icon="volume",
                                tip="Watches the sound for a few seconds; best while the game and music are playing")
        self.add(self.guard, line(label("Buffer", "sub", wrap=False), box, self.check_btn, stretch_at=99))
        self.add(self.guard, desc)
        self.guard_result = self.add(self.guard, label("", "sub"))

    def check(self):
        self.check_btn.setEnabled(False)
        self.guard_result.setText("Listening for 5 seconds…")

        def done(out, code):
            self.check_btn.setEnabled(True)
            found = [ln.split("\t") for ln in out.strip().splitlines() if "\t" in ln]
            if code != 0:
                self.guard_result.setText("Couldn't listen: pw-top isn't answering.")
            elif not found:
                self.guard_result.setText(f"<span style='color:{S.SUCCESS}'>●</span> No dropouts: the sound kept up.")
            else:
                names = ", ".join(f"{n} ({c})" for n, c in found[:4])
                self.guard_result.setText(f"<span style='color:{S.WARNING}'>●</span> Dropouts in {names}. "
                                          "Try Steady: a slightly bigger buffer stops them.")
        sysinfo.Job(self, ["python3", SOUND, "dropouts"], done, demo=("", 0))
