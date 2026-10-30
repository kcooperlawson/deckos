"""DecKoOS Shelf's eyes: what's on the Desktop, said as tiles. The Shelf (the org.deckos.shelf desktop widget, which
takes over from Plasma's icon grid) runs this and draws what it prints; it runs it again when the folder changes.

Each thing on the Desktop becomes one tile, newest first:
  game    a Steam game's launcher: its art, when it was last played, how long in all
  app     any other launcher (.desktop): its name and icon
  folder  how many things are in it, how big it is, and up to four of its pictures
  image   the picture itself
  text    its first few lines
  partial a download still arriving (.part, .crdownload), on the Desktop or in Downloads: how much has come so far
  file    anything else: its size and kind

Only reads; the widget opens, moves and trashes things itself. No Qt; tests/test_shelf.py checks it.

    shelf.py [FOLDER [DOWNLOADS]]   JSON {folder, url, items}; the Desktop and Downloads (xdg-user-dirs) by default
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gamedoctor"))
import steamfiles as sf  # noqa: E402

IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif", ".svg"}
TEXTS = {".txt", ".md", ".log", ".csv", ".json", ".toml", ".ini", ".conf", ".py", ".sh", ".js", ".ts", ".qml",
         ".c", ".h", ".cpp", ".rs", ".go", ".html", ".css", ".yaml", ".yml", ".xml", ".nfo", ".srt", ".lrc"}
PARTIAL = {".part", ".crdownload", ".download", ".partial"}
KINDS = {".pdf": "PDF", ".docx": "Word document", ".doc": "Word document", ".odt": "Document",
         ".xlsx": "Spreadsheet", ".ods": "Spreadsheet", ".pptx": "Slides", ".odp": "Slides", ".zip": "Archive",
         ".7z": "Archive", ".rar": "Archive", ".tar": "Archive", ".gz": "Archive", ".zst": "Archive", ".iso": "Disk image",
         ".img": "Disk image", ".exe": "Windows program", ".msi": "Windows installer", ".appimage": "AppImage",
         ".mp3": "Music", ".flac": "Music", ".ogg": "Music", ".opus": "Music", ".wav": "Music", ".m4a": "Music",
         ".mp4": "Video", ".mkv": "Video", ".webm": "Video", ".mov": "Video", ".avi": "Video", ".torrent": "Torrent"}
GAME = re.compile(r"steam://rungameid/(\d+)")
ARRIVING = 90  # s: a partial download in Downloads written to this recently is still coming
FOLDER_SCAN = 4000  # entries looked at to size a folder; past this its size is "at least"
LINES, LINE_CHARS = 3, 64


def user_dir(name, fallback):
    """An xdg-user-dirs folder (DESKTOP, DOWNLOAD), else ~/fallback."""
    conf = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "user-dirs.dirs"
    try:
        m = re.search(rf'^XDG_{name}_DIR="([^"]+)"', conf.read_text(), re.M)
    except OSError:
        m = None
    return Path(m.group(1).replace("$HOME", str(Path.home()))) if m else Path.home() / fallback


def desktop_dir():
    return user_dir("DESKTOP", "Desktop")


def arriving(folder, now):
    """Downloads still coming into `folder` (a browser's .part or .crdownload written to in the last ARRIVING s)."""
    out = []
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return out
    for e in entries:
        p = Path(e.path)
        try:
            if p.suffix.lower() in PARTIAL and e.is_file() and now - e.stat().st_mtime < ARRIVING \
                    and e.stat().st_size > 0:
                out.append({**describe(p, now), "arriving": True})
        except OSError:
            continue
    return out


def size_text(n):
    for unit, step in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= step:
            v = n / step
            return f"{v:.1f} {unit}" if v < 10 else f"{v:.0f} {unit}"
    return f"{n} bytes"


def ago_text(ts, now):
    """'2 h ago', 'yesterday', '12 days ago', or 'Mar 2025'."""
    s = now - ts
    if s < 3600:
        return "just now" if s < 120 else f"{int(s // 60)} min ago"
    if s < 86400:
        return f"{int(s // 3600)} h ago"
    if s < 2 * 86400:
        return "yesterday"
    if s < 30 * 86400:
        return f"{int(s // 86400)} days ago"
    return time.strftime("%b %Y", time.localtime(ts))


def read_desktop(path):
    """[Desktop Entry]'s keys (unlocalised) from a .desktop file."""
    out, inside = {}, False
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            inside = line == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    return out


def steam_played():
    """{appid: (last played epoch, minutes in all)} from every Steam account here."""
    out = {}
    for user in sf.users():
        try:
            apps = sf._ci(sf.read(user / "config/localconfig.vdf"), "UserLocalConfigStore", "Software", "Valve",
                          "Steam", "apps") or {}
        except (OSError, ValueError):
            continue
        for appid, a in apps.items():
            if not isinstance(a, dict):
                continue
            last = int(a.get("LastPlayed") or a.get("lastplayed") or 0) if str(
                a.get("LastPlayed") or a.get("lastplayed") or "0").isdigit() else 0
            mins = str(a.get("Playtime") or a.get("playtime") or "0")
            mins = int(mins) if mins.isdigit() else 0
            was = out.get(appid, (0, 0))
            out[appid] = (max(was[0], last), max(was[1], mins))
    return out


def steam_art(appid):
    """The widest art Steam has cached for a game (hero, then header, then the cover), or ""."""
    cache = sf.STEAM / "appcache/librarycache"
    for name in ("library_hero.jpg", "header.jpg", "library_600x900.jpg"):
        for p in (cache / f"{appid}_{name}", cache / appid / name):
            if p.is_file():
                return str(p)
        hit = next(iter(sorted((cache / appid).glob(f"*/{name}"))), None) if (cache / appid).is_dir() else None
        if hit:
            return str(hit)
    return ""


def folder_facts(path):
    """(things in it, bytes (of its first FOLDER_SCAN entries, all the way down), more than that?, [pictures])."""
    try:
        top = [e for e in os.scandir(path) if not e.name.startswith(".")]
    except OSError:
        return 0, 0, False, []
    pics = sorted((e for e in top if e.is_file() and Path(e.name).suffix.lower() in IMAGES),
                  key=lambda e: e.stat().st_mtime, reverse=True)[:4]
    total, seen, stack = 0, 0, [path]
    while stack and seen < FOLDER_SCAN:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    seen += 1
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
                    if seen >= FOLDER_SCAN:
                        break
        except OSError:
            continue
    return len(top), total, bool(stack) or seen >= FOLDER_SCAN, [str(e.path) for e in pics]


def first_lines(path):
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return []
    if b"\0" in head:
        return []
    out = []
    for line in head.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line:
            out.append(line if len(line) <= LINE_CHARS else line[:LINE_CHARS - 1] + "…")
        if len(out) == LINES:
            break
    return out


def describe(path, now, played=None):
    """One tile: {kind, name, path, url, time, title, detail, ...}."""
    url = path.absolute().as_uri()  # the link itself, not what it points at: trashing a link trashes the link
    if not path.exists():  # a link to something that's gone
        return {"kind": "file", "name": path.name, "path": str(path), "url": url, "time": path.lstat().st_mtime,
                "title": path.name, "detail": "Link to something that's gone"}
    st = path.stat()
    base = {"name": path.name, "path": str(path), "url": url, "time": st.st_mtime, "title": path.name, "detail": ""}
    ext = path.suffix.lower()
    if path.is_dir():
        n, size, more, pics = folder_facts(path)
        return {**base, "kind": "folder", "count": n, "pictures": [Path(p).as_uri() for p in pics],
                "detail": f"{n} {'thing' if n == 1 else 'things'} · {'over ' if more else ''}{size_text(size)}"}
    if ext == ".desktop":
        entry = read_desktop(path)
        title = entry.get("Name") or path.stem
        m = GAME.search(entry.get("Exec", "") + " " + entry.get("URL", ""))
        if m:
            appid = m.group(1)
            last, mins = (played if played is not None else steam_played()).get(appid, (0, 0))
            bits = [f"Played {ago_text(last, now)}" if last else "Not played yet"]
            if mins >= 60:
                bits.append(f"{mins // 60} h in all")
            elif mins:
                bits.append(f"{mins} min in all")
            art = steam_art(appid)
            return {**base, "kind": "game", "title": title, "appid": appid, "art": Path(art).as_uri() if art else "",
                    "launch": f"steam://rungameid/{appid}", "detail": " · ".join(bits)}
        return {**base, "kind": "app", "title": title, "icon": entry.get("Icon", "application-x-executable"),
                "detail": entry.get("Comment", "") or entry.get("GenericName", "")}
    if ext in PARTIAL:
        return {**base, "kind": "partial", "title": path.stem, "size": st.st_size,
                "detail": f"{size_text(st.st_size)} so far" + ("" if path.parent == desktop_dir() else
                                                             f" · into {path.parent.name}")}
    if ext in IMAGES:
        return {**base, "kind": "image", "detail": size_text(st.st_size)}
    if ext in TEXTS or (not ext and st.st_size < 1 << 20):
        lines = first_lines(path)
        if lines or st.st_size == 0:
            return {**base, "kind": "text", "lines": lines, "detail": size_text(st.st_size) if lines else "Empty"}
    return {**base, "kind": "file", "detail": f"{KINDS.get(ext, ext[1:].upper() + ' file' if ext else 'File')} · "
                                              f"{size_text(st.st_size)}"}


def items(folder, now=None, downloads=None):
    """Every visible thing in `folder` as a tile, newest first, after any downloads still arriving in `downloads`."""
    now = now or time.time()
    try:
        entries = [Path(e.path) for e in os.scandir(folder) if not e.name.startswith(".")]
    except OSError:
        return []
    played = steam_played() if any(p.suffix == ".desktop" for p in entries) else {}
    out = []
    for p in entries:
        try:
            out.append(describe(p, now, played))
        except OSError:  # gone between the listing and the look
            continue
    out.sort(key=lambda t: t["time"], reverse=True)
    if downloads and Path(downloads) != Path(folder):
        out = sorted(arriving(downloads, now), key=lambda t: t["time"], reverse=True) + out
    return out


def main(argv):
    folder = Path(argv[0]).expanduser() if argv else desktop_dir()
    downloads = Path(argv[1]).expanduser() if len(argv) > 1 else user_dir("DOWNLOAD", "Downloads")
    print(json.dumps({"folder": str(folder), "url": folder.as_uri() if folder.is_absolute() else "",
                      "items": items(folder, downloads=downloads)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
