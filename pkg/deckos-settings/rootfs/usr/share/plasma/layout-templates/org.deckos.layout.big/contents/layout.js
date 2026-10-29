// Shared by the DecKoOS layouts (assets/themes.py writes them).
function deckosMenu(panel) {
    var menu = panel.addWidget("org.deckos.menu");
    menu.currentConfigGroup = ["General"];
    menu.writeConfig("icon", "deckos");
}
function deckosTasks(panel, labels) {
    var tasks = panel.addWidget("org.deckos.taskbar");
    tasks.currentConfigGroup = ["General"];
    tasks.writeConfig("launchers", ["preferred://filemanager", "applications:org.deckos.terminal.desktop", "preferred://browser", "applications:steam.desktop", "applications:deckos-hub.desktop"]);
    tasks.writeConfig("showLabels", labels ? "true" : "false");
}
function deckosTray(panel) {
    panel.addWidget("org.deckos.quicksettings");
    var tray = panel.addWidget("org.kde.plasma.systemtray");
    tray.currentConfigGroup = ["General"];
    tray.writeConfig("hiddenItems", ["org.kde.plasma.networkmanagement", "org.kde.plasma.volume", "org.kde.plasma.bluetooth", "org.kde.plasma.brightness", "org.kde.plasma.battery", "org.kde.plasma.mediacontroller", "org.kde.plasma.vault", "org.kde.kdeconnect", "org.kde.plasma.clipboard", "org.kde.kupapplet", "org.kde.plasma.weather", "org.kde.plasma.printmanager", "org.kde.plasma.dwellclicker", "org.kde.plasma.manage-inputmethod", "org.kde.kscreen", "org.kde.plasma.keyboardindicator"]);
}
function deckosClock(panel, oneLine) {
    var clock = panel.addWidget("org.kde.plasma.digitalclock");
    clock.currentConfigGroup = ["Appearance"];
    clock.writeConfig("showDate", "true");
    // the DecKo type (Chakra Petch), sized to fit the panel
    clock.writeConfig("autoFontAndSize", "false");
    clock.writeConfig("fontFamily", "Chakra Petch");
    clock.writeConfig("fontStyleName", "SemiBold");
    clock.writeConfig("fontWeight", "600");
    clock.writeConfig("fontSize", "72");
    clock.writeConfig("dateFormat", oneLine ? "shortDate" : "isoDate");
}

var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 4.4 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";
deckosMenu(panel);
deckosTasks(panel, false);
deckosTray(panel);
deckosClock(panel, false);
