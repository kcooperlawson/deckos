"""What DecKoOS Music's visuals react to: the sound actually coming out of the PC (Spotify, local files, anything),
read from PipeWire's monitor of the default output with parec, like the Vibes visualizer.

Each frame (about 86 a second) gives: 64 spectrum bars, bass / mids / highs, the overall energy, a beat flag and
its strength, and a slow "intensity" that follows how loud the song is right now compared with its recent past, so
a quiet verse is calm and a drop is wild. No Qt: Analyzer runs in its own thread; the window reads `latest`.
Only runs while the window shows music. tests/test_music.py feeds `Features` made-up signals.
"""
import subprocess
import threading

import numpy as np

RATE = 44100
HOP = 512  # samples per frame: ~11.6 ms
FFT = 2048
BARS = 64


def band_edges(bars=BARS, low=30.0, high=16000.0, n=FFT, rate=RATE):
    """FFT bin edges for bars spaced like hearing (log), each at least one bin wide."""
    freqs = np.geomspace(low, high, bars + 1)
    bins = np.clip((freqs * n / rate).astype(int), 1, n // 2)
    for i in range(1, len(bins)):
        bins[i] = max(bins[i], bins[i - 1] + 1)
    return bins


class Features:
    """Turns audio blocks into the numbers the visuals use. Kept apart from the thread so tests can feed it."""

    def __init__(self):
        self.window = np.hanning(FFT).astype(np.float32)
        self.edges = band_edges()
        self.buf = np.zeros(FFT, np.float32)
        self.bars = np.zeros(BARS, np.float32)
        self.peak = 1e-3  # running loudest bar, so bars fill the height whatever the volume
        self.flux_hist = np.zeros(43, np.float32)  # ~0.5 s of the low end's level, for beat detection
        self.prev = np.zeros(BARS, np.float32)
        self.energy_hist = np.zeros(430, np.float32)  # ~5 s of loudness, for intensity
        self.last_beat = 0.0
        self.n = 0
        self.state = {"bars": [0.0] * BARS, "bass": 0.0, "mid": 0.0, "high": 0.0, "energy": 0.0, "beat": False,
                      "beat_strength": 0.0, "intensity": 0.0, "silent": True, "t": 0.0}

    def push(self, block, now=None):
        """One hop of mono float samples in; the latest features out. Time is counted in audio, not on the clock:
        a beat's spacing is the music's, however fast the frames arrive."""
        self.n += 1
        now = self.n * HOP / RATE if now is None else now
        self.buf = np.concatenate([self.buf[len(block):], block.astype(np.float32)])
        spec = np.abs(np.fft.rfft(self.buf * self.window))
        cs = np.concatenate([[0.0], np.cumsum(spec)])
        raw = (cs[self.edges[1:]] - cs[self.edges[:-1]]) / np.maximum(np.diff(self.edges), 1)
        raw = np.log1p(raw)
        self.peak = max(self.peak * 0.9995, float(raw.max()), 1e-3)
        level = np.clip(raw / self.peak, 0, 1)
        # Bars rise at once and fall gently, so they read as motion rather than flicker
        self.bars = np.maximum(level, self.bars * 0.86)
        bass, mid, high = float(level[:10].mean()), float(level[10:40].mean()), float(level[40:].mean())
        energy = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))
        # Beat: the low end (a kick, a bass hit) jumping well above where it's been for the last half second, and
        # still rising. A kick's attack spreads over a few frames, so this compares levels, not one frame's change.
        low = float(level[:12].mean())
        avg = float(self.flux_hist.mean())
        rising = low > float(self.prev[:12].mean())
        self.prev = level
        self.flux_hist = np.roll(self.flux_hist, -1)
        self.flux_hist[-1] = low
        beat = rising and low > avg * 1.3 + 0.04 and now - self.last_beat > 0.2
        flux, sd = low - avg, max(avg, 0.05)
        if beat:
            self.last_beat = now
        self.energy_hist = np.roll(self.energy_hist, -1)
        self.energy_hist[-1] = energy
        recent = self.energy_hist[self.energy_hist > 0]
        loud = float(np.percentile(recent, 90)) if len(recent) > 20 else max(energy, 1e-3)
        silent = energy < 2e-4
        target = 0.0 if silent else float(np.clip(energy / max(loud, 1e-4), 0, 1.2))
        s = self.state
        s["intensity"] += (target - s["intensity"]) * (0.08 if target > s["intensity"] else 0.02)
        s.update(bars=self.bars.tolist(), bass=bass, mid=mid, high=high, energy=energy, beat=beat,
                 beat_strength=min(1.0, flux / (sd * 2)) if beat else s["beat_strength"] * 0.9,
                 silent=silent, t=now)
        return s


class Analyzer:
    """parec in a thread, Features on every hop. `latest` is a dict the window reads each frame; nothing runs
    until start() and stop() ends it."""

    def __init__(self, device="@DEFAULT_MONITOR@"):
        self.device, self.features = device, Features()
        self.latest = dict(self.features.state)
        self.proc, self.thread, self.running = None, None, False

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.proc:
            self.proc.terminate()
            self.proc = None

    def _run(self):
        try:
            self.proc = subprocess.Popen(["parec", "-d", self.device, "--format=float32le", f"--rate={RATE}",
                                          "--channels=1", "--latency-msec=20", "--client-name=DecKoOS Music"],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self.running = False
            return
        need = HOP * 4
        while self.running and self.proc:
            data = self.proc.stdout.read(need)
            if not data or len(data) < need:
                break
            self.latest = dict(self.features.push(np.frombuffer(data, np.float32)))
        self.running = False


class FakeAnalyzer:
    """For --demo: a made-up song (a kick every half second, a melody, swells), no sound needed."""

    def __init__(self):
        self.features = Features()
        self.latest = dict(self.features.state)
        self.phase = 0
        self.tone = 0.0  # the melody's phase, carried across blocks

    def start(self):
        pass

    def stop(self):
        pass

    def step(self):
        t = self.phase / RATE  # the song's own time, not the clock's: a slow machine (CI) must hear the same song
        n = np.arange(HOP) + self.phase
        self.phase += HOP
        x = n / RATE
        kick = np.exp(-((x % 0.5) * 18)) * np.sin(2 * np.pi * 55 * x)
        # Its pitch glides, so its phase carries on from the last block: restarting it clicked, and the clicks'
        # low end read as extra kicks
        step = 2 * np.pi * (440 + 110 * np.sin(t * 0.7)) / RATE
        melody = 0.3 * np.sin(self.tone + step * np.arange(1, HOP + 1))
        self.tone = (self.tone + step * HOP) % (2 * np.pi)
        hats = 0.05 * np.random.default_rng(self.phase).standard_normal(HOP) * (x % 0.25 < 0.03)
        swell = 0.4 + 0.6 * (0.5 + 0.5 * np.sin(t * 0.25))
        self.latest = dict(self.features.push((kick + melody + hats).astype(np.float32) * 0.3 * swell))
        return self.latest
