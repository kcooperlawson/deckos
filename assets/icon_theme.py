"""Generates the DeckOS icon theme's own icons: app icons for the everyday system and KDE apps, and file
type icons. Everything else (and every brand's own logo: Firefox, Steam, Discord...) comes from
Papirus-Dark, which the theme inherits; the PKGBUILD adds Papirus' places in the DeckOS blue.

App icons are a "plate": a rounded tile in the app's colour, lit from the top, with the DeckOS line glyph in
white and four small screw heads (the brand motif). File type icons are a slate sheet with a folded corner,
a glyph for what's inside and a coloured band with the type's name (outlined from Inter, so no font is
needed when they're drawn).

    python assets/icon_theme.py            # writes pkg/deckos-settings/rootfs/usr/share/icons/DeckOS/scalable
    python assets/icon_theme.py --sheet    # and assets/icon-theme-preview.png (needs PySide6)
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from icons import ICONS  # noqa: E402
from generate import INTER, text_path  # noqa: E402

OUT = HERE.parent / "pkg/deckos-settings/rootfs/usr/share/icons/DeckOS/scalable"

# Glyphs only these icons need (24-unit grid, 1.75 stroke, like assets/icons.py)
GLYPHS = dict(ICONS)
GLYPHS.update({
    "archive": '<rect x="3.5" y="4" width="17" height="4.5" rx="1"/><path d="M5 8.5v10a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-10"/><path d="M10 12h4"/>',
    "camera": '<path d="M4.5 7.5h3l1.5-2.5h6l1.5 2.5h3a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18V9a1.5 1.5 0 0 1 1.5-1.5z"/><circle cx="12" cy="13" r="3.5"/>',
    "book": '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5z"/><path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5z"/>',
    "chart": '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M7.5 15l3.5-4 3 2.5 5-6"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "wallet": '<rect x="3.5" y="6" width="17" height="13" rx="2"/><path d="M15 12.5h5.5M6 6l9-2.5 1 2.5"/>',
    "phone": '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 17.5h2"/>',
    "palette": '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.4 0 2-1 1.5-2.2-.5-1.2.3-2.3 1.6-2.3H17a3.5 3.5 0 0 0 3.5-3.5C20.5 7 16.7 3.5 12 3.5z"/><circle cx="8" cy="11" r=".9"/><circle cx="11.5" cy="7.5" r=".9"/><circle cx="15.5" cy="9" r=".9"/>',
    "ruler": '<path d="M3.5 15.5l12-12 5 5-12 12z"/><path d="M7.5 11.5l2 2M10.5 8.5l2 2M13.5 5.5l2 2"/>',
    "broom": '<path d="M14 4l6 6"/><path d="M17 7l-6.5 6.5"/><path d="M10.5 13.5c-3-1-5.5 1-6.5 6.5 5.5-1 7.5-3.5 6.5-6.5z"/>',
    "char": '<path d="M6 19l6-14 6 14"/><path d="M8.5 13.5h7"/>',
    "pie": '<path d="M12 3.5v8.5h8.5A8.5 8.5 0 1 1 12 3.5z"/><path d="M15 3.8A8.5 8.5 0 0 1 20.2 9H15z"/>',
    "font": '<path d="M5 19l5-14h1l5 14"/><path d="M7 14h7"/><path d="M17 11.5v7.5M15 13h4"/>',
    "disc": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2"/>',
    "gear-box": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 12h6M12 9v6"/>',
    "people": '<circle cx="9" cy="8.5" r="3"/><path d="M3.5 19c.6-3 2.7-4.5 5.5-4.5s4.9 1.5 5.5 4.5"/><circle cx="16.5" cy="9.5" r="2.5"/><path d="M16 14.5c2.4 0 4 1.3 4.5 4"/>',
    "mail": '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M4 7l8 6 8-6"/>',
    "chat": '<path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4h0A1.5 1.5 0 0 1 4 14.5z"/>',
    "cloud": '<path d="M7 18.5a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 9.2a4.7 4.7 0 0 1 .5 9.3z"/>',
    "remote": '<rect x="3.5" y="4.5" width="17" height="11" rx="1.5"/><path d="M9 20h6M12 15.5V20"/><path d="M9.5 10h5M12.5 8l2 2-2 2"/>',
    "scan": '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><path d="M4 12h16"/>',
    "print": '<path d="M7 8V4h10v4"/><rect x="3.5" y="8" width="17" height="8" rx="1.5"/><path d="M7 13.5h10V20H7z"/>',
    "text": '<path d="M5 6.5h14M5 10.5h14M5 14.5h10M5 18.5h7"/>',
    "sheet": '<rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M4 9.5h16M4 14.5h16M10 4v16"/>',
    "slides": '<rect x="3.5" y="4.5" width="17" height="11" rx="1.5"/><path d="M12 15.5v4M8.5 19.5h7"/>',
    "binary": '<path d="M7 5v6M5.5 5H7M5.5 11h3"/><rect x="11" y="5" width="4" height="6" rx="2"/><rect x="5" y="13" width="4" height="6" rx="2"/><path d="M15 13v6M13.5 13H15M13.5 19h3"/>',
    "bolt": '<path d="M13 3L5.5 13.5H12L11 21l7.5-10.5H12z"/>',
    "db": '<ellipse cx="12" cy="6" rx="7.5" ry="2.5"/><path d="M4.5 6v12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5V6"/><path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    "magnet": '<path d="M6 4v8a6 6 0 0 0 12 0V4"/><path d="M6 8h4M14 8h4"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l8.5-8.5M16 7l2.5 2.5M14 9l2 2"/>',
    "film": '<rect x="4" y="3.5" width="16" height="17" rx="1.5"/><path d="M8 3.5v17M16 3.5v17M4 8h4M4 12h4M4 16h4M16 8h4M16 12h4M16 16h4"/>',
    "wave": '<path d="M3 12h2l2-5 3 10 3-14 3 12 2-3h3"/>',
})

# ---- colours: each app tile is two stops of one hue, lighter at the top

HUES = {
    "blue": ("#5A9BFF", "#2F6BE0"), "violet": ("#9A7CFF", "#5E3FE0"), "teal": ("#2FC5B0", "#11897A"),
    "green": ("#4CCB7A", "#1E8C4A"), "amber": ("#F5B84B", "#C77A12"), "orange": ("#FF8A4C", "#D2541A"),
    "red": ("#FF6B6B", "#C9363F"), "pink": ("#F27BB0", "#C03C7A"), "slate": ("#5A6377", "#2B3140"),
    "graphite": ("#3A4150", "#1D212A"), "cyan": ("#3CC4F0", "#1584B8"), "indigo": ("#6A7CFF", "#3A47C9"),
}

# icon name(s) -> (glyph, hue). The names are the freedesktop ones and the KDE/GNOME apps' own.
APPS = [
    (("utilities-terminal", "org.kde.konsole", "terminal", "org.gnome.Terminal", "org.gnome.Console"), "terminal", "graphite"),
    (("system-file-manager", "org.kde.dolphin", "org.gnome.Nautilus", "file-manager"), "folder", "blue"),
    (("accessories-text-editor", "org.kde.kate", "org.kde.kwrite", "kate", "kwrite", "org.gnome.TextEditor",
      "text-editor"), "rename", "indigo"),
    (("accessories-calculator", "org.kde.kcalc", "kcalc", "org.gnome.Calculator"), "calculator", "slate"),
    (("preferences-system", "systemsettings", "org.kde.systemsettings", "preferences-desktop", "org.gnome.Settings",
      "gnome-control-center"), "sliders", "slate"),
    (("utilities-system-monitor", "org.kde.plasma-systemmonitor", "ksysguard", "org.gnome.SystemMonitor",
      "gnome-system-monitor"), "gauge", "teal"),
    (("org.kde.spectacle", "spectacle", "applets-screenshooter", "org.gnome.Screenshot", "accessories-screenshot"),
     "camera", "pink"),
    (("org.kde.gwenview", "gwenview", "eog", "org.gnome.eog", "image-viewer", "multimedia-photo-viewer",
      "org.gnome.Loupe"), "image", "teal"),
    (("org.kde.okular", "okular", "org.gnome.Evince", "evince", "accessories-document-viewer",
      "org.gnome.Papers"), "book", "red"),
    (("org.kde.ark", "ark", "org.gnome.FileRoller", "file-roller", "utilities-file-archiver",
      "application-x-archive-manager"), "archive", "amber"),
    (("org.kde.discover", "plasmadiscover", "system-software-install", "org.gnome.Software",
      "applications-other"), "store", "violet"),
    (("system-software-update", "software-update-available", "update-manager"), "update", "green"),
    (("org.kde.haruna", "haruna", "org.kde.dragonplayer", "dragonplayer", "multimedia-video-player",
      "applications-multimedia", "totem", "org.gnome.Totem", "celluloid", "io.github.celluloid_player.Celluloid",
      "mpv"), "play", "pink"),
    (("org.kde.elisa", "elisa", "multimedia-audio-player", "audio-player", "org.gnome.Rhythmbox3", "rhythmbox",
      "org.gnome.Music"), "music", "violet"),
    (("org.kde.filelight", "filelight", "baobab", "org.gnome.baobab", "disk-usage-analyzer"), "pie", "orange"),
    (("org.kde.partitionmanager", "partitionmanager", "gparted", "org.gnome.DiskUtility", "gnome-disks",
      "drive-harddisk-system"), "drives", "slate"),
    (("org.kde.kinfocenter", "kinfocenter", "hwinfo", "hardinfo", "org.gnome.SystemInfo", "help-about"), "info", "cyan"),
    (("help-browser", "org.kde.khelpcenter", "khelpcenter", "yelp", "org.gnome.Yelp"), "book", "blue"),
    (("org.kde.kcharselect", "kcharselect", "accessories-character-map", "org.gnome.Characters",
      "gucharmap"), "char", "slate"),
    (("org.kde.kdeconnect", "kdeconnect", "kdeconnect.app", "org.kde.kdeconnect.app", "gsconnect"), "phone", "teal"),
    (("org.kde.kwalletmanager", "kwalletmanager", "kwalletmanager2", "seahorse", "org.gnome.seahorse.Application",
      "dialog-password", "preferences-desktop-user-password"), "key", "amber"),
    (("org.kde.ksystemlog", "ksystemlog", "logviewer", "org.gnome.Logs", "gnome-logs", "utilities-log-viewer"),
     "list", "graphite"),
    (("org.kde.kmenuedit", "kmenuedit", "menu-editor", "alacarte"), "menu", "slate"),
    (("org.kde.kcolorchooser", "kcolorchooser", "color-picker", "gcolor3", "nl.hjdskes.gcolor3"), "palette", "pink"),
    (("org.kde.kruler", "kruler"), "ruler", "amber"),
    (("org.kde.sweeper", "sweeper", "bleachbit", "org.bleachbit.BleachBit"), "broom", "green"),
    (("org.kde.kfind", "kfind", "system-search", "edit-find", "catfish", "org.gnome.Catfish"), "search", "blue"),
    (("org.kde.krdc", "krdc", "org.gnome.Connections", "remmina", "org.remmina.Remmina", "preferences-desktop-remote-desktop"),
     "remote", "indigo"),
    (("org.kde.krfb", "krfb"), "network", "indigo"),
    (("org.kde.kclock", "kclock", "org.gnome.clocks", "preferences-system-time", "clock"), "clock", "slate"),
    (("org.kde.merkuro.calendar", "org.kde.kalendar", "kalendar", "office-calendar", "org.gnome.Calendar",
      "korganizer"), "calendar", "red"),
    (("org.kde.kontact", "kontact", "org.kde.kmail2", "kmail", "internet-mail", "mail-client", "evolution",
      "org.gnome.Evolution", "thunderbird-mail-client"), "mail", "blue"),
    (("org.kde.kaddressbook", "kaddressbook", "x-office-address-book", "org.gnome.Contacts"), "people", "teal"),
    (("org.kde.skanlite", "skanlite", "org.kde.skanpage", "skanpage", "scanner", "simple-scan",
      "org.gnome.SimpleScan"), "scan", "slate"),
    (("printer", "system-config-printer", "preferences-devices-printer", "org.kde.print-manager"), "print", "slate"),
    (("org.kde.kweather", "kweather", "org.gnome.Weather", "weather-few-clouds"), "cloud", "cyan"),
    (("preferences-desktop-theme", "preferences-desktop-color", "preferences-desktop-wallpaper",
      "org.kde.plasma.themeexplorer"), "appearance", "violet"),
    (("preferences-desktop-display", "video-display", "org.kde.kscreen", "display"), "display", "blue"),
    (("preferences-desktop-keyboard", "input-keyboard", "preferences-desktop-keyboard-shortcuts"), "keyboard", "slate"),
    (("preferences-system-network", "network-workgroup", "preferences-system-network-connection", "nm-connection-editor",
      "networkmanager"), "network", "cyan"),
    (("preferences-system-bluetooth", "bluetooth", "blueman", "bluedevil"), "bluetooth", "blue"),
    (("preferences-desktop-sound", "multimedia-volume-control", "pavucontrol", "org.pulseaudio.pavucontrol",
      "audio-card"), "volume", "violet"),
    (("preferences-system-power", "preferences-system-power-management", "battery", "gnome-power-manager"),
     "battery", "green"),
    (("preferences-system-users", "system-users", "user-info", "preferences-desktop-user"), "user", "indigo"),
    (("preferences-desktop-notification", "preferences-desktop-notification-bell", "notifications"), "bell", "amber"),
    (("preferences-system-firewall", "firewall-config", "gufw", "security-high", "preferences-security"),
     "shield", "green"),
    (("system-backup", "deja-dup", "org.gnome.DejaDup", "backintime", "timeshift", "kup", "org.kde.kup",
      "btrfs-assistant"), "snapshot", "teal"),
    (("system-run", "krunner", "org.kde.krunner"), "search", "graphite"),
    (("applications-games", "input-gaming", "applications-games-symbolic", "preferences-desktop-gaming"),
     "gaming", "violet"),
    (("applications-science", "applications-education"), "flask", "teal"),
    (("applications-development", "applications-engineering", "org.kde.kdevelop", "kdevelop", "builder",
      "org.gnome.Builder"), "code", "indigo"),
    (("applications-office", "libreoffice-startcenter"), "doc", "blue"),
    (("applications-internet", "web-browser", "internet-web-browser", "org.gnome.Epiphany", "org.kde.falkon",
      "falkon", "org.kde.konqueror", "konqueror"), "globe", "blue"),
    (("applications-utilities", "applications-accessories", "applications-system", "utilities-tweak-tool",
      "org.gnome.tweaks"), "system", "slate"),
    (("applications-graphics",), "image", "pink"),
    (("system-lock-screen", "preferences-desktop-screensaver"), "lock", "graphite"),
    (("system-log-out", "system-shutdown", "application-exit"), "power", "red"),
    (("org.kde.plasma-welcome", "plasma-welcome", "org.gnome.Tour"), "star", "violet"),
    (("org.kde.kdiskfree", "kdf", "drive-harddisk"), "drives", "graphite"),
    (("org.kde.ktorrent", "ktorrent", "transmission", "transmission-qt", "transmission-gtk", "com.transmissionbt.Transmission",
      "qbittorrent", "org.qbittorrent.qBittorrent", "fragments", "de.haeckerfelix.Fragments"), "download", "green"),
    (("org.kde.kdenlive", "kdenlive", "shotcut", "org.shotcut.Shotcut", "pitivi"), "film", "pink"),
    (("org.kde.kwave", "audacity", "org.audacityteam.Audacity", "tenacity"), "wave", "orange"),
    (("org.kde.krita", "krita", "gimp", "org.gimp.GIMP", "pinta", "com.github.PintaProject.Pinta", "mypaint"),
     "palette", "orange"),
    (("org.kde.neochat", "neochat", "org.kde.tokodon", "chat", "internet-chat"), "chat", "indigo"),
    (("org.kde.kdebugsettings", "kdebugsettings", "org.kde.drkonqi", "drkonqi", "tools-report-bug"), "alert", "red"),
    (("system-reboot",), "refresh", "amber"),
    (("org.kde.kgpg", "kgpg", "org.kde.kleopatra", "kleopatra", "gpa"), "lock", "amber"),
    (("org.kde.kamoso", "kamoso", "org.gnome.Snapshot", "cheese", "camera-web"), "camera", "teal"),
    (("org.kde.kmag", "kmag", "org.gnome.Zoom", "accessibility", "preferences-desktop-accessibility"), "eye", "blue"),
    (("org.kde.kgeography", "marble", "org.kde.marble", "org.gnome.Maps", "applications-geography"), "globe", "green"),
    (("database", "org.kde.kexi", "sqlitebrowser", "org.sqlitebrowser.sqlitebrowser", "dbeaver", "io.dbeaver.DBeaverCommunity"),
     "db", "amber"),
    (("org.kde.isoimagewriter", "isoimagewriter", "org.fedoraproject.MediaWriter", "balena-etcher", "media-optical-burn",
      "brasero", "k3b", "org.kde.k3b"), "disc", "orange"),
    (("virtualbox", "org.virt_manager.virt-manager", "virt-manager", "org.gnome.Boxes", "gnome-boxes", "qemu"),
     "display", "indigo"),
    (("org.kde.ksnip", "ksnip", "flameshot", "org.flameshot.Flameshot"), "cut", "pink"),
    (("org.kde.kolourpaint", "kolourpaint", "drawing", "com.github.maoschanz.drawing"), "palette", "cyan"),
]

# file types: mime icon name(s) -> (glyph, band colour, label or "")
CODE, DOCS, IMAGE, VIDEO, AUDIO, ARCHIVE, EXEC, OFFICE, DATA, FONT, DISC, WEB = (
    "#4C8DFF", "#8C94A6", "#14B8A6", "#EC4899", "#8B5CF6", "#F59E0B", "#EF4444", "#22A559", "#06B6D4", "#A3A3A3",
    "#F97316", "#3B82F6")
MIMES = [
    (("text-plain", "text-x-generic", "text-x-readme", "text-x-changelog", "text-x-copying", "text-x-authors",
      "text-x-install"), "text", DOCS, "TXT"),
    (("text-markdown", "text-x-markdown"), "text", DOCS, "MD"),
    (("text-x-log",), "list", DOCS, "LOG"),
    (("text-x-python", "text-x-python3", "application-x-python-bytecode"), "code", CODE, "PY"),
    (("application-x-shellscript", "text-x-script", "application-x-executable-script", "text-x-sh"), "terminal", CODE, "SH"),
    (("text-x-csrc", "text-x-c"), "code", CODE, "C"),
    (("text-x-chdr",), "code", CODE, "H"),
    (("text-x-c++src", "text-x-cpp"), "code", CODE, "C++"),
    (("text-x-c++hdr",), "code", CODE, "HPP"),
    (("text-rust", "text-x-rust"), "code", CODE, "RS"),
    (("text-x-go",), "code", CODE, "GO"),
    (("text-x-java", "application-x-java"), "code", CODE, "JAVA"),
    (("application-javascript", "text-javascript", "application-x-javascript"), "code", CODE, "JS"),
    (("application-typescript", "text-x-typescript"), "code", CODE, "TS"),
    (("text-x-qml",), "code", CODE, "QML"),
    (("text-x-cmake",), "code", CODE, "CMAKE"),
    (("text-x-makefile",), "code", CODE, "MAKE"),
    (("text-x-lua",), "code", CODE, "LUA"),
    (("text-x-csharp",), "code", CODE, "C#"),
    (("application-x-php", "text-x-php"), "code", CODE, "PHP"),
    (("application-x-ruby", "text-x-ruby"), "code", CODE, "RB"),
    (("text-x-patch", "text-x-diff"), "split", CODE, "DIFF"),
    (("text-html", "application-xhtml+xml"), "globe", WEB, "HTML"),
    (("text-css", "text-x-scss", "text-x-sass"), "appearance", WEB, "CSS"),
    (("application-json",), "code", DATA, "JSON"),
    (("application-x-yaml", "text-x-yaml", "application-yaml"), "list", DATA, "YAML"),
    (("application-toml", "text-x-toml"), "list", DATA, "TOML"),
    (("application-xml", "text-xml"), "code", DATA, "XML"),
    (("text-csv", "text-x-csv", "text-tab-separated-values"), "sheet", OFFICE, "CSV"),
    (("text-x-ini", "text-x-config", "application-x-desktop", "text-x-systemd-unit"), "sliders", DATA, "CONF"),
    (("application-x-sqlite3", "application-vnd.sqlite3", "application-x-sqlite2"), "db", DATA, "DB"),
    (("application-sql", "text-x-sql"), "db", DATA, "SQL"),
    (("application-pdf",), "book", "#E11D48", "PDF"),
    (("application-epub+zip", "application-x-mobipocket-ebook"), "book", "#E11D48", "EPUB"),
    (("application-vnd.oasis.opendocument.text", "application-msword", "x-office-document",
      "application-vnd.openxmlformats-officedocument.wordprocessingml.document", "application-rtf"), "text", "#2563EB", "DOC"),
    (("application-vnd.oasis.opendocument.spreadsheet", "application-vnd.ms-excel", "x-office-spreadsheet",
      "application-vnd.openxmlformats-officedocument.spreadsheetml.sheet"), "sheet", OFFICE, "XLS"),
    (("application-vnd.oasis.opendocument.presentation", "application-vnd.ms-powerpoint", "x-office-presentation",
      "application-vnd.openxmlformats-officedocument.presentationml.presentation"), "slides", "#EA580C", "PPT"),
    (("image-x-generic", "image-bmp", "image-tiff", "image-x-tga", "image-vnd.microsoft.icon", "image-x-icon"),
     "image", IMAGE, "IMG"),
    (("image-png",), "image", IMAGE, "PNG"),
    (("image-jpeg",), "image", IMAGE, "JPG"),
    (("image-gif",), "image", IMAGE, "GIF"),
    (("image-webp",), "image", IMAGE, "WEBP"),
    (("image-avif", "image-heif", "image-heic"), "image", IMAGE, "HEIC"),
    (("image-svg+xml", "image-svg+xml-compressed"), "appearance", IMAGE, "SVG"),
    (("image-x-xcf", "image-x-krita", "application-x-krita", "image-vnd.adobe.photoshop"), "palette", IMAGE, "ART"),
    (("image-x-dcraw", "image-x-adobe-dng", "image-x-canon-cr2", "image-x-nikon-nef", "image-x-sony-arw"), "camera",
     IMAGE, "RAW"),
    (("video-x-generic", "video-mpeg", "video-quicktime", "video-x-msvideo", "video-x-flv"), "play", VIDEO, "VID"),
    (("video-mp4",), "play", VIDEO, "MP4"),
    (("video-x-matroska",), "play", VIDEO, "MKV"),
    (("video-webm",), "play", VIDEO, "WEBM"),
    (("audio-x-generic", "audio-aac", "audio-x-aiff", "audio-x-ms-wma", "audio-mp4", "audio-x-m4a"), "music", AUDIO, "AUD"),
    (("audio-mpeg", "audio-mp3", "audio-x-mp3"), "music", AUDIO, "MP3"),
    (("audio-flac", "audio-x-flac"), "music", AUDIO, "FLAC"),
    (("audio-x-wav", "audio-wav"), "wave", AUDIO, "WAV"),
    (("audio-ogg", "audio-x-vorbis+ogg", "audio-x-opus+ogg", "audio-opus"), "music", AUDIO, "OGG"),
    (("audio-x-mpegurl", "audio-x-scpls", "audio-x-ms-asx"), "list", AUDIO, "M3U"),
    (("application-zip", "application-x-zip", "application-x-zip-compressed"), "archive", ARCHIVE, "ZIP"),
    (("application-x-tar", "application-x-compressed-tar", "application-x-bzip-compressed-tar",
      "application-x-xz-compressed-tar", "application-x-zstd-compressed-tar", "application-x-lzma-compressed-tar",
      "application-x-gtar"), "archive", ARCHIVE, "TAR"),
    (("application-x-7z-compressed",), "archive", ARCHIVE, "7Z"),
    (("application-x-rar", "application-vnd.rar", "application-x-rar-compressed"), "archive", ARCHIVE, "RAR"),
    (("application-gzip", "application-x-gzip", "application-x-bzip", "application-x-bzip2", "application-x-xz",
      "application-x-zstd", "application-zstd", "application-x-lzma", "application-x-compress"), "archive", ARCHIVE, "GZ"),
    (("application-x-archive", "package-x-generic", "application-x-cpio"), "package", ARCHIVE, "PKG"),
    (("application-x-iso9660-image", "application-x-cd-image", "application-x-raw-disk-image",
      "application-x-iso9660-appimage"), "disc", DISC, "ISO"),
    (("application-vnd.debian.binary-package", "application-x-deb"), "package", "#C2185B", "DEB"),
    (("application-x-rpm", "application-x-redhat-package-manager"), "package", "#C2185B", "RPM"),
    (("application-vnd.flatpak", "application-vnd.flatpak.ref", "application-vnd.flatpak.repo"), "package", "#4A90D9",
     "FLAT"),
    (("application-x-appimage", "application-vnd.appimage"), "package", "#4A90D9", "APP"),
    (("application-x-executable", "application-x-sharedlib", "application-x-object", "application-x-elf"), "binary",
     EXEC, "BIN"),
    (("application-x-ms-dos-executable", "application-x-msdownload", "application-x-ms-shortcut",
      "application-vnd.microsoft.portable-executable", "application-x-msi", "application-x-ms-installer"),
     "binary", EXEC, "EXE"),
    (("application-x-bat", "application-x-msdos-program"), "terminal", EXEC, "BAT"),
    (("application-x-java-archive", "application-java-archive"), "package", EXEC, "JAR"),
    (("font-x-generic", "application-x-font-ttf", "font-ttf", "application-x-font-otf", "font-otf", "font-woff",
      "font-woff2", "application-x-font-type1"), "font", FONT, "FONT"),
    (("application-x-bittorrent",), "magnet", "#22A559", "TOR"),
    (("text-calendar", "text-x-vcalendar"), "calendar", "#EF4444", "ICS"),
    (("text-vcard", "text-x-vcard", "text-directory"), "people", "#14B8A6", "VCF"),
    (("message-rfc822", "message-x-generic", "application-mbox"), "mail", "#3B82F6", "EML"),
    (("application-pgp-keys", "application-pgp-encrypted", "application-pgp-signature", "application-x-x509-ca-cert",
      "application-pkcs12", "application-x-pem-key"), "key", "#F59E0B", "KEY"),
    (("application-x-trash",), "trash", DOCS, ""),
    (("application-octet-stream", "unknown", "application-x-zerosize", "inode-x-generic"), "binary", DOCS, ""),
    (("x-office-drawing", "application-vnd.oasis.opendocument.graphics"), "palette", "#D946EF", "ODG"),
    (("application-x-steam-launcher",), "gaming", "#2563EB", "GAME"),
    (("application-x-nintendo-ds-rom", "application-x-gameboy-rom", "application-x-gba-rom", "application-x-n64-rom",
      "application-x-snes-rom", "application-x-nes-rom", "application-x-genesis-rom", "application-x-sms-rom",
      "application-x-gamecube-rom", "application-x-wii-rom", "application-x-psx-rom", "application-x-cue"), "gaming",
     "#7C3AED", "ROM"),
    (("text-x-script-generic", "text-x-tex", "text-x-bibtex"), "text", CODE, "TEX"),
    (("application-x-ipynb+json",), "flask", DATA, "IPYNB"),
]


def screws(size, inset, r, color):
    out = []
    for x in (inset, size - inset):
        for y in (inset, size - inset):
            out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
                       f'<path d="M{x - r * .55} {y + r * .55}L{x + r * .55} {y - r * .55}" stroke="#000" '
                       f'stroke-opacity=".35" stroke-width="{r * .45:.2f}" stroke-linecap="round"/>')
    return "".join(out)


def app_icon(glyph, hue):
    top, bottom = HUES[hue]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        '<defs>'
        f'<linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/></linearGradient>'
        '<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".28"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '</defs>'
        # soft shadow, the plate, its top light and a hairline rim
        '<rect x="5" y="7" width="54" height="54" rx="14" fill="#000" opacity=".28"/>'
        '<rect x="5" y="4" width="54" height="54" rx="14" fill="url(#t)"/>'
        '<rect x="5" y="4" width="54" height="54" rx="14" fill="url(#s)"/>'
        '<rect x="5.5" y="4.5" width="53" height="53" rx="13.5" fill="none" stroke="#fff" stroke-opacity=".18"/>'
        + screws(64, 11.5, 1.6, "#fff").replace('fill="#fff"', 'fill="#fff" fill-opacity=".45"').replace(
            f'cy="{64 - 11.5}"', f'cy="{58 - 7.5}"').replace('cy="11.5"', 'cy="10.5"')
        + '<g transform="translate(14 13) scale(1.5)" fill="none" stroke="#fff" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[glyph]}</g>'
        '</svg>\n').replace('fill="#000"', 'fill="#000"')


def mime_icon(glyph, band, label):
    # The sheet: 64 grid, folded top-right corner
    body = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        '<path d="M14 5h26l14 14v38a3 3 0 0 1-3 3H14a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3z" fill="#000" opacity=".25" '
        'transform="translate(0 1.5)"/>'
        '<path d="M14 4h26l14 14v38a3 3 0 0 1-3 3H14a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z" fill="#252A35"/>'
        '<path d="M14 4h26l14 14v38a3 3 0 0 1-3 3H14a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z" fill="none" stroke="#3A4152"/>'
        f'<path d="M40 4v11a3 3 0 0 0 3 3h11z" fill="{band}" opacity=".9"/>'
    )
    if label:
        body += f'<path d="M11 44h43v12a3 3 0 0 1-3 3H14a3 3 0 0 1-3-3z" fill="{band}"/>'
        size = 10.5 if len(label) <= 3 else 9 if len(label) <= 4 else 7.5
        d, width = text_path(INTER, label, 0, 0, size)
        x = 32.5 - width / 2
        d, _ = text_path(INTER, label, x, 55.3, size)
        body += f'<path d="{d}" fill="#fff"/>'
        gy = 15
    else:
        gy = 21
    body += (f'<g transform="translate(20.5 {gy}) scale(1)" fill="none" stroke="{band}" stroke-width="1.9" '
             f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[glyph]}</g>')
    return body + '</svg>\n'


def write():
    # A name listed twice would be written through the first one's link, over its icon
    names = [n for entries in (APPS, MIMES) for group, *_ in entries for n in group]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"listed twice: {dupes}"
    if OUT.exists():
        shutil.rmtree(OUT)
    apps, mimes = OUT / "apps", OUT / "mimetypes"
    apps.mkdir(parents=True)
    mimes.mkdir(parents=True)
    n_app = n_mime = 0
    for names, glyph, hue in APPS:
        svg = app_icon(glyph, hue)
        (apps / f"{names[0]}.svg").write_text(svg, newline="\n")
        for alias in names[1:]:  # one file, the other names link to it (the package keeps symlinks)
            if not (apps / f"{alias}.svg").exists():
                (apps / f"{alias}.svg").symlink_to(f"{names[0]}.svg")
        n_app += len(names)
    for names, glyph, band, label in MIMES:
        (mimes / f"{names[0]}.svg").write_text(mime_icon(glyph, band, label), newline="\n")
        for alias in names[1:]:
            if not (mimes / f"{alias}.svg").exists():
                (mimes / f"{alias}.svg").symlink_to(f"{names[0]}.svg")
        n_mime += len(names)
    print(f"{len(APPS)} app icons ({n_app} names), {len(MIMES)} file type icons ({n_mime} names) -> {OUT}")


def sheet(path):
    """A contact sheet of every drawn icon at 64 px and 22 px, for review."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    app = QGuiApplication.instance() or QGuiApplication(["x"])  # noqa: F841
    files = [OUT / "apps" / f"{n[0]}.svg" for n, *_ in APPS] + [OUT / "mimetypes" / f"{n[0]}.svg" for n, *_ in MIMES]
    cols = 16
    rows = (len(files) + cols - 1) // cols
    img = QImage(cols * 92 + 20, rows * 104 + 20, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("#0F1115"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    for i, f in enumerate(files):
        x, y = 20 + (i % cols) * 92, 20 + (i // cols) * 104
        r = QSvgRenderer(str(f))
        r.render(p, QRectF(x, y, 64, 64))
        r.render(p, QRectF(x + 21, y + 70, 22, 22))
    p.end()
    img.save(str(path))
    print("->", path)


if __name__ == "__main__":
    write()
    if "--sheet" in sys.argv:
        sheet(HERE / "icon-theme-preview.png")
