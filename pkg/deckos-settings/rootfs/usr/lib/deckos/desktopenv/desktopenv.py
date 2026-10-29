"""The desktop's environment for windows DecKoOS's background services open (Game Doctor, Care's questions, Vibe
mode's offer). A user service keeps the environment it started with, and the ones that start at login can start
before Plasma has told systemd where the screen is (WAYLAND_DISPLAY, DISPLAY): a window opened with that environment
has no display and Qt aborts. So the session's current values are read from systemd just before a window opens.
No Qt; tests/test_desktopenv.py checks it.
"""
import os
import subprocess

KEYS = ("WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION", "QT_QPA_PLATFORMTHEME", "KDE_FULL_SESSION")


def parse(text):
    """`systemctl --user show-environment` output as {name: value}, only the desktop's keys."""
    out = {}
    for line in text.splitlines():
        name, sep, value = line.partition("=")
        if sep and name in KEYS:
            out[name] = value
    return out


def env(base=None, systemd_text=None):
    """`base` (this process's environment) with the desktop's keys as the session has them now."""
    merged = dict(os.environ if base is None else base)
    if systemd_text is None:
        try:
            systemd_text = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True,
                                          text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            systemd_text = ""
    merged.update(parse(systemd_text))
    return merged
