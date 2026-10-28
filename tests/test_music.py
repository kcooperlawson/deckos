"""DecKoOS Music: the library (tags from names, albums, search, the scan cache), Spotify's MPRIS lines, and the
sound analysis on made-up signals (beats on time, none in silence). No sound card or Spotify needed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/music"))
import analysis  # noqa: E402
import library  # noqa: E402


class LibraryTests(unittest.TestCase):
    def test_names_stand_in_for_missing_tags(self):
        root = Path("/m")
        self.assertEqual(library.guess(root / "Daft Punk/Discovery/03 - Digital Love.flac", root),
                         {"title": "Digital Love", "artist": "Daft Punk", "album": "Discovery", "track": 3})
        self.assertEqual(library.guess(root / "Mix/1-07 Robyn - Dancing On My Own.mp3", root),
                         {"title": "Dancing On My Own", "artist": "Robyn", "album": "Mix", "track": 7})

    def test_scan_reads_once_and_groups_albums(self):
        with tempfile.TemporaryDirectory() as d:
            root, cache = Path(d) / "Music", Path(d) / "cache"
            for i, name in enumerate(["01 One.flac", "02 Two.flac"]):
                f = root / "Band/First" / name
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(b"x" * (i + 1))
            (root / "Band/First/cover.jpg").write_bytes(b"jpg")
            (root / "Band/First/notes.txt").write_text("not music")
            reads = []
            fake = lambda p: reads.append(p) or {"year": 2001}  # noqa: E731
            tracks = library.scan([root], cache, read=fake)
            self.assertEqual([t["title"] for t in tracks], ["One", "Two"])
            self.assertEqual(len(reads), 2)
            library.scan([root], cache, read=fake)
            self.assertEqual(len(reads), 2)  # nothing changed: nothing read again
            al = library.albums(tracks)
            self.assertEqual((al[0]["title"], al[0]["artist"], al[0]["year"]), ("First", "Band", 2001))
            self.assertTrue(library.cover_for(tracks[0], cache).endswith("cover.jpg"))
            self.assertEqual(json.loads((cache / "library.json").read_text())["tracks"][0]["title"], "One")

    def test_search_needs_every_word(self):
        tracks = [{"title": "Digital Love", "artist": "Daft Punk", "album": "Discovery", "path": "/a"},
                  {"title": "Love Story", "artist": "Taylor Swift", "album": "Fearless", "path": "/b"}]
        self.assertEqual([t["path"] for t in library.search(tracks, "love daft")], ["/a"])
        self.assertEqual(len(library.search(tracks, "love")), 2)
        self.assertEqual(library.search(tracks, "  "), [])

    def test_times(self):
        self.assertEqual((library.fmt_time(65), library.fmt_time(3725)), ("1:05", "1:02:05"))


class SpotifyLineTests(unittest.TestCase):
    def test_playerctl_lines(self):
        sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/hub"))
        import sources
        line = sources.SEP.join(["Playing", "Molly", "Lil Dicky", "Professional Rapper",
                                 "https://open.spotify.com/image/abc", "244000000", "165000000"])
        now = sources.parse_playerctl(line)
        self.assertEqual((now.title, now.artist, now.playing, now.length, now.position),
                         ("Molly", "Lil Dicky", True, 244.0, 165.0))
        self.assertEqual(now.art, "https://i.scdn.co/image/abc")  # the address that still serves pictures
        self.assertIsNone(sources.parse_playerctl("half|a|line"))


class AnalysisTests(unittest.TestCase):
    def test_beats_land_on_the_kick(self):
        f = analysis.FakeAnalyzer()
        beats = [i * analysis.HOP / analysis.RATE for i in range(860) if f.step()["beat"]]
        self.assertGreaterEqual(len(beats), 17)  # a kick every half second for 10 s
        self.assertTrue(all(abs(b * 2 - round(b * 2)) < 0.05 for b in beats))

    def test_silence_is_calm(self):
        q = analysis.Features()
        for _ in range(200):
            s = q.push(np.zeros(analysis.HOP, np.float32))
        self.assertTrue(s["silent"])
        self.assertFalse(s["beat"])
        self.assertLess(s["intensity"], 0.05)

    def test_bars_cover_hearing(self):
        edges = analysis.band_edges()
        self.assertEqual(len(edges), analysis.BARS + 1)
        self.assertTrue(all(b > a for a, b in zip(edges, edges[1:])))


if __name__ == "__main__":
    unittest.main()
