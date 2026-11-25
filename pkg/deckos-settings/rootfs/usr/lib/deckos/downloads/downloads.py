"""DecKoOS Downloads: big files that don't give up. A queue of downloads that resume where they stopped (HTTP Range,
checked against the file's ETag/Last-Modified so a changed file starts over instead of being spliced), retry with a
growing wait while the connection is down, and carry on after a logout or a restart.

One file is the truth: ~/.local/state/deckos/downloads/queue.json (every writer takes queue.lock). The window and
`deckos download` change it; `serve` (the user unit deckos-downloads.service) does the downloading and writes
progress into it twice a second, and exits once nothing is left to do, so nothing runs while idle. A file arrives as
NAME.part in its folder (the Desktop shelf shows it coming) and becomes NAME when it's whole. No Qt;
tests/test_downloads.py.

    downloads.py add URL [FOLDER] | pause ID | resume ID | cancel ID | remove ID | clear | list | serve
"""
import fcntl
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

STATE = Path(os.environ.get("DECKOS_DOWNLOADS_STATE") or Path.home() / ".local/state/deckos/downloads")
QUEUE, LOCK = STATE / "queue.json", STATE / "queue.lock"
AT_ONCE = 3  # downloads running together; the rest wait their turn
CONNECTIONS = 8  # per big download: servers often cap each connection, not the whole
SPLIT_MIN = 16 << 20  # smaller than this isn't worth splitting
STEAL_MIN = 2 << 20  # a finished connection takes half of another's rest while that's at least twice this
CHUNK = 1 << 20
TICK = 0.5  # s between progress writes
AGENT = "Mozilla/5.0 (X11; Linux x86_64) DecKoOS-Downloads/1"  # some servers turn away anything that looks like a script
ACTIVE = ("queued", "downloading", "waiting")  # waiting: the connection dropped, trying again soon
FINISHED = ("done", "failed", "cancelled")
GIVE_UP = {400, 401, 403, 404, 405, 410, 451}  # the server said no: retrying won't change it


def downloads_dir():
    try:
        d = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        d = ""
    return Path(d if d and d != str(Path.home()) else Path.home() / "Downloads")


CONF = Path.home() / ".config/deckos/downloads.conf"  # folder=PATH: where the window saves, when it isn't Downloads


def saved_folder():
    """The folder picked in the window last time, if it's still there (a drive that isn't plugged in: Downloads)."""
    try:
        for line in CONF.read_text().splitlines():
            if line.startswith("folder="):
                p = Path(line[7:].strip())
                return p if p.is_dir() else None
    except OSError:
        pass
    return None


def save_folder(folder):
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text(f"folder={folder}\n" if folder else "")


@contextmanager
def locked():
    STATE.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        yield


def load():
    try:
        return json.loads(QUEUE.read_text()).get("jobs", [])
    except (OSError, ValueError):
        return []


def save(jobs):
    tmp = QUEUE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"jobs": jobs}, indent=1))
    os.replace(tmp, QUEUE)  # the window never reads half a file


def clean_name(name):
    name = "".join(c for c in name if c not in '/\\\0\n\r\t').strip().strip(".")
    return name[:200] or "download"


def name_from_url(url):
    return clean_name(urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]))


def name_from_header(cd):
    """A file name from Content-Disposition (filename*=UTF-8''… wins over filename=…), else ''."""
    if not cd:
        return ""
    m = re.search(r"filename\*\s*=\s*([\w-]+)''([^;]+)", cd, re.I)
    if m:
        return clean_name(urllib.parse.unquote(m.group(2).strip().strip('"'), encoding=m.group(1) or "utf-8"))
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.I) or re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    return clean_name(m.group(1).strip()) if m else ""


def free_name(folder, name, taken=()):
    """NAME, or "NAME (2).ext" when that's already in the folder (or another download is about to be)."""
    stem, dot, ext = name.rpartition(".") if "." in name[1:] else (name, "", "")
    n = 1
    while True:
        cand = name if n == 1 else f"{stem} ({n}){dot}{ext}"
        if not (folder / cand).exists() and not (folder / (cand + ".part")).exists() and cand not in taken:
            return cand
        n += 1


def valid_url(url):
    return bool(re.fullmatch(r"(https?|ftp)://[^\s/]+\S*", url or ""))


def add(url, folder=None, start=True):
    """Queues URL; returns the job. The same link already in the queue (not finished) is resumed instead."""
    url = url.strip()
    if not valid_url(url):
        raise ValueError("that isn't a web link (http, https or ftp)")
    folder = Path(folder or downloads_dir()).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    with locked():
        jobs = load()
        for j in jobs:
            if j["url"] == url and j["state"] not in ("done", "cancelled"):
                j.update(state="queued", error="")
                save(jobs)
                break
        else:
            taken = {j["name"] for j in jobs if j["folder"] == str(folder) and j["state"] in ACTIVE + ("paused",)}
            j = {"id": uuid.uuid4().hex[:8], "url": url, "folder": str(folder),
                 "name": free_name(folder, name_from_url(url) or "download", taken), "named": False,
                 "state": "queued", "got": 0, "size": 0, "speed": 0, "added": time.time(), "finished": 0,
                 "error": "", "tries": 0, "validator": ""}
            jobs.append(j)
            save(jobs)
    if start:
        wake()
    return j


def change(job_id, how):
    """pause | resume | cancel | remove. Cancel deletes the unfinished .part; remove forgets a finished one (the file
    stays)."""
    with locked():
        jobs = load()
        j = next((j for j in jobs if j["id"] == job_id), None)
        if j is None:
            raise ValueError(f"no download {job_id}")
        if how == "pause" and j["state"] in ACTIVE:
            j.update(state="paused", speed=0)
        elif how == "resume" and j["state"] in ("paused", "failed", "waiting"):
            j.update(state="queued", error="", tries=0)
        elif how == "cancel" and j["state"] not in ("done", "cancelled"):
            running = j["state"] == "downloading"
            j.update(state="cancelled", speed=0, finished=time.time(), segs=[])
            if not running:  # a running one's .part goes once its worker has stopped (serve), or it'd write on
                try:
                    (Path(j["folder"]) / (j["name"] + ".part")).unlink()
                except OSError:
                    pass
        elif how == "remove" and j["state"] in FINISHED:
            jobs.remove(j)
        save(jobs)
    if how == "resume":
        wake()


def clear():
    """Forgets every finished download (their files stay where they are)."""
    with locked():
        save([j for j in load() if j["state"] not in FINISHED])


def wake():
    """Starts the service if it isn't running (it stops itself when the queue is empty)."""
    if os.environ.get("DECKOS_DOWNLOADS_NO_SERVICE"):
        return
    try:
        subprocess.Popen(["systemctl", "--user", "start", "--no-block", "deckos-downloads.service"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def size_text(n):
    for unit, step in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= step:
            v = n / step
            return f"{v:.1f} {unit}" if v < 100 else f"{v:.0f} {unit}"
    return f"{int(n)} bytes"


def time_text(s):
    s = int(s)
    if s < 60:
        return f"{max(1, s)} s"
    if s < 3600:
        return f"{s // 60} min"
    return f"{s // 3600} h {s % 3600 // 60} min"


def describe(j):
    """The line under a download's name, in plain words."""
    st, got, size = j["state"], j.get("got", 0), j.get("size", 0)
    amount = f"{size_text(got)} of {size_text(size)}" if size else size_text(got)
    if st == "downloading":
        if j.get("speed", 0) > 0 and size:
            return f"{amount} · {size_text(j['speed'])}/s · {time_text((size - got) / j['speed'])} left"
        return f"{amount} · starting…" if not got else amount
    return {"queued": f"Waiting its turn · {amount}" if got else "Waiting its turn",
            "waiting": f"{j.get('error') or 'Connection lost'} · {amount}",
            "paused": f"Paused · {amount}",
            "done": size_text(size or got),
            "failed": j.get("error") or "Stopped",
            "cancelled": "Cancelled"}.get(st, st)


# ------------------------------------------------------------------ the downloader

class Stop(Exception):
    pass


class Worker(threading.Thread):
    """Downloads one job into NAME.part, resuming from what's there. A big file from a server that takes ranges is
    split across CONNECTIONS connections (servers often cap each one), each writing its own part of the file; one that
    finishes takes half of the slowest one's rest, so the end doesn't crawl on a single connection. Where each part
    has got to is kept in job["segs"] ([start, end, at]), so a resume carries on every part. Progress goes into
    `self.job` (the server writes it out); `self.stop` ends it early (pause/cancel)."""

    def __init__(self, job):
        super().__init__(daemon=True)
        self.job, self.stop = dict(job), threading.Event()
        self.job["segs"] = [list(x) for x in job.get("segs") or []]
        self.outcome, self.wait = None, 0  # outcome: done | retry | failed | stopped

    def part(self):
        return Path(self.job["folder"]) / (self.job["name"] + ".part")

    def run(self):
        try:
            self.fetch()
            self.outcome = "done"
        except Stop:
            self.outcome = "stopped"
        except urllib.error.HTTPError as e:
            e.close()
            if e.code in GIVE_UP:
                self.job["error"] = f"The server said no ({e.code} {e.reason})"
                self.outcome = "failed"
            else:
                self.retry(f"The server is busy ({e.code})")
        except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as e:
            reason = getattr(e, "reason", e)
            if isinstance(e, OSError) and getattr(e, "errno", None) == 28:  # ENOSPC
                self.job["error"] = "The drive is full"
                self.outcome = "failed"
            else:
                self.retry("Connection lost" if "timed out" not in str(reason) else "The connection stalled")

    def retry(self, why):
        self.job["tries"] = self.job.get("tries", 0) + 1
        self.wait = min(60, 3 * 2 ** min(self.job["tries"] - 1, 5))
        self.job["error"] = f"{why}, trying again in {self.wait} s"
        self.outcome = "retry"

    def open(self, start=None, end=None, check=True):
        headers = {"User-Agent": AGENT, "Accept-Encoding": "identity"}
        if start is not None:
            headers["Range"] = f"bytes={start}-" + ("" if end is None else str(end - 1))
            if check and self.job.get("validator"):
                headers["If-Range"] = self.job["validator"]  # changed on the server: it sends the whole new file
        return urllib.request.urlopen(urllib.request.Request(self.job["url"], headers=headers), timeout=30)

    def restart(self):
        """From nothing: the file changed on the server, or what's here can't be trusted."""
        self.job.update(segs=[], got=0, validator="")
        try:
            self.part().unlink()
        except OSError:
            pass

    def fetch(self):
        j = self.job
        if j["segs"] and self.part().exists() and self.part().stat().st_size == j.get("size"):
            return self.split()
        if j["segs"]:  # the parts' file is gone or the wrong size: they can't be trusted
            self.restart()
        part = self.part()
        have = part.stat().st_size if part.exists() else 0
        try:
            resp = self.open(have if have else 0, check=bool(have))
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:
                # Nothing after what's here. That's only "done" if what's here is the whole known size; servers also
                # say 416 when a link expired or the file shrank: then start over rather than keep a short file
                e.close()
                if j.get("size") and have == j["size"]:
                    j["got"] = have
                    return
                self.restart()
                raise urllib.error.URLError("the server didn't take the resume")
            raise
        with resp:
            if not j.get("named"):
                better = name_from_header(resp.headers.get("Content-Disposition", ""))
                if better and better != j["name"] and not have:
                    j["name"] = free_name(Path(j["folder"]), better)
                    part = self.part()
                j["named"] = True
            j["validator"] = resp.headers.get("ETag") or resp.headers.get("Last-Modified") or ""
            length = int(resp.headers.get("Content-Length") or 0)
            total = content_range_total(resp.headers.get("Content-Range", ""))
            if resp.status != 206:
                have = 0  # the server can't resume, or the file changed: from the start
            j["size"] = total or (have + length if length else 0)
            j["got"], j["tries"], j["error"] = have, 0, ""
            if resp.status == 206 and total and total - have >= SPLIT_MIN and not os.environ.get("DECKOS_DOWNLOADS_ONE"):
                resp.close()  # a big one from a server that takes ranges: share it out
                with open(part, "ab") as f:
                    f.truncate(total)  # sparse: the parts fill it in
                j["segs"] = plan_segs(have, total)
                if have:
                    j["segs"].insert(0, [0, have, have])
                return self.split()
            with open(part, "ab" if resp.status == 206 else "wb") as f:
                while True:
                    if self.stop.is_set():
                        raise Stop
                    block = resp.read(CHUNK)
                    if not block:
                        break
                    f.write(block)
                    j["got"] += len(block)
        if j["size"] and j["got"] != j["size"]:
            raise urllib.error.URLError("the connection closed early")

    def split(self):
        j, segs = self.job, self.job["segs"]
        errors, lock = [], threading.Lock()
        fd = os.open(self.part(), os.O_RDWR)

        def count():
            j["got"] = sum(min(at, end) - start for start, end, at in segs)

        def one(seg):
            while not self.stop.is_set() and not errors:
                if seg[2] >= seg[1]:
                    with lock:  # done: help the part with the most left
                        rest = max(segs, key=lambda x: x[1] - x[2])
                        if rest[1] - rest[2] < 2 * STEAL_MIN:
                            return
                        cut = rest[2] + (rest[1] - rest[2]) // 2
                        seg = [cut, rest[1], cut]
                        rest[1] = cut
                        segs.append(seg)
                try:
                    with self.open(seg[2], seg[1]) as resp:
                        if resp.status != 206:  # changed on the server mid-way: none of it can be kept
                            raise Changed
                        while seg[2] < seg[1] and not self.stop.is_set() and not errors:
                            block = resp.read(min(CHUNK, seg[1] - seg[2]))
                            if not block:
                                raise urllib.error.URLError("the connection closed early")
                            os.pwrite(fd, block, seg[2])
                            seg[2] += len(block)
                            count()
                except Exception as e:  # noqa: BLE001 the first failure ends them all; run() sorts out what it was
                    errors.append(e)
                    return

        try:
            threads = [threading.Thread(target=one, args=(seg,), daemon=True) for seg in list(segs) if seg[2] < seg[1]]
            threads = threads or [threading.Thread(target=lambda: None)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            os.close(fd)
            count()
            segs.sort()
        if self.stop.is_set():
            raise Stop
        if errors and isinstance(errors[0], Changed):
            self.restart()
            raise urllib.error.URLError("the file changed on the server")
        if errors:
            raise errors[0]
        if j["got"] != j["size"]:
            raise urllib.error.URLError("parts of the file are missing")


class Changed(Exception):
    pass


def content_range_total(value):
    m = re.search(r"/(\d+)\s*$", value or "")
    return int(m.group(1)) if m else 0


def plan_segs(start, total, n=None):
    n = n or CONNECTIONS
    step = max(SPLIT_MIN // 4, (total - start) // n)
    out, at = [], start
    while at < total:
        end = total if total - at < step * 1.5 else at + step
        out.append([at, end, at])
        at = end
    return out


def finish(job):
    """NAME.part becomes NAME (never over a file that appeared meanwhile)."""
    folder = Path(job["folder"])
    have = (folder / (job["name"] + ".part")).stat().st_size
    if job.get("size") and have != job["size"]:
        raise OSError(5, f"only {size_text(have)} of {size_text(job['size'])} arrived")
    final = free_name(folder, job["name"]) if (folder / job["name"]).exists() else job["name"]
    os.replace(folder / (job["name"] + ".part"), folder / final)
    job["name"] = final


def notify(title, body, icon="download"):
    if shutil.which("notify-send") and not os.environ.get("DECKOS_DOWNLOADS_NO_SERVICE"):
        subprocess.Popen(["notify-send", "-a", "DecKoOS Downloads", "-i", icon, title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def serve(idle_exit=True):
    """Runs the queue until nothing's left to do. Workers download; this loop moves their progress into the queue
    file and picks up pauses, cancels and new links from it."""
    workers, retry_at, speeds = {}, {}, {}
    with locked():  # a restart left some marked downloading: they carry on
        jobs = load()
        for j in jobs:
            if j["state"] == "downloading":
                j["state"] = "queued"
        save(jobs)
    while True:
        now = time.time()
        with locked():
            jobs = load()
            by_id = {j["id"]: j for j in jobs}
            for jid, w in list(workers.items()):
                j = by_id.get(jid)
                if j is None or j["state"] != "downloading":  # paused, cancelled or removed in the window
                    w.stop.set()
                    w.join(5)
                    del workers[jid]
                    if j is not None and j["state"] == "cancelled":
                        try:
                            (Path(j["folder"]) / (j["name"] + ".part")).unlink()
                        except OSError:
                            pass
                    continue
                prev_got, prev_t = speeds.get(jid, (w.job["got"], now - TICK))
                inst = (w.job["got"] - prev_got) / max(0.05, now - prev_t)
                speeds[jid] = (w.job["got"], now)
                j.update(name=w.job["name"], got=w.job["got"], size=w.job["size"], named=w.job.get("named", False),
                         segs=[list(x) for x in w.job.get("segs", [])],
                         validator=w.job.get("validator", ""), error=w.job.get("error", ""),
                         speed=round(0.7 * j.get("speed", 0) + 0.3 * inst) if j.get("speed") else round(inst))
                if w.is_alive():
                    continue
                del workers[jid]
                speeds.pop(jid, None)
                j["tries"] = w.job.get("tries", 0)
                if w.outcome == "done":
                    try:
                        finish(j)
                        j.update(state="done", speed=0, finished=now, size=j["size"] or j["got"])
                        notify("Downloaded", j["name"])
                    except OSError as e:
                        j.update(state="failed", speed=0, error=f"Couldn't finish the file: {e.strerror}")
                elif w.outcome == "failed":
                    j.update(state="failed", speed=0, finished=now)
                    notify("Download stopped", f"{j['name']}: {j['error']}", "dialog-warning")
                elif w.outcome == "retry":
                    j.update(state="waiting", speed=0)
                    retry_at[jid] = now + w.wait
            for j in jobs:
                if j["state"] == "waiting" and retry_at.get(j["id"], 0) <= now and j["id"] not in workers:
                    j["state"] = "queued"  # after a restart there's no timer: try at once
            for j in sorted(jobs, key=lambda j: j["added"]):
                if len(workers) >= AT_ONCE:
                    break
                if j["state"] == "queued" and j["id"] not in workers:
                    j.update(state="downloading", error="", speed=0)
                    w = workers[j["id"]] = Worker(j)
                    w.start()
            save(jobs)
            busy = workers or any(j["state"] in ACTIVE for j in jobs)
        if not busy and idle_exit:
            return
        time.sleep(TICK)


def main(argv):
    cmd = argv[0] if argv else ""
    try:
        if cmd == "add" and len(argv) in (2, 3):
            j = add(argv[1], argv[2] if len(argv) == 3 else None)
            print(f"{j['id']}\t{Path(j['folder']) / j['name']}")
        elif cmd in ("pause", "resume", "cancel", "remove") and len(argv) == 2:
            change(argv[1], cmd)
        elif cmd == "clear":
            clear()
        elif cmd == "list":
            for j in load():
                print(f"{j['id']}\t{j['state']}\t{j['name']}\t{describe(j)}")
        elif cmd == "serve":
            serve()
        else:
            print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
            return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
