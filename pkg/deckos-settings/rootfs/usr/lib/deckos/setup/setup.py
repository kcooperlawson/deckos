"""Take your DecKoOS setup with you: one file with what makes this PC yours (the look, the panel and its pinned
apps, DecKoOS's settings, game profiles, Game Doctor's fixes, DecKoOS Retro's folders), to bring to a new PC
or back after a reinstall. Never passwords, keys, games or system files: only the files in WHAT.

Importing keeps everything it replaces in ~/.local/state/deckos/setup-backups/STAMP and records it in the
timeline, whose Undo (`deckos setup undo STAMP`) puts that back.

    setup.py export FILE      setup.py import FILE      setup.py undo STAMP      setup.py show FILE
"""
import io
import json
import os
import shutil
import socket
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pulse"))
try:
    import pulse
except ImportError:
    pulse = None

FORMAT = 1
# What a setup holds, relative to home: (path, what it is). Folders go whole.
WHAT = [
    (".config/kdeglobals", "colours, accent, icons and theme"),
    (".config/plasmarc", "desktop style"),
    (".config/kcminputrc", "mouse pointer"),
    (".config/kwinrc", "window behaviour"),
    (".config/plasma-org.kde.plasma.desktop-appletsrc", "panels, pinned apps and widgets"),
    (".config/plasmashellrc", "panel sizes"),
    (".config/deckos", "DecKoOS settings, game profiles and Retro's folders"),
    (".local/state/deckos/gamedoctor", "Game Doctor's fixes"),
    (".config/environment.d/90-deckos-gaming.conf", "gaming settings (FSR 4)"),
]
NEVER = ("token", "secret", "password", "key", "credentials")  # a file with these in its name stays behind


def home():
    return Path(os.environ.get("DECKOS_SETUP_HOME") or Path.home())


def backups():
    return home() / ".local/state/deckos/setup-backups"


def _files():
    """[(relative path, absolute path)] of what exists now."""
    out = []
    for rel, _ in WHAT:
        p = home() / rel
        if p.is_file():
            out.append((rel, p))
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not any(w in f.name.lower() for w in NEVER):
                    out.append((str(f.relative_to(home())), f))
    return out


def export(path):
    """Writes the setup file; returns how many files went in."""
    files = _files()
    manifest = {"format": FORMAT, "made": time.time(), "from": socket.gethostname(),
                "version": _version(), "files": [rel for rel, _ in files]}
    path = Path(path)
    with tarfile.open(path, "w:gz") as tar:
        data = json.dumps(manifest, indent=1).encode()
        info = tarfile.TarInfo("deckos-setup.json")
        info.size, info.mtime = len(data), int(time.time())
        tar.addfile(info, io.BytesIO(data))
        for rel, p in files:
            tar.add(p, arcname=f"home/{rel}", recursive=False)
    return len(files)


def _version():
    try:
        return Path("/usr/share/deckos/version").read_text().strip()
    except OSError:
        return ""


def show(path):
    with tarfile.open(path, "r:gz") as tar:
        return json.loads(tar.extractfile("deckos-setup.json").read())


def _allowed(rel):
    """Only the places WHAT names, and never a path that climbs out of them."""
    parts = Path(rel).parts
    if not parts or ".." in parts or Path(rel).is_absolute():
        return False
    return any(rel == w or rel.startswith(w.rstrip("/") + "/") for w, _ in WHAT)


def import_(path):
    """Brings a setup in. Returns (stamp, how many files). What it replaces is kept for undo."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    keep = backups() / stamp
    n = 0
    with tarfile.open(path, "r:gz") as tar:
        manifest = json.loads(tar.extractfile("deckos-setup.json").read())
        if manifest.get("format") != FORMAT:
            raise ValueError("That setup file is from a newer DecKoOS: update this PC first.")
        new = []
        for m in tar.getmembers():
            if not m.name.startswith("home/") or not m.isfile():
                continue  # links, devices and anything outside home/ never come in
            rel = m.name[len("home/"):]
            if not _allowed(rel):
                continue
            new.append((rel, m))
        for rel, m in new:
            dest = home() / rel
            if dest.exists():
                (keep / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, keep / rel)
            else:  # remember it was new, so undo removes it
                (keep / ".new").parent.mkdir(parents=True, exist_ok=True)
                with open(keep / ".new", "a") as f:
                    f.write(rel + "\n")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(m) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
            n += 1
    if pulse:
        try:
            pulse.emit("setup", f"Brought in a setup from {manifest.get('from') or 'another PC'} ({n} files)",
                       app="Setup", undo=["deckos", "setup", "undo", stamp])
        except (OSError, ValueError):
            pass
    return stamp, n


def undo(stamp):
    keep = backups() / stamp
    if not keep.is_dir() or "/" in stamp or stamp.startswith("."):
        raise ValueError(f"no setup backup called {stamp}")
    for f in keep.rglob("*"):
        if f.is_file() and f.name != ".new":
            rel = f.relative_to(keep)
            if _allowed(str(rel)):
                (home() / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, home() / rel)
    if (keep / ".new").exists():
        for rel in (keep / ".new").read_text().splitlines():
            if rel and _allowed(rel):
                (home() / rel).unlink(missing_ok=True)
    shutil.rmtree(keep)


def main(argv):
    try:
        if argv[:1] == ["export"] and len(argv) == 2:
            n = export(argv[1])
            print(f"Saved {n} files to {argv[1]}")
        elif argv[:1] == ["import"] and len(argv) == 2:
            stamp, n = import_(argv[1])
            print(f"Brought in {n} files. Log out and back in to see it all. Undo: deckos setup undo {stamp}")
        elif argv[:1] == ["undo"] and len(argv) == 2:
            undo(argv[1])
            print("Put back the files from before. Log out and back in to see it.")
        elif argv[:1] == ["show"] and len(argv) == 2:
            m = show(argv[1])
            print(f"From {m.get('from')} (DecKoOS {m.get('version') or '?'}), {len(m['files'])} files")
        else:
            print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError, tarfile.TarError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
