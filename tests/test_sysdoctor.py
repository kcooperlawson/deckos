"""DeckOS System Doctor: findings from canned journal, systemd and disk output; nothing real is read."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/sysdoctor'))
import sysdoctor as sd  # noqa: E402

T0 = 1792856484  # 11:41:24, the reference machine's Gaming Mode crash


def dump(comm, cmdline, at):
    return json.dumps({"COREDUMP_COMM": comm, "COREDUMP_CMDLINE": cmdline, "COREDUMP_SIGNAL_NAME": "SIGABRT",
                       "COREDUMP_TIMESTAMP": str(int(at * 1e6))})


# The morning of October 24: gamescope, then the desktop's programs within a second, then a game crash
DUMPS = "\n".join([
    dump("gamescope-wl", "gamescope -e -- steam", T0),
    *[dump(c, f"/usr/bin/{c}", T0 + 8) for c in ("plasmashell", "ksplashqml", "plasma-fallback", "ksecretd",
                                                  "kdeconnectd", "drkonqi-coredum")],
    dump("plasmashell", "/usr/bin/plasmashell", T0 + 8.5),
    dump("GameThread", "Z:\\Games\\Cyberpunk2077\\bin\\x64\\Cyberpunk2077.exe", T0 + 600),
    dump("python3", "python3 /usr/lib/deckos/hub/deckos_hub.py", T0 + 700),
])

OUTPUT = {
    ("systemctl", "--failed"): "drkonqi-coredump-pickup.service loaded failed failed Consume pending crashes\n",
    ("systemctl", "--user", "--failed"): "",
    ("journalctl", "--user", "-b", "-u"): "drkonqi-coredump-pickup: Failed with result 'exit-code'.\n",
    ("journalctl", "-b", "-u"): "Started Consume pending crashes.\nFailed with result 'exit-code'.\n",
    ("journalctl", "--since"): DUMPS,
    ("systemd-analyze",): "Startup finished in 18.6s (firmware) + 6.0s (loader) + 5.9s (kernel) + 9.5s (userspace) = 40.1s\n",
    ("systemd-analyze", "blame"): "6.466s NetworkManager-wait-online.service\n12.1s plymouth-quit-wait.service\n980ms x.service\n",
    ("journalctl", "-b", "-p"): ('sdb: Failed to find and pin callout binary "/usr/bin/hdparm": No such file or directory\n' * 3
                                + "kwin_wayland: atomic commit failed: Invalid argument\n" * 4
                                + "Process 1234 (python3) of user 1000 dumped core.\nStack trace of thread 1234:\n"),
    ("pacman", "-F"): "",
    ("pacman", "-Si"): "Name : hdparm\n",
    ("journalctl", "-b", "-k"): "Oct 24 11:41:20.1 deckos kernel: amdgpu 0000:03:00.0: amdgpu: GPU reset begin!\n",
}


def fake_run(cmd, timeout=30):
    best = max((k for k in OUTPUT if tuple(cmd[:len(k)]) == k), key=len, default=None)
    if cmd[:2] == ["pacman", "-Si"] and cmd[2] != "hdparm":
        return 1, ""
    return (0, OUTPUT[best]) if best else (1, "")


class Checkup(unittest.TestCase):
    def setUp(self):
        self.fstab = tempfile.NamedTemporaryFile("w", suffix="fstab", delete=False)
        self.fstab.write("UUID=1 / btrfs defaults 0 0\n")
        self.fstab.close()
        # not the machine's own fstab: CI runners have network mounts
        self.patches = [patch.object(sd, "run", fake_run), patch.object(sd, "FSTAB", Path(self.fstab.name))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        os.unlink(self.fstab.name)

    def findings(self):
        with patch.object(sd.os, "statvfs", lambda m: os.statvfs_result((4096, 4096, 50_000_000, 25_000_000,
                                                                          25_000_000, 0, 0, 0, 0, 255, 0))):
            return {f.key: f for f in sd.checkup()}

    def test_failed_unit_with_its_log_and_fixes(self):
        f = self.findings()["unit:system:drkonqi-coredump-pickup.service"]
        self.assertEqual(f.title, "KDE's crash reporter failed")
        self.assertIn("Failed with result 'exit-code'.", f.evidence)
        self.assertEqual([x.cmd[:3] for x in f.fixes], [["pkexec", "systemctl", "restart"],
                                                         ["pkexec", "systemctl", "reset-failed"]])

    def test_a_desktop_crash_burst_is_one_finding(self):
        found = self.findings()
        burst = found["crash:desktop-burst"]
        self.assertEqual(burst.level, sd.BAD)
        self.assertIn("6 desktop programs stopped at the same moment", burst.text)
        self.assertFalse([k for k in found if k in ("crash:The desktop (plasmashell)", "crash:A desktop service")])
        self.assertIn("crash:Gaming Mode (gamescope)", found)  # gamescope went first, separately

    def test_crashes_are_named_by_what_ran(self):
        found = self.findings()
        self.assertEqual(found["crash:A game"].open, ["deckos-gamedoctor"])
        self.assertIn("DeckOS app", found["crash:DeckOS Hub"].text)
        self.assertEqual(sd.name_program("python3", "python3 /tmp/x/tool.py --demo"), ("tool.py (Python)", "app"))

    def test_slow_boot_and_missing_program(self):
        found = self.findings()
        self.assertEqual(found["boot:wait-online"].fixes[0].cmd,
                         ["pkexec", "systemctl", "disable", "NetworkManager-wait-online.service"])
        self.assertIn("boot:plymouth-quit-wait.service", found)
        hd = found["missing:/usr/bin/hdparm"]
        self.assertIn("3 times this start-up", hd.text)
        self.assertEqual(hd.fixes[0].cmd[-1], "hdparm")

    def test_gpu_reset_points_at_the_display_fix(self):
        self.assertEqual(self.findings()["gpu:reset"].open, ["deckos-hub", "--page", "display"])

    def test_other_errors_leave_out_what_has_a_finding(self):
        lines = self.findings()["journal"].evidence
        self.assertEqual(lines, ["4×  kwin_wayland: atomic commit failed: Invalid argument"])

    def test_worst_first_and_disk_space(self):
        with patch.object(sd.os, "statvfs", lambda m: os.statvfs_result((4096, 4096, 50_000_000, 900_000, 900_000,
                                                                          0, 0, 0, 0, 255, 0))):
            found = sd.checkup()
        levels = [f.level for f in found]
        self.assertEqual(levels, sorted(levels, key=sd.ORDER.get))
        disk = next(f for f in found if f.key == "disk:/")
        self.assertEqual(disk.level, sd.BAD)  # 3.7 GB free
        self.assertIn("Only 4 GB free", disk.title)

    def test_restart_pending_when_the_running_kernel_is_gone(self):
        with patch.object(sd.os, "uname", lambda: os.uname_result(("Linux", "pc", "6.0.0-old", "", "x86_64"))):
            self.assertEqual(sd.restart_pending()[0].key, "restart")

    def test_a_broken_check_does_not_hide_the_others(self):
        def boom():
            raise ValueError("journal unreadable")
        with patch.object(sd, "CHECKS", [boom, sd.slow_boot]):
            keys = [f.key for f in sd.checkup()]
        self.assertIn("check:boom", keys)
        self.assertIn("boot:wait-online", keys)

    def test_no_wait_online_fix_with_network_drives(self):
        with tempfile.TemporaryDirectory() as d:
            fstab = Path(d) / 'fstab'
            fstab.write_text('UUID=1 / btrfs defaults 0 0\n# nas:/x /mnt/old nfs defaults 0 0\n')
            with patch.object(sd, 'FSTAB', fstab):
                self.assertIn('boot:wait-online', [f.key for f in sd.slow_boot()])
            fstab.write_text('UUID=1 / btrfs defaults 0 0\nnas:/media /mnt/nas nfs defaults,_netdev 0 0\n')
            with patch.object(sd, 'FSTAB', fstab):
                self.assertNotIn('boot:wait-online', [f.key for f in sd.slow_boot()])


class Window(unittest.TestCase):
    def test_demo_renders_and_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as out:
            shot = Path(out) / 'doctor.png'
            r = subprocess.run([sys.executable, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/sysdoctor/deckos_sysdoctor.py'),
                                '--demo', '--screenshot', str(shot)], capture_output=True, text=True, timeout=60,
                               env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            self.assertGreater(shot.stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
