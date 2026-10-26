"""Writes CHANGELOG.md from the release notes (usr/share/deckos/releases/X.Y.0.toml, what What's New shows) and the
git tags (patch releases). Re-run after a release and commit it.
    python assets/changelog.py
"""
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REL = ROOT / "pkg/deckos-settings/rootfs/usr/share/deckos/releases"


def key(v):
    return tuple(int(x) for x in v.split("."))


def main():
    notes = {}
    for f in REL.glob("*.toml"):
        d = tomllib.load(open(f, "rb"))
        notes[d["version"]] = d
    tags = subprocess.run(["git", "-C", str(ROOT), "tag", "-l", "v*", "--format=%(refname:short)\t%(creatordate:short)"],
                          capture_output=True, text=True).stdout.splitlines()
    dates = {t.split("\t")[0][1:]: t.split("\t")[1] for t in tags if "\t" in t}
    out = ["# DecKoOS changelog", "",
           "What each release brought, newest first. Feature releases (X.Y.0) have the notes DecKoOS shows in What's New;",
           "patch releases (X.Y.Z) are fixes. Generated from the release notes by `assets/changelog.py`.", ""]
    for v in sorted(set(notes) | set(dates), key=key, reverse=True):
        when = f" ({dates[v]})" if v in dates else ""
        if v not in notes:
            out += [f"### {v}{when}", "", "Fixes and polish.", ""]
            continue
        n = notes[v]
        out += [f"## {v}: {n.get('name', '')}{when}", "", n.get("tagline", ""), ""]
        out += [f"- **{h['title']}**: {re.sub(r'\s+', ' ', h.get('text', '')).strip()}" for h in n.get("highlights", [])]
        if n.get("fixes"):
            out += ["", "Fixes:", ""] + [f"- {x}" for x in n["fixes"]]
        out.append("")
    (ROOT / "CHANGELOG.md").write_text("\n".join(out))


if __name__ == "__main__":
    main()
