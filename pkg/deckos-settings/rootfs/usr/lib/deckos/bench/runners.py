"""DecKoOS Bench runners: the system suite (no games needed) and the game runners.

System suite: CPU (7-Zip, one core and all of them), memory (bandwidth and latency), disk (fio), GPU
(vkmark), local AI (Ollama tokens per second). Games: titles whose own benchmark runs with nobody at
the controls; BeamNG.drive's BananaBench is the first.
"""
import json
import hashlib
import uuid
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from bench_core import CACHE, HERE, Runner, run_text


def call(argv, timeout=900, cwd=None, env=None):
    command_env = dict(os.environ if env is None else env, LC_ALL="C")
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=command_env,
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout).strip().splitlines()[-3:]
        raise RuntimeError(f"{Path(argv[0]).name} exited {p.returncode}: {' / '.join(tail)}")
    return p.stdout


# ------------------------------------------------------------------ CPU

class Cpu7z(Runner):
    key, title, group = "cpu-7z", "CPU: 7-Zip", "cpu"
    about = "LZMA compression and decompression, on one core and on all of them (MIPS ratings)."
    needs = ("7z",)
    minutes = 0.6

    @staticmethod
    def ratings(out):
        """(compress, decompress, total) from 7-Zip's Avr:/Tot: lines."""
        avr = re.search(r"^Avr:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", out, re.M)
        tot = re.search(r"^Tot:\s+(\d+)\s+(\d+)\s+(\d+)", out, re.M)
        if not avr or not tot:
            raise RuntimeError("couldn't read 7-Zip's results")
        return int(avr.group(4)), int(avr.group(8)), int(tot.group(3))

    def run(self, result, say):
        c, d, t = self.ratings(call(["7z", "b", "-mmt1"]))
        result.add("single", "One core (total)", "MIPS", t)
        result.add("single_compress", "One core, compress", "MIPS", c)
        c, d, t = self.ratings(call(["7z", "b"]))
        result.add("multi", "All cores (total)", "MIPS", t)
        result.add("multi_compress", "All cores, compress", "MIPS", c)
        result.add("multi_decompress", "All cores, decompress", "MIPS", d)


# ------------------------------------------------------------------ memory

class Memory(Runner):
    key, title, group = "memory", "Memory", "memory"
    about = "RAM bandwidth (STREAM-style copy and triad, every core) and latency (a random pointer chase)."
    needs = ("cc",)
    minutes = 0.2

    def prepare(self, say):
        src = HERE / "membench.c"
        self.binary = CACHE / "membench"
        # rebuilt when the source changes or for another CPU (-march=native)
        stamp = CACHE / "membench.stamp"
        want = f"{src.stat().st_mtime}:{run_text(['uname', '-m'])}:{os.uname().release}"
        if not self.binary.exists() or not stamp.exists() or stamp.read_text() != want:
            say("  compiling the memory test")
            CACHE.mkdir(parents=True, exist_ok=True)
            call(["cc", "-O3", "-march=native", "-fopenmp", str(src), "-o", str(self.binary)], timeout=120)
            stamp.write_text(want)

    def run(self, result, say):
        values = dict(l.split("=", 1) for l in call([str(self.binary)], timeout=300).splitlines() if "=" in l)
        result.add("triad", "Bandwidth (triad)", "GB/s", values["triad_gbs"])
        result.add("copy", "Bandwidth (copy)", "GB/s", values["copy_gbs"])
        result.add("latency", "Latency", "ns", values["latency_ns"], higher_better=False)


# ------------------------------------------------------------------ disk

class Disk(Runner):
    key, title, group = "disk", "Disk", "disk"
    about = "Sequential and random reads and writes on the drive your home folder is on (fio, direct I/O)."
    needs = ("fio",)
    minutes = 1.0

    def __init__(self, folder=None):
        self.folder = Path(folder or CACHE / "disk")

    def available(self):
        ok, why = super().available()
        if not ok:
            return ok, why
        self.folder.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.folder).free
        return (True, "") if free > 6e9 else (False, "less than 6 GB free there")

    def prepare(self, say):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.work = tempfile.TemporaryDirectory(prefix="run-", dir=self.folder)
        # btrfs (DecKoOS's /home) compresses and copies on write: fio would measure zstd and the page cache,
        # not the drive. A no-copy-on-write folder gets neither, and its new files inherit that.
        if run_text(["stat", "-f", "-c", "%T", self.work.name]) == "btrfs":
            call(["chattr", "+C", self.work.name])
        self.filename = Path(self.work.name) / "deckos-bench.fio"
    def fill(self, say):
        # Random writes remap the file on the SSD. Refill before every repetition so later
        # sequential reads do not measure a different layout from the first repetition.
        say("  filling the test file before measuring reads")
        out = call(["fio", "--name=prepare", f"--filename={self.filename}", "--size=2G",
              "--rw=write", "--bs=1M", "--ioengine=io_uring", "--direct=1",
              "--iodepth=16", "--end_fsync=1", "--output-format=json"], timeout=300)
        jobs = json.loads(out[out.index("{"):])["jobs"]
        if not jobs or any(job.get("error", 0) for job in jobs):
            raise RuntimeError("fio could not initialize the test file")

    def job(self, name, rw, bs, depth):
        out = call(["fio", f"--name={name}", f"--filename={self.filename}", "--size=2G",
                    f"--rw={rw}", f"--bs={bs}", f"--iodepth={depth}", "--ioengine=io_uring", "--direct=1",
                    "--time_based", "--runtime=8", "--ramp_time=2", "--numjobs=1", "--group_reporting",
                    "--output-format=json"], timeout=120)
        job = json.loads(out[out.index("{"):])["jobs"][0]
        if job.get("error", 0):
            raise RuntimeError(f"fio reported I/O error {job['error']}")
        side = job["read"] if "read" in rw else job["write"]
        return side["bw_bytes"] / 1e6, side["iops"]

    def run(self, result, say):
        self.fill(say)
        result.notes.append("Test file initialized sequentially before each repetition; direct I/O, no CoW on btrfs.")
        mb, _ = self.job("seq-read", "read", "1M", 16)
        result.add("seq_read", "Sequential read", "MB/s", mb)
        mb, _ = self.job("seq-write", "write", "1M", 16)
        result.add("seq_write", "Sequential write", "MB/s", mb)
        _, iops = self.job("rand-read", "randread", "4k", 32)
        result.add("rand_read", "Random 4K read (QD32)", "IOPS", iops)
        _, iops = self.job("rand-write", "randwrite", "4k", 32)
        result.add("rand_write", "Random 4K write (QD32)", "IOPS", iops)
        _, iops = self.job("rand-read-1", "randread", "4k", 1)
        result.add("rand_read_qd1", "Random 4K read (QD1, how snappy it feels)", "IOPS", iops)

    def finish(self, say):
        if hasattr(self, "work"):
            self.work.cleanup()


# ------------------------------------------------------------------ GPU

class Gpu(Runner):
    key, title, group = "gpu-vkmark", "Graphics: vkmark", "gpu"
    about = "Vulkan scenes at 1920×1080 using vkmark's default graphics device. Opens a benchmark window when needed."
    needs = ("vkmark",)
    minutes = 1.0

    def winsys(self):
        plugins = {p.stem for d in ("/usr/lib/vkmark", "/usr/lib64/vkmark") for p in Path(d).glob("*.so")}
        return "headless" if "headless" in plugins else None

    def run(self, result, say):
        # immediate isn't offered by the headless backend (radv); mailbox renders as fast as it can too
        argv = ["vkmark", "--size", "1920x1080", "--present-mode", "mailbox"]
        if self.winsys():
            argv[1:1] = ["--winsys", "headless"]
        out = call(argv, timeout=600)
        score = re.search(r"vkmark Score:\s*(\d+)", out)
        if not score:
            raise RuntimeError("couldn't read vkmark's score")
        result.add("score", "vkmark score", "points", int(score.group(1)))
        for scene, config, fps in re.findall(r"^\[(\w+)\](.*?)FPS:\s*(\d+)", out, re.M):
            name = f"{scene} {config.strip()}"
            key = hashlib.sha256(name.encode()).hexdigest()[:12]
            result.add(f"scene_{scene}_{key}", f"Scene: {name}", "FPS", int(fps))


# ------------------------------------------------------------------ local AI

AI_PROMPT = ("You are reviewing a pull request for a Linux distribution's installer. In about 150 words, explain "
             "what could go wrong when an installer shares the EFI system partition with Windows, and how to "
             "avoid each problem. Be specific.")


class LocalAI(Runner):
    key, title, group = "ai-ollama", "Local AI: Ollama", "ai"
    about = "How fast the local model reads a prompt and writes an answer on the graphics card (tokens per second)."
    needs = ("ollama",)
    minutes = 0.5

    def __init__(self, model=None):
        self.model = model

    def api(self, path, body=None, timeout=600):
        host = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
        url = (host if host.startswith("http") else "http://" + host) + path
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    def available(self):
        ok, why = super().available()
        if not ok:
            return ok, why
        sys.path.insert(0, str(HERE.parent / "assistant"))
        try:
            from assistant import pick_model
            self.model = self.model or pick_model()
        except Exception:
            pass
        if not self.model:
            return False, "no local model (sudo deckos ai setup)"
        try:
            self.api("/api/tags", timeout=5)
        except OSError:
            return False, "Ollama isn't running"
        return True, ""

    def prepare(self, say):
        self.was_loaded = any(m["name"] == self.model for m in self.api("/api/ps", timeout=5).get("models", []))
        say(f"  loading {self.model}")
        t = time.monotonic()
        self.api("/api/generate", {"model": self.model, "prompt": "", "keep_alive": "10m"})
        self.load_seconds = time.monotonic() - t

    def run(self, result, say):
        # A new first line every run: Ollama reuses its cache for a prompt it has seen, which would make
        # every run after the first "read" almost nothing.
        prompt = f"Review {time.time_ns()}.\n{AI_PROMPT}"
        r = self.api("/api/generate", {"model": self.model, "prompt": prompt, "stream": False, "keep_alive": "10m",
                                       "options": {"temperature": 0, "seed": 1, "num_predict": 256, "num_ctx": 4096}})
        result.add("generate", f"Writing ({self.model})", "tokens/s", r["eval_count"] / (r["eval_duration"] / 1e9))
        result.add("prompt", f"Reading the prompt ({self.model})", "tokens/s",
                   r["prompt_eval_count"] / (r["prompt_eval_duration"] / 1e9))
        if not result.notes:
            result.notes.append(f"model {self.model}; loaded in {self.load_seconds:.1f} s")

    def finish(self, say):
        if not getattr(self, "was_loaded", True):  # leave graphics memory as it was
            self.api("/api/generate", {"model": self.model, "keep_alive": 0}, timeout=10)


class PinnedAI(LocalAI):
    """The DecKoOS Score's AI part: always the score's own model, so tokens per second compare across PCs."""

    def available(self):
        ok, why = Runner.available(self)
        if not ok:
            return ok, why
        try:
            names = {m["name"] for m in self.api("/api/tags", timeout=5).get("models", [])}
        except OSError:
            return False, "Ollama isn't running"
        if self.model not in names and f"{self.model}:latest" not in names:
            return False, f"the score's model isn't installed: ollama pull {self.model}"
        return True, ""


# ------------------------------------------------------------------ games that benchmark themselves

def steam_libraries():
    steam = Path.home() / ".local/share/Steam"
    libs = [steam]
    vdf = steam / "steamapps/libraryfolders.vdf"
    try:
        libs += [Path(p) for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text())]
    except OSError:
        pass
    return list(dict.fromkeys(libs))


def steam_game(appid):
    """(install folder, library) for an installed Steam game, or (None, None)."""
    for lib in steam_libraries():
        manifest = lib / f"steamapps/appmanifest_{appid}.acf"
        try:
            folder = re.search(r'"installdir"\s+"([^"]+)"', manifest.read_text()).group(1)
        except (OSError, AttributeError):
            continue
        path = lib / "steamapps/common" / folder
        if path.is_dir():
            return path, lib
    return None, None


def proton():
    """The newest Proton we can run games' tools with: DecKoOS's Proton-CachyOS first."""
    for d in ["/usr/share/steam/compatibilitytools.d/proton-cachyos-slr", "/usr/share/steam/compatibilitytools.d/proton-cachyos"]:
        if Path(d, "proton").exists():
            return Path(d, "proton")
    for lib in steam_libraries():
        found = sorted(lib.glob("steamapps/common/Proton*/proton"))
        if found:
            return found[-1]
    return None


class BeamNG(Runner):
    """BeamNG.drive's BananaBench: its physics engine on every core, no window, no input. The Linux
    build's console crashes at start on current Arch (its bundled mimalloc against the system
    libstdc++), so it runs the Windows build through Proton, in a prefix of its own."""
    key, title, group = "game-beamng", "Game: BeamNG.drive (BananaBench)", "game"
    about = "Experimental. BeamNG's physics benchmark through Proton: simulation throughput and vehicles in real time."
    minutes = 8.0
    APPID = 284160

    def available(self):
        self.folder, self.library = steam_game(self.APPID)
        if not self.folder:
            return False, "BeamNG.drive isn't installed"
        self.proton = proton()
        if not self.proton:
            return False, "no Proton found"
        if not (self.folder / "Bin64/console.x64.exe").exists():
            return False, "BeamNG's console isn't in this version"
        return True, ""

    def run(self, result, say):
        prefix = CACHE / "beamng-prefix"
        prefix.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, STEAM_COMPAT_DATA_PATH=str(prefix), SteamAppId=str(self.APPID),
                   STEAM_COMPAT_CLIENT_INSTALL_PATH=str(Path.home() / ".local/share/Steam"))
        # A fresh name, so a previous run's report can't be mistaken for this one. BeamNG only writes
        # inside its own user folder (an absolute Z:/ path is refused), so it's a bare file name there.
        name = f"deckos-banana-{uuid.uuid4().hex}.json"
        user = prefix / "pfx/drive_c/users"
        try:
            call([str(self.proton), "run", "./Bin64/console.x64.exe", "file",
                  "lua/console/bananabench-json.lua", name],
                 timeout=3600, cwd=self.folder, env=env)
            report = next(user.glob(f"*/AppData/Local/BeamNG/BeamNG.drive/**/{name}"), None)
            if report is None:
                raise RuntimeError("BananaBench didn't write its report (see BeamNG's console.log in "
                                   f"{user}/*/AppData/Local/BeamNG/BeamNG.drive/current)")
            parse_bananabench(report.read_text(), result)
            result.notes.append("BeamNG BananaBench via Proton; default vehicle sweep. This is physics throughput, not rendered FPS.")
        finally:
            for leftover in user.glob(f"*/AppData/Local/BeamNG/BeamNG.drive/**/{name}"):
                leftover.unlink(missing_ok=True)


def parse_bananabench(text, result):
    """Read the installed game's bananabench-json.lua schema (bench.physics result)."""
    data = json.loads(text)
    tests = data.get("tests", {})
    if not isinstance(tests, dict) or not tests:
        raise RuntimeError("BananaBench report contains no vehicle tests")
    for vehicle, test in tests.items():
        prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", vehicle)
        result.add(f"{prefix}_throughput", f"{vehicle}: peak physics throughput", "MBeams/s", test["maxMbeams"])
        result.add(f"{prefix}_realtime", f"{vehicle}: vehicles in real time", "vehicles", test["maxRealtimeVehicles"])
    result.notes.append(f"BananaBench version {data.get('version', 'unknown')}; vehicle range "
                        f"{data.get('vehicleMin', '?')}–{data.get('vehicleMax', '?')}")


SYSTEM = [Cpu7z, Memory, Disk, Gpu, LocalAI]


def score_runners():
    """What a DecKoOS Score run measures: every system test, the AI part on the score's own model."""
    from score import AI_MODEL
    return [PinnedAI(AI_MODEL) if cls is LocalAI else cls() for cls in SYSTEM]
GAMES = [BeamNG]
ALL = {cls.key: cls for cls in SYSTEM + GAMES}
