"""Vibe mode's lyrics: synced lyrics (LRC: a time on each line) for whatever plays, from an .lrc file next to your
own music or from LRCLIB (lrclib.net, a free, open lyrics library: no account, no key). A lookup sends the song's
title, artist, album and length there and nothing else; answers (and songs it doesn't have) are kept in
~/.cache/deckos/music/lyrics, so each song is asked for once. Vibe mode's Lyrics switch turns lookups off.
No Qt; tests/test_music.py checks it.
"""
import bisect
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache/deckos/music/lyrics"
API = "https://lrclib.net/api"
AGENT = "DecKoOS Music (https://github.com/kcooperlawson/deckos)"
MISS_DAYS = 3  # a song LRCLIB didn't have is asked for again after this

STAMP = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
WORD = re.compile(r"<(\d+):(\d+(?:\.\d+)?)>")
OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\]", re.I)


def parse_lrc(text):
    """LRC text into lines [{t, text, words}], in time order: t in seconds; words [(t, word)] when the line has
    word times (<mm:ss.xx>, "enhanced" LRC), else []. Several times on one line repeat it; [offset:ms] shifts all
    (positive: earlier, as the format has it). Lines without a time (tags, plain text) are left out."""
    m = OFFSET.search(text or "")
    shift = -int(m.group(1)) / 1000 if m else 0.0
    out = []
    for raw in (text or "").splitlines():
        stamps = STAMP.findall(raw)
        if not stamps:
            continue
        body = STAMP.sub("", raw).strip()
        words = [(int(a) * 60 + float(b) + shift, w.strip())
                 for (a, b), w in zip(WORD.findall(body), WORD.split(body)[3::3])]
        words = [(t, w) for t, w in words if w]
        body = re.sub(r"\s+", " ", WORD.sub("", body)).strip()
        for mins, secs in stamps:
            out.append({"t": max(0.0, int(mins) * 60 + float(secs) + shift), "text": body, "words": words})
    out.sort(key=lambda line: line["t"])
    return out


def at(lines, position):
    """(index of the line sung at `position`, how far through it 0..1); index -1 before the first line."""
    if not lines:
        return -1, 0.0
    i = bisect.bisect_right([line["t"] for line in lines], position) - 1
    if i < 0:
        return -1, 0.0
    end = lines[i + 1]["t"] if i + 1 < len(lines) else lines[i]["t"] + 5
    return i, min(1.0, max(0.0, (position - lines[i]["t"]) / max(0.1, end - lines[i]["t"])))


def local_lrc(path):
    """The .lrc beside a music file (song.flac -> song.lrc), or ""."""
    try:
        lrc = Path(str(path).removeprefix("file://")).with_suffix(".lrc")
        return lrc.read_text(errors="replace") if lrc.is_file() else ""
    except (OSError, ValueError):
        return ""


def key(artist, title, duration):
    return hashlib.sha1(f"{artist.lower()}|{title.lower()}|{round(duration or 0)}".encode()).hexdigest()


def cached(artist, title, duration, folder=None, now=None):
    """A stored answer: {"synced": LRC text, "plain": text} (both "" for a recent miss), or None to ask."""
    f = Path(folder or CACHE) / f"{key(artist, title, duration)}.json"
    try:
        data = json.loads(f.read_text())
    except (OSError, ValueError):
        return None
    if not data.get("synced") and not data.get("plain") and (now or time.time()) - data.get("at", 0) > MISS_DAYS * 86400:
        return None
    return data


def store(artist, title, duration, answer, folder=None):
    folder = Path(folder or CACHE)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{key(artist, title, duration)}.json").write_text(json.dumps({**answer, "at": time.time()}))
    except OSError:
        pass


def _get(path, params, timeout):
    req = urllib.request.Request(f"{API}/{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # lrclib.net only (API is fixed above)
        return json.loads(r.read().decode("utf-8", "replace"))


def pick(results, duration):
    """Of LRCLIB's search results, the one with synced lyrics whose length is closest (within 5 s), else one with
    plain lyrics, else None."""
    def close(r):
        return not duration or abs((r.get("duration") or 0) - duration) <= 5
    synced = [r for r in results if r.get("syncedLyrics") and close(r)]
    if synced:
        return min(synced, key=lambda r: abs((r.get("duration") or 0) - (duration or 0)))
    return next((r for r in results if r.get("plainLyrics") and close(r)), None)


def fetch(artist, title, album="", duration=0, timeout=8, folder=None):
    """{"synced", "plain"} for a song (an exact match first, then a search), cached; {"synced": "", "plain": ""}
    when LRCLIB doesn't have it or can't be reached (a failed connection isn't remembered as a miss)."""
    if not title:
        return {"synced": "", "plain": ""}
    hit = cached(artist, title, duration, folder)
    if hit is not None:
        return {"synced": hit.get("synced", ""), "plain": hit.get("plain", "")}
    found = None
    try:
        params = {"artist_name": artist, "track_name": title}
        if album:
            params["album_name"] = album
        if duration:
            params["duration"] = round(duration)
        try:
            found = _get("get", params, timeout)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        if not found or not (found.get("syncedLyrics") or found.get("plainLyrics")):
            found = pick(_get("search", {"artist_name": artist, "track_name": title}, timeout) or [], duration)
    except (OSError, ValueError):
        return {"synced": "", "plain": ""}
    answer = {"synced": (found or {}).get("syncedLyrics") or "", "plain": (found or {}).get("plainLyrics") or ""}
    store(artist, title, duration, answer, folder)
    return answer
