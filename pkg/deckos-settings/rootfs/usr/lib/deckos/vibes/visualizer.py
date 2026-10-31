"""The music visualizer's ears: what the PC is playing (PipeWire's monitor of the default output, through parec), as
BARS levels 0..1, sent ~30 times a second to the DecKoOS Vibe wallpaper over a local-only WebSocket. No widgets.

It also finds the beat, once, for everything that moves with the music (the dock, the menu, DecKoOS apps, the
wallpaper's scenes): from the raw sound's low end (40-150 Hz, a 2048-sample window, 60 looks a second), a kick is
energy well above the last second's and still rising. Each beat goes out as a text message, "beat STRENGTH", held back
by the speaker delay you set (react.conf delay=MS: a soundbar plays the music later than the PC hands it over, so
the beat would arrive early), and the bars are held back the same.

It costs next to nothing when it isn't wanted: it only listens while the wallpaper is connected, sends nothing
after a few seconds of silence, and stops listening while a game runs (workload modes' $XDG_RUNTIME_DIR/deckos-mode).

    visualizer.py serve | test        (deckos-visualizer.service runs `serve`)
"""
import os
import sys
from pathlib import Path

import numpy as np

BARS = 48
RATE = 44100
FRAME = 1470  # samples per frame: 30 frames a second
PORT = int(os.environ.get("DECKOS_VISUALIZER_PORT") or 47823)
SILENT = 1e-4  # RMS under this is silence
QUIET_FRAMES = 90  # 3 s of silence and it stops sending
MODE_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "deckos-mode"


def edges(bars=BARS, rate=RATE, n=FRAME, lo=40.0, hi=14000.0):
    """FFT bin ranges per bar, spaced logarithmically (each bar about the same musical width)."""
    freqs = np.fft.rfftfreq(n, 1 / rate)
    cuts = np.geomspace(lo, hi, bars + 1)
    idx = np.searchsorted(freqs, cuts)
    return [(int(a), max(int(b), int(a) + 1)) for a, b in zip(idx[:-1], idx[1:])]


class Analyser:
    """Samples in, smoothed bar levels out: fast rise, slow fall, loudness that follows the music."""

    def __init__(self, bars=BARS):
        self.edges = edges(bars)
        self.window = np.hanning(FRAME)
        self.levels = np.zeros(bars)
        self.peak = 1e-3

    def feed(self, samples):
        x = np.asarray(samples, dtype=np.float32)
        if len(x) < FRAME:
            x = np.pad(x, (0, FRAME - len(x)))
        spectrum = np.abs(np.fft.rfft(x[:FRAME] * self.window))
        raw = np.array([spectrum[a:b].mean() for a, b in self.edges])
        raw *= np.linspace(1.0, 4.0, len(raw))  # high notes are quieter in a spectrum; lift them to show
        self.peak = max(self.peak * 0.995, raw.max(), 1e-3)
        target = np.clip(raw / self.peak, 0, 1) ** 0.7
        rise = target > self.levels
        self.levels = np.where(rise, self.levels + (target - self.levels) * 0.6, self.levels * 0.85)
        return self.levels

    @staticmethod
    def rms(samples):
        x = np.asarray(samples, dtype=np.float32)
        return float(np.sqrt(np.mean(x * x))) if len(x) else 0.0


class Beats:
    """Kicks in the raw sound: low-end energy over its last second, rising. feed(samples) -> strength 0..1, or 0."""

    WINDOW, LOW, HIGH = 2048, 40.0, 150.0

    def __init__(self, rate=RATE):
        self.buf = np.zeros(self.WINDOW, dtype=np.float32)
        self.win = np.hanning(self.WINDOW)
        freqs = np.fft.rfftfreq(self.WINDOW, 1 / rate)
        self.low = (freqs >= self.LOW) & (freqs <= self.HIGH)
        self.hist, self.prev, self.since = [], 0.0, 99
        self.rate = rate

    def feed(self, samples):
        x = np.asarray(samples, dtype=np.float32)
        self.buf = np.concatenate([self.buf[len(x):], x])[-self.WINDOW:]
        e = float((np.abs(np.fft.rfft(self.buf * self.win))[self.low] ** 2).sum())
        self.hist = (self.hist + [e])[-int(self.rate / max(1, len(x))):]  # the last second
        avg = float(np.mean(self.hist))
        rising, self.prev = e > self.prev, e
        self.since += len(x) / self.rate
        if len(self.hist) > 20 and avg > 0 and e > avg * 1.5 and rising and self.since > 0.25:
            self.since = 0
            return float(min(1.0, (e / avg - 1.5) / 2 + 0.3))
        return 0.0


REACT_CONF = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "deckos/react.conf"


def speaker_delay(conf=None):
    """The delay to hold the beat and bars back by, in ms (0..400): how much later the speakers play than the PC."""
    try:
        for line in Path(conf or REACT_CONF).read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "delay" and v.strip().lstrip("-").isdigit():
                return max(0, min(400, int(v)))
    except OSError:
        pass
    return 0


def gaming(mode_file=None):
    try:
        return "game=" in Path(mode_file or MODE_FILE).read_text()
    except OSError:
        return False


def encode(levels):
    """One frame on the wire: a byte per bar (0-255), small and simple for QML to read."""
    return bytes(np.clip(np.asarray(levels) * 255, 0, 255).astype(np.uint8))


def serve():
    from PySide6.QtCore import QCoreApplication, QFileSystemWatcher, QProcess, QTimer
    from PySide6.QtNetwork import QHostAddress
    from PySide6.QtWebSockets import QWebSocketServer

    app = QCoreApplication(sys.argv)
    server = QWebSocketServer("deckos-visualizer", QWebSocketServer.NonSecureMode)
    if not server.listen(QHostAddress.LocalHost, PORT):  # never on the network
        print(f"port {PORT} is taken", file=sys.stderr)
        return 1
    clients = []
    an = Analyser()
    beats = Beats()
    delay = {"ms": speaker_delay(), "read": 0.0}
    state = {"quiet": 0, "buf": b""}
    rec = QProcess()

    def out(fn):  # now, or after the speaker delay
        import time
        if time.monotonic() - delay["read"] > 2:  # the delay is set in the Hub while music plays: look again now and then
            delay["ms"], delay["read"] = speaker_delay(), time.monotonic()
        if delay["ms"]:
            QTimer.singleShot(delay["ms"], fn)
        else:
            fn()

    def send(levels):
        data = encode(levels)
        out(lambda: [c.sendBinaryMessage(data) for c in list(clients)])

    def beat(strength):
        msg = f"beat {strength:.2f}"
        out(lambda: [c.sendTextMessage(msg) for c in list(clients)])

    def listen():
        want = bool(clients) and not gaming()
        running = rec.state() != QProcess.NotRunning
        if want and not running:
            rec.start("parec", ["-d", "@DEFAULT_MONITOR@", "--format=float32le", f"--rate={RATE}", "--channels=1",
                                "--latency-msec=30", "--client-name=DecKoOS visualizer"])
        elif not want and running:
            rec.kill()
            send(np.zeros(BARS))

    def gone(c):
        if c in clients:
            clients.remove(c)
        listen()

    def connected():
        while server.hasPendingConnections():
            c = server.nextPendingConnection()
            clients.append(c)
            c.disconnected.connect(lambda c=c: gone(c))
        listen()

    def audio():
        state["buf"] += bytes(rec.readAllStandardOutput())
        size = FRAME * 4
        while len(state["buf"]) >= size:
            chunk, state["buf"] = state["buf"][:size], state["buf"][size:]
            samples = np.frombuffer(chunk, dtype="<f4")
            half = len(samples) // 2
            for part in (samples[:half], samples[half:]):  # 60 looks a second for the beat's timing
                hit = beats.feed(part)
                if hit:
                    beat(hit)
            if Analyser.rms(samples) < SILENT:
                state["quiet"] += 1
                if state["quiet"] == QUIET_FRAMES:
                    send(np.zeros(BARS))
                if state["quiet"] >= QUIET_FRAMES:
                    continue
            else:
                state["quiet"] = 0
            send(an.feed(samples))

    rec.readyReadStandardOutput.connect(audio)
    server.newConnection.connect(connected)
    # Games come and go: follow workload modes' file, no polling
    watch = QFileSystemWatcher([str(MODE_FILE.parent)])
    watch.directoryChanged.connect(lambda _p: listen())
    # An update replaces this file while the old code keeps running (and the dock, menu and apps wait for beats the
    # old one never sends): leave, and systemd starts the new one (Restart=on-failure, so not with 0)
    me = QFileSystemWatcher([str(Path(__file__).resolve())])
    me.fileChanged.connect(lambda _p: app.exit(3))
    QTimer.singleShot(0, listen)
    return app.exec()


def main(argv):
    if argv[:1] == ["serve"]:
        return serve()
    if argv[:1] == ["test"]:  # a 440 Hz tone lights one bar in the lower middle
        t = np.arange(FRAME) / RATE
        an = Analyser()
        for _ in range(10):
            levels = an.feed(np.sin(2 * np.pi * 440 * t))
        print(" ".join(f"{v:.1f}" for v in levels))
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
