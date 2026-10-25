"""DecKoOS Store lookup for DecKoOS Menu: the Store apps a search matches that aren't installed, as JSON.

    store_find.py [--limit N] [--demo] -- TERM

Prints [{"key", "name", "summary", "icon", "source"}…]. Reads the slim index the Store writes
(~/.cache/deckos-store/menu-index.json); the first time there is none it builds the catalog, which
takes a few seconds (the menu runs this in the background, so nothing waits on it). No Qt: it has
to start fast, since it runs while you type.
"""
import json
import os
import sys
from pathlib import Path

from store_catalog import (CACHE, DEMO, MENU_INDEX, SOURCE_NAMES, SOURCE_ORDER, App, Catalog, Installed,
                           demo_apps)


def load_index():
    if DEMO:
        return [App(key=a.key, name=a.name, summary=a.summary, icon=a.icon, desktop_id=a.desktop_id,
                    sources=a.sources) for a in demo_apps()]
    try:
        if MENU_INDEX.stat().st_mtime >= (CACHE / "catalog.json").stat().st_mtime:
            return [App(**r) for r in json.loads(MENU_INDEX.read_text())]
    except (OSError, ValueError, TypeError):
        pass
    catalog = Catalog()
    catalog.load()  # (re)writes the index
    return list(catalog.apps.values())


def app_dirs():
    """Where installed apps' .desktop files live, Flatpak exports included."""
    data = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    dirs = [home, home / "flatpak/exports/share", Path("/var/lib/flatpak/exports/share")]
    dirs += [Path(d) for d in data.split(":") if d]
    return [d / "applications" for d in dirs if (d / "applications").is_dir()]


def repo_packages():
    """Installed package names, from pacman's database folders (name-version-release) without running pacman."""
    try:
        return {d.name.rsplit("-", 2)[0] for d in Path("/var/lib/pacman/local").iterdir() if d.is_dir()}
    except OSError:
        return set()


def main():
    args = sys.argv[1:]
    term = " ".join(args[args.index("--") + 1:]) if "--" in args else (args[-1] if args else "")
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 4
    catalog = Catalog()
    catalog.apps = {a.key: a for a in load_index()}

    if DEMO:
        inst = Installed()
        inst.refresh()
        have = inst.app_installed
    else:
        dirs, packages = app_dirs(), repo_packages()

        def have(app):
            ids = [app.desktop_id] + ([app.sources["flathub"] + ".desktop"] if "flathub" in app.sources else [])
            return app.sources.get("repo") in packages or any((d / i).exists() for d in dirs for i in ids if i)

    out = []
    for app in catalog.search(term):
        if have(app):
            continue
        source = next((s for s in SOURCE_ORDER if s in app.sources), None)
        out.append({"key": app.key, "name": app.name, "summary": app.summary, "icon": app.icon,
                    "source": SOURCE_NAMES.get(source, "")})
        if len(out) >= limit:
            break
    print(json.dumps(out))


if __name__ == "__main__":
    main()
