"""The DecKoOS Score: one number for the whole PC, like 3DMark's, built from Bench's own measurements.

Each part (CPU, memory, storage, graphics, local AI) scores its key measurements against a fixed reference PC, which
scores 5,000 in every part; the DecKoOS Score is the weighted geometric mean of the five. Geometric means, so a part
can't hide a weak measurement behind a strong one, and twice as fast anywhere is the same step up. Medians of the
repetitions, so one odd repetition doesn't move it; the range comes from scoring each repetition on its own.

The formula is versioned. Scores from the same VERSION compare across PCs and over time; a new version changes the
reference or the measurements and starts a new scale, never quietly rescoring old runs. No Qt.
"""
import math

VERSION = 1
BASE = 5000
# The local AI part runs one fixed model: tokens per second mean nothing across different models. Small, so it fits
# any graphics card that runs local AI at all.
AI_MODEL = "qwen3:0.6b"

# part: (name, runner, [(metric, weight, reference value, higher is better)], weight in the total)
# The references are a mid-range 2024 gaming PC's numbers, fixed for version 1 (estimates, not one measured machine).
PARTS = {
    "cpu": ("CPU", "cpu-7z", [("multi", 0.7, 60000, True), ("single", 0.3, 6000, True)], 0.25),
    "memory": ("Memory", "memory", [("triad", 0.6, 30, True), ("latency", 0.4, 90, False)], 0.125),
    "storage": ("Storage", "disk", [("seq_read", 0.2, 3000, True), ("seq_write", 0.15, 2500, True),
                                     ("rand_read", 0.2, 300000, True), ("rand_write", 0.15, 250000, True),
                                     ("rand_read_qd1", 0.3, 12000, True)], 0.125),
    "graphics": ("Graphics", "gpu-vkmark", [("score", 1.0, 8000, True)], 0.30),
    "ai": ("Local AI", "ai-ollama", [("generate", 0.7, 150, True), ("prompt", 0.3, 2000, True)], 0.20),
}
ORDER = ["cpu", "graphics", "ai", "memory", "storage"]


def _median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _points(values_by_metric, spec):
    """BASE × the weighted geometric mean of value/reference (reference/value when lower is better)."""
    log = 0.0
    for metric, weight, ref, higher in spec:
        v = values_by_metric[metric]
        if v <= 0:
            return None
        log += weight * math.log(v / ref if higher else ref / v)
    return BASE * math.exp(log / sum(w for _, w, _, _ in spec))


def _result(run, runner):
    return next((r for r in run.get("results", []) if r.get("runner") == runner), None)


def part(run, key):
    """{"score", "low", "high"} for one part of a saved run, or {"missing": why}."""
    name, runner, spec, _ = PARTS[key]
    res = _result(run, runner)
    if res is None:
        return {"missing": "not measured"}
    if res.get("error"):
        return {"missing": res["error"]}
    metrics = res.get("metrics", {})
    absent = [m for m, *_ in spec if not metrics.get(m, {}).get("values")]
    if absent:
        return {"missing": "not every measurement it needs was taken"}
    if key == "ai" and f"({AI_MODEL})" not in metrics["generate"].get("name", ""):
        return {"missing": f"run with another model (the score uses {AI_MODEL})"}
    medians = {m: _median(metrics[m]["values"]) for m, *_ in spec}
    score = _points(medians, spec)
    if score is None:
        return {"missing": "a measurement was zero"}
    reps = min(len(metrics[m]["values"]) for m, *_ in spec)
    each = [p for p in (_points({m: metrics[m]["values"][i] for m, *_ in spec}, spec) for i in range(reps)) if p]
    return {"score": round(score), "low": round(min(each, default=score)), "high": round(max(each, default=score))}


def score(run):
    """The run's score: {"version", "total" (None unless all five parts were measured), "partial" (the same over the
    parts that were, or None), "parts": {key: part()}, "complete": bool}."""
    parts = {key: part(run, key) for key in ORDER}
    have = {k: p for k, p in parts.items() if "score" in p}

    def combine(field):
        if not have:
            return None
        weights = {k: PARTS[k][3] for k in have}
        return round(math.exp(sum(w * math.log(have[k][field]) for k, w in weights.items()) / sum(weights.values())))

    complete = len(have) == len(PARTS)
    return {"version": VERSION, "complete": complete, "total": combine("score") if complete else None,
            "partial": combine("score"), "low": combine("low"), "high": combine("high"), "parts": parts}


def headline(s):
    """The number to show and what it is: ("12,345", "DecKoOS Score") or a partial one, or ("—", why)."""
    if s["total"] is not None:
        return f"{s['total']:,}", "DecKoOS Score"
    if s["partial"] is not None:
        return f"{s['partial']:,}", "Partial score"
    return "—", "No score yet"
