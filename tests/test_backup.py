"""Before a reinstall: the whole-home backup round-trips (links included), leaves caches out, catches damage, and
a restore never replaces a newer file."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/backup"))
import backup  # noqa: E402


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.home, self.drive = t / "home", t / "drive"
        self.drive.mkdir()
        (self.home / "Documents").mkdir(parents=True)
        (self.home / "Documents/notes.txt").write_text("keep me")
        (self.home / ".config/deckos").mkdir(parents=True)
        (self.home / ".config/deckos/vibe").write_text("neon")
        (self.home / ".cache/big").mkdir(parents=True)
        (self.home / ".cache/big/junk").write_text("x" * 1000)
        prefix = self.home / ".local/share/deckos/proton-prefixes/lib"
        prefix.mkdir(parents=True)
        (prefix / "pfx.lock").write_text("")
        os.symlink("pfx.lock", prefix / "link")  # what a Windows-format drive can't hold as a file

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        return backup.make(self.drive, base=self.home, say=lambda s: None)

    def test_round_trip(self):
        folder = self.make()
        self.assertTrue(folder.name.startswith("DecKoOS backup "))
        self.assertEqual(backup.verify(folder)[0], True)
        names = {p.name for p in folder.iterdir()}
        self.assertTrue({"home.tar.zst", "manifest.json", "README.txt", "packages.txt", "drives.txt"} <= names)
        new = Path(self.tmp.name) / "newhome"
        new.mkdir()
        backup.restore(folder, base=new, say=lambda s: None)
        self.assertEqual((new / "Documents/notes.txt").read_text(), "keep me")
        self.assertEqual((new / ".config/deckos/vibe").read_text(), "neon")
        link = new / ".local/share/deckos/proton-prefixes/lib/link"
        self.assertTrue(link.is_symlink())
        self.assertFalse((new / ".cache").exists())  # caches rebuild themselves

    def test_restore_keeps_newer_files(self):
        folder = self.make()
        new = Path(self.tmp.name) / "newhome"
        (new / "Documents").mkdir(parents=True)
        mine = new / "Documents/notes.txt"
        mine.write_text("written after the reinstall")
        future = time.time() + 3600
        os.utime(mine, (future, future))
        backup.restore(folder, base=new, say=lambda s: None)
        self.assertEqual(mine.read_text(), "written after the reinstall")

    def test_sparse_image_stays_sparse(self):
        # A test disk image is mostly holes: restored full size, a 380 GB set of them nearly filled the disk
        img = self.home / "Documents/disk.img"
        with open(img, "wb") as f:
            f.truncate(1 << 30)
        folder = self.make()
        new = Path(self.tmp.name) / "newhome"
        new.mkdir()
        heard = []
        backup.restore(folder, base=new, say=heard.append)
        out = new / "Documents/disk.img"
        self.assertEqual(out.stat().st_size, 1 << 30)
        self.assertLess(out.stat().st_blocks * 512, 1 << 20)
        self.assertTrue(any("Checking" in s for s in heard))  # the long verify isn't silent

    def test_damage_is_caught(self):
        folder = self.make()
        with open(folder / "home.tar.zst", "r+b") as f:
            f.seek(40)
            f.write(b"\xff\xff\xff\xff")
        ok, why = backup.verify(folder)
        self.assertFalse(ok)
        self.assertIn("changed", why)
        with self.assertRaises(RuntimeError):
            backup.restore(folder, base=Path(self.tmp.name), say=lambda s: None)

    def test_refuses_a_folder_inside_home(self):
        inside = self.home / "Backups"
        inside.mkdir()
        with self.assertRaisesRegex(RuntimeError, "outside your home"):
            backup.make(inside, base=self.home, say=lambda s: None)

    def test_listed_newest_first(self):
        first = self.make()
        m = json.loads((first / "manifest.json").read_text())
        m["made"] -= 100
        (first / "manifest.json").write_text(json.dumps(m))
        (self.drive / "DecKoOS backup unfinished").mkdir()  # no manifest: not listed
        time.sleep(61 - time.localtime().tm_sec if time.localtime().tm_sec > 58 else 0)
        found = backup.backups_in(self.drive)
        self.assertEqual([f for f, _ in found], [first])


if __name__ == "__main__":
    unittest.main()
