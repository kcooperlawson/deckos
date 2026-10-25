#!/usr/bin/env python3
# The apps the "Pin an app" list offers: every visible .desktop file in the XDG data dirs (user ones
# win), as JSON [{name, icon, url, comment}] sorted by name. Run by main.qml when the list opens.
import json, os
from pathlib import Path

dirs = [os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))]
dirs += os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
dirs += [str(Path.home() / ".local/share/flatpak/exports/share"), "/var/lib/flatpak/exports/share"]

lang = os.environ.get("LANG", "").split(".")[0]
seen, apps = set(), []
for d in dirs:
    base = Path(d) / "applications"
    if not base.is_dir():
        continue
    for f in sorted(base.rglob("*.desktop")):
        fid = str(f.relative_to(base)).replace("/", "-")
        if fid in seen:
            continue
        seen.add(fid)
        entry, section = {}, None
        try:
            for line in f.read_text(errors="replace").splitlines():
                line = line.strip()
                if line.startswith("["):
                    section = line
                elif section == "[Desktop Entry]" and "=" in line:
                    k, v = line.split("=", 1)
                    entry.setdefault(k.strip(), v.strip())
        except OSError:
            continue
        if entry.get("Type") != "Application" or entry.get("NoDisplay") == "true" or entry.get("Hidden") == "true":
            continue
        name = entry.get(f"Name[{lang}]") or entry.get("Name")
        if not name:
            continue
        apps.append({"name": name, "icon": entry.get("Icon", "application-x-executable"),
                     "url": "applications:" + fid, "comment": entry.get("GenericName") or entry.get("Comment", "")})

apps.sort(key=lambda a: a["name"].lower())
print(json.dumps(apps))
