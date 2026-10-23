"""What DeckOS Welcome reads on top of the Hub's hub_system: screens and their scale, colour
schemes, controllers, Spotify, and whether this user has seen the welcome.

Apart from the welcome's own files in ~/.config/deckos it only reads, like hub_system; changes
go through `deckos`, pkexec or Plasma's own tools. `--demo` swaps in canned data.
"""
import json
import os
import shutil
from pathlib import Path

import hub_system as sysinfo
from hub_system import DEMO, kconfig, read, run

# The launcher checks welcome-done before starting Python, so a seen welcome costs nothing at login.
# welcome-startup remembers "Show at startup", which keeps welcome-done away.
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "deckos"
DONE_FILE = CONFIG / "welcome-done"
STARTUP_FILE = CONFIG / "welcome-startup"


def show_at_startup():
    return STARTUP_FILE.exists()


def set_show_at_startup(on):
    if DEMO:
        return
    try:
        CONFIG.mkdir(parents=True, exist_ok=True)
        if on:
            STARTUP_FILE.touch()
            DONE_FILE.unlink(missing_ok=True)
        else:
            STARTUP_FILE.unlink(missing_ok=True)
            DONE_FILE.write_text(sysinfo.deckos_version() + "\n")
    except OSError:
        pass


def mark_seen():
    """After the first look the welcome stops opening at login, unless "Show at startup" is ticked."""
    if not show_at_startup():
        set_show_at_startup(False)


# ------------------------------------------------------------------ screens

SCALES = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]


def screens():
    """[{name, label, width, height, refresh, scale, primary}] for connected, enabled outputs."""
    if DEMO:
        return [dict(name="DP-1", label="Odyssey G70B", width=3840, height=2160, refresh=144, scale=1.5, primary=True),
                dict(name="DP-2", label="LG ULTRAGEAR", width=2560, height=1440, refresh=165, scale=1.0, primary=False)]
    try:
        data = json.loads(run(["kscreen-doctor", "-j"]) or "{}")
    except ValueError:
        return []
    names = dict(sysinfo.monitors())  # EDID names from `deckos display monitors`, where kscreen has none
    out = []
    for o in data.get("outputs", []):
        if not (o.get("connected") and o.get("enabled")):
            continue
        mode = next((m for m in o.get("modes", []) if str(m.get("id")) == str(o.get("currentModeId"))), {})
        size = mode.get("size") or {}
        out.append(dict(name=o.get("name", ""), label=names.get(o.get("name", "")) or o.get("name", "Screen"),
                        width=size.get("width", 0), height=size.get("height", 0),
                        refresh=round(mode.get("refreshRate", 0)), scale=float(o.get("scale", 1.0)),
                        primary=o.get("priority") == 1 or bool(o.get("primary"))))
    return sorted(out, key=lambda s: not s["primary"])


# ------------------------------------------------------------------ colours

def color_schemes():
    """(dark scheme, light scheme or None): DeckOS is dark; light uses a DeckOS light scheme if one
    is installed, else Breeze Light."""
    have = {f.stem for d in sysinfo._dirs("color-schemes") if d.is_dir() for f in d.glob("*.colors")}
    if DEMO:
        have.add("BreezeLight")
    light = next((n for n in ("DeckOSLight", "BreezeLight") if n in have), None)
    return "DeckOS", light


def current_scheme():
    return kconfig("kdeglobals", "General", "ColorScheme", "DeckOS")


# ------------------------------------------------------------------ controllers

# Microsoft's Xbox Wireless Adapters (USB ids); the xone driver runs them.
XBOX_ADAPTERS = {("045e", "02e6"), ("045e", "02fe"), ("045e", "02f9"), ("045e", "091e")}


def xone():
    """(driver installed, driver loaded, adapter plugged in) for the Xbox Wireless Adapter."""
    if DEMO:
        return True, True, False
    installed = any(Path("/usr/src").glob("xone*")) or bool(run(["pacman", "-Qq", "xone-dkms"]))
    loaded = any(Path("/sys/module").glob("xone*"))
    plugged = any((read(d / "idVendor"), read(d / "idProduct")) in XBOX_ADAPTERS
                  for d in Path("/sys/bus/usb/devices").glob("*") if (d / "idVendor").exists())
    return installed, loaded, plugged


# ------------------------------------------------------------------ extras

SPOTIFY_DIRS = [Path.home() / ".local/share/spotify-launcher/install/usr/share/spotify", Path("/opt/spotify"),
                Path("/usr/share/spotify"), Path("/var/lib/flatpak/app/com.spotify.Client"),
                Path.home() / ".local/share/flatpak/app/com.spotify.Client"]


def spotify_installed():
    return DEMO or shutil.which("spotify") is not None or any(d.is_dir() for d in SPOTIFY_DIRS)


def gaming_conf():
    """Gaming Mode settings: system defaults with the user's own on top (as the Hub reads them)."""
    return {**sysinfo.conf("/etc/deckos/gaming.conf"), **sysinfo.conf(Path.home() / ".config/deckos/gaming.conf")}
