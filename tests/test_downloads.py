"""DecKoOS Downloads: resumes after a dropped connection, starts over when the file changed, names files from the
server, gives up only when the server says no, and pause/cancel/remove do what they say. A local server only."""
import http.server
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/downloads"))
os.environ["DECKOS_DOWNLOADS_NO_SERVICE"] = "1"
import downloads as D  # noqa: E402

BODY = bytes(range(251)) * 16000  # about 4 MB; 251 so every part's bytes differ from its neighbours'


class Server(http.server.BaseHTTPRequestHandler):
    drop_once = set()  # paths that cut the connection halfway the first time
    etag = '"v1"'
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Server.seen.append((self.path, self.headers.get("Range"), self.headers.get("If-Range")))
        if self.path == "/missing":
            return self.send_error(404)
        body, start, end = BODY, 0, len(BODY)
        rng = self.headers.get("Range")
        if self.path == "/expired" and rng and rng != "bytes=0-":
            return self.send_error(416)  # what some servers say once a link has expired
        if rng and self.path != "/norange" and self.headers.get("If-Range", Server.etag) == Server.etag:
            a, _, b = rng.split("=")[1].partition("-")
            start, end = int(a), (int(b) + 1 if b else len(body))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end - 1}/{len(body)}")
        else:
            self.send_response(200)
        if self.path == "/named":
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''Big%20Game.iso")
        self.send_header("ETag", Server.etag)
        self.send_header("Content-Length", str(end - start))
        self.end_headers()
        if self.path in Server.drop_once and end - start > 300_000:
            Server.drop_once.discard(self.path)
            self.wfile.write(body[start:start + 100_000])
            try:
                self.wfile.flush()
                self.connection.shutdown(2)
            except OSError:
                pass
            return
        try:
            self.wfile.write(body[start:end])
        except (BrokenPipeError, ConnectionResetError):
            pass  # a part handed half of its rest to another closes early


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        D.STATE = Path(self.tmp.name) / "state"
        D.QUEUE, D.LOCK = D.STATE / "queue.json", D.STATE / "queue.lock"
        self.dir = Path(self.tmp.name) / "dl"
        Server.seen.clear()
        Server.etag = '"v1"'
        self._wait = D.Worker.retry

        def quick(w, why):  # no 3 s waits in tests
            self._wait(w, why)
            w.wait = 0
        D.Worker.retry = quick

    def tearDown(self):
        D.Worker.retry = self._wait
        self.tmp.cleanup()

    def run_queue(self):
        t = threading.Thread(target=D.serve, daemon=True)
        t.start()
        t.join(30)
        self.assertFalse(t.is_alive(), "the queue never finished")
        return {j["id"]: j for j in D.load()}

    def test_resumes_after_a_dropped_connection(self):
        Server.drop_once.add("/file.bin")
        j = D.add(self.base + "/file.bin", self.dir)
        done = self.run_queue()[j["id"]]
        self.assertEqual(done["state"], "done")
        self.assertEqual((self.dir / "file.bin").read_bytes(), BODY)
        self.assertFalse((self.dir / "file.bin.part").exists())
        self.assertTrue(any(r and r.startswith("bytes=") for _, r, _ in Server.seen), "it didn't resume")

    def test_a_changed_file_starts_over(self):
        j = D.add(self.base + "/file.bin", self.dir)
        (self.dir / "file.bin.part").write_bytes(b"\0" * 1000)  # half of an old version
        with D.locked():
            jobs = D.load()
            jobs[0]["validator"] = '"v0"'
            D.save(jobs)
        self.run_queue()
        self.assertEqual((self.dir / "file.bin").read_bytes(), BODY)
        self.assertEqual(Server.seen[0][2], '"v0"')

    def test_named_by_the_server_and_never_over_a_file(self):
        self.dir.mkdir()
        (self.dir / "Big Game.iso").write_text("mine")
        j = D.add(self.base + "/named", self.dir)
        done = self.run_queue()[j["id"]]
        self.assertEqual(done["name"], "Big Game (2).iso")
        self.assertEqual((self.dir / "Big Game.iso").read_text(), "mine")

    def test_server_without_ranges_starts_over(self):
        Server.drop_once.add("/norange")
        j = D.add(self.base + "/norange", self.dir)
        self.run_queue()
        self.assertEqual((self.dir / "norange").read_bytes(), BODY)

    def test_a_big_file_comes_in_parts(self):
        D.SPLIT_MIN, D.STEAL_MIN = 1 << 20, 64 << 10
        Server.drop_once.add("/file.bin")  # one part's connection drops: it carries on alone
        try:
            j = D.add(self.base + "/file.bin", self.dir)
            done = self.run_queue()[j["id"]]
        finally:
            D.SPLIT_MIN, D.STEAL_MIN = 16 << 20, 2 << 20
        self.assertEqual(done["state"], "done")
        self.assertEqual((self.dir / "file.bin").read_bytes(), BODY)
        ranged = [r for _, r, _ in Server.seen if r and r != "bytes=0-"]
        self.assertGreaterEqual(len(ranged), D.CONNECTIONS)

    def test_a_short_file_is_never_done(self):
        # The server says 416 to a resume (an expired link): what's there is only part of it, so start again
        j = D.add(self.base + "/expired", self.dir, start=False)
        self.dir.mkdir(exist_ok=True)
        (self.dir / "expired.part").write_bytes(BODY[:200_000])
        with D.locked():
            jobs = D.load()
            jobs[0]["size"] = len(BODY)
            D.save(jobs)
        done = self.run_queue()[j["id"]]
        self.assertEqual(done["state"], "done")
        self.assertEqual((self.dir / "expired").read_bytes(), BODY)

    def test_one_connection_on_windows_drives(self):
        mounts = Path(self.tmp.name) / "mounts"
        mounts.write_text("/dev/nvme0n1p2 / btrfs rw 0 0\n/dev/sda1 /mnt/SSD ntfs3 rw 0 0\n"
                          "/dev/sdc1 /mnt/My\\040Drive exfat rw 0 0\n")
        old, D.MOUNTS = D.MOUNTS, str(mounts)
        try:
            self.assertTrue(D.sparse_ok("/home"))
            self.assertFalse(D.sparse_ok("/mnt/SSD/Games"))
            self.assertFalse(D.sparse_ok("/mnt/My Drive"))
            self.assertTrue(D.sparse_ok("/mnt/SSDx"))  # not under /mnt/SSD
        finally:
            D.MOUNTS = old

    def test_cancel_then_again_starts(self):
        # Cancelling a running download and adding the same link straight away starts a new one at once
        D.SPLIT_MIN, D.STEAL_MIN = 1 << 20, 64 << 10
        t = threading.Thread(target=D.serve, daemon=True)
        try:
            a = D.add(self.base + "/file.bin", self.dir)
            t.start()
            for _ in range(100):
                if D.load()[0]["state"] == "downloading":
                    break
                time.sleep(0.02)
            D.change(a["id"], "cancel")
            b = D.add(self.base + "/file.bin", self.dir)
            self.assertNotEqual(a["id"], b["id"])
            t.join(30)
        finally:
            D.SPLIT_MIN, D.STEAL_MIN = 16 << 20, 2 << 20
        jobs = {j["id"]: j for j in D.load()}
        self.assertEqual(jobs[b["id"]]["state"], "done")
        self.assertEqual((self.dir / jobs[b["id"]]["name"]).read_bytes(), BODY)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), [jobs[b["id"]]["name"]])  # no stray .part

    def test_gives_up_on_404(self):
        j = D.add(self.base + "/missing", self.dir)
        done = self.run_queue()[j["id"]]
        self.assertEqual(done["state"], "failed")
        self.assertIn("404", done["error"])

    def test_pause_cancel_remove(self):
        j = D.add(self.base + "/file.bin", self.dir, start=False)
        D.change(j["id"], "pause")
        self.assertEqual(D.load()[0]["state"], "paused")
        self.run_queue()  # a paused download isn't touched
        self.assertFalse((self.dir / "file.bin").exists())
        (self.dir / "file.bin.part").write_bytes(b"x")
        D.change(j["id"], "cancel")
        self.assertFalse((self.dir / "file.bin.part").exists())
        D.change(j["id"], "remove")
        self.assertEqual(D.load(), [])

    def test_the_same_link_again_resumes(self):
        a = D.add(self.base + "/file.bin", self.dir, start=False)
        D.change(a["id"], "pause")
        b = D.add(self.base + "/file.bin", self.dir, start=False)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(D.load()), 1)
        self.assertEqual(D.load()[0]["state"], "queued")

    def test_words(self):
        self.assertEqual(D.name_from_header('attachment; filename="a b.zip"'), "a b.zip")
        self.assertEqual(D.name_from_url("https://x.org/f/My%20File.tar.gz?x=1"), "My File.tar.gz")
        self.assertEqual(D.clean_name("../../etc/passwd"), "etcpasswd")
        j = {"state": "downloading", "got": 500e6, "size": 2e9, "speed": 25e6}
        self.assertEqual(D.describe(j), "500 MB of 2.0 GB · 25.0 MB/s · 1 min left")
        with self.assertRaises(ValueError):
            D.add("file:///etc/passwd", self.dir)


if __name__ == "__main__":
    unittest.main()
