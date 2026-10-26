"""DecKoOS fixes, the safe way: a library of vetted recipes. An AI (DecKoOS Assistant, System Doctor's explain) may
choose a recipe and fill in its blanks; it never writes a command. Every blank is checked against an allow-list (a
package from the official repos, a service from a short list, a number in range), every finished command is
checked against a deny list (sudo, polkit, PAM, SSH, passwords, the firewall), and fixes that need root take a
"before" snapshot first and go on the timeline, where Undo puts the whole system back.

New recipes are written by people and reviewed like any code: that's the line between "self-healing" and an AI
with root. No Qt; tests/test_heal.py throws hostile input at it.

    heal.py list [--json] | plan ID [KEY=VALUE...] | apply ID [KEY=VALUE...] [--finding=KEY]   (root recipes: as root)
    heal.py outcome ID worked|failed [FINDING] | history | report [--open] | triage    (heal_report.py)
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The blanks a recipe may have, and what fills them
USER_UNITS = ["plasma-plasmashell.service", "pipewire.service", "pipewire-pulse.service", "wireplumber.service",
              "deckos-visualizer.service", "deckos-modes.service", "deckos-care.service", "deckos-gamedoctor.service"]
SYSTEM_UNITS = ["NetworkManager.service", "bluetooth.service", "power-profiles-daemon.service",
                "systemd-timesyncd.service", "ollama.service", "deckos-gpu.service", "deckos-kids-time.service"]

RECIPES = {
    "install-package": {
        "title": "Install {package}", "why": "Something on this PC needs it and it isn't installed",
        "params": {"package": "repo-package"}, "root": True,
        "steps": [["pacman", "-S", "--needed", "--noconfirm", "{package}"]]},
    "repair-package": {
        "title": "Reinstall {package}", "why": "Its files are missing or damaged; reinstalling puts them back",
        "params": {"package": "repo-package"}, "root": True,
        "steps": [["pacman", "-S", "--noconfirm", "{package}"]]},
    "restart-user-service": {
        "title": "Restart {unit}", "why": "It stopped working; starting it again usually fixes that",
        "params": {"unit": USER_UNITS}, "root": False,
        "steps": [["systemctl", "--user", "restart", "{unit}"]]},
    "restart-system-service": {
        "title": "Restart {unit}", "why": "It stopped working; starting it again usually fixes that",
        "params": {"unit": SYSTEM_UNITS}, "root": True,
        "steps": [["systemctl", "restart", "{unit}"]]},
    "skip-network-wait": {
        "title": "Don't wait for the network at start-up", "why": "Starting up waits for the network, which a desktop "
        "doesn't need", "params": {}, "root": True,
        "steps": [["systemctl", "disable", "NetworkManager-wait-online.service"]]},
    "display-fix-level": {
        "title": "Display fix: level {level}", "why": "Screens that blink black on Radeon cards (takes effect after a "
        "restart)", "params": {"level": ("int", 0, 5)}, "root": True,
        "steps": [["deckos", "display", "set", "{level}"]]},
    "nvidia-driver": {
        "title": "Set up the NVIDIA driver", "why": "The NVIDIA card has no driver, or the wrong one",
        "params": {}, "root": True,
        "steps": [["pacman", "-S", "--needed", "--noconfirm", "chwd"], ["chwd", "-a"]]},
    "intel-microcode": {
        "title": "Install Intel's microcode", "why": "13th/14th gen Intel processors need it to stay stable",
        "params": {}, "root": True,
        "steps": [["pacman", "-S", "--needed", "--noconfirm", "intel-ucode"]]},
    "clear-package-cache": {
        "title": "Clear old package downloads", "why": "The drive is nearly full", "params": {}, "root": True,
        "steps": [["paccache", "-rk1"]]},
    "relink-drives": {
        "title": "Find your Windows drives again", "why": "A drive isn't mounted", "params": {}, "root": True,
        "steps": [["deckos", "drives", "rescan"]]},
    "undo-update": {
        "title": "Undo update {snapshot}", "why": "Something broke after an update (from the next start)",
        "params": {"snapshot": ("int", 1, 999999)}, "root": True, "snapshot": False,  # it is the snapshot
        "steps": [["deckos", "undo", "{snapshot}"]]},
    "clear-shader-cache": {
        "title": "Clear the shader cache", "why": "Games stutter or show glitches after a driver update; the cache "
        "is rebuilt as you play", "params": {}, "root": False,
        "steps": [["find", "{home}/.cache/mesa_shader_cache", "-mindepth", "1", "-delete"]]},
    "rebuild-font-cache": {
        "title": "Rebuild the font list", "why": "Text shows in the wrong font or as boxes", "params": {}, "root": False,
        "steps": [["fc-cache", "-f"]]},
    "repair-flatpaks": {
        "title": "Repair Flathub apps", "why": "A Flathub app won't start or update", "params": {}, "root": False,
        "steps": [["flatpak", "repair", "--user"]]},
}

# Second wall: whatever a recipe says, never these
DENY = re.compile(r"sudoers|polkit|pam\.d|/etc/(shadow|passwd|group|gshadow)|\bssh|authorized_keys|firewall|nft\b|"
                  r"iptables|usermod|useradd|passwd|chmod|chown|visudo|curl|wget|\bsh\b|bash|eval|pacman\.conf|"
                  r"mirrorlist|pacman-key|gpg|/boot|grub|\.\.|[;&|`$<>]|://|\.pkg\.tar")
PKG_RE = re.compile(r"^[a-z0-9@][a-z0-9@._+-]{0,99}$")


# The programs a recipe may run: a new one is a code change for a person to review, never something a draft adds
# and what each may do: its first argument. pacman only installs from the official repos (-S), never -U (a file or
# URL) or -R; systemctl only starts things; deckos only its fix commands. Checked on every run, not just for drafts.
PROGRAMS = {"pacman": {"-S"}, "systemctl": {"restart", "start", "enable", "disable", "--user"},
            "deckos": {"display", "drives", "undo"}, "chwd": {"-a"}, "paccache": {"-rk1"}, "find": None,
            "fc-cache": {"-f"}, "flatpak": {"repair"}}
ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
LITERAL_RE = re.compile(r"^[A-Za-z0-9@%+=:,./_-]+$")


class Refused(Exception):
    """A recipe that doesn't exist, a blank that doesn't fit, or a command on the deny list."""


def repo_package(name, check=None):
    """A package from the official repos (pacman's sync databases): never the AUR, never a file or URL."""
    if not PKG_RE.match(name or ""):
        raise Refused(f"'{name}' isn't a package name")
    check = check or (lambda n: subprocess.run(["pacman", "-Si", "--", n], capture_output=True).returncode == 0)
    if not check(name):
        raise Refused(f"'{name}' isn't in the official repositories")
    return name


def fill(spec, value, check=None):
    if spec == "repo-package":
        return repo_package(str(value), check)
    if isinstance(spec, list):
        if value not in spec:
            raise Refused(f"'{value}' isn't one of: {', '.join(spec)}")
        return value
    if isinstance(spec, tuple) and spec[0] == "int":
        if not re.fullmatch(r"\d{1,7}", str(value)) or not spec[1] <= int(value) <= spec[2]:
            raise Refused(f"'{value}' isn't a number from {spec[1]} to {spec[2]}")
        return str(int(value))
    raise Refused("unknown blank")


def check_recipe(rid, r):
    """A recipe's shape, whoever wrote it (the library's are checked by the tests; a model's draft must pass too):
    a known program first, blanks only as whole arguments ({name}, or {home} at the start of a path), blanks of a
    known kind, nothing on the deny list with sample values in. Raises Refused with the reason."""
    if not ID_RE.match(rid or ""):
        raise Refused(f"'{rid}' isn't a recipe name (lowercase words with dashes)")
    if not isinstance(r, dict) or not isinstance(r.get("title"), str) or not isinstance(r.get("why"), str):
        raise Refused("a recipe needs a title and a why")
    if not isinstance(r.get("root"), bool):
        raise Refused("a recipe must say whether it needs root")
    params = r.get("params")
    if not isinstance(params, dict):
        raise Refused("params must be a mapping")
    samples = {}
    for name, spec in params.items():
        if not re.fullmatch(r"[a-z]{2,20}", name) or name == "home":
            raise Refused(f"'{name}' isn't a blank name")
        if spec == "repo-package":
            samples[name] = "vlc"
        elif isinstance(spec, list) and spec and all(isinstance(x, str) and LITERAL_RE.match(x) for x in spec):
            samples[name] = spec[0]
        elif isinstance(spec, tuple) and len(spec) == 3 and spec[0] == "int" and all(isinstance(x, int) for x in spec[1:]) \
                and 0 <= spec[1] <= spec[2] <= 10_000_000:
            samples[name] = str(spec[1])
        else:
            raise Refused(f"blank '{name}' must be a repo package, a list of plain words, or a number range")
    steps = r.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > 4:
        raise Refused("a recipe has 1 to 4 steps")
    for step in steps:
        if not isinstance(step, list) or not step or not all(isinstance(x, str) for x in step):
            raise Refused("each step is a list of words")
        if step[0] not in PROGRAMS:
            raise Refused(f"'{step[0]}' isn't one of the programs fixes may run ({', '.join(sorted(PROGRAMS))})")
        for part in step:
            if re.fullmatch(r"\{[a-z]+\}", part):
                if part[1:-1] not in params:
                    raise Refused(f"{part} isn't one of this recipe's blanks")
            elif part.startswith("{home}/"):
                if not LITERAL_RE.match(part[len("{home}/"):]):
                    raise Refused(f"'{part}' isn't a plain path")
            elif "{" in part or not LITERAL_RE.match(part):
                raise Refused(f"'{part}': a blank must be a whole word, and words plain")
    with patch_recipes({rid: r}):
        plan(rid, samples, check=lambda _n: True, home="/home/someone")
    return True


class patch_recipes:
    """Plans a recipe that isn't in the library (a draft), for check_recipe."""

    def __init__(self, extra):
        self.extra = extra

    def __enter__(self):
        self.saved = {k: RECIPES.get(k) for k in self.extra}
        RECIPES.update(self.extra)

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                RECIPES.pop(k, None)
            else:
                RECIPES[k] = v


def plan(recipe_id, values=None, check=None, home=None):
    """{"id", "title", "why", "root", "snapshot", "steps"}: the finished commands, every blank checked. Raises Refused."""
    r = RECIPES.get(recipe_id)
    if r is None:
        raise Refused(f"there's no DecKoOS fix called '{recipe_id}'")
    values = dict(values or {})
    extra = set(values) - set(r["params"])
    if extra:
        raise Refused(f"'{recipe_id}' has no {', '.join(sorted(extra))}")
    filled = {k: fill(spec, values.get(k), check) for k, spec in r["params"].items()}
    filled["home"] = str(home or Path.home())
    steps = [[part.format(**filled) for part in step] for step in r["steps"]]
    for step in steps:
        allowed = PROGRAMS.get(step[0], set())
        if step[0] not in PROGRAMS or (allowed is not None and (len(step) < 2 or step[1] not in allowed)):
            raise Refused(f"refused: '{' '.join(step[:2])}' isn't something a fix may run")
        joined = " ".join(step).replace(filled["home"], "~")
        if DENY.search(joined):
            raise Refused(f"refused: '{joined}' touches something no fix may")
    return {"id": recipe_id, "title": r["title"].format(**filled), "why": r["why"], "root": r["root"],
            "snapshot": r["root"] and r.get("snapshot", True), "steps": steps}


def snapshot_before(title):
    """A btrfs "before" snapshot (snapper pre), so `deckos undo N` can put the whole system back. Its number, or None."""
    out = subprocess.run(["snapper", "--no-dbus", "-c", "root", "create", "-t", "pre", "-p", "-c", "number",
                          "-d", f"Before DecKoOS fix: {title}"], capture_output=True, text=True)
    return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip().isdigit() else None


def remember(recipe, result, finding=""):
    try:
        sys.path.insert(0, str(HERE))
        import heal_report
        heal_report.record(recipe, result, finding)
    except Exception:  # remembering is a help; a fix never fails over it
        pass


def apply(p, finding=""):
    if p["root"] and os.geteuid() != 0:
        raise Refused("this fix needs administrator rights: run it through pkexec deckos heal apply")
    pre = snapshot_before(p["title"]) if p["snapshot"] else None
    for step in p["steps"]:
        r = subprocess.run(step)
        if r.returncode != 0:
            remember(p["id"], "failed", finding)
            raise Refused(f"'{' '.join(step)}' failed (exit {r.returncode})"
                          + (f"; sudo deckos undo {pre} puts things back" if pre else ""))
    try:
        sys.path.insert(0, str(HERE.parent / "pulse"))
        import pulse
        pulse.emit("care", f"Fixed: {p['title']}", detail=p["why"], app="DecKoOS",
                   undo=["deckos", "undo", str(pre)] if pre else None)
    except Exception:
        pass
    remember(p["id"], "applied", finding)
    return pre


def parse(args):
    out = {}
    for a in args:
        k, sep, v = a.partition("=")
        if not sep:
            raise Refused(f"'{a}': blanks are KEY=VALUE")
        out[k] = v
    return out


def main(argv):
    try:
        if argv[:1] == ["list"]:
            if "--json" in argv:
                print(json.dumps({k: {"title": r["title"], "why": r["why"], "root": r["root"],
                                      "params": {p: (s if isinstance(s, list) else str(s)) for p, s in r["params"].items()}}
                                  for k, r in RECIPES.items()}))
            else:
                for k, r in RECIPES.items():
                    blanks = " ".join(f"{p}=…" for p in r["params"])
                    print(f"  {k:<24} {r['title']}  {blanks}")
            return 0
        if argv[:1] in (["outcome"], ["history"], ["report"], ["triage"], ["draft"]):
            sys.path.insert(0, str(HERE))
            import heal_report
            return heal_report.main(argv)
        if argv[:1] in (["plan"], ["apply"]) and len(argv) > 1:
            finding = next((a.split("=", 1)[1] for a in argv[2:] if a.startswith("--finding=")), "")
            p = plan(argv[1], parse([a for a in argv[2:] if not a.startswith("--finding=")]))
            if argv[0] == "plan":
                print(json.dumps(p))
                return 0
            pre = apply(p, finding)
            print(f"done: {p['title']}" + (f" (undo: sudo deckos undo {pre})" if pre else ""))
            return 0
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
    print(__doc__.split("\n\n")[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
