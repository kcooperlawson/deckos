"""DecKoOS's self-test: each check's verdict and cause from canned command output, and that the same failure is
only told once (never the real system)."""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/selftest'))


class SelfTestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        import selftest
        self.t = importlib.reload(selftest)
        self.t.STATE = Path(self.temp.name) / 'selftest.json'
        self.answers = {}

    def tearDown(self):
        self.temp.cleanup()

    def fake(self, cmd, timeout=60):
        for key, ans in self.answers.items():
            if " ".join(cmd).startswith(key):
                return ans
        return 0, "", ""

    def test_the_signature_bug_is_named(self):
        err = "==> ERROR: Cannot fetch updates\nerror: deckos: missing required signature\n"
        self.assertIn("deckos repo's signature", self.t.update_cause(err))
        self.assertIn("No connection", self.t.update_cause("error: failed retrieving file 'core.db' from x : "
                                                           "Could not resolve host: x"))
        self.assertEqual(self.t.update_cause("error: something new\n"), "error: something new")
        self.assertIn("without saying", self.t.update_cause(""))

    def test_updates_check(self):
        with patch.object(self.t, "run", self.fake), patch.object(self.t.shutil, "which", lambda _n: "/usr/bin/x"):
            self.answers = {"checkupdates": (2, "", "")}
            self.assertTrue(self.t.check_updates().ok)  # 2: nothing to update
            self.answers = {"checkupdates": (1, "", "error: deckos: missing required signature")}
            r = self.t.check_updates()
            self.assertEqual((r.ok, r.fix), (False, "deckos update"))

    def test_sound_and_units(self):
        with patch.object(self.t, "run", self.fake):
            self.answers = {"pw-metadata": (0, "key:'clock.min-quantum' value:'32'", "")}
            self.assertEqual(self.t.check_sound().fix, "deckos sound buffer balanced")
            self.answers = {"pw-metadata": (127, "", "")}
            self.assertTrue(self.t.check_sound().skipped)
            self.answers = {"systemctl is-enabled": (0, "enabled\n", ""), "systemctl is-active": (3, "failed\n", "")}
            r = self.t.check_unit("scheduler", "Game scheduler", "scx_loader.service")
            self.assertEqual((r.ok, r.fix), (False, "pkexec systemctl restart scx_loader.service"))
            self.answers = {"systemctl --user is-enabled": (0, "enabled\n", ""),
                            "systemctl --user is-active": (3, "inactive\n", "")}
            self.assertEqual(self.t.check_unit("m", "M", "x.service", user=True).fix, "systemctl --user restart x.service")
            self.answers = {"systemctl is-enabled": (1, "disabled\n", "")}
            self.assertTrue(self.t.check_unit("s", "S", "y.service").skipped)  # turned off on purpose: not a failure
            self.answers = {"systemctl --failed": (0, "a.service loaded failed failed A\n", "")}
            self.assertIn("a.service", self.t.check_failed_units().cause)

    def test_a_failure_is_told_once(self):
        bad = [self.t.Result("updates", False, "Checking for updates", "sig"), self.t.Result("sound", True, "Sound")]
        told = []
        with patch.object(self.t, "checks", lambda: bad), patch.object(self.t, "notify", told.append):
            self.t.run_all()
            self.t.run_all()
            self.assertEqual([[r.id for r in n] for n in told], [["updates"], []])
            bad[0] = self.t.Result("updates", False, "Checking for updates", "no connection")  # a new cause: told
            self.t.run_all()
            self.assertEqual([r.id for r in told[-1]], ["updates"])
            bad[0] = self.t.Result("updates", True, "Checking for updates")
            self.t.run_all()
            bad[0] = self.t.Result("updates", False, "Checking for updates", "sig")  # broke again after a fix
            self.t.run_all()
            self.assertEqual([r.id for r in told[-1]], ["updates"])


if __name__ == '__main__':
    unittest.main()
