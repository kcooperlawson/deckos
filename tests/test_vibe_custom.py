"""Your own Vibes: checked before they're saved (their values go into a desktop script), saved with their photo,
shared as one file and imported without trusting it. Plus the editor's light finder. No real config touched."""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos"
sys.path[:0] = [str(LIB / "vibes"), str(LIB / "hub")]
import vibes  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class CustomVibeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.folder, self.photos = self.home / "vibes", self.home / "photos"
        self.pic = self.home / "my photo.jpg"
        self.pic.write_bytes(JPEG)

    def tearDown(self):
        self.tmp.cleanup()

    def vibe(self, **over):
        return {"name": "Rain lights", "scene": "photo", "colorA": "#FF9E7A", "colorB": "#7AD7FF",
                "photo": str(self.pic), "lights": [[0.2, 0.3, 0.12, "bass"], [0.7, 0.4, 0.1, "high"]], **over}

    def test_saved_with_its_photo(self):
        key = vibes.save(self.vibe(), folder=self.folder, photos=self.photos)
        self.assertEqual(key, "rain-lights")
        mine = vibes.user_vibes(self.folder)[key]
        self.assertEqual(Path(mine["photo"]), self.photos / "rain-lights.jpg")  # a copy: moving the original is fine
        self.assertEqual(mine["lights"][1], [0.7, 0.4, 0.1, "high"])
        self.assertEqual(vibes.save(self.vibe(), folder=self.folder, photos=self.photos), "rain-lights-2")  # never replaced
        vibes.delete(key, folder=self.folder, photos=self.photos)
        self.assertNotIn(key, vibes.user_vibes(self.folder))
        self.assertFalse((self.photos / "rain-lights.jpg").exists())

    def test_nothing_unsafe_gets_through(self):
        bad = [{"name": "x'); evil(); ('"}, {"colorA": "red"}, {"scene": "../../etc"}, {"theme": "org.evil"},
               {"lights": [[0.5, 0.5, 0.1, "everything"]]}, {"lights": [[2, 0.5, 0.1, "bass"]]},
               {"lights": [["0.5", 0.5, 0.1, "bass"]]}, {"grain": 5}, {"photo": "/no/such/file.jpg"}]
        for over in bad:
            with self.subTest(over=over), self.assertRaises(ValueError):
                vibes.check(self.vibe(**over))
        quote = self.home / "it's.jpg"
        quote.write_bytes(JPEG)
        with self.assertRaises(ValueError):
            vibes.check(self.vibe(photo=str(quote)))  # a quote in a path would end the script's string
        with self.assertRaises(ValueError):
            vibes.delete("lofi", folder=self.folder)  # DecKoOS's own can't be deleted
        (self.folder).mkdir()
        (self.folder / "broken.json").write_text('{"name": "x", "colorA": "nope"}')
        self.assertNotIn("broken", vibes.user_vibes(self.folder))  # a tampered file is skipped, not applied

    def test_share_and_import(self):
        key = vibes.save(self.vibe(), folder=self.folder, photos=self.photos)
        look = self.home / "shared.deckos-look"
        vibes.export(key, look, folder=self.folder)
        with zipfile.ZipFile(look) as z:
            self.assertEqual(sorted(z.namelist()), ["photo.jpg", "vibe.json"])
            self.assertNotIn(str(self.home), z.read("vibe.json").decode())  # no paths from this PC
        other_folder, other_photos = self.home / "theirs", self.home / "their-photos"
        new = vibes.import_look(look, folder=other_folder, photos=other_photos)
        self.assertEqual(vibes.user_vibes(other_folder)[new]["lights"][0], [0.2, 0.3, 0.12, "bass"])

    def test_a_bad_look_is_refused(self):
        def look(files):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for n, d in files.items():
                    z.writestr(n, d)
            p = self.home / "bad.deckos-look"
            p.write_bytes(buf.getvalue())
            return p
        v = {k: x for k, x in self.vibe().items() if k != "photo"}
        with self.assertRaises(ValueError):  # the "picture" is a script
            vibes.import_look(look({"vibe.json": json.dumps({**v, "photo": "photo.jpg"}),
                                    "photo.jpg": b"#!/bin/sh\nrm -rf ~\n"}), self.folder, self.photos)
        with self.assertRaises(ValueError):  # a picture path that climbs out
            vibes.import_look(look({"vibe.json": json.dumps({**v, "photo": "../../.bashrc"})}), self.folder, self.photos)


class EditorTests(unittest.TestCase):
    def test_lights_are_found_on_bright_points_not_bright_areas(self):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        import hub_vibe_editor as E
        img = QImage(1600, 900, QImage.Format_RGB32)
        img.fill(QColor("#101018"))
        p = QPainter(img)
        p.fillRect(0, 0, 1600, 200, QColor("#C8C8D0"))  # a pale sky: bright, but not a light
        p.setBrush(QColor("#FFFFFF"))
        for x, y in ((400, 500), (1200, 650)):
            p.drawEllipse(QPointF(x, y), 12, 12)
        p.end()
        found = E.find_lights(img)
        self.assertEqual(sorted(round(f[0], 1) for f in found), [0.2, 0.8])  # the two lamps, not the sky
        a, b = E.photo_colours(img)
        self.assertRegex(a, r"^#[0-9A-F]{6}$")


if __name__ == "__main__":
    unittest.main()
