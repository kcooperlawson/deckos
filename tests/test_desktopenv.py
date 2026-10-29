"""desktopenv: background services open windows with the session's display as it is now."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/desktopenv"))
import desktopenv  # noqa: E402

SYSTEMD = "HOME=/home/k\nWAYLAND_DISPLAY=wayland-1\nDISPLAY=:0\nXDG_SESSION_TYPE=wayland\nPATH=/usr/bin\nBOGUS\n"


class DesktopEnvTests(unittest.TestCase):
    def test_takes_only_the_desktops_keys(self):
        self.assertEqual(desktopenv.parse(SYSTEMD),
                         {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"})

    def test_a_service_started_before_the_desktop_gets_its_display(self):
        early = {"HOME": "/home/k", "PATH": "/usr/local/bin:/usr/bin"}  # what a login-time service starts with
        env = desktopenv.env(early, SYSTEMD)
        self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-1")
        self.assertEqual(env["DISPLAY"], ":0")
        self.assertEqual(env["PATH"], "/usr/local/bin:/usr/bin")  # the service's own settings stay

    def test_nothing_from_systemd_leaves_it_as_it_was(self):
        self.assertEqual(desktopenv.env({"A": "1"}, ""), {"A": "1"})


if __name__ == "__main__":
    unittest.main()
