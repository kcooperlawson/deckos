"""DecKoOS Music: the library (tags from names, albums, search, the scan cache), Spotify's MPRIS lines, the sound
analysis on made-up signals (beats on time, none in silence), Vibe mode's world across monitors and its compiled
shader. No sound card, Spotify or monitors needed."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/music"))
import analysis  # noqa: E402
import looks  # noqa: E402
import lyrics  # noqa: E402
import library  # noqa: E402
import world  # noqa: E402


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


class WorldTests(unittest.TestCase):
    def test_two_screens_one_world_cover_on_the_main_one(self):
        w = world.layout([(1920, 0, 1920, 1080), (0, 0, 1920, 1080)], primary=0)
        self.assertEqual((w["width"], w["height"]), (3840, 1080))
        self.assertEqual(w["home"], 0)
        self.assertEqual(w["cover"], (2880, 432))
        self.assertEqual(w["screens"][1]["x"], 0)

    def test_three_screens_cover_in_the_middle(self):
        w = world.layout([(-2560, 0, 2560, 1440), (0, 0, 2560, 1440), (2560, 0, 2560, 1440)], primary=2)
        self.assertEqual(w["width"], 7680)
        self.assertEqual(w["home"], 1)  # the middle one, whichever is main
        self.assertEqual([s["x"] for s in w["screens"]], [0, 2560, 5120])

    def test_different_sizes_and_heights(self):
        w = world.layout([(0, 0, 3840, 2160), (3840, 540, 1920, 1080)], primary=1)
        self.assertEqual((w["width"], w["height"]), (5760, 2160))
        self.assertEqual(w["home"], 1)  # of two, the main one
        self.assertEqual(w["screens"][1]["y"], 540)

    def test_main_monitor_from_kscreen(self):
        out = ("\x1b[01;32mOutput: \x1b[0;0m1 DP-3 5e1e\n\tenabled\n\tpriority 1\n"
               "\x1b[01;32mOutput: \x1b[0;0m2 DP-2 f1af\n\tpriority 2\n")
        self.assertEqual(world.main_output(out), "DP-3")
        self.assertEqual(world.main_output("nothing useful"), "")

    def test_no_screens_still_a_stage(self):
        self.assertEqual(world.layout([])["width"], 1920)

    def test_real_sizes_and_the_gap_on_the_desk(self):
        # A 27" (597 mm) left of the main 32" (698 mm), both 1920 px wide, 6 inches (152 mm) apart
        w = world.layout([(1920, 0, 1920, 1080), (0, 0, 1920, 1080)], primary=0,
                         physical=[(698, 392), (597, 336)], gap_mm=152)
        main, left = w["screens"]
        per_mm = 1920 / 698
        self.assertEqual((main["width"], main["scale"]), (1920, 1.0))  # the cover's screen stays in pixels
        self.assertAlmostEqual(left["width"], 597 * per_mm, delta=0.1)  # the smaller screen is narrower in the world
        self.assertAlmostEqual(left["scale"], 1920 / (597 * per_mm), places=3)
        self.assertEqual((left["pw"], left["ph"]), (1920, 1080))  # its window keeps its own pixels
        self.assertAlmostEqual(main["x"], left["width"] + 152 * per_mm, delta=0.2)  # the gap is in between
        self.assertAlmostEqual(left["y"], (1080 - left["width"] * 1080 / 1920) / 2, delta=0.2)  # centred on each other
        self.assertEqual(main["height"], 1080)  # heights from the pixels' shape: pixels stay square
        self.assertEqual(w["home"], 0)
        self.assertAlmostEqual(w["cover"][0], main["x"] + 960, delta=0.2)

    def test_no_real_sizes_or_stacked_screens_keep_the_desktops_layout(self):
        flat = world.layout([(0, 0, 1920, 1080), (1920, 0, 1920, 1080)], physical=[(0, 0), (598, 336)], gap_mm=150)
        self.assertEqual(flat["width"], 3840)
        nonsense = world.layout([(0, 0, 1920, 1080), (1920, 0, 1920, 1080)], physical=[(160, 90), (100, 100)])
        self.assertEqual(nonsense["screens"][1]["scale"], 1.0)  # a square 'monitor' for a 16:9 one: not trusted
        stacked = world.layout([(0, 0, 1920, 1080), (0, 1080, 1920, 1080)], physical=[(598, 336)] * 2, gap_mm=150)
        self.assertEqual(stacked["height"], 2160)
        self.assertEqual(stacked["screens"][1]["scale"], 1.0)

    def test_lyrics_go_next_to_the_cover(self):
        two = world.layout([(1920, 0, 1920, 1080), (0, 0, 1920, 1080)], primary=0)
        self.assertEqual(world.lyrics_screen(two), 1)
        self.assertIsNone(world.lyrics_screen(world.layout([(0, 0, 1920, 1080)])))
        three = world.layout([(0, 0, 1920, 1080), (1920, 0, 1920, 1080), (3840, 0, 1920, 1080)], primary=1)
        self.assertEqual(world.lyrics_screen(three), 2)  # between two: the right one


class LyricsTests(unittest.TestCase):
    LRC = ("[ar:Someone]\n[offset:+500]\n[00:12.50]First line\n[00:15.00][01:15.00]Chorus  line\n"
           "[00:20.00]<00:20.00>Word <00:20.40>by <00:20.80>word\nno time here\n[00:25.00]\n")

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.dir = Path(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_parses_times_repeats_offset_and_words(self):
        lines = lyrics.parse_lrc(self.LRC)
        self.assertEqual([round(l["t"], 2) for l in lines], [12.0, 14.5, 19.5, 24.5, 74.5])  # offset: half a second earlier
        self.assertEqual(lines[1]["text"], "Chorus line")
        self.assertEqual(lines[4]["text"], "Chorus line")  # two times on one line: sung twice
        self.assertEqual(lines[2]["text"], "Word by word")
        self.assertEqual([w for _t, w in lines[2]["words"]], ["Word", "by", "word"])
        self.assertEqual(lines[3]["text"], "")  # a gap in the singing

    def test_the_line_at_a_moment(self):
        lines = lyrics.parse_lrc(self.LRC)
        self.assertEqual(lyrics.at(lines, 3.0), (-1, 0.0))
        i, through = lyrics.at(lines, 13.25)
        self.assertEqual(i, 0)
        self.assertAlmostEqual(through, 0.5)
        self.assertEqual(lyrics.at(lines, 999)[0], 4)
        self.assertEqual(lyrics.at([], 10), (-1, 0.0))

    def test_cache_keeps_answers_and_forgets_misses(self):
        lyrics.store("A", "Song", 200, {"synced": "[00:01.00]hi", "plain": "hi"}, self.dir)
        self.assertEqual(lyrics.cached("a", "song", 200.4, self.dir)["synced"], "[00:01.00]hi")
        lyrics.store("A", "Nothing", 100, {"synced": "", "plain": ""}, self.dir)
        self.assertIsNotNone(lyrics.cached("A", "Nothing", 100, self.dir))  # a recent miss isn't asked again
        later = lyrics.time.time() + (lyrics.MISS_DAYS + 1) * 86400
        self.assertIsNone(lyrics.cached("A", "Nothing", 100, self.dir, now=later))  # an old one is

    def test_fetch_falls_back_to_search_and_remembers(self):
        calls = []
        def fake(path, params, timeout):
            calls.append(path)
            if path == "get":
                raise lyrics.urllib.error.HTTPError("u", 404, "no", {}, None)
            return [{"duration": 300, "syncedLyrics": "[00:01.00]far"},
                    {"duration": 201, "syncedLyrics": "[00:01.00]near", "plainLyrics": "near"}]
        real = lyrics._get
        lyrics._get = fake
        try:
            got = lyrics.fetch("A", "Song", duration=200, folder=self.dir)
            again = lyrics.fetch("A", "Song", duration=200, folder=self.dir)
        finally:
            lyrics._get = real
        self.assertEqual(got["synced"], "[00:01.00]near")  # the closest length wins
        self.assertEqual(again, got)
        self.assertEqual(calls, ["get", "search"])  # the second time came from the cache

    def test_no_connection_is_not_remembered_as_a_miss(self):
        real = lyrics._get
        lyrics._get = lambda *a: (_ for _ in ()).throw(OSError("offline"))
        try:
            self.assertEqual(lyrics.fetch("A", "B", folder=self.dir), {"synced": "", "plain": ""})
        finally:
            lyrics._get = real
        self.assertIsNone(lyrics.cached("A", "B", 0, self.dir))

    def test_an_lrc_beside_the_song(self):
        (self.dir / "song.lrc").write_text("[00:01.00]mine")
        self.assertEqual(lyrics.local_lrc(f"file://{self.dir}/song.flac"), "[00:01.00]mine")
        self.assertEqual(lyrics.local_lrc(self.dir / "other.mp3"), "")


class ShaderTests(unittest.TestCase):
    QML = ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/music/qml"

    def test_compiled_shaders_are_current(self):
        qsb = shutil.which("qsb") or next((p for p in ("/usr/lib/qt6/bin/qsb", "/usr/lib/qt6/libexec/qsb")
                                           if Path(p).exists()), None)
        if not qsb:
            self.skipTest("qsb (qt6-shadertools) isn't installed")
        frags = sorted(self.QML.glob("*.frag"))
        self.assertGreaterEqual(len(frags), 5)
        with tempfile.TemporaryDirectory() as d:
            for frag in frags:
                out = Path(d) / (frag.name + ".qsb")
                subprocess.run([qsb, "--qt6", "-o", str(out), str(frag)], check=True)
                self.assertEqual(out.read_bytes(), (self.QML / out.name).read_bytes(),
                                 f"run: qsb --qt6 -o {out.name} {frag.name} (in usr/lib/deckos/music/qml)")


class LooksTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.dir = Path(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_choices_round_trip_and_ignore_junk(self):
        conf = self.dir / "music.conf"
        self.assertEqual(looks.load(conf), looks.DEFAULT)
        looks.save({"style": "spectrum", "colours": "cover"}, conf)
        self.assertEqual(looks.load(conf), {**looks.DEFAULT, "style": "spectrum", "colours": "cover"})
        looks.save({**looks.DEFAULT, "style": "kaleido", "lyrics": "off", "gap": "152"}, conf)
        self.assertEqual(looks.load(conf), {"style": "kaleido", "colours": "vibe", "lyrics": "off", "gap": "152"})
        conf.write_text("style=milkdrop\ncolours=rainbow\nlyrics=maybe\ngap=-3\ngap=99999\n")
        self.assertEqual(looks.load(conf), looks.DEFAULT)

    def test_style_follows_the_vibe_unless_you_pick_one(self):
        neon = looks.vibes.all_vibes(self.dir)["neon"]
        self.assertEqual(looks.resolve(looks.DEFAULT, neon), ("spectrum", "vibe"))
        self.assertEqual(looks.resolve({"style": "trails", "colours": "vibe"}, neon), ("trails", "vibe"))
        self.assertEqual(looks.resolve(looks.DEFAULT, None), ("glow", "cover"))  # no Vibe: calm, the cover's

    def test_every_built_in_vibe_has_a_stage(self):
        for key, vibe in looks.vibes.VIBES.items():
            self.assertIn(vibe["stage"], looks.STYLES, key)

    def test_current_vibe(self):
        f = self.dir / "vibe"
        self.assertIsNone(looks.current_vibe(f, self.dir))
        f.write_text("cozy\n")
        self.assertEqual(looks.current_vibe(f, self.dir)["stage"], "glow")
        f.write_text("gone\n")
        self.assertIsNone(looks.current_vibe(f, self.dir))

    def test_vibe_colours_keep_a_dark_ground(self):
        base, a, b = looks.vibe_colours({"colorA": "#FF4FD8", "colorB": "#3DE0FF"})
        self.assertEqual((a, b), ("#FF4FD8", "#3DE0FF"))
        self.assertLess(max(int(base[i:i + 2], 16) for i in (1, 3, 5)), 40)

if __name__ == "__main__":
    unittest.main()
