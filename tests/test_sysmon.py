"""System Monitor's /proc and /sys reading, on a fake tree (never the real one)."""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/sysmon'))


def stat_line(pid, comm, ppid, utime, stime, rss_pages, threads=4):
    # fields after "(comm)": state ppid pgrp session tty tpgid flags minflt cminflt majflt cmajflt utime stime
    # cutime cstime priority nice num_threads itrealvalue starttime vsize rss
    return (f'{pid} ({comm}) S {ppid} 1 1 0 -1 0 0 0 0 0 {utime} {stime} 0 0 20 0 {threads} 0 100 1000 '
            f'{rss_pages} 0 0 0\n')


class SysmonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.proc = Path(self.temp.name) / 'proc'
        self.sys = Path(self.temp.name) / 'sys'
        os.environ['DECKOS_PROC'] = str(self.proc)
        os.environ['DECKOS_SYS'] = str(self.sys)
        import sysmon
        self.sm = importlib.reload(sysmon)
        self.sm._APPS = {'firefox': ('Firefox', 'firefox')}
        (self.proc / 'net').mkdir(parents=True)
        self.write('meminfo', 'MemTotal:       32000000 kB\nMemAvailable:   24000000 kB\n'
                              'SwapTotal:      1000000 kB\nSwapFree:        750000 kB\n')
        self.write('uptime', '3725.5 1000.0\n')
        self.write('cpuinfo', 'cpu MHz\t\t: 4000.000\ncpu MHz\t\t: 5000.000\n')
        self.cpu(0, 0)
        self.write('diskstats', '259 0 nvme0n1 10 0 1000 0 10 0 2000 0 0 0 0\n'
                                '259 1 nvme0n1p1 10 0 1000 0 10 0 2000 0 0 0 0\n'
                                '7 0 loop0 1 0 8 0 0 0 0 0 0 0 0\n')
        self.net(1000, 500)
        self.add(100, 'firefox', 1, 100, 0, 1000, '/usr/lib/firefox/firefox\0')
        self.add(101, 'Isolated Web Co', 100, 50, 0, 2000, '/usr/lib/firefox/firefox\0-contentproc\0')
        self.add(102, 'python3', 1, 10, 0, 500, '/usr/bin/python3\0-u\0/usr/lib/deckos/hub/deckos_hub.py\0')
        self.add(103, 'odd ) name', 1, 0, 0, 10, '')
        self.add(3, 'kworker/0:0', 2, 0, 0, 0, '')  # a kernel thread: hidden
        card = self.sys / 'class/drm/card1/device'
        (card / 'hwmon/hwmon3').mkdir(parents=True)
        for name, value in (('gpu_busy_percent', '87'), ('mem_info_vram_used', '8000000000'),
                            ('mem_info_vram_total', '16000000000'), ('vendor', '0x1002'), ('device', '0x7550'),
                            ('hwmon/hwmon3/temp1_input', '65000'), ('hwmon/hwmon3/power1_average', '250000000')):
            (card / name).write_text(value)
        igpu = self.sys / 'class/drm/card0/device'
        igpu.mkdir(parents=True)
        (igpu / 'gpu_busy_percent').write_text('0')
        (igpu / 'mem_info_vram_total').write_text('500000000')
        (self.sys / 'class/drm/card2').mkdir(parents=True)  # no busy counter (not amdgpu): skipped

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop('DECKOS_PROC', None)
        os.environ.pop('DECKOS_SYS', None)

    def write(self, name, text):
        (self.proc / name).write_text(text)

    def cpu(self, busy, idle):
        self.write('stat', f'cpu  {busy} 0 0 {idle} 0 0 0 0 0 0\ncpu0 {busy} 0 0 {idle} 0 0 0 0 0 0\n'
                           f'cpu1 0 0 0 {busy + idle} 0 0 0 0 0 0\nintr 1\n')

    def net(self, down, up):
        self.write('net/dev', 'Inter-|   Receive\n face |bytes\n'
                              f'    lo: 999 0 0 0 0 0 0 0 999 0 0 0 0 0 0 0\n'
                              f'  eth0: {down} 0 0 0 0 0 0 0 {up} 0 0 0 0 0 0 0\n')

    def add(self, pid, comm, ppid, utime, stime, rss, cmdline):
        d = self.proc / str(pid)
        d.mkdir(exist_ok=True)
        (d / 'stat').write_text(stat_line(pid, comm, ppid, utime, stime, rss))
        (d / 'cmdline').write_text(cmdline)
        (d / 'status').write_text(f'Name:\t{comm}\nUid:\t{os.getuid()}\t0\t0\t0\n')
        (d / 'io').write_text('read_bytes: 0\nwrite_bytes: 0\n')

    def test_first_sample_has_no_rates_second_does(self):
        s = self.sm.Sampler()
        first = s.sample()
        self.assertEqual(first.cpu, 0.0)
        self.assertEqual(first.net, (0.0, 0.0))
        self.cpu(300, 700)  # 30% busy across the whole machine since the first sample
        self.add(100, 'firefox', 1, 250, 0, 1000, '/usr/lib/firefox/firefox\0')  # +150 of 1000 ticks
        self.net(201000, 50500)
        second = s.sample()
        self.assertAlmostEqual(second.cpu, 30.0)
        self.assertEqual(len(second.cores), 2)
        firefox = next(p for p in second.procs if p.pid == 100)
        self.assertAlmostEqual(firefox.cpu, 15.0)
        self.assertGreater(second.net[0], 0)
        self.assertGreater(second.net[1], 0)

    def test_memory_gpu_and_disks(self):
        snap = self.sm.Sampler().sample()
        self.assertEqual(snap.mem_total, 32000000 * 1024)
        self.assertEqual(snap.mem_used, 8000000 * 1024)
        self.assertEqual(snap.swap_used, 250000 * 1024)
        self.assertEqual(snap.cpu_mhz, 4500.0)
        self.assertEqual(snap.uptime, 3725.5)
        # the card with the most video memory comes first; one without a busy counter is left out
        self.assertEqual([g.card for g in snap.gpus], ['card1', 'card0'])
        main = snap.gpus[0]
        self.assertEqual((main.busy, main.temp, main.power), (87.0, 65.0, 250.0))
        self.assertTrue(main.name)  # from pci.ids when present, else "Graphics card"
        s = self.sm.Sampler()
        s.sample()
        self.assertEqual(set(s.sample().disks), {'nvme0n1'})  # whole disks only

    def test_processes_are_named_and_grouped_like_people_say(self):
        procs = self.sm.Sampler().sample().procs
        names = {p.pid: p.name for p in procs}
        self.assertNotIn(3, names)  # kernel threads stay out
        self.assertEqual(names[100], 'Firefox')
        self.assertEqual(names[101], 'Firefox')  # a tab process belongs with its browser
        self.assertEqual(names[102], 'deckos_hub.py')  # the script, not "python3"
        self.assertEqual(names[103], 'odd ) name')  # comm with a bracket and spaces
        groups = self.sm.group(procs)
        self.assertEqual(len(groups['Firefox']), 2)

    def test_stop_reports_a_process_that_is_gone(self):
        self.assertEqual(self.sm.stop(2 ** 22 + 12345), 'It had already closed.')

    def test_sizes_read_naturally(self):
        self.assertEqual(self.sm.size(512), '512 B')
        self.assertEqual(self.sm.size(1500), '2 KB')
        self.assertEqual(self.sm.size(27_000_000), '27.0 MB')
        self.assertEqual(self.sm.size(4.4e9), '4.4 GB')


if __name__ == '__main__':
    unittest.main()
