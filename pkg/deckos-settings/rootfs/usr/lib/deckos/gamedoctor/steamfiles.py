"""Steam's own files, read and written the way Steam does: game names, launch options, Proton choice.

Steam keeps per-game launch options in userdata/<id>/config/localconfig.vdf and per-game compatibility
tools (Proton versions) in config/config.vdf, in Valve's KeyValues text format. Steam rewrites both when
it exits, so anything written here must be written while Steam is closed (steam_running(), close_steam()).
Every write keeps the previous file as NAME.deckos-bak.
"""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

STEAM = Path(os.environ.get("DECKOS_STEAM_ROOT") or Path.home() / ".local/share/Steam")


# ------------------------------------------------------------------ KeyValues (VDF)

TOKEN = re.compile(r'\s*(?:(//[^\n]*)|"((?:[^"\\]|\\.)*)"|([{}])|([^\s{}"]+))', re.S)


def _unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def loads(text):
    """KeyValues text to nested dicts (insertion order kept, so a dump writes it back the same way)."""
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip():
                raise ValueError(f"unreadable VDF at offset {pos}")
            break
        pos = m.end()
        if m.group(1) is not None:  # a comment
            continue
        if m.group(2) is not None:
            tokens.append(("s", _unescape(m.group(2))))
        elif m.group(3):
            tokens.append((m.group(3), None))
        elif m.group(4):
            tokens.append(("s", m.group(4)))
    stack, key = [{}], None
    for kind, value in tokens:
        if kind == "s":
            if key is None:
                key = value
            else:
                stack[-1][key] = value
                key = None
        elif kind == "{":
            if key is None:
                raise ValueError("a block without a name")
            child = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        else:  # }
            if len(stack) == 1:
                raise ValueError("unbalanced braces")
            stack.pop()
    if len(stack) != 1 or key is not None:
        raise ValueError("unbalanced VDF")
    return stack[0]


def dumps(data, depth=0):
    out = []
    pad = "\t" * depth
    for k, v in data.items():
        if isinstance(v, dict):
            out.append(f'{pad}"{_escape(k)}"\n{pad}{{\n{dumps(v, depth + 1)}{pad}}}\n')
        else:
            out.append(f'{pad}"{_escape(k)}"\t\t"{_escape(str(v))}"\n')
    return "".join(out)


def read(path):
    return loads(Path(path).read_text(encoding="utf-8", errors="replace"))


def write(path, data):
    path = Path(path)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".deckos-bak"))
    tmp = path.with_name(path.name + ".deckos-tmp")
    tmp.write_text(dumps(data), encoding="utf-8")
    tmp.replace(path)


def _ci(d, *keys):
    """d[k1][k2]... matching keys case-insensitively (Steam isn't consistent), creating dicts on the way."""
    for k in keys:
        found = next((x for x in d if x.lower() == k.lower()), None)
        if found is None:
            d[k] = {}
            found = k
        d = d[found]
    return d


# ------------------------------------------------------------------ games, tools, users

def libraries():
    libs = [STEAM]
    try:
        for entry in read(STEAM / "steamapps/libraryfolders.vdf").get("libraryfolders", {}).values():
            if isinstance(entry, dict) and entry.get("path"):
                libs.append(Path(entry["path"]))
    except (OSError, ValueError):
        pass
    return list(dict.fromkeys(libs))


def game(appid):
    """{name, installdir, library, compatdata} for an installed game, or None."""
    for lib in libraries():
        manifest = lib / f"steamapps/appmanifest_{appid}.acf"
        try:
            state = read(manifest).get("AppState", {})
        except (OSError, ValueError):
            continue
        return {"appid": str(appid), "name": state.get("name", f"App {appid}"),
                "installdir": lib / "steamapps/common" / state.get("installdir", ""),
                "library": lib, "compatdata": lib / f"steamapps/compatdata/{appid}"}
    return None


def users():
    return [d for d in (STEAM / "userdata").glob("*") if d.name.isdigit() and (d / "config/localconfig.vdf").exists()]


def launch_options(appid):
    for u in users():
        try:
            apps = _ci(read(u / "config/localconfig.vdf"), "UserLocalConfigStore", "Software", "Valve", "Steam", "apps")
        except (OSError, ValueError):
            continue
        app = next((v for k, v in apps.items() if k == str(appid) and isinstance(v, dict)), None)
        if app and app.get("LaunchOptions"):
            return app["LaunchOptions"]
    return ""


def set_launch_options(appid, options):
    """For every Steam user on this PC. Steam must be closed."""
    for u in users():
        path = u / "config/localconfig.vdf"
        data = read(path)
        apps = _ci(data, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps")
        app = apps.setdefault(str(appid), {})
        if options:
            app["LaunchOptions"] = options
        else:
            app.pop("LaunchOptions", None)
        write(path, data)


def compat_tools():
    """{internal name: display name} for the Proton versions and other tools Steam can use."""
    tools = {}
    for base in (STEAM / "compatibilitytools.d", Path("/usr/share/steam/compatibilitytools.d")):
        for d in base.glob("*"):
            try:
                for name, info in read(d / "compatibilitytool.vdf").get("compatibilitytools", {}).get(
                        "compat_tools", {}).items():
                    tools[name] = info.get("display_name", name) if isinstance(info, dict) else name
            except (OSError, ValueError):
                continue
    for lib in libraries():
        for d in (lib / "steamapps/common").glob("Proton*"):
            if (d / "proton").exists():
                internal = "proton_experimental" if "Experimental" in d.name else \
                    "proton_" + re.sub(r"[^0-9]", "", d.name.split()[-1])[:2]
                tools.setdefault(internal, d.name)
    return tools


def compat_tool(appid):
    try:
        mapping = _ci(read(STEAM / "config/config.vdf"), "InstallConfigStore", "Software", "Valve", "Steam",
                      "CompatToolMapping")
    except (OSError, ValueError):
        return ""
    entry = mapping.get(str(appid))
    return entry.get("name", "") if isinstance(entry, dict) else ""


def set_compat_tool(appid, tool):
    """Pin a game to a compatibility tool ('' for Steam's default). Steam must be closed."""
    path = STEAM / "config/config.vdf"
    data = read(path)
    mapping = _ci(data, "InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping")
    if tool:
        mapping[str(appid)] = {"name": tool, "config": "", "priority": "250"}
    else:
        mapping.pop(str(appid), None)
    write(path, data)


# ------------------------------------------------------------------ Steam itself

def steam_running():
    return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0


def close_steam(timeout=60):
    """Ask Steam to quit and wait for it, so its config files can be written. True once it's gone."""
    if not steam_running():
        return True
    subprocess.Popen(["steam", "-shutdown"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not steam_running():
            time.sleep(1)  # its last config writes
            return True
        time.sleep(0.5)
    return False


def start_steam(url=None):
    subprocess.Popen(["steam", "-silent"] + ([url] if url else []), stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
