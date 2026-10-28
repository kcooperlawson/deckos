"""DecKoOS Music's library: the music files in your folders, their tags and covers, grouped into albums and artists.
No Qt: tests/test_music.py checks it. Tags come from mutagen when it's there; without it (or for an untagged file)
the folder and file names stand in ("Artist/Album/01 Title.flac").

A scan remembers each file's size and time, so the next one only reads what changed. The cache is
~/.cache/deckos/music/library.json; covers found inside files are saved next to it.
"""
import hashlib
import json
import os
import re
from pathlib import Path

try:
    import mutagen
except ImportError:  # the player still works, from file names
    mutagen = None

HOME = Path.home()
CACHE = HOME / ".cache/deckos/music"
AUDIO = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma", ".aiff", ".aif", ".alac", ".ape",
         ".wv", ".mka"}
COVER_NAMES = ("cover", "folder", "front", "album", "albumart", "artwork")
COVER_EXT = (".jpg", ".jpeg", ".png", ".webp")


def default_roots():
    """~/Music, and a Music folder at the top of each mounted drive."""
    roots = [HOME / "Music"]
    for base in (Path("/mnt"), Path("/media"), Path("/run/media") / os.environ.get("USER", "")):
        try:
            roots += [d / name for d in base.iterdir() for name in ("Music", "music") if (d / name).is_dir()]
        except OSError:
            continue
    return [r for r in roots if r.is_dir()]


# ------------------------------------------------------------------ one file

def guess(path, root=None):
    """Title, artist, album and track number from where a file sits: Artist/Album/01 - Title.ext, or
    "Artist - Title.ext" on its own."""
    p = Path(path)
    stem = p.stem
    track = 0
    m = re.match(r"^(?:(\d{1,2})[-.](\d{1,3})|(\d{1,3}))[\s._-]+(.*)$", stem)
    if m:
        track = int(m.group(2) or m.group(3))
        stem = m.group(4)
    artist, title = "", stem
    if " - " in stem:
        artist, title = (s.strip() for s in stem.split(" - ", 1))
    parts = p.parent.parts
    rel = list(Path(p.parent).relative_to(root).parts) if root and Path(root) in p.parents else list(parts[-2:])
    album = rel[-1] if rel else ""
    if not artist and len(rel) >= 2:
        artist = rel[-2]
    return {"title": title.replace("_", " ").strip() or p.stem, "artist": artist, "album": album, "track": track}


def _first(tags, *keys):
    for k in keys:  # easy=True: every tag is a list of strings
        v = tags.get(k)
        if v:
            return str(v[0] if isinstance(v, list) else v).strip()
    return ""


def _number(text):
    m = re.match(r"\s*(\d+)", text or "")
    return int(m.group(1)) if m else 0


def read_tags(path):
    """{title, artist, album, albumartist, track, disc, year, genre, duration} from the file's own tags ({} when
    there are none or mutagen isn't installed)."""
    if mutagen is None:
        return {}
    try:
        f = mutagen.File(path, easy=True)
    except Exception:  # a broken file mustn't stop the scan
        return {}
    if f is None:
        return {}
    tags = f.tags or {}
    out = {"title": _first(tags, "title"), "artist": _first(tags, "artist"), "album": _first(tags, "album"),
           "albumartist": _first(tags, "albumartist", "album artist"), "track": _number(_first(tags, "tracknumber")),
           "disc": _number(_first(tags, "discnumber")), "year": _number(_first(tags, "date", "year")),
           "genre": _first(tags, "genre")}
    out["duration"] = round(getattr(f.info, "length", 0) or 0, 1)
    return {k: v for k, v in out.items() if v}


def embedded_cover(path):
    """The picture inside a music file (ID3 APIC, FLAC/Vorbis pictures, MP4 covr) as bytes, or None."""
    if mutagen is None:
        return None
    try:
        f = mutagen.File(path)
    except Exception:
        return None
    if f is None:
        return None
    for pic in getattr(f, "pictures", []) or []:  # FLAC
        return pic.data
    tags = f.tags or {}
    for key in list(getattr(tags, "keys", lambda: [])()):
        if str(key).startswith("APIC"):  # MP3
            return tags[key].data
    covr = tags.get("covr") if hasattr(tags, "get") else None  # M4A
    if covr:
        return bytes(covr[0])
    pics = tags.get("metadata_block_picture") if hasattr(tags, "get") else None  # Ogg/Opus
    if pics:
        import base64
        from mutagen.flac import Picture
        try:
            return Picture(base64.b64decode(pics[0])).data
        except Exception:
            return None
    return None


def folder_cover(folder):
    """A cover picture sitting next to the music (cover.jpg, folder.png…), or None."""
    try:
        files = {f.name.lower(): f for f in Path(folder).iterdir() if f.suffix.lower() in COVER_EXT}
    except OSError:
        return None
    for name in COVER_NAMES:
        for ext in COVER_EXT:
            if name + ext in files:
                return files[name + ext]
    return next(iter(sorted(files.values())), None)


def cover_for(track, cache=None):
    """A path to a track's cover: next to it, else the picture inside it (saved once into the cache)."""
    cache = Path(cache or CACHE) / "covers"
    found = folder_cover(Path(track["path"]).parent)
    if found:
        return str(found)
    key = hashlib.sha1(f"{track.get('albumartist') or track.get('artist')}|{track.get('album')}".encode()).hexdigest()
    saved = cache / f"{key}.jpg"
    if saved.exists():
        return str(saved)
    data = embedded_cover(track["path"])
    if not data:
        return ""
    cache.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(data)
    return str(saved)


# ------------------------------------------------------------------ the whole library

def scan(roots=None, cache=None, read=read_tags):
    """Every music file under the roots, tags read only for new or changed files. Returns tracks (dicts, sorted
    by artist, album, disc, track)."""
    cache_dir = Path(cache or CACHE)
    store = cache_dir / "library.json"
    try:
        known = {t["path"]: t for t in json.loads(store.read_text()).get("tracks", [])}
    except (OSError, ValueError):
        known = {}
    tracks = []
    for root in roots if roots is not None else default_roots():
        for dirpath, dirnames, files in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in files:
                p = Path(dirpath) / name
                if p.suffix.lower() not in AUDIO:
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                stamp = [st.st_size, int(st.st_mtime)]
                old = known.get(str(p))
                if old and old.get("stamp") == stamp:
                    tracks.append(old)
                    continue
                t = {**guess(p, root), **read(p), "path": str(p), "stamp": stamp}
                t.setdefault("albumartist", "")
                tracks.append(t)
    tracks.sort(key=sort_key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps({"tracks": tracks}))
    return tracks


def sort_key(t):
    return ((t.get("albumartist") or t.get("artist") or "").lower(), (t.get("album") or "").lower(),
            t.get("disc") or 0, t.get("track") or 0, (t.get("title") or "").lower())


def albums(tracks):
    """[{title, artist, year, tracks}] in artist order; an album's artist is its album artist, else the artist most
    of its songs have ("Various artists" when they all differ)."""
    groups = {}
    for t in tracks:
        key = ((t.get("album") or "Unknown album").lower(), str(Path(t["path"]).parent))
        groups.setdefault(key, []).append(t)
    out = []
    for songs in groups.values():
        first = songs[0]
        artists = [s.get("artist") for s in songs if s.get("artist")]
        artist = first.get("albumartist") or (max(set(artists), key=artists.count) if artists else "")
        if not first.get("albumartist") and len(set(artists)) > 3 and artists.count(artist) < len(songs) / 2:
            artist = "Various artists"
        out.append({"title": first.get("album") or "Unknown album", "artist": artist or "Unknown artist",
                    "year": max((s.get("year") or 0) for s in songs), "tracks": songs})
    out.sort(key=lambda a: (a["artist"].lower(), a["year"], a["title"].lower()))
    return out


def artists(tracks):
    """{artist: [tracks]} by name."""
    out = {}
    for t in tracks:
        out.setdefault(t.get("albumartist") or t.get("artist") or "Unknown artist", []).append(t)
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def search(tracks, query, limit=200):
    """Tracks whose title, artist or album has every word of the query."""
    words = [w for w in re.split(r"\W+", query.lower()) if w]
    if not words:
        return []
    hits = []
    for t in tracks:
        text = f"{t.get('title', '')} {t.get('artist', '')} {t.get('album', '')}".lower()
        if all(w in text for w in words):
            hits.append(t)
            if len(hits) >= limit:
                break
    return hits


def fmt_time(seconds):
    s = int(max(0, seconds or 0))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
