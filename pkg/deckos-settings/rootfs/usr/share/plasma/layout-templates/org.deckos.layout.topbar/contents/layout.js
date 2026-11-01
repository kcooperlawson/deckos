// Shared by the DecKoOS layouts (assets/themes.py writes them).
function deckosMenu(panel) {
    var menu = panel.addWidget("org.deckos.menu");
    menu.currentConfigGroup = ["General"];
    menu.writeConfig("icon", "deckos");
}
function deckosTasks(panel, labels) {
    var tasks = panel.addWidget("org.deckos.taskbar");
    tasks.currentConfigGroup = ["General"];
    tasks.writeConfig("launchers", ["preferred://filemanager", "applications:org.deckos.terminal.desktop", "preferred://browser", "applications:steam.desktop", "applications:code.desktop", "applications:deckos-hub.desktop"]);
    tasks.writeConfig("showLabels", labels ? "true" : "false");
}
function deckosTray(panel) {
    panel.addWidget("org.kde.plasma.marginsseparator");
    panel.addWidget("org.deckos.quicksettings");
    var tray = panel.addWidget("org.kde.plasma.systemtray");
    tray.currentConfigGroup = ["General"];
    tray.writeConfig("hiddenItems", ["org.kde.plasma.networkmanagement", "org.kde.plasma.volume", "org.kde.plasma.bluetooth", "org.kde.plasma.brightness", "org.kde.plasma.battery", "org.kde.plasma.mediacontroller", "org.kde.plasma.vault", "org.kde.kdeconnect", "org.kde.plasma.clipboard", "org.kde.kupapplet", "org.kde.plasma.weather", "org.kde.plasma.printmanager", "org.kde.plasma.dwellclicker", "org.kde.plasma.manage-inputmethod", "org.kde.kscreen", "org.kde.plasma.keyboardindicator"]);
}
// The time in the DecKo type (Chakra Petch), sized to the panel so it stays inside the plate's outline. The date
// only on a one-line top bar: stacked under the time it spills past the plate (the desktop's clock has the date).
function deckosClock(panel, oneLine) {
    var clock = panel.addWidget("org.kde.plasma.digitalclock");
    clock.currentConfigGroup = ["Appearance"];
    clock.writeConfig("showDate", oneLine ? "true" : "false");
    clock.writeConfig("dateFormat", oneLine ? "shortDate" : "isoDate");
    clock.writeConfig("autoFontAndSize", "false");
    clock.writeConfig("fontFamily", "Chakra Petch");
    clock.writeConfig("fontStyleName", "SemiBold");
    clock.writeConfig("fontWeight", "600");
    clock.writeConfig("fontSize", String(Math.max(11, Math.min(28, Math.round(panel.height * 0.4)))));
}

var top = new Panel;
top.location = "top";
top.height = 2 * Math.floor(gridUnit * 1.7 / 2);
top.floating = false;
top.lengthMode = "fill";
deckosMenu(top);
top.addWidget("org.kde.plasma.panelspacer");
deckosClock(top, true);
top.addWidget("org.kde.plasma.panelspacer");
deckosTray(top);
var dock = new Panel;
dock.location = "bottom";
dock.height = 2 * Math.floor(gridUnit * 3 / 2);
dock.floating = true;
dock.lengthMode = "fit";
dock.alignment = "center";
deckosTasks(dock, false);
