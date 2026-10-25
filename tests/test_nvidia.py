"""NVIDIA and Intel PCs, without one: a simulated i9-14900K + RTX 5070 Ti (NVML, System Doctor, the AI model pick,
DecKoOS Hub's tiles)."""
import ctypes
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'pkg/deckos-settings/rootfs/usr/lib/deckos'
sys.path[:0] = [str(LIB / d) for d in ('gpu', 'sysdoctor', 'assistant', 'sysmon')]
import models  # noqa: E402
import nvml  # noqa: E402
import sysdoctor as sd  # noqa: E402

GiB = 1 << 30


class FakeNVML:
    """libnvidia-ml.so with one RTX 5070 Ti; `broken` names calls that fail (a driver missing a reading)."""

    def __init__(self, broken=()):
        self.broken = set(broken)

    def __getattr__(self, name):
        if name in self.broken:
            return lambda *a: 3  # NVML_ERROR_NOT_SUPPORTED
        return getattr(self, '_' + name)

    @staticmethod
    def _set(ref, value):
        ref._obj.value = value

    def _nvmlInit_v2(self):
        return 0

    def _nvmlDeviceGetCount_v2(self, ref):
        self._set(ref, 1)
        return 0

    def _nvmlDeviceGetHandleByIndex_v2(self, i, ref):
        self._set(ref, 0x1234)
        return 0

    def _nvmlDeviceGetName(self, buf, size_buf, size):
        ctypes.memmove(size_buf, b'NVIDIA GeForce RTX 5070 Ti\0', 27)
        return 0

    def _nvmlDeviceGetMemoryInfo(self, h, ref):
        ref._obj.total, ref._obj.used = 16 * GiB, 3 * GiB
        return 0

    def _nvmlDeviceGetUtilizationRates(self, h, ref):
        ref._obj.gpu = 87
        return 0

    def _nvmlDeviceGetTemperature(self, h, kind, ref):
        self._set(ref, 64)
        return 0

    def _nvmlDeviceGetPowerUsage(self, h, ref):
        self._set(ref, 251000)
        return 0

    def _nvmlDeviceGetEnforcedPowerLimit(self, h, ref):
        self._set(ref, 300000)
        return 0

    def _nvmlDeviceGetClockInfo(self, h, kind, ref):
        self._set(ref, 14001)
        return 0

    def _nvmlDeviceGetMaxClockInfo(self, h, kind, ref):
        self._set(ref, 14001)
        return 0


class NvmlTests(unittest.TestCase):
    def tearDown(self):
        nvml.reset()

    def test_readings(self):
        d = nvml.devices(loader=lambda _name: FakeNVML())[0]
        self.assertEqual(d['name'], 'GeForce RTX 5070 Ti')
        self.assertEqual((d['vram_total'], d['vram_used'], d['busy'], d['temp']), (16 * GiB, 3 * GiB, 87.0, 64.0))
        self.assertEqual((d['power'], d['power_limit'], d['mem_clock']), (251.0, 300.0, 14001))

    def test_a_missing_reading_keeps_the_rest(self):
        d = nvml.devices(loader=lambda _name: FakeNVML(broken={'nvmlDeviceGetPowerUsage'}))[0]
        self.assertIsNone(d['power'])
        self.assertEqual(d['temp'], 64.0)

    def test_no_driver_no_devices(self):
        def missing(_name):
            raise OSError('libnvidia-ml.so.1: cannot open shared object file')
        self.assertEqual(nvml.devices(loader=missing), [])


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(sd, SYS=self.root / 'sys', PROC=self.root / 'proc')
        self.paths.start()
        (self.root / 'proc').mkdir()

    def tearDown(self):
        self.paths.stop()
        self.temp.cleanup()

    def card(self, driver):
        dev = self.root / 'sys/bus/pci/devices/0000:01:00.0'
        dev.mkdir(parents=True)
        for f, v in (('class', '0x030000'), ('vendor', '0x10de'), ('device', '0x2c05')):  # RTX 5070 Ti
            (dev / f).write_text(v + '\n')
        if driver:
            drv = self.root / f'sys/bus/pci/drivers/{driver}'
            drv.mkdir(parents=True)
            (dev / 'driver').symlink_to(drv)

    def test_on_nouveau(self):
        self.card('nouveau')
        f = sd.nvidia_driver()
        self.assertEqual(len(f), 1)
        self.assertIn('nouveau', f[0].text)
        self.assertIn('chwd -a', ' '.join(f[0].fixes[0].cmd))

    def test_no_driver_mentions_secure_boot(self):
        self.card(None)
        self.assertIn('Secure Boot', sd.nvidia_driver()[0].text)

    def test_rtx_50_needs_the_open_module(self):
        self.card('nvidia')
        (self.root / 'proc/driver/nvidia').mkdir(parents=True)
        version = self.root / 'proc/driver/nvidia/version'
        version.write_text('NVRM version: NVIDIA UNIX x86_64 Kernel Module  570.153.02\n')
        self.assertIn('open driver', sd.nvidia_driver()[0].title)
        version.write_text('NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  570.153.02\n')
        self.assertEqual(sd.nvidia_driver(), [])

    def cpu(self, microcode):
        (self.root / 'proc/cpuinfo').write_text(
            'vendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 183\n'
            f'model name\t: Intel(R) Core(TM) i9-14900K\nmicrocode\t: {microcode}\n')

    def test_14900k_microcode(self):
        self.cpu('0x129')
        f = sd.intel_microcode()
        self.assertEqual(len(f), 1)
        self.assertIn('i9-14900K', f[0].evidence[0])
        self.cpu('0x12f')
        self.assertEqual(sd.intel_microcode(), [])

    def test_amd_cpu_is_left_alone(self):
        (self.root / 'proc/cpuinfo').write_text('vendor_id\t: AuthenticAMD\ncpu family\t: 25\nmodel\t\t: 97\n')
        self.assertEqual(sd.intel_microcode(), [])


class ModelPickTests(unittest.TestCase):
    def hw(self, vram_gb, accel='cuda', ram_gb=64):
        return {'gpu': 'GeForce RTX 5070 Ti', 'vendor': 'nvidia', 'vram': int(vram_gb * GiB), 'accel': accel,
                'ram': ram_gb * GiB}

    def test_picks_by_graphics_memory(self):
        self.assertEqual(models.recommend(self.hw(15.9)), 'gpt-oss:20b')  # 5070 Ti / RX 9070 XT (16 GB)
        self.assertEqual(models.recommend(self.hw(24)), 'gpt-oss:20b')  # measured beats merely bigger
        self.assertEqual(models.recommend(self.hw(12)), 'qwen3:8b')  # 14B wants 12 GB plus the desktop's 2
        self.assertEqual(models.recommend(self.hw(8)), 'qwen3:4b')
        self.assertEqual(models.recommend(self.hw(0, 'cpu', 32)), 'qwen3:4b')

    def test_fit_labels(self):
        hw = self.hw(15.9)
        by = {r['tag']: r for r in models.rows(hw, installed=['qwen3:8b'])}
        self.assertEqual(by['gpt-oss:20b']['fit'], 'fits')
        self.assertTrue(by['gpt-oss:20b']['recommended'])
        self.assertTrue(by['qwen3:8b']['installed'])
        self.assertEqual(by['qwen3:32b']['fit'], 'slow')
        self.assertEqual(by['gpt-oss:120b']['fit'], 'too big')

    def test_nvidia_card_is_found_through_nvml(self):
        fake = [{'name': 'GeForce RTX 5070 Ti', 'vram_total': 16 * GiB}]
        with patch.object(models.nvml, 'devices', return_value=fake), patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DECKOS_SYS', None)
            hw = models.hardware()
        self.assertEqual((hw['vendor'], hw['accel'], hw['vram']), ('nvidia', 'cuda', 16 * GiB))
        self.assertIn('CUDA', models.describe(hw))


if __name__ == '__main__':
    unittest.main()
