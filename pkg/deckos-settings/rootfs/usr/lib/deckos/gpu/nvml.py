"""NVIDIA cards' live numbers through NVML (libnvidia-ml.so, which nvidia-utils installs and nvidia-smi uses), read in
process: no nvidia-smi every couple of seconds. NVIDIA's driver has no amdgpu-style sysfs files, so this is how
DecKoOS Hub, System Monitor and the local AI setup see an NVIDIA card. Everything returns nothing (never raises)
when there's no NVIDIA driver.

    devices() -> [{"name", "busy", "vram_used", "vram_total", "temp", "power", "power_limit", "mem_clock",
                   "mem_clock_max"}]
"""
import ctypes

_lib = None
_ready = None

NVML_TEMPERATURE_GPU = 0
NVML_CLOCK_MEM = 2


class _Memory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


def _load(loader=None):
    """Opens and initialises NVML once; False if there's no NVIDIA driver."""
    global _lib, _ready
    if _ready is not None:
        return _ready
    try:
        _lib = (loader or ctypes.CDLL)("libnvidia-ml.so.1")
        _ready = _lib.nvmlInit_v2() == 0
    except OSError:
        _ready = False
    return _ready


def reset():
    """For tests: forget the loaded library."""
    global _lib, _ready
    _lib, _ready = None, None


def devices(loader=None):
    if not _load(loader):
        return []
    count = ctypes.c_uint(0)
    if _lib.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0:
        return []
    out = []
    for i in range(count.value):
        h = ctypes.c_void_p()
        if _lib.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(h)) != 0:
            continue
        name = ctypes.create_string_buffer(96)
        mem, util = _Memory(), _Utilization()
        temp, power, limit = ctypes.c_uint(0), ctypes.c_uint(0), ctypes.c_uint(0)
        clock, top = ctypes.c_uint(0), ctypes.c_uint(0)
        d = {"name": "NVIDIA graphics card", "busy": None, "vram_used": 0, "vram_total": 0, "temp": None,
             "power": None, "power_limit": None, "mem_clock": None, "mem_clock_max": None}
        # Each reading on its own: a card or driver that lacks one still gives the rest
        if _lib.nvmlDeviceGetName(h, name, 96) == 0:
            d["name"] = name.value.decode(errors="replace").removeprefix("NVIDIA ")
        if _lib.nvmlDeviceGetMemoryInfo(h, ctypes.byref(mem)) == 0:
            d["vram_used"], d["vram_total"] = mem.used, mem.total
        if _lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(util)) == 0:
            d["busy"] = float(util.gpu)
        if _lib.nvmlDeviceGetTemperature(h, NVML_TEMPERATURE_GPU, ctypes.byref(temp)) == 0:
            d["temp"] = float(temp.value)
        if _lib.nvmlDeviceGetPowerUsage(h, ctypes.byref(power)) == 0:
            d["power"] = power.value / 1000  # mW -> W
        if _lib.nvmlDeviceGetEnforcedPowerLimit(h, ctypes.byref(limit)) == 0:
            d["power_limit"] = limit.value / 1000
        if _lib.nvmlDeviceGetClockInfo(h, NVML_CLOCK_MEM, ctypes.byref(clock)) == 0:
            d["mem_clock"] = clock.value
        if _lib.nvmlDeviceGetMaxClockInfo(h, NVML_CLOCK_MEM, ctypes.byref(top)) == 0:
            d["mem_clock_max"] = top.value
        out.append(d)
    return out


def driver():
    """('570.153', open) for the loaded NVIDIA kernel module, or ('', False). Blackwell (RTX 50) needs the open
    module; the closed one doesn't support it."""
    try:
        text = open("/proc/driver/nvidia/version").read()
    except OSError:
        return "", False
    import re
    m = re.search(r"Kernel Module(?: for x86_64)?\s+([\d.]+)", text)
    return (m.group(1) if m else "?"), "Open Kernel Module" in text
