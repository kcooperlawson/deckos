"""Self-healing, phase 2 and 3 (docs/self-healing.md): what each fix did, reports a person chooses to send, and the
maintainer's grouping of them. Reports, never patches: what goes upstream is evidence (the problem, the fix tried,
whether it worked, a scrubbed hardware summary), and a person writes any new recipe.

Nothing is ever sent by DecKoOS: `report` shows the text and, if asked, opens a pre-filled GitHub issue in the
browser, where the person reads it and presses Submit themselves.

    heal_report.py outcome ID worked|failed [FINDING] | ask ID [FINDING] | history | report [--open] | triage [--json] |
                   draft N
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
    line = json.dumps({"time": int(time.time()), "recipe": recipe, "result": result, "finding": finding}) + "\n"
    if not who:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(line)
        return
    # Root writing into a home follows whatever links the home holds (heal.jsonl -> /etc/shadow): write as the person.
    import pwd
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([])
            os.setgid(pwd.getpwuid(who[0]).pw_gid)
            os.setuid(who[0])
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(line)
            os._exit(0)
        except BaseException:
            os._exit(1)
    os.waitpid(pid, 0)


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
        # Only problems: a report that doesn't name what was broken (a System Doctor finding) isn't grouped, so a
        # fix run on a whim, or a wish, never reaches drafting
        if not d.get("finding"):
            continue
        key = (d["finding"], d.get("recipe") or "?")
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


def ask(recipe, finding="", notify=None):
    """After a fix: "Did that fix it?" as a notification with two buttons; the answer goes in the history. Skipped
    when the person turned remembering off. Waits as long as it takes (some fixes need a restart to show)."""
    sys.path.insert(0, str(HERE))
    import heal
    if not heal.is_on("remember") or recipe not in heal.RECIPES:
        return None
    if notify is None and os.environ.get("DECKOS_HEAL_ASK") == "off":  # tests/check.sh: never on a real desktop
        return None
    title = heal.RECIPES[recipe]["title"].split("{")[0].strip() or recipe
    notify = notify or (lambda: subprocess.run(
        ["notify-send", "--app-name=DecKoOS", "--icon=deckos", "--expire-time=0", "--action=worked=Yes, fixed",
         "--action=failed=Not really", "Did that fix it?", f"{title}: telling DecKoOS helps it suggest the right fix."],
        capture_output=True, text=True).stdout.strip())
    answer = notify()
    if answer in ("worked", "failed"):
        record(recipe, answer, finding)
        return answer
    return None


DRAFTS = Path.home() / ".local/share/deckos/heal-drafts"

DRAFT_PROMPT = """You maintain DecKoOS's library of fixes. Reports from users' PCs were grouped:

{group}

Propose ONE recipe for the library, as JSON only (no other text), in exactly this shape:
{{"id": "lowercase-with-dashes", "title": "Short, plain, like a button", "why": "One plain sentence: when it helps",
  "root": true or false, "params": {{"name": "repo-package" | ["allowed", "values"] | ["int", min, max]}},
  "steps": [["program", "arg", "{{name}}"]]}}

Scope: a recipe repairs something that's broken (the problem above). Never a new feature, a tweak, a change of
look, a setting someone prefers or an extra app: for anything like that, answer {{"none": "not a fix"}}.
Rules: steps start with one of these programs: {programs}. A blank ({{name}}) is a whole argument, never part of one.
Nothing may touch sudo, polkit, PAM, SSH, users, passwords, the firewall, the bootloader or pacman's keys, and
nothing downloads from the internet. Prefer an existing recipe if one already fits: {existing}. If none can be written
within these rules, answer {{"none": "why"}}."""


def describe_group(g):
    vendors = ", ".join(f"{v} {n}" for v, n in sorted(g["vendors"].items()))
    return (f"Problem (System Doctor key): {g['finding']}\nFix people tried: {g['recipe']}\n"
            f"PCs: {g['reports']}, it worked on {g['worked']}\nGraphics vendors: {vendors}")


def parse_draft(reply):
    """A model's reply to a recipe: the first JSON object in it, ["int", a, b] turned into the library's tuple."""
    m = re.search(r"\{.*\}", reply or "", re.S)
    if not m:
        raise ValueError("no JSON in the answer")
    d = json.loads(m.group(0))
    if "none" in d:
        return None, str(d["none"])
    params = {k: (tuple(v) if isinstance(v, list) and v[:1] == ["int"] else v) for k, v in (d.get("params") or {}).items()}
    rid = d.pop("id", "")
    return rid, {"title": d.get("title"), "why": d.get("why"), "root": d.get("root"), "params": params,
                 "steps": d.get("steps")}


def draft(group, ask, save=True):
    """Asks a model (ask(prompt) -> text) for a recipe for one triage group; returns (id, recipe) once the recipe
    passes heal.check_recipe, saved for a person to review. Never added to the library by itself."""
    sys.path.insert(0, str(HERE))
    import heal
    if not group.get("finding") or group["finding"] == "?":
        raise heal.Refused("drafts are only for problems System Doctor found, not wishes or tweaks")
    prompt = DRAFT_PROMPT.format(group=describe_group(group), programs=", ".join(sorted(heal.PROGRAMS)),
                                 existing=", ".join(heal.RECIPES))
    rid, recipe = parse_draft(ask(prompt))
    if rid is None:
        raise heal.Refused(f"the model found no fix within the rules: {recipe}")
    if rid in heal.RECIPES:
        return rid, heal.RECIPES[rid]  # an existing recipe fits: nothing new to review
    heal.check_recipe(rid, recipe)
    if save:
        DRAFTS.mkdir(parents=True, exist_ok=True)
        (DRAFTS / f"{rid}.json").write_text(json.dumps({"id": rid, "group": group, **recipe}, indent=2))
    return rid, recipe


def local_model(prompt):
    sys.path.insert(0, str(HERE.parent / "assistant"))
    import assistant
    model = assistant.pick_model()
    return assistant.chat(model, [{"role": "user", "content": prompt}]).get("content", "")


def main(argv):
    sys.path.insert(0, str(HERE))
    import heal
    if argv[:1] == ["outcome"] and len(argv) >= 3 and argv[2] in ("worked", "failed"):
        if heal.is_on("remember"):
            record(argv[1], argv[2], argv[3] if len(argv) > 3 else "")
        return 0
    if argv[:1] == ["ask"] and len(argv) > 1:
        ask(argv[1], argv[2] if len(argv) > 2 else "")
        return 0
    if argv[:1] == ["report"] and not heal.is_on("reports"):
        print("Fix reports are turned off (DecKoOS Hub > Health > Fixes, or: deckos heal settings reports on).")
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
    if argv[:1] == ["draft"] and len(argv) > 1 and argv[1].isdigit():
        sys.path.insert(0, str(HERE))
        import heal
        out = subprocess.run(["gh", "issue", "list", "-R", REPO, "--label", LABEL, "--state", "open", "--limit", "500",
                              "--json", "number,title,body"], capture_output=True, text=True)
        groups = triage(json.loads(out.stdout or "[]")) if out.returncode == 0 else []
        n = int(argv[1])
        if not 1 <= n <= len(groups):
            print(f"no group {n} (deckos heal triage lists {len(groups)})", file=sys.stderr)
            return 1
        try:
            rid, recipe = draft(groups[n - 1], local_model)
        except (heal.Refused, ValueError) as e:
            print(f"no draft: {e}", file=sys.stderr)
            return 3
        print(f"Draft '{rid}' passed the checks. To add it, review it and paste into RECIPES in heal.py:\n")
        print(f'    "{rid}": {recipe!r},')
        print(f"\n(saved: {DRAFTS / (rid + '.json')})")
        return 0
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
