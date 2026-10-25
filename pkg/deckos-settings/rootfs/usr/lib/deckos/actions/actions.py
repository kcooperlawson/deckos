"""DecKoOS actions: everything DecKoOS can do, from one list (/usr/share/deckos/actions.toml), so DecKoOS
Menu's search, `deckos do ID` and DecKoOS Assistant offer the same things the same way.

    actions.py find QUERY [--limit N]   matches as JSON, best first (DecKoOS Menu)
    actions.py run ID                   does it (detached: an app opens, a terminal shows the output)
    actions.py list [--json]            all of them
"""
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

CATALOG = Path(os.environ.get("DECKOS_ACTIONS") or "/usr/share/deckos/actions.toml")
if not CATALOG.exists():  # a checkout's list, for running from the repo
    CATALOG = Path(__file__).resolve().parents[3] / "share/deckos/actions.toml"


def load(path=None):
    data = tomllib.loads(Path(path or CATALOG).read_text())
    out = []
    for a in data.get("action", []):
        if a.get("id") and a.get("title") and isinstance(a.get("run"), list) and a["run"]:
            a.setdefault("how", "app")
            out.append(a)
    return out


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def score(action, query):
    """0 when it doesn't match; higher is better. Every word typed must start some word of the action."""
    q = words(query)
    if not q:
        return 0
    title, keys = words(action["title"]), words(action.get("keywords", "") + " " + action.get("summary", ""))
    total = 0
    for w in q:
        if any(t.startswith(w) for t in title):
            total += 3
        elif any(k.startswith(w) for k in keys):
            total += 1
        else:
            return 0
    if " ".join(title).startswith(" ".join(q)):
        total += 2
    return total


def find(query, limit=3, actions=None):
    ranked = sorted(((score(a, query), i, a) for i, a in enumerate(actions or load())), key=lambda x: (-x[0], x[1]))
    return [{k: a[k] for k in ("id", "title", "summary", "icon") if k in a} for s, _, a in ranked if s > 0][:limit]


def command(action):
    """The argv that does it: terminal actions open DecKoOS Terminal (Konsole if it's missing) and stay open."""
    if action["how"] == "terminal":
        term = "deckos-terminal" if subprocess.run(["which", "deckos-terminal"], capture_output=True).returncode == 0 \
            else "konsole"
        return [term, "--hold", "-e", *action["run"]]
    return list(action["run"])


def run(action_id, actions=None):
    action = next((a for a in actions or load() if a["id"] == action_id), None)
    if action is None:
        raise KeyError(f"no DecKoOS action called {action_id}")
    subprocess.Popen(command(action), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return action


def main(argv):
    if argv[:1] == ["find"] and len(argv) > 1:
        limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv[:-1] else 3
        query = " ".join(a for a in argv[1:] if a not in ("--limit", str(limit)) and a != "--")
        print(json.dumps(find(query, limit), ensure_ascii=False))
        return 0
    if argv[:1] == ["run"] and len(argv) == 2:
        try:
            run(argv[1])
        except KeyError as e:
            print(e.args[0], file=sys.stderr)
            return 2
        return 0
    if argv[:1] == ["list"]:
        acts = load()
        if "--json" in argv:
            print(json.dumps(acts, ensure_ascii=False))
        else:
            for a in acts:
                print(f"  {a['id']:<18} {a['title']}")
        return 0
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
