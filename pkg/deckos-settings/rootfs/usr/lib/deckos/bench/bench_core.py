"""DecKoOS Bench engine: runners, sensor sampling, statistics, saved results.

A runner measures one thing (7-Zip, memory, a game's own benchmark...) and returns one value per
metric per repetition. The engine repeats it, samples the hardware the whole time, and keeps every
value, so results carry their spread and comparisons carry a confidence range, not just two numbers.

Everything is plain Python (no Qt): `deckos bench` runs it from a terminal, the Hub from a thread.
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "deckos/bench"
RUNS = DATA / "runs"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "deckos/bench"
HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------ results

@dataclass
class Metric:
    key: str
    name: str
    unit: str
    higher_better: bool = True
    values: list = field(default_factory=list)

    @property
    def stats(self):
        return describe(self.values)


@dataclass
class Result:
    runner: str
    title: str
    group: str                       # cpu, memory, disk, gpu, ai, game
    metrics: dict = field(default_factory=dict)   # key -> Metric
    sensors: dict = field(default_factory=dict)   # summary: name -> {avg, max}
    trace: dict = field(default_factory=dict)     # name -> [values every SAMPLE_EVERY s], for graphs
    seconds: float = 0.0
    error: str = ""
    notes: list = field(default_factory=list)

    def add(self, key, name, unit, value, higher_better=True):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{name} returned a non-finite result")
        m = self.metrics.setdefault(key, Metric(key, name, unit, higher_better))
        m.values.append(value)


# ------------------------------------------------------------------ statistics

def describe(values):
    """mean, median, stdev, cv (%), min, max and a 95% bootstrap range for the mean."""
    v = [float(x) for x in values]
    n = len(v)
    if not n:
        return {"n": 0}
    mean = sum(v) / n
    s = sorted(v)
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    sd = (sum((x - mean) ** 2 for x in v) / (n - 1)) ** 0.5 if n > 1 else 0.0
    lo, hi = bootstrap(v, lambda xs: sum(xs) / len(xs)) if n > 1 else (mean, mean)
    return {"n": n, "mean": mean, "median": median, "stdev": sd, "cv": (sd / mean * 100) if mean else 0.0,
            "min": s[0], "max": s[-1], "ci_low": lo, "ci_high": hi}


def bootstrap(values, stat, rounds=4000, seed=1):
    """95% percentile bootstrap range of stat(values). Seeded, so the same data gives the same range."""
    rng = random.Random(seed)
    n = len(values)
    est = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(rounds))
    return est[int(rounds * 0.025)], est[int(rounds * 0.975) - 1]


def compare(a_values, b_values, higher_better=True, seed=1):
    """B against A as a percentage, with a 95% bootstrap range, and what it means.

    verdict: better / worse (the range is all on one side of zero), same (within noise), or
    unsure (fewer than 3 runs a side: no range to trust)."""
    a, b = [float(x) for x in a_values], [float(x) for x in b_values]
    if not a or not b:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    diff = (mb - ma) / ma * 100 if ma else 0.0
    if len(a) < 3 or len(b) < 3:
        return {"diff": diff, "low": None, "high": None, "verdict": "unsure"}
    rng = random.Random(seed)
    est = []
    for _ in range(4000):
        ra = [a[rng.randrange(len(a))] for _ in a]
        rb = [b[rng.randrange(len(b))] for _ in b]
        mra = sum(ra) / len(ra)
        est.append((sum(rb) / len(rb) - mra) / mra * 100 if mra else 0.0)
    est.sort()
    lo, hi = est[100], est[3899]
    if lo > 0 or hi < 0:
        up = lo > 0
        verdict = "better" if up == higher_better else "worse"
    else:
        verdict = "same"
    return {"diff": diff, "low": lo, "high": hi, "verdict": verdict}


# ------------------------------------------------------------------ the hardware while it runs

SAMPLE_EVERY = 0.5


def _read(path, default=None):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def amd_gpu():
    """The discrete AMD card's sysfs device folder (most VRAM), or None."""
    best, size = None, 0
    for d in Path("/sys/class/drm").glob("card[0-9]*/device"):
        total = _read(d / "mem_info_vram_total")
        if total and int(total) > size:
            best, size = d, int(total)
    return best


def _hwmon(device_or_name):
    if isinstance(device_or_name, Path):
        return next(iter(device_or_name.glob("hwmon/hwmon*")), None)
    for h in Path("/sys/class/hwmon").glob("hwmon*"):
        if _read(h / "name") == device_or_name:
            return h
    return None


def _dpm_now(path):
    """The current clock from pp_dpm_sclk/mclk ("1: 2450Mhz *")."""
    text = _read(path, "")
    m = re.search(r"(\d+)Mhz \*", text)
    return float(m.group(1)) if m else None


class Sensors:
    """Samples CPU and GPU every half second on a thread; summary() and trace() when it stops."""

    def __init__(self):
        self.gpu = amd_gpu()
        self.gpu_hw = _hwmon(self.gpu) if self.gpu else None
        self.cpu_hw = _hwmon("k10temp") or _hwmon("coretemp")
        self.samples = {}
        self._stop = threading.Event()
        self._thread = None
        self._last_cpu = None

    def _cpu_busy(self):
        fields = [int(x) for x in _read("/proc/stat", "cpu 0 0 0 0").splitlines()[0].split()[1:]]
        idle, total = fields[3] + (fields[4] if len(fields) > 4 else 0), sum(fields)
        busy = None
        if self._last_cpu:
            di, dt = idle - self._last_cpu[0], total - self._last_cpu[1]
            busy = (1 - di / dt) * 100 if dt else None
        self._last_cpu = (idle, total)
        return busy

    def _cpu_mhz(self):
        freqs = [int(f.read_text()) for f in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq")
                 if f.exists()]
        return sum(freqs) / len(freqs) / 1000 if freqs else None

    def sample(self):
        s = {"cpu_busy": self._cpu_busy(), "cpu_mhz": self._cpu_mhz()}
        if self.cpu_hw:
            t = _read(self.cpu_hw / "temp1_input")
            s["cpu_temp"] = int(t) / 1000 if t else None
        if self.gpu:
            busy = _read(self.gpu / "gpu_busy_percent")
            used = _read(self.gpu / "mem_info_vram_used")
            s.update(gpu_busy=float(busy) if busy else None, gpu_mhz=_dpm_now(self.gpu / "pp_dpm_sclk"),
                     vram_mhz=_dpm_now(self.gpu / "pp_dpm_mclk"), vram_gb=int(used) / 1e9 if used else None)
        if self.gpu_hw:
            temps = {(_read(p.with_name(p.name.replace("input", "label"))) or ""): p for p in self.gpu_hw.glob("temp*_input")}
            hot = temps.get("junction") or temps.get("edge") or next(iter(temps.values()), None)
            if hot:
                s["gpu_temp"] = int(_read(hot)) / 1000
            power = _read(self.gpu_hw / "power1_average") or _read(self.gpu_hw / "power1_input")
            s["gpu_watts"] = int(power) / 1e6 if power else None
        meminfo = dict(l.split(":", 1) for l in _read("/proc/meminfo", "").splitlines() if ":" in l)
        try:
            s["ram_gb"] = (int(meminfo["MemTotal"].split()[0]) - int(meminfo["MemAvailable"].split()[0])) / 1e6
        except (KeyError, ValueError):
            pass
        for k, v in s.items():
            if v is not None:
                self.samples.setdefault(k, []).append(round(v, 2))

    def _loop(self):
        self._cpu_busy()
        while not self._stop.wait(SAMPLE_EVERY):
            self.sample()

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()

    def summary(self):
        return {k: {"avg": round(sum(v) / len(v), 2), "max": max(v)} for k, v in self.samples.items() if v}

    def trace(self, points=240):
        out = {}
        for k, v in self.samples.items():
            step = max(1, len(v) // points)
            out[k] = v[::step]
        return out


def cpu_temp():
    h = _hwmon("k10temp") or _hwmon("coretemp")
    t = _read(h / "temp1_input") if h else None
    return int(t) / 1000 if t else None


def cpu_busy(window=1.0):
    """How busy the CPU was over the last `window` seconds, in percent (from /proc/stat)."""
    def snap():
        f = [int(x) for x in _read("/proc/stat", "cpu 0 0 0 0").splitlines()[0].split()[1:]]
        return f[3] + (f[4] if len(f) > 4 else 0), sum(f)
    i0, t0 = snap()
    time.sleep(window)
    i1, t1 = snap()
    return (1 - (i1 - i0) / (t1 - t0)) * 100 if t1 > t0 else 0.0


def settle(limit=45, say=lambda text: None, cancelled=lambda: False):
    """Wait (up to `limit` s) for the system to cool down and go quiet, so a run doesn't start hot or
    busy from the one before: CPU under 10% busy over the last second and its temperature no longer
    falling. Not the load average: after an all-core run it stays high for minutes on an idle CPU."""
    start, last = time.monotonic(), None
    while time.monotonic() - start < limit:
        if cancelled():
            raise InterruptedError("Stopped by user")
        busy, t = cpu_busy(), cpu_temp()
        if busy < 10 and t is not None and last is not None and last - t < 1.0:
            return
        last = t
        for _ in range(10):
            if cancelled():
                raise InterruptedError("Stopped by user")
            time.sleep(0.2)
    say("didn't fully settle; carrying on")


# ------------------------------------------------------------------ what the PC is

def run_text(argv, timeout=20):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def environment():
    """What a result depends on, saved with it: compare two runs and the differences are listed."""
    env = {}
    cpu = re.search(r"Model name:\s*(.+)", run_text(["lscpu"]))
    env["cpu"] = cpu.group(1).strip() if cpu else ""
    env["cores"] = os.cpu_count()
    gpu = [l.split(": ", 1)[-1] for l in run_text(["lspci"]).splitlines() if re.search(r"VGA|3D|Display", l)]
    env["gpu"] = " + ".join(gpu)
    meminfo = _read("/proc/meminfo", "")
    m = re.search(r"MemTotal:\s*(\d+)", meminfo)
    env["ram_gb"] = round(int(m.group(1)) / 1e6, 1) if m else None
    env["kernel"] = os.uname().release
    env["mesa"] = (re.search(r"Version\s*:\s*(\S+)", run_text(["pacman", "-Qi", "mesa"])) or [None, ""])[1]
    env["deckos"] = _read("/usr/share/deckos/version", "")
    sched = dict(l.split("=", 1) for l in run_text(["deckos", "scheduler", "status"]).splitlines() if "=" in l)
    env["scheduler"] = sched.get("running") or "kernel default"
    env["power_profile"] = run_text(["powerprofilesctl", "get"]) or "unknown"
    env["governor"] = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "")
    env["display_fix"] = (re.search(r"amdgpu\.dcdebugmask=\S+", _read("/proc/cmdline", "")) or [""])[0] or "none"
    gpu_dev = amd_gpu()
    hw = _hwmon(gpu_dev) if gpu_dev else None
    cap = _read(hw / "power1_cap") if hw else None
    env["gpu_power_cap_w"] = int(cap) / 1e6 if cap else None
    return env


# ------------------------------------------------------------------ runners

class Runner:
    """One benchmark. Subclasses set key/title/group and implement run(result, say)."""
    key = title = group = ""
    about = ""
    needs = ()          # commands that must exist
    minutes = 1.0       # rough length of one repetition, for "about N min"

    def available(self):
        missing = [c for c in self.needs if not shutil.which(c)]
        return (False, "needs " + ", ".join(missing)) if missing else (True, "")

    def prepare(self, say):
        """Once before the repetitions (compile, load a model). Not timed."""

    def run(self, result, say):
        raise NotImplementedError

    def finish(self, say):
        """Once after the repetitions."""


def run_suite(runners, repeat=3, label="", say=print, settle_between=True, on_result=None,
              on_progress=None, cancelled=lambda: False):
    """Run each runner `repeat` times with the sensors on; returns the saved run (a dict)."""
    if not isinstance(repeat, int) or repeat < 1:
        raise ValueError("repeat must be a positive integer")
    started = time.time()
    env = environment()
    results = []
    for index, runner in enumerate(runners):
        if cancelled():
            break
        if on_progress:
            on_progress(index, len(runners), runner.key, 0, repeat)
        try:
            ok, why = runner.available()
        except Exception as error:
            ok, why = False, str(error)

        res = Result(runner.key, runner.title, runner.group)
        if not ok:
            res.error = why
            results.append(res)
            say(f"{runner.title}: skipped ({why})")
            if on_result:
                on_result(res)
            continue
        say(f"{runner.title}")
        sensors = None
        t = None
        try:
            runner.prepare(say)
            sensors = Sensors().start()
            t = time.monotonic()
            for i in range(repeat):
                if cancelled():
                    raise InterruptedError("Stopped by user")
                if settle_between and i:
                    settle(say=say, cancelled=cancelled)
                if on_progress:
                    on_progress(index, len(runners), runner.key, i + 1, repeat)
                say(f"  run {i + 1} of {repeat}")
                # Commit a repetition only after it finishes: a failed half-run is not a sample.
                sample = Result(runner.key, runner.title, runner.group)
                runner.run(sample, say)
                if cancelled():
                    raise InterruptedError("Stopped by user")
                for key, metric in sample.metrics.items():
                    res.metrics.setdefault(key, Metric(metric.key, metric.name, metric.unit,
                                                       metric.higher_better)).values.extend(metric.values)
                res.notes.extend(note for note in sample.notes if note not in res.notes)
        except Exception as e:  # one runner failing doesn't lose the others' results
            res.error = "Stopped by user" if cancelled() else str(e) or type(e).__name__
            say(f"  failed: {res.error}")
        finally:
            if sensors is not None:
                sensors.stop()
                res.sensors, res.trace = sensors.summary(), sensors.trace()
            if t is not None:
                res.seconds = round(time.monotonic() - t, 1)
            try:
                runner.finish(say)
            except Exception:
                pass
        results.append(res)
        if on_result:
            on_result(res)
        if cancelled():
            break
        if settle_between and runner is not runners[-1]:
            try:
                settle(say=say, cancelled=cancelled)
            except InterruptedError:
                break
    run = {"version": 1, "label": label, "started": started, "seconds": round(time.time() - started, 1),
           "repeat": repeat, "environment": env, "status": "cancelled" if cancelled() else "complete",
           "results": [dict(asdict(r), metrics={k: asdict(m) for k, m in r.metrics.items()}) for r in results]}
    return run


def save(run, kind="system"):
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(run["started"]))
    name = stamp + (("-" + re.sub(r"[^\w-]+", "-", run["label"]).strip("-")[:40]) if run.get("label") else "")
    RUNS.mkdir(parents=True, exist_ok=True)
    base, suffix = name, 0
    while True:
        folder = RUNS / name
        try:
            folder.mkdir()
            break
        except FileExistsError:
            suffix += 1
            name = f"{base}-{suffix:02d}"
    run["kind"] = kind
    run["id"] = name
    (folder / "result.json.tmp").write_text(json.dumps(run, indent=1, allow_nan=False), encoding="utf-8")
    (folder / "result.json.tmp").replace(folder / "result.json")
    return folder


def load(ref):
    """A saved run by folder name, path or 'last' / 'last-1'."""
    if re.fullmatch(r"last(?:-\d+)?", ref):
        runs = sorted(RUNS.glob("*/result.json"))
        back = int(ref.split("-", 1)[1]) if "-" in ref else 0
        if len(runs) <= back:
            raise FileNotFoundError("not that many saved runs")
        path = runs[-1 - back]
    else:
        p = Path(ref)
        path = p / "result.json" if p.is_dir() else p if p.exists() else RUNS / ref / "result.json"
    return json.loads(Path(path).read_text()), Path(path).parent
