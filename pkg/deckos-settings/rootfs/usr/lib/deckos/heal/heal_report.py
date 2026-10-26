"""Self-healing, phase 2 and 3 (docs/self-healing.md): what each fix did, reports a person chooses to send, and the
maintainer's grouping of them. Reports, never patches: what goes upstream is evidence (the problem, the fix tried,
whether it worked, a scrubbed hardware summary), and a person writes any new recipe.

Nothing is ever sent by DecKoOS: `report` shows the text and, if asked, opens a pre-filled GitHub issue in the
browser, where the person reads it and presses Submit themselves.

    heal_report.py outcome ID worked|failed [FINDING] | history | report [--open] | triage [--json]
"""
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
HISTORY = Path(os.environ.get("DECKOS_HEAL_HISTORY") or Path.home() / ".local/state/deckos/heal.jsonl")
REPO = "kcooperlawson/deckos"
LABEL = "heal-report"


def asker():
    """(uid, home) of the person a root fix was run for (pkexec or sudo), else None."""
    import pwd
    uid = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
    if os.geteuid() != 0 or not (uid or "").isdigit():
        return None
    try:
        return int(uid), Path(pwd.getpwuid(int(uid)).pw_dir)
    except KeyError:
        return None


def record(recipe, result, finding="", path=None):
    """Remembers a fix on this PC: which recipe, for which problem (a System Doctor finding key), and how it went.
    A root fix is remembered for the person it ran for, in their file, which stays theirs."""
    who = None if path or os.environ.get("DECKOS_HEAL_HISTORY") else asker()
    path = Path(path or (who[1] / ".local/state/deckos/heal.jsonl" if who else HISTORY))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"time": int(time.time()), "recipe": recipe, "result": result, "finding": finding}) + "\n")
    if who:
        os.chown(path, who[0], -1)


def history(path=None):
    try:
        lines = Path(path or HISTORY).read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def hardware():
    """The few facts that tell PCs apart for a fix: no names, serials, ids or addresses (scrubbed again after)."""
    sys.path.insert(0, str(HERE.parent / "report"))
    import deckos_report as rep
    cpu = re.search(r"model name: (.*)", rep.cpu())
    # "VGA compatible controller [0300]: AMD [AMD/ATI] Navi 48 [Radeon RX 9070 XT] [1002:7550]": the name up to the ids
    gpus = re.findall(r"\[03(?:00|02|80)\]: (.*) \[[0-9a-f]{4}:[0-9a-f]{4}\]", rep.run(["lspci", "-nn"]))
    version = rep.read("/usr/share/deckos/version")
    return {"deckos": version if "unreadable" not in version else "?", "kernel": platform.release(),
            "cpu": cpu.group(1).strip() if cpu else "?", "gpu": "; ".join(gpus) or "?"}


def report_text(entry, hw):
    """The issue's title and body, scrubbed: what goes to GitHub, exactly as the person sees it first."""
    sys.path.insert(0, str(HERE.parent / "report"))
    import deckos_report as rep
    sys.path.insert(0, str(HERE))
    import heal
    r = heal.RECIPES.get(entry["recipe"], {})
    outcome = {"worked": "worked", "failed": "didn't work"}.get(entry["result"], "was applied (not yet confirmed)")
    title = f"[heal] {entry['finding'] or 'no finding'}: {entry['recipe']} {outcome}"
    body = "\n".join([
        "<!-- A DecKoOS fix report. Made by `deckos heal report`; nothing else was sent. -->",
        f"**Problem:** {entry['finding'] or '(none recorded)'}",
        f"**Fix tried:** `{entry['recipe']}` ({r.get('title', '?').split('{')[0].strip()})",
        f"**Result:** it {outcome}",
        "",
        f"**DecKoOS:** {hw['deckos']}  ·  **Kernel:** {hw['kernel']}",
        f"**Processor:** {hw['cpu']}",
        f"**Graphics:** {hw['gpu']}",
        "",
        f"<!-- heal: {json.dumps({'recipe': entry['recipe'], 'finding': entry['finding'], 'result': entry['result'], 'gpu': hw['gpu'], 'cpu': hw['cpu']})} -->",
    ])
    return rep.scrub(title), rep.scrub(body)


def issue_url(title, body):
    """A pre-filled new-issue page: the person reads it there and submits it themselves (or doesn't)."""
    # The repo takes issues through forms only (.github/ISSUE_TEMPLATE/heal.yml): its `report` field is filled here
    q = urllib.parse.urlencode({"template": "heal.yml", "title": title, "report": body})
    return f"https://github.com/{REPO}/issues/new?{q}"


def triage(issues):
    """Groups heal reports (GitHub issues with the heal-report label, as `gh issue list --json` gives them) by problem
    and fix: how many PCs, how often it worked, on which graphics vendors. Most-reported first."""
    groups = {}
    for issue in issues:
        m = re.search(r"<!-- heal: (\{.*?\}) -->", issue.get("body") or "")
        if not m:
            continue
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        key = (d.get("finding") or "?", d.get("recipe") or "?")
        g = groups.setdefault(key, {"finding": key[0], "recipe": key[1], "reports": 0, "worked": 0, "vendors": {},
                                    "issues": []})
        g["reports"] += 1
        g["worked"] += d.get("result") == "worked"
        gpu = (d.get("gpu") or "").lower()
        vendor = "amd" if "amd" in gpu or "radeon" in gpu else "nvidia" if "nvidia" in gpu else \
            "intel" if "intel" in gpu else "other"
        g["vendors"][vendor] = g["vendors"].get(vendor, 0) + 1
        g["issues"].append(issue.get("number"))
    return sorted(groups.values(), key=lambda g: (-g["reports"], g["finding"]))


def main(argv):
    if argv[:1] == ["outcome"] and len(argv) >= 3 and argv[2] in ("worked", "failed"):
        record(argv[1], argv[2], argv[3] if len(argv) > 3 else "")
        return 0
    if argv[:1] == ["history"]:
        for e in history()[-20:]:
            print(f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(e['time']))}  {e['recipe']:<24} {e['result']:<7} "
                  f"{e['finding']}")
        return 0
    if argv[:1] == ["report"]:
        h = history()
        if not h:
            print("No fixes yet: nothing to report.")
            return 0
        title, body = report_text(h[-1], hardware())
        print(f"This is everything the report contains:\n\n{title}\n\n{body}\n")
        if "--open" in argv:
            subprocess.Popen(["xdg-open", issue_url(title, body)])
            print("Opened on GitHub: read it there, and submit it if you're happy to.")
        else:
            print("To send it: deckos heal report --open (it opens on GitHub for you to check and submit).")
        return 0
    if argv[:1] == ["triage"]:
        out = subprocess.run(["gh", "issue", "list", "-R", REPO, "--label", LABEL, "--state", "open", "--limit", "500",
                              "--json", "number,title,body"], capture_output=True, text=True)
        if out.returncode != 0:
            print(out.stderr.strip() or "gh couldn't list the issues (gh auth login?)", file=sys.stderr)
            return 1
        groups = triage(json.loads(out.stdout or "[]"))
        if "--json" in argv:
            print(json.dumps(groups))
            return 0
        if not groups:
            print("No fix reports yet.")
        for g in groups:
            vendors = ", ".join(f"{v} {n}" for v, n in sorted(g["vendors"].items()))
            print(f"  {g['reports']:>3} PCs  {g['worked']}/{g['reports']} worked  {g['finding']} → {g['recipe']}  "
                  f"({vendors})  #{', #'.join(str(i) for i in g['issues'][:5])}")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
