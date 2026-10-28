"""A release with brakes: DecKoOS Builder's Release button and `python3 release.py` both go through here. No Qt.

A version is only tagged on a commit that already passed: the checks run here first, then the code goes to main on
its own and GitHub's Checks workflow (.github/workflows/checks.yml) must pass on that exact commit; only then is
VERSION bumped, tagged and pushed. And fixes are gathered into one release: another within RELEASE_GAP of the last
needs --hotfix (something people can't wait for), so a day of small fixes ships once.

    release.py X.Y.Z "summary" [--hotfix] [--iso]
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

RELEASE_GAP = 12 * 3600  # seconds after a release before the next one, unless it's a hotfix
CHECKS = "checks.yml"
REPO_DIR = next((p for p in Path(__file__).resolve().parents if (p / "VERSION").exists() and (p / ".git").exists()),
                None)


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def problems(state, version, hotfix=False, now=None):
    """Why this release can't go out yet, in plain words ([] when it can). `state`: branch, version (VERSION now),
    changed (tracked files with changes), behind (commits on origin/main not here), last_tag_at (epoch of the
    newest release tag, or 0)."""
    out = []
    if state["branch"] != "main":
        out.append(f"Releases go out from main; this checkout is on {state['branch']}.")
    if state["changed"]:
        out.append("Commit or put away your changes first: " + ", ".join(state["changed"][:5])
                   + (" …" if len(state["changed"]) > 5 else ""))
    if state["behind"]:
        out.append(f"main on GitHub has {state['behind']} commit(s) this checkout doesn't: pull first.")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or vkey(version) <= vkey(state["version"]):
        out.append(f"The version must be newer than {state['version']} (like 1.2.3).")
    since = (now or time.time()) - state["last_tag_at"] if state["last_tag_at"] else None
    if since is not None and since < RELEASE_GAP and not hotfix:
        hours = max(1, round((RELEASE_GAP - since) / 3600))
        out.append(f"The last release was {round(since / 3600, 1)} h ago. Gather fixes into one release (in about "
                   f"{hours} h), or mark this a hotfix if people can't wait for it.")
    return out


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def gh(*args):
    r = subprocess.run(["gh", *args], cwd=REPO_DIR, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def read_state():
    git("fetch", "--quiet", "origin", "main", "--tags")
    tag = git("describe", "--tags", "--abbrev=0", "--match", "v*", check=False)
    return {
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "version": (REPO_DIR / "VERSION").read_text().strip(),
        "changed": git("diff", "--name-only", "HEAD").splitlines(),  # staged or not; new untracked files don't count
        "behind": int(git("rev-list", "--count", "HEAD..origin/main") or 0),
        "last_tag_at": int(git("log", "-1", "--format=%ct", tag)) if tag else 0,
    }


def local_checks(say, bash="bash"):
    for part in ("lint", "tests"):
        say(f"Running the checks here ({part})…")
        r = subprocess.run([bash, "tests/check.sh", part], cwd=REPO_DIR, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode:
            tail = "\n".join(re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr).splitlines()[-12:])
            raise RuntimeError(f"the {part} checks failed here, so nothing was released:\n{tail}")


def github_checks(sha, say, timeout=1800):
    """Wait for the Checks workflow on this exact commit; True only when it passed."""
    deadline = time.time() + timeout
    run = None
    while time.time() < deadline:
        runs = json.loads(gh("run", "list", "--workflow", CHECKS, "--commit", sha, "--json",
                             "databaseId,status,conclusion,url", "--limit", "1") or "[]")
        if runs:
            run = runs[0]
            if run["status"] == "completed":
                if run["conclusion"] != "success":
                    raise RuntimeError(f"GitHub's checks failed on {sha[:7]} ({run['conclusion']}), so nothing "
                                       f"was tagged: {run['url']}")
                return True
            say(f"Waiting for GitHub's checks on {sha[:7]}…")
        else:
            say(f"Waiting for GitHub to start the checks on {sha[:7]}…")
        time.sleep(15)
    raise RuntimeError("GitHub's checks took too long; nothing was tagged. Release again once they've passed.")


def release(version, summary, hotfix=False, iso=False, say=print, bash="bash"):
    state = read_state()
    why = problems(state, version, hotfix)
    if why:
        raise RuntimeError("\n".join(why))
    if not summary.strip():
        raise RuntimeError("Add a short summary first.")
    if git("tag", "-l", f"v{version}"):
        raise RuntimeError(f"v{version} already exists.")
    local_checks(say, bash)
    sha = git("rev-parse", "HEAD")
    say("Sending the code to main…")
    git("push", "origin", "HEAD:main")
    github_checks(sha, say)
    (REPO_DIR / "VERSION").write_text(version + "\n")
    msg = f"DecKoOS {version}: {summary.strip()}"
    git("commit", "-m", msg, "--", "VERSION")
    git("tag", "-a", f"v{version}", "-m", msg + (" [iso]" if iso else ""))  # [iso]: CI's plan job builds one
    git("push", "origin", "HEAD:main")
    git("push", "origin", f"v{version}")
    say(f"Released DecKoOS {version} to testing: testing PCs get it in about 5 minutes.")


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    try:
        release(args[0], args[1], hotfix="--hotfix" in argv, iso="--iso" in argv)
    except RuntimeError as e:
        print(f"Not released: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
