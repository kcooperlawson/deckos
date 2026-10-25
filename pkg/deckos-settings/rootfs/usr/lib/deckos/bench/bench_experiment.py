"""DecKoOS Bench experiments: the same tests with one setting changed, A and B in turn.

The order alternates (A B B A A B...) so a PC that warms up or a background task that starts halfway
doesn't favour either side. Each value's repetitions are saved as a normal run, so History and Compare
show them, and the setting is put back afterwards whatever happens.

Settings need no password: the power profile (power-profiles-daemon) and whether the local AI model
sits in graphics memory (what DecKoOS's workload modes free for games).
"""
import json
import os
import shutil
import subprocess
import urllib.request
from copy import deepcopy

from bench_core import run_suite, save, settle


class Setting:
    key = name = ""
    values = ()
    labels = {}

    def available(self):
        return True, ""

    def get(self):
        raise NotImplementedError

    def set(self, value):
        raise NotImplementedError

    def label(self, value):
        return self.labels.get(value, value)


class PowerProfile(Setting):
    key, name = "power", "Power profile"
    values = ("performance", "balanced", "power-saver")
    labels = {"performance": "Performance", "balanced": "Balanced", "power-saver": "Power saver"}

    def available(self):
        if not shutil.which("powerprofilesctl"):
            return False, "needs power-profiles-daemon"
        return True, ""

    def get(self):
        return subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=10).stdout.strip()

    def set(self, value):
        subprocess.run(["powerprofilesctl", "set", value], check=True, capture_output=True, timeout=10)


class AiModel(Setting):
    """The local model loaded in graphics memory, or not: what a game gets back when it's unloaded."""
    key, name = "ai-loaded", "Local AI model in graphics memory"
    values = ("unloaded", "loaded")
    labels = {"unloaded": "Unloaded", "loaded": "Loaded"}

    def _api(self, path, body=None, timeout=300):
        host = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
        url = (host if host.startswith("http") else "http://" + host) + path
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    def model(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assistant"))
        from assistant import pick_model
        return pick_model()

    def available(self):
        try:
            self._api("/api/tags", timeout=5)
        except OSError:
            return False, "Ollama isn't running"
        return (True, "") if self.model() else (False, "no local model (sudo deckos ai setup)")

    def get(self):
        loaded = [m["name"] for m in self._api("/api/ps", timeout=5).get("models", [])]
        return "loaded" if self.model() in loaded else "unloaded"

    def set(self, value):
        keep = "30m" if value == "loaded" else 0
        self._api("/api/generate", {"model": self.model(), "prompt": "", "keep_alive": keep})


SETTINGS = {s.key: s for s in (PowerProfile(), AiModel())}


def order(repeat):
    """A B, B A, A B...: each pair swaps who goes first."""
    out = []
    for i in range(repeat):
        out += ["a", "b"] if i % 2 == 0 else ["b", "a"]
    return out


def merge(runs, label):
    """One run per value: every repetition's samples together, sensors and timings from the last."""
    merged = deepcopy(runs[0])
    merged["label"], merged["repeat"] = label, len(runs)
    merged["seconds"] = round(sum(r["seconds"] for r in runs), 1)
    merged["status"] = "cancelled" if any(r.get("status") == "cancelled" for r in runs) else "complete"
    by_runner = {r["runner"]: r for r in merged["results"]}
    for run in runs[1:]:
        for res in run["results"]:
            into = by_runner.get(res["runner"])
            if into is None:
                merged["results"].append(deepcopy(res))
                by_runner[res["runner"]] = merged["results"][-1]
                continue
            if res.get("error") and not into.get("error"):
                into["error"] = res["error"]
            for key, metric in res["metrics"].items():
                if key in into["metrics"]:
                    into["metrics"][key]["values"] = into["metrics"][key]["values"] + metric["values"]
                else:
                    into["metrics"][key] = deepcopy(metric)
            if res.get("sensors"):
                into["sensors"], into["trace"] = res["sensors"], res.get("trace", {})
    return merged


def run_experiment(setting_key, a, b, make_runners, repeat=3, label="", say=print, cancelled=lambda: False,
                   on_progress=None):
    """Runs every test once per turn, alternating the setting; returns (run A, run B), saved."""
    setting = SETTINGS[setting_key]
    if a not in setting.values or b not in setting.values or a == b:
        raise ValueError(f"choose two different values of {setting.name}: {', '.join(setting.values)}")
    ok, why = setting.available()
    if not ok:
        raise RuntimeError(f"{setting.name}: {why}")
    values = {"a": a, "b": b}
    original = setting.get()
    turns = order(repeat)
    done = {"a": [], "b": []}
    try:
        for i, side in enumerate(turns):
            if cancelled():
                break
            value = values[side]
            say(f"{setting.name}: {setting.label(value)} (turn {i + 1} of {len(turns)})")
            setting.set(value)
            settle(say=say, cancelled=cancelled)
            run = run_suite(make_runners(), repeat=1, label="", say=say, cancelled=cancelled,
                            settle_between=True,
                            on_progress=(lambda index, total, key, rep, _r, i=i: on_progress(i, len(turns), key, rep, 1))
                            if on_progress else None)
            done[side].append(run)
    finally:
        try:
            setting.set(original)
            say(f"{setting.name} back to {setting.label(original)}")
        except Exception as error:  # the runs still count; say what couldn't be put back
            say(f"Couldn't put {setting.name} back to {setting.label(original)}: {error}")
    if not done["a"] or not done["b"]:
        raise InterruptedError("Stopped before both sides ran")
    name = label or setting.name
    out = []
    for side in ("a", "b"):
        run = merge(done[side], f"{name}: {setting.label(values[side])}")
        run["experiment"] = {"setting": setting_key, "value": values[side], "side": side}
        folder = save(run, "experiment")
        run["_folder"] = str(folder)
        out.append(run)
    return out[0], out[1]
