"""DecKoOS Sound: sorting apps into kinds, reading pactl and pw-top, the buffer and equalizer files, and System
Doctor's crackle check, on canned output (never the real sound server)."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / 'sound'), str(LIB / 'sysdoctor')]


def stream(index, sink=1, volume=100, **props):
    return {"index": index, "sink": sink, "mute": False, "corked": False, "properties": props,
            "volume": {"front-left": {"value_percent": f"{volume}%"}, "front-right": {"value_percent": f"{volume - 5}%"}}}


class SoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        os.environ.pop('DECKOS_SOUND_DEMO', None)
        import sound
        self.s = importlib.reload(sound)
        self.s.DEMO = False
        self.s.PW_CONF = self.home / 'pw'
        self.s.PULSE_CONF = self.home / 'pulse'
        self.s.BUFFER_FILE = self.s.PW_CONF / '60-deckos-buffer.conf'
        self.s.PULSE_BUFFER_FILE = self.s.PULSE_CONF / '60-deckos-buffer.conf'
        self.s.EQ_FILE = self.home / 'sound-eq.conf'
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def fake_run(self, cmd, timeout=6):
        self.calls.append(cmd)
        return ""

    def test_apps_are_sorted_into_kinds(self):
        k = self.s.kind_of
        self.assertEqual(k({"application.name": "Spotify", "media.role": "music"}), "music")
        self.assertEqual(k({"application.name": "WEBRTC VoiceEngine", "application.process.binary": "Discord"}), "voice")
        self.assertEqual(k({"application.name": "Cyberpunk2077.exe", "application.process.binary": "wine64-preloader"}),
                         "game")
        self.assertEqual(k({"application.name": "Firefox", "application.process.binary": "firefox"}), "browser")
        self.assertEqual(k({"application.name": "libcanberra", "media.role": "event"}), "system")
        self.assertEqual(k({"application.name": "Mystery"}), "other")
        # The role an app gives wins over its name: a browser playing a call is voice chat
        self.assertEqual(k({"application.name": "Firefox", "media.role": "phone"}), "voice")

    def test_apps_from_pactl(self):
        text = json.dumps([stream(5, application__name="x"),  # no name: still listed, as "Something"
                           stream(6, sink=2, volume=40, **{"application.name": "Spotify", "media.role": "music"}),
                           stream(7, **{"application.name": "DecKoOS visualizer"})])
        apps = self.s.apps(text)
        self.assertEqual([a["index"] for a in apps], [5, 6])  # DecKoOS's own visualizer isn't listed
        self.assertEqual(apps[1], {"index": 6, "name": "Spotify", "kind": "music", "volume": 40, "mute": False,
                                   "sink": 2, "binary": "", "corked": False})
        self.assertEqual(self.s.apps("not json"), [])

    def test_devices_leave_out_monitors(self):
        sinks = json.dumps([{"index": 1, "name": "spk", "description": "Speakers", "mute": False,
                             "volume": {"mono": {"value_percent": "76%"}}}])
        sources = json.dumps([{"index": 2, "name": "spk.monitor", "description": "Monitor of Speakers",
                               "monitor_source": "", "properties": {"device.class": "monitor"}},
                              {"index": 3, "name": "mic", "description": "Headset mic", "mute": True,
                               "volume": {"mono": {"value_percent": "80%"}}}])
        devs = self.s.devices(sinks, sources, "spk", "mic")
        self.assertEqual([(d["kind"], d["label"], d["volume"], d["default"]) for d in devs],
                         [("output", "Speakers", 76, True), ("input", "Headset mic", 80, True)])
        self.assertTrue(devs[1]["mute"])

    def test_a_kind_slider_sets_every_app_of_that_kind(self):
        apps = [{"index": 1, "kind": "music"}, {"index": 2, "kind": "game"}, {"index": 3, "kind": "music"}]
        with patch.object(self.s, "run", self.fake_run):
            self.assertEqual(self.s.set_kind_volume("music", 180, apps), 2)
        self.assertEqual(self.calls, [["pactl", "set-sink-input-volume", "1", "150%"],  # never louder than 150%
                                      ["pactl", "set-sink-input-volume", "3", "150%"]])

    def test_buffer_is_kept_and_applied_now(self):
        self.assertEqual(self.s.buffer_now(), "balanced")  # nothing written: DecKoOS's default
        with patch.object(self.s, "run", self.fake_run):
            self.s.set_buffer("steady")
        self.assertIn("default.clock.min-quantum = 512", self.s.BUFFER_FILE.read_text())
        self.assertIn("pulse.min.quantum = 512/48000", self.s.PULSE_BUFFER_FILE.read_text())
        self.assertEqual(self.calls, [["pw-metadata", "-n", "settings", "0", "clock.min-quantum", "512"]])
        self.assertEqual(self.s.buffer_now(), "steady")
        with self.assertRaises(ValueError):
            self.s.set_buffer("tiny")

    def test_shipped_default_matches_balanced(self):
        shipped = ROOT / 'pkg/deckos-settings/rootfs/usr/share/pipewire'
        pw, pulse = self.s.buffer_conf(self.s.DEFAULT_BUFFER)
        body = lambda t: t.split("\n", 1)[1]  # past the comment line
        self.assertEqual(body((shipped / 'pipewire.conf.d/60-deckos-buffer.conf').read_text()), body(pw))
        self.assertEqual(body((shipped / 'pipewire-pulse.conf.d/60-deckos-buffer.conf').read_text()), body(pulse))

    def test_equalizer_file_and_off(self):
        conf = self.s.eq_conf("footsteps", "alsa_output.speakers")
        self.assertIn("libpipewire-module-filter-chain", conf)
        self.assertIn('target.object = "alsa_output.speakers"', conf)
        self.assertEqual(conf.count("label = bq_"), len(self.s.EQ_PRESETS["footsteps"][2]))
        self.assertIn('output = "eq0:Out" input = "eq1:In"', conf)
        with patch.object(self.s, "run", self.fake_run), patch.object(self.s.time, "sleep", lambda _s: None):
            self.s.set_eq("night", "alsa_output.speakers")
            self.assertEqual(self.s.eq_now(), "night")
            self.assertEqual(self.s.eq_target(), "alsa_output.speakers")
            self.calls.clear()
            self.s.set_eq("off")
        self.assertFalse(self.s.EQ_FILE.exists())
        # Off puts the default output back on the device the equalizer played into
        self.assertIn(["pactl", "set-default-sink", "alsa_output.speakers"], self.calls)
        with self.assertRaises(ValueError):
            self.s.set_eq("loudness-war")

    def test_dropouts_from_pw_top(self):
        text = ("S   ID  QUANT   RATE    WAIT    BUSY   W/Q   B/Q  ERR FORMAT           NAME\n"
                "R   66    256  48000  50.1us  20.0us  0.01  0.00    0    S32LE 2 48000 alsa_output.speakers\n"
                "R   90    256  48000  10.0us  90.0us  0.00  0.02   14    F32LE 2 48000  + Spotify\n"
                "S   54      0      0    ---     ---   ---   ---     0                  Midi-Bridge\n")
        self.assertEqual(self.s.dropouts(text), {"Spotify": 14})
        self.assertEqual(self.s.dropouts(""), {})

    def test_demo_state_has_every_part(self):
        st = self.s.demo_state()
        self.assertTrue(st["running"])
        self.assertIn(st["buffer"], self.s.BUFFERS)
        self.assertIn(st["eq"], self.s.EQ_PRESETS)
        self.assertEqual({a["kind"] for a in st["apps"]} - set(self.s.KIND_NAMES), set())


class RuleTests(unittest.TestCase):
    def setUp(self):
        import sound
        self.s = sound
        self.devs = [{"kind": "output", "name": "a50.game", "index": 62}, {"kind": "output", "name": "a50.chat", "index": 63},
                     {"kind": "output", "name": "speakers", "index": 66}, {"kind": "input", "name": "mic", "index": 64}]

    def app(self, index, kind, sink=66, volume=80, corked=False):
        return {"index": index, "kind": kind, "sink": sink, "volume": volume, "corked": corked}

    def test_each_kind_goes_to_its_output(self):
        apps = [self.app(1, "game"), self.app(2, "voice", sink=63), self.app(3, "music")]
        rule = {"outputs": {"game": "a50.game", "voice": "a50.chat", "music": "unplugged.headset"}}
        actions, ducked = self.s.plan(apps, self.devs, rule, {})
        # Already right: left alone; an output that isn't plugged in: left alone
        self.assertEqual(actions, [("move", 1, 62)])
        self.assertEqual(ducked, {})
        # Moved by hand later: seen before, so it stays where the person put it
        self.assertEqual(self.s.plan(apps, self.devs, rule, {}, seen={1, 2, 3}), ([], {}))

    def test_music_is_lower_during_a_call_and_comes_back(self):
        rule = {"duck": 40}
        music, call = self.app(3, "music", volume=80), self.app(9, "voice")
        actions, ducked = self.s.plan([music, call], self.devs, rule, {})
        self.assertEqual((actions, ducked), ([("volume", 3, 32)], {3: 80}))
        # Still in the call: nothing more (not lowered twice); a new song player is lowered too
        late = self.app(4, "music", volume=50)
        actions, ducked = self.s.plan([dict(music, volume=32), call, late], self.devs, rule, ducked)
        self.assertEqual((actions, ducked), ([("volume", 4, 20)], {3: 80, 4: 50}))
        # The call ends: each goes back to where it was; one that closed meanwhile is forgotten
        actions, ducked = self.s.plan([dict(music, volume=32)], self.devs, rule, ducked)
        self.assertEqual((actions, ducked), ([("volume", 3, 80)], {}))

    def test_a_paused_call_or_no_rule_lowers_nothing(self):
        apps = [self.app(3, "music"), self.app(9, "voice", corked=True)]
        self.assertEqual(self.s.plan(apps, self.devs, {"duck": 40}, {}), ([], {}))
        self.assertEqual(self.s.plan([self.app(3, "music"), self.app(9, "voice")], self.devs, {}, {}), ([], {}))

    def test_rules_are_kept_and_checked(self):
        with tempfile.TemporaryDirectory() as d, patch.object(self.s, "RULES", Path(d) / "sound.json"), \
                patch.object(self.s, "run", lambda *a, **k: ""), patch.object(self.s, "DEMO", False):
            self.s.set_rule("output", "game", "a50.game")
            self.s.set_rule("duck", value=40)
            self.assertEqual(self.s.rules(), {"outputs": {"game": "a50.game"}, "duck": 40})
            self.s.set_rule("output", "game", None)
            self.s.set_rule("duck", value=None)
            self.assertEqual(self.s.rules(), {"outputs": {}})
            with self.assertRaises(ValueError):
                self.s.set_rule("output", "everything", "x")
            with self.assertRaises(ValueError):
                self.s.set_rule("duck", value=150)


class CrackleCheckTests(unittest.TestCase):
    def test_tiny_floor_is_flagged_with_a_fix(self):
        import sysdoctor as sd
        meta = "update: id:0 key:'clock.min-quantum' value:'32' type:''\n"
        with patch.object(sd, "run", lambda cmd, timeout=30: (0, meta)):
            f, = sd.sound_buffer()
        self.assertEqual((f.key, f.level), ("sound:buffer", sd.WARN))
        self.assertEqual(f.fixes[0].cmd, ["deckos", "sound", "buffer", "balanced"])
        ok = meta.replace("'32'", "'256'")
        with patch.object(sd, "run", lambda cmd, timeout=30: (0, ok)):
            self.assertEqual(sd.sound_buffer(), [])
        with patch.object(sd, "run", lambda cmd, timeout=30: (127, "")):
            self.assertEqual(sd.sound_buffer(), [])  # no PipeWire: nothing to say


if __name__ == '__main__':
    unittest.main()
