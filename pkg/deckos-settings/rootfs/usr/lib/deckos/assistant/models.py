"""Which local AI model suits this PC: what the graphics card (or processor) can run, the models DecKoOS offers, how
each fits, and the one to start with. `deckos ai setup` downloads the recommended one when no model is named;
DecKoOS Hub's "Choose a model" shows them all.

Only models that call DecKoOS Assistant's tools reliably are listed (the Assistant acts through tools; a model
that answers in chat instead can't set anything up). Measured ones went through tests/eval/assistant_tools.py
(docs/assistant-models.md): gpt-oss:20b and qwen3-coder:30b called the right tool every time, gemma4:12b asked
in chat instead of installing. The others are expected to work, and say so.

    models.py hardware | list [--json] | recommend
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gpu"))
try:
    import nvml
except ImportError:
    nvml = None

GiB = 1 << 30
RESERVED = 2 * GiB  # what Ollama leaves free for the desktop (ollama.service.d/10-deckos.conf)
SYS = Path(os.environ.get("DECKOS_SYS") or "/sys")
PROC = Path(os.environ.get("DECKOS_PROC") or "/proc")

# tag, title, what it's good for, download (GB), graphics memory to run it whole on the card (GB, with the
# Assistant's 16k context), measured on DecKoOS
CATALOG = [
    ("qwen3:4b", "Qwen3 4B", "Quick answers on small graphics cards, or the processor alone", 2.6, 5, False),
    ("qwen3:8b", "Qwen3 8B", "A good all-rounder for 8 GB cards", 5.2, 7.5, False),
    ("qwen3:14b", "Qwen3 14B", "Sharper answers on 12 GB cards", 9.3, 12, False),
    ("gpt-oss:20b", "gpt-oss 20B", "The best DecKoOS Assistant on 16 GB cards (measured)", 13, 13.5, True),
    ("qwen3-coder:30b", "Qwen3 Coder 30B (MoE)", "Code and DecKoOS's tools; runs partly on the processor below 24 GB "
     "(measured)", 18, 21, True),
    ("qwen3:30b", "Qwen3 30B (MoE)", "Fast for its size on 24 GB cards", 19, 22, False),
    ("qwen3:32b", "Qwen3 32B", "The most capable here for 24 GB cards and up", 20, 24, False),
    ("gpt-oss:120b", "gpt-oss 120B", "Workstations with 80 GB of graphics memory", 65, 70, False),
]


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def _pci_name(dev):
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sysmon"))
        import sysmon
        return sysmon.pci_name(_read(dev / "vendor"), _read(dev / "device"))
    except ImportError:
        return ""


def hardware():
    """{"gpu", "vendor", "vram", "accel", "ram"}: the card the models would run on (the one with the most memory),
    how (cuda, rocm, or cpu) and the PC's memory, in bytes."""
    ram = 0
    m = re.search(r"^MemTotal:\s+(\d+) kB", _read(PROC / "meminfo"), re.M)
    if m:
        ram = int(m.group(1)) * 1024
    best = {"gpu": "", "vendor": "", "vram": 0, "accel": "cpu", "ram": ram}
    for d in (nvml.devices() if nvml and not os.environ.get("DECKOS_SYS") else []):
        if d["vram_total"] > best["vram"]:
            best.update(gpu=d["name"], vendor="nvidia", vram=d["vram_total"], accel="cuda")
    for card in sorted((SYS / "class/drm").glob("card[0-9]")):
        dev = card / "device"
        if _read(dev / "vendor") != "0x1002":
            continue
        vram = int(_read(dev / "mem_info_vram_total") or 0)
        if vram >= 4 * GiB and vram > best["vram"]:  # a Ryzen's built-in graphics isn't for models
            best.update(gpu=_read(dev / "product_name") or _pci_name(dev) or "AMD graphics card", vendor="amd", vram=vram,
                        accel="rocm")
    return best


def fit(model, hw):
    """'fits' (whole model on the card), 'tight' (needs the memory kept free for the desktop: may stutter it),
    'slow' (partly on the processor) or 'too big' (not enough memory at all)."""
    _, _, _, download, need, _ = model
    need_b = need * GiB
    if hw["accel"] != "cpu" and hw["vram"]:
        if need_b <= hw["vram"] - RESERVED:
            return "fits"
        if need_b <= hw["vram"]:
            return "tight"
    # Split between the card and the processor (Ollama does that by itself), or on the processor alone: what the
    # card can't hold goes to system memory, of which the desktop and apps keep a good part
    card = max(hw["vram"] - RESERVED, 0) if hw["accel"] != "cpu" else 0
    if max(need_b, download * GiB * 1.3) <= card + hw["ram"] * 0.6:
        return "slow"
    return "too big"


def recommend(hw=None):
    """The model to start with: gpt-oss:20b if it fits (measured), else the biggest that fits; on the processor alone,
    the smallest."""
    hw = hw or hardware()
    fitting = [m for m in CATALOG if fit(m, hw) == "fits"]
    measured = [m for m in fitting if m[5]]
    if measured:
        return measured[0][0]
    if fitting:
        return max(fitting, key=lambda m: m[4])[0]
    return CATALOG[0][0]


def rows(hw=None, installed=()):
    hw = hw or hardware()
    best = recommend(hw)
    out = []
    for m in CATALOG:
        tag, title, good, download, need, measured = m
        out.append({"tag": tag, "title": title, "good_for": good, "download_gb": download, "vram_gb": need,
                    "measured": measured, "fit": fit(m, hw), "recommended": tag == best,
                    "installed": tag in installed or f"{tag}:latest" in installed})
    return out


def describe(hw):
    if hw["accel"] == "cpu":
        return f"No graphics card for AI: models run on the processor ({hw['ram'] / GiB:.0f} GB of memory)"
    how = {"cuda": "CUDA", "rocm": "ROCm"}[hw["accel"]]
    return f"{hw['gpu']} · {hw['vram'] / GiB:.0f} GB · {how}"


FIT_TEXT = {"fits": "fits", "tight": "tight fit", "slow": "slower (partly on the processor)", "too big": "too big"}


def main(argv):
    hw = hardware()
    if argv[:1] == ["hardware"]:
        print(json.dumps(hw))
    elif argv[:1] == ["recommend"]:
        print(recommend(hw))
    elif argv[:1] == ["list"]:
        r = rows(hw)
        if "--json" in argv:
            print(json.dumps({"hardware": hw, "describe": describe(hw), "models": r}))
        else:
            print(describe(hw))
            for x in r:
                mark = "→" if x["recommended"] else " "
                print(f" {mark} {x['tag']:<16} {FIT_TEXT[x['fit']]:<24} {x['download_gb']:>5.1f} GB  {x['good_for']}")
    else:
        print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
