"""Every setting, in one searchable list: DecKoOS Hub's own pages, DecKoOS's actions (actions.toml) and the Plasma
panels DecKoOS doesn't redo, under plain names. The Hub's search and its "More settings" page read it, so the
Hub is the one place to start from. No Qt: tests/test_settings.py checks it.

An entry is {"title", "summary", "keywords", "icon", "group", "go"}; `go` is ("hub", PAGE) for a Hub page,
("plasma", KCM) for one of Plasma's panels (opened in System Settings) or ("action", ID).
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# DecKoOS Hub's own pages: what's on them, in the words people search with
HUB = [
    ("display", "Display fix", "Blackouts and flicker on Radeon cards, screen scale", "display",
     "blackout flicker screen monitor black fams scale resolution refresh"),
    ("gaming", "Gaming Mode", "Steam full screen, its resolution, VRR and HDR", "gaming",
     "steam big picture deck couch vrr freesync gsync hdr resolution refresh rate"),
    ("gaming", "Game performance", "CPU scheduler, FSR 4, shader cache, NTSYNC", "gauge",
     "scheduler lavd fsr upscaling shader cache ntsync performance fps stutter"),
    ("games", "Games", "Steam, Heroic and Lutris games, profiles and Game Doctor", "grid",
     "library play launch profile game doctor proton protondb crash"),
    ("drives", "Drives", "Windows drives, read-only drives, Move In", "drives",
     "ntfs windows disk drive mount read only fast startup move in"),
    ("aidev", "Local AI", "Ollama, choose a model, DecKoOS Assistant", "ai",
     "ai ollama model llm assistant gpt chat local claude code"),
    ("aidev", "Development", "Claude Code, DecKoOS Work, dev tools", "code",
     "code developer docker vscode work claude terminal"),
    ("system", "Updates", "Update DecKoOS and apps, automatic updates, test channel", "update",
     "update upgrade pacman automatic overnight channel testing"),
    ("system", "Snapshots and undo", "Go back to before an update, home snapshots", "snapshot",
     "snapshot undo rollback restore backup btrfs snapper"),
    ("system", "Firewall", "What's open to your network", "shield", "firewall ports network security open"),
    ("system", "Take my setup with me", "Save or bring in your DecKoOS setup", "download",
     "export import backup setup move new pc reinstall"),
    ("appearance", "Theme and colours", "Global theme, accent colour, wallpaper", "appearance",
     "theme colour color accent dark light wallpaper background look"),
    ("appearance", "Style", "Logo, corners and text size in DecKoOS apps", "sliders",
     "style corners rounded text size font bigger logo"),
    ("appearance", "Sounds", "DecKoOS sounds, Plasma's, or none", "volume", "sound sounds audio notification chime mute"),
    ("appearance", "Desktop layout", "Where the panels go, performance graphs", "panel-right",
     "layout panel taskbar dock classic graphs widget"),
    ("timeline", "Timeline", "What changed recently, and undo", "clock", "history changes undo recent log timeline"),
]

# Plasma's panels DecKoOS uses as they are, grouped; titles say what they're for
PLASMA = [
    ("Devices", "kcm_bluetooth", "Bluetooth", "Pair headphones, controllers and mice", "bluetooth",
     "bluetooth pair headphones earbuds controller wireless"),
    ("Devices", "kcm_pulseaudio", "Sound devices and volume", "Speakers, headset, microphone", "volume",
     "audio sound speakers headset microphone mic volume output input"),
    ("Devices", "kcm_mouse", "Mouse", "Speed, acceleration, buttons", "system", "mouse speed acceleration pointer buttons"),
    ("Devices", "kcm_touchpad", "Touchpad", "Tap to click, scrolling, gestures", "system",
     "touchpad trackpad tap scroll gesture laptop"),
    ("Devices", "kcm_keyboard", "Keyboard and layouts", "Layouts, repeat rate, NumLock", "keyboard",
     "keyboard layout language typing repeat numlock"),
    ("Devices", "kcm_gamecontroller", "Game controllers", "Test a controller's buttons and sticks", "gaming",
     "controller gamepad joystick test xbox playstation"),
    ("Devices", "kcm_printer_manager", "Printers", "Add and manage printers", "doc", "printer print scanner"),
    ("Devices", "kcm_kscreen", "Screens", "Arrangement, resolution, refresh rate, scale, HDR", "display",
     "monitor screen resolution refresh rate scale hdr arrange multiple displays"),
    ("Devices", "kcm_nightlight", "Night Light", "Warmer colours in the evening", "night",
     "night light blue light warm colour evening"),
    ("Network", "kcm_networkmanagement", "Wi-Fi and network connections", "Networks, VPN, hotspot", "wifi",
     "wifi wireless ethernet network vpn connection internet"),
    ("Network", "kcm_kaccounts", "Online accounts", "Google, Nextcloud and other accounts", "user",
     "account google nextcloud online cloud"),
    ("Network", "kcm_krdpserver", "Remote desktop", "Let another PC see and control this one", "network",
     "remote desktop rdp share screen control"),
    ("Desktop", "kcm_keys", "Keyboard shortcuts", "Change or add shortcuts", "keyboard", "shortcut hotkey keys bind"),
    ("Desktop", "kcm_kwin_virtualdesktops", "Virtual desktops", "Several desktops to switch between", "grid",
     "virtual desktops workspaces"),
    ("Desktop", "kcm_kwinoptions", "Window behaviour", "Focus, titlebar clicks, moving windows", "system",
     "window focus click titlebar move behaviour behavior"),
    ("Desktop", "kcm_kwinscreenedges", "Screen edges", "What happens at the corners", "display", "screen edge corner hot"),
    ("Desktop", "kcm_kwin_effects", "Desktop effects", "Animations and window effects", "star",
     "effects animation blur wobbly"),
    ("Desktop", "kcm_notifications", "Notifications", "Do Not Disturb, which apps notify", "bell",
     "notifications do not disturb popups alerts"),
    ("Desktop", "kcm_plasmasearch", "Search", "What the menu's search looks through", "search", "search krunner find"),
    ("Desktop", "kcm_fonts", "Fonts", "Desktop fonts and smoothing", "doc", "font fonts text size antialiasing"),
    ("Personal", "kcm_componentchooser", "Default apps", "Browser, email, file manager, terminal", "grid",
     "default apps browser email open with"),
    ("Personal", "kcm_filetypes", "File types", "Which app opens which file", "doc", "file type association open with"),
    ("Personal", "kcm_autostart", "Apps at login", "What starts when you log in", "play", "autostart startup login start"),
    ("Personal", "kcm_users", "Users", "Your account, password and picture", "user", "user account password avatar picture"),
    ("Personal", "kcm_access", "Accessibility", "Zoom, sticky keys, screen reader", "eye",
     "accessibility zoom magnifier screen reader sticky keys"),
    ("System", "kcm_regionandlang", "Language and region", "Language, number and date formats", "globe",
     "language region locale date format currency"),
    ("System", "kcm_clock", "Date and time", "Time zone and clock", "clock", "date time timezone clock"),
    ("System", "kcm_powerdevilprofilesconfig", "Power and sleep", "Screen off, sleep, power button", "power",
     "power sleep suspend battery screen off energy"),
    ("System", "kcm_about-distro", "About this PC", "Hardware and versions", "info", "about system info version hardware"),
]

PLASMA_GROUPS = ["Devices", "Network", "Desktop", "Personal", "System"]


def actions():
    sys.path.insert(0, str(HERE.parent / "actions"))
    try:
        import actions as acts
        return acts.load()
    except Exception:  # the list is a help, never a reason for the Hub not to start
        return []


KCMS = Path("/usr/lib/qt6/plugins/plasma/kcms")


def installed_kcm(kcm, root=KCMS):
    """A panel whose plugin isn't installed (no printer support, say) is left out, so nothing leads nowhere."""
    return not root.is_dir() or any((root / d / f"{kcm}.so").exists() for d in (".", "systemsettings",
                                                                               "systemsettings_qwidgets", "kinfocenter"))


def entries():
    out = [{"title": t, "summary": s, "keywords": k, "icon": i, "group": "DecKoOS Hub", "go": ("hub", page)}
           for page, t, s, i, k in HUB]
    out += [{"title": t, "summary": s, "keywords": k, "icon": i, "group": g, "go": ("plasma", kcm)}
            for g, kcm, t, s, i, k in PLASMA if installed_kcm(kcm)]
    for a in actions():
        out.append({"title": a["title"], "summary": a.get("summary", ""), "keywords": a.get("keywords", ""),
                    "icon": a.get("icon", "star"), "group": "Do it", "go": ("action", a["id"])})
    return out


def search(query, items=None, limit=12):
    """Best matches first: a title that starts with the words, then titles, then keywords and summaries."""
    words = [w for w in re.split(r"\W+", query.lower()) if w]
    if not words:
        return []
    scored = []
    for e in items if items is not None else entries():
        title, rest = e["title"].lower(), f"{e['keywords']} {e['summary']}".lower()
        score = 0
        for w in words:
            if re.search(rf"\b{re.escape(w)}", title):
                score += 3
            elif re.search(rf"\b{re.escape(w)}", rest):
                score += 1
            else:
                score = -1
                break
        if score > 0:
            score += 2 if title.startswith(words[0]) else 0
            score += 1 if e["go"][0] == "hub" else 0  # DecKoOS's own page first when it's a tie
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:limit]]


def plasma_command(kcm):
    """Opens one of Plasma's panels inside System Settings (kcmshell6 alone when that's all there is)."""
    if shutil.which("systemsettings"):
        return ["systemsettings", kcm]
    return ["kcmshell6", kcm]
