"""What DecKoOS Music's visuals react to: the sound actually coming out of the PC (Spotify, local files, anything),
read from PipeWire's monitor of the default output with parec, like the Vibes visualizer.

Each frame (about 86 a second) gives: 64 spectrum bars, bass / mids / highs, the overall energy, a beat flag and
its strength, and a slow "intensity" that follows how loud the song is right now compared with its recent past, so
a quiet verse is calm and a drop is wild. No Qt: Analyzer runs in its own thread; the window reads `latest`.
Only runs while the window shows music. tests/test_music.py feeds `Features` made-up signals.
"""
import subprocess
import threading
import time

import numpy as np

RATE = 44100
HOP = 512  # samples per frame: ~11.6 ms
FFT = 2048
BARS = 64
# What counts as a beat (Features.push): the kick's bands fully, the snare's and bass notes' less, hi-hats not at all
BEAT_WEIGHT = np.concatenate([np.full(12, 1.0), np.linspace(0.8, 0.3, 28), np.zeros(24)]).astype(np.float32)
BEAT_K = 1.8  # spreads above the last second's usual rise
BEAT_GAP = 0.18  # seconds between beats at the least


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
        self.flux_hist = np.zeros(86, np.float32)  # ~1 s of how sharply the low and mid sound rose, for beats
        self.prev = None  # the last hop's (log) bands
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
        # Beat: a hit you hear (kick, snare, a bass note): how sharply the low and mid bands rose, peaking well
        # above the last second's usual (mean + BEAT_K spreads). Rises, not levels: a bass line that's always there
        # hid every kick under it, and a triplet groove fooled a tempo guess (measured on real songs: this catches
        # ~90% of the hits, 95% of what it fires on is one). Known one hop after the peak, dated at the peak.
        rise = 0.0 if self.prev is None else float(np.maximum(raw - self.prev, 0) @ BEAT_WEIGHT)
        self.prev = raw
        hist = self.flux_hist
        peak, before = float(hist[-1]), float(hist[-2])
        mean, sd = float(hist[:-1].mean()), float(hist[:-1].std())
        at = now - HOP / RATE
        beat = (peak > mean + BEAT_K * sd and peak >= before and peak >= rise and peak > 0.05
                and at - self.last_beat > BEAT_GAP)
        flux = (peak - mean) / max(sd * 4, 1e-3)
        self.flux_hist = np.roll(hist, -1)
        self.flux_hist[-1] = rise
        if beat:
            self.last_beat = at
        self.energy_hist = np.roll(self.energy_hist, -1)
        self.energy_hist[-1] = energy
        recent = self.energy_hist[self.energy_hist > 0]
        loud = float(np.percentile(recent, 90)) if len(recent) > 20 else max(energy, 1e-3)
        silent = energy < 2e-4
        target = 0.0 if silent else float(np.clip(energy / max(loud, 1e-4), 0, 1.2))
        s = self.state
        s["intensity"] += (target - s["intensity"]) * (0.08 if target > s["intensity"] else 0.02)
        s.update(bars=self.bars.tolist(), bass=bass, mid=mid, high=high, energy=energy, beat=beat,
                 beat_strength=min(1.0, flux) if beat else s["beat_strength"] * 0.9,
                 silent=silent, t=now)
        return s


class Analyzer:
    """parec in a thread, Features on every hop. `latest` is a dict the window reads each frame; nothing runs
    until start() and stop() ends it."""

    def __init__(self, device="@DEFAULT_MONITOR@"):
        self.device, self.features = device, Features()
        self.latest = dict(self.features.state)
        self.beat_at = 0.0  # the clock time (time.time()) the last beat was heard: windows date it from this
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
            if self.latest["beat"]:
                self.beat_at = time.time() - HOP / RATE  # the peak was the hop before
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
