"""DecKoOS Builder's Website card, without Qt: which release ISOs exist where (this PC, a CI build, being built), and
publishing one to the website (site/build.py) with a signature when the DecKoOS key is on this PC.

An ISO only counts as built by CI when its whole run passed: the install tests on all three disk layouts included.
"""
import re
import subprocess
import sys
from pathlib import Path

FINGERPRINT = "F67E15FABF95D2DA72BE5D3F6322881773088C41"
TAG_WORKFLOW = "build-iso.yml"     # every version tag (an ISO only when the installer changed)
VERSION_WORKFLOW = "iso-version.yml"  # one release's ISO on request: build and install tests, never publishes
ARTIFACT = "deckos-iso"
SERVICE = "deckos-site"
URL = "http://localhost:8080/"
VERSION_RE = re.compile(r"^\d{1,2}\.\d+\.\d+$")


def iso_name(version):
    return f"deckos-{version}-x86_64.iso"


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def release_versions(tags, limit=8):
    """The newest release versions from git tags (v0.14.0 -> 0.14.0), newest first."""
    vs = {t[1:] for t in tags if t.startswith("v") and VERSION_RE.match(t[1:])}
    return sorted(vs, key=vkey, reverse=True)[:limit]


def runs_for(version, tag_runs, version_runs):
    """The CI runs that build this version's ISO, newest first."""
    mine = [r for r in tag_runs if r.get("head_branch") == f"v{version}" and r.get("event") == "push"]
    mine += [r for r in version_runs if (r.get("display_title") or "").split()[-1:] == [version]]
    return sorted(mine, key=lambda r: r.get("created_at", ""), reverse=True)


def sources(versions, out_dir, tag_runs, version_runs, artifacts_of):
    """Where each version's ISO can come from, newest version first: [{"version", "state", "path", "run", "expires"}].
    state: "local" (in out_dir), "ci" (a passed run's ISO, until it expires), "building", "failed" or "none".
    artifacts_of(run_id) lists a run's artifacts; it's only asked for runs that passed."""
    out = []
    for v in versions:
        item = {"version": v, "state": "none", "path": None, "run": None, "expires": None}
        local = Path(out_dir) / iso_name(v)
        runs = runs_for(v, tag_runs, version_runs)
        if local.is_file():
            item.update(state="local", path=local)
        elif any(r["status"] != "completed" for r in runs if r in version_runs):
            item.update(state="building", run=next(r for r in runs if r["status"] != "completed"))
        else:
            for r in runs:
                if r["status"] != "completed" or r.get("conclusion") != "success":
                    continue
                art = next((a for a in artifacts_of(r["id"]) if a["name"] == ARTIFACT and not a.get("expired")), None)
                if art:
                    item.update(state="ci", run=r, expires=art.get("expires_at"))
                    break
            else:
                # The newest on-request build failed: say so (a tag run that built no ISO isn't a failure)
                asked = [r for r in runs if r in version_runs]
                if asked and asked[0].get("conclusion") != "success":
                    item.update(state="failed", run=asked[0])
        out.append(item)
    return out


def describe(item):
    """One line for the publish dialog."""
    return {"local": "In the ISO folder on this PC: boot-test one you built here before publishing",
            "ci": f"Built and install-tested by CI{', kept until ' + item['expires'][:10] if item.get('expires') else ''}",
            "building": "Building on GitHub now (about 45 minutes with the install tests)",
            "failed": "The last build on GitHub failed: open it to see why, or build again",
            "none": "No ISO yet: GitHub can build and test one (about 45 minutes)"}[item["state"]]


def has_key(run=subprocess.run):
    try:
        return run(["gpg", "--batch", "--list-secret-keys", FINGERPRINT], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def sign(iso, run=subprocess.run):
    """Signs the ISO with the DecKoOS key when it's on this PC (gpg asks for its passphrase). Returns what happened.
    A signature left from another file of the same name is removed: it would only fail to verify."""
    iso = Path(iso)
    sig = iso.with_name(iso.name + ".sig")
    if not has_key(run):
        if sig.exists() and sig.stat().st_mtime < iso.stat().st_mtime:
            sig.unlink()
        return "not signed: the DecKoOS key isn't in gpg on this PC"
    r = run(["gpg", "--local-user", FINGERPRINT, "--detach-sign", "--yes", "--output", str(sig), str(iso)],
            capture_output=True, text=True)
    if r.returncode != 0:
        sig.unlink(missing_ok=True)
        lines = (r.stderr or "").strip().splitlines()
        return f"not signed: {lines[-1] if lines else 'gpg failed'}"
    return "signed"


def build(root, iso=None, run=subprocess.run):
    """Runs site/build.py (it offers the pinned ISO by itself). Returns its summary line; RuntimeError on failure."""
    root = Path(root)
    r = run([sys.executable, str(root / "site/build.py"), *(["--iso", str(iso)] if iso else [])],
            capture_output=True, text=True, cwd=root)
    if r.returncode != 0:
        raise RuntimeError(((r.stderr or r.stdout or "").strip().splitlines() or ["site/build.py failed"])[-1])
    return ((r.stdout or "").strip().splitlines() or ["site built"])[-1]


def publish(root, iso, run=subprocess.run):
    """Makes the site offer this ISO (out/site-iso keeps the choice for later rebuilds) and rebuilds it. Returns
    site/build.py's summary line; raises RuntimeError when the build fails."""
    root = Path(root)
    pin = root / "out/site-iso"
    pin.parent.mkdir(parents=True, exist_ok=True)
    pin.write_text(f"{Path(iso).resolve()}\n")
    return build(root, iso, run)


def offered(root):
    """The ISO file name the built site offers, or None."""
    dl = Path(root) / "site/public/downloads"
    return next((p.name for p in sorted(dl.glob("deckos-*-x86_64.iso"))), None) if dl.is_dir() else None


def service_active(run=subprocess.run):
    try:
        return run(["systemctl", "--user", "is-active", "--quiet", SERVICE]).returncode == 0
    except FileNotFoundError:
        return False
