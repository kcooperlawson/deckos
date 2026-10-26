"""The music visualizer's ears: what the PC is playing (PipeWire's monitor of the default output, through parec), as
BARS levels 0..1, sent ~30 times a second to the DecKoOS Vibe wallpaper over a local-only WebSocket. No widgets.

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
    state = {"quiet": 0, "buf": b""}
    rec = QProcess()

    def send(levels):
        data = encode(levels)
        for c in list(clients):
            c.sendBinaryMessage(data)

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
