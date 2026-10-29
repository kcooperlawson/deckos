"""Back up everything before a reinstall, and bring it back after: your whole home folder (one archive, so it keeps
links and permissions even on a Windows-format drive), your DecKoOS setup, which apps you installed and how your
drives were set up. A reinstall wipes the home folder; this is what makes that safe.

A backup is a folder "DecKoOS backup YYYY-MM-DD HHMM" on the drive you pick:
    home.tar.zst     the home folder (caches, the trash and downloaded games left out: those come back on their own)
    setup.tar.gz     `deckos setup export`: the look, panels, DecKoOS settings
    packages.txt     apps from the repositories you installed yourself (pacman -Qqe), flatpaks.txt the Flatpaks
    drives.txt       /etc/fstab, to see how drives were mounted
    manifest.json    what's in it, sizes, the archive's file count and SHA-256 (what `verify` checks)
    README.txt       how to restore, in plain words

Restoring never overwrites a newer file in your home. No Qt; tests/test_backup.py.

    backup.py plan [HOME] | make DEST | verify FOLDER | restore FOLDER | list DEST
"""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

FORMAT = 1
# Left out of the home archive, relative to home: rebuilt or downloaded again by themselves
SKIP = [".cache", ".local/share/Trash", ".local/share/Steam/steamapps/common",
        ".local/share/Steam/steamapps/shadercache", ".local/share/Steam/steamapps/downloading",
        ".local/share/Steam/steamapps/temp", ".var/app/*/cache", ".local/share/baloo"]
PREFIX = "DecKoOS backup"
README = """DecKoOS backup, made {made} on {host} (DecKoOS {version}).

To bring it back after reinstalling DecKoOS:
  DecKoOS Hub > System > Before a reinstall > Restore a backup, and pick this folder.
  Or in a terminal:  deckos backup restore "{folder}"

What's here:
  home.tar.zst   your home folder ({files} files). Restoring never replaces a file that's newer on the PC.
  setup.tar.gz   your look, panels and DecKoOS settings (brought in after the home folder).
  packages.txt   apps you installed. Reinstall them: sudo pacman -S --needed - < packages.txt
  flatpaks.txt   Flatpak apps. Reinstall them: xargs -a flatpaks.txt flatpak install -y flathub
  drives.txt     how your drives were mounted (DecKoOS Disks sets them up again).
"""


def home():
    return Path(os.environ.get("DECKOS_BACKUP_HOME") or Path.home())


def _run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)


def _version():
    try:
        return Path("/usr/share/deckos/version").read_text().strip()
    except OSError:
        return "?"


def excludes():
    """tar --exclude patterns, anchored at the top of the archive (a project's own .cache stays in)."""
    return ["--anchored", *[f"--exclude={p}" for p in SKIP]]


def du(path):
    out = _run(["du", "-s", "--block-size=1", str(path)]).stdout.split()  # on disk: sparse VM images count as what they use
    return int(out[0]) if out else 0


def plan(base=None):
    """What a backup would hold: [(what, bytes)], and the total. Sizes are before compression."""
    h = Path(base or home())
    rows = [("Home folder", du(h))]
    for p in SKIP:
        if "*" not in p and (h / p).exists():
            rows.append((f"left out: {p}", -du(h / p)))
    return rows, sum(n for _, n in rows)


def free(dest):
    try:
        return shutil.disk_usage(dest).free
    except OSError:
        return 0


def sha256(path, chunk=8 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def count(archive):
    """Entries in a .tar.zst, by reading it all the way through (which is also the check it isn't damaged)."""
    p = subprocess.Popen(["tar", "--zstd", "-tf", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    n = sum(1 for _ in p.stdout)
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError(f"the archive can't be read: {err.strip()[:300]}")
    return n


def make(dest, base=None, say=print):
    """Writes a backup folder in DEST; returns its path. Raises RuntimeError with a plain reason on failure."""
    h = Path(base or home())
    dest = Path(dest)
    if not dest.is_dir():
        raise RuntimeError(f"{dest} isn't a folder")
    if dest.resolve() == h.resolve() or h.resolve() in dest.resolve().parents:
        raise RuntimeError("pick a folder outside your home folder: that's what gets wiped")
    _rows, need = plan(h)
    if free(dest) < need * 0.8:  # zstd shrinks most homes; a full drive halfway through is worse than asking
        raise RuntimeError(f"not enough space on {dest}: about {need / 1e9:.0f} GB needed, "
                           f"{free(dest) / 1e9:.0f} GB free")
    folder = dest / f"{PREFIX} {time.strftime('%Y-%m-%d %H%M')}"
    folder.mkdir()
    archive = folder / "home.tar.zst"
    say(f"Packing your home folder (about {need / 1e9:.0f} GB)…")
    # The home folder's items, not "." (the new home already exists, and a restore over its folder entry fails);
    # relative, so a restore lands in whatever the new home is; --sparse keeps disk images small
    items = sorted(os.listdir(h))
    tar = _run(["tar", "--zstd", "--sparse", "--warning=no-file-changed", "--warning=no-file-removed",
                *excludes(), "-cf", str(archive), "-C", str(h), "--", *items])
    if tar.returncode not in (0, 1):  # 1: a file changed while it was read (a running app's), which is fine
        raise RuntimeError(f"packing failed: {tar.stderr.strip()[-400:]}")
    say("Saving your DecKoOS setup and app lists…")
    setup = Path(__file__).resolve().parent.parent / "setup/setup.py"
    if setup.exists():
        _run([sys.executable, str(setup), "export", str(folder / "setup.tar.gz")],
             env={**os.environ, "DECKOS_SETUP_HOME": str(h)})
    (folder / "packages.txt").write_text(_run(["pacman", "-Qqe"]).stdout if shutil.which("pacman") else "")
    (folder / "flatpaks.txt").write_text(_run(["flatpak", "list", "--app", "--columns=application"]).stdout
                                         if shutil.which("flatpak") else "")
    try:
        shutil.copyfile("/etc/fstab", folder / "drives.txt")
    except OSError:
        pass
    say("Checking the backup reads back…")
    files = count(archive)
    manifest = {"format": FORMAT, "made": time.time(), "host": socket.gethostname(), "version": _version(),
                "home": str(h), "files": files, "bytes": archive.stat().st_size, "sha256": sha256(archive)}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (folder / "README.txt").write_text(README.format(made=time.strftime("%Y-%m-%d %H:%M"), host=manifest["host"],
                                                     version=manifest["version"], folder=folder, files=files))
    say(f"Done: {files} files, {manifest['bytes'] / 1e9:.1f} GB in {folder}")
    return folder


def verify(folder, say=lambda s: None):
    """(ok, message): the archive is the one the manifest describes, and reads all the way through. Both passes read
    the whole archive (a 100 GB+ home over USB takes a while), so SAY hears what it's on."""
    folder = Path(folder)
    try:
        m = json.loads((folder / "manifest.json").read_text())
    except (OSError, ValueError):
        return False, "no manifest.json: not a finished DecKoOS backup"
    archive = folder / "home.tar.zst"
    if not archive.exists():
        return False, "home.tar.zst is missing"
    if archive.stat().st_size != m.get("bytes"):
        return False, "home.tar.zst isn't the size it was when it was made"
    say(f"Checking the archive matches ({archive.stat().st_size / 1e9:.0f} GB, the slow part)…")
    if sha256(archive) != m.get("sha256"):
        return False, "home.tar.zst changed since it was made (damaged?)"
    say(f"Checking all {m.get('files')} files read back…")
    try:
        n = count(archive)
    except RuntimeError as e:
        return False, str(e)
    if n != m.get("files"):
        return False, f"{n} files read back, {m.get('files')} expected"
    return True, f"good: {n} files, made {time.strftime('%Y-%m-%d %H:%M', time.localtime(m['made']))}"


def restore(folder, base=None, say=print):
    """Unpacks the home folder (never over a newer file), then brings the setup in. Verifies first."""
    folder = Path(folder)
    ok, why = verify(folder, say=say)
    if not ok:
        raise RuntimeError(f"this backup didn't check out: {why}")
    h = Path(base or home())
    say("Unpacking your home folder…")
    # Into a folder beside it first (same drive), then merged in with rsync --update: a file that's newer on the PC
    # stays (tar's own --keep-newer-files trips over folders that already exist); --sparse, or a disk image that's
    # mostly holes (tar --sparse kept it small) is written out full size
    say("Putting your files back…")
    stage = h / ".local/state/deckos/restore-staging"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    try:
        tar = _run(["tar", "--zstd", "-xf", str(folder / "home.tar.zst"), "-C", str(stage)])
        if tar.returncode != 0:
            raise RuntimeError(f"unpacking failed: {tar.stderr.strip()[-400:]}")
        sync = _run(["rsync", "-aHAX", "--sparse", "--update", f"{stage}/", f"{h}/"])
        if sync.returncode != 0:
            raise RuntimeError(f"putting files back failed: {sync.stderr.strip()[-400:]}")
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    setup = Path(__file__).resolve().parent.parent / "setup/setup.py"
    if (folder / "setup.tar.gz").exists() and setup.exists():
        say("Bringing your DecKoOS setup back…")
        _run([sys.executable, str(setup), "import", str(folder / "setup.tar.gz")],
             env={**os.environ, "DECKOS_SETUP_HOME": str(h)})
    say("Done. Log out and back in to see everything as it was.")


def backups_in(dest):
    """[(folder, manifest)] newest first: finished backups in DEST."""
    out = []
    for f in Path(dest).glob(f"{PREFIX} *"):
        try:
            out.append((f, json.loads((f / "manifest.json").read_text())))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda x: -x[1].get("made", 0))


def main(argv):
    cmd = argv[0] if argv else ""
    try:
        if cmd == "plan":
            rows, total = plan(argv[1] if len(argv) > 1 else None)
            for what, n in rows:
                print(f"{what}\t{n / 1e9:.1f} GB")
            print(f"total\t{total / 1e9:.1f} GB")
        elif cmd == "make" and len(argv) == 2:
            print(f"BACKUP={make(argv[1], say=lambda s: print(s, flush=True))}")
        elif cmd == "verify" and len(argv) == 2:
            ok, why = verify(argv[1], say=lambda s: print(s, flush=True))
            print(why)
            return 0 if ok else 1
        elif cmd == "restore" and len(argv) == 2:
            restore(argv[1], say=lambda s: print(s, flush=True))
        elif cmd == "list" and len(argv) == 2:
            for f, m in backups_in(argv[1]):
                print(f"{f}\t{m.get('files')} files\t{m.get('bytes', 0) / 1e9:.1f} GB")
        else:
            print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
            return 2
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
