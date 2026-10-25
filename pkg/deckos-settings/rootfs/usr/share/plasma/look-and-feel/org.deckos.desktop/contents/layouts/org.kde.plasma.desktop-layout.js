// DecKoOS default desktop: one floating dock-style panel, DecKoOS wallpaper on every screen.

var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.6 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";

var menu = panel.addWidget("org.deckos.menu");  // DecKoOS Menu (replaces Kickoff; Meta opens it)
menu.currentConfigGroup = ["General"];
menu.writeConfig("icon", "deckos");

var tasks = panel.addWidget("org.deckos.taskbar");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "preferred://filemanager",
    "applications:org.deckos.terminal.desktop",
    "preferred://browser",
    "applications:steam.desktop",
    "applications:code.desktop",
    "applications:deckos-hub.desktop"
].join(","));  // no Store: DecKoOS Menu's search offers Store apps with "Get it"

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.deckos.quicksettings");  // Wi-Fi, sound, Gaming Mode, updates and more

// The tray keeps notifications, app icons and whatever is active (a USB stick, the camera). What Quick
// Settings already does, and the rarely used, wait under the arrow. Same list as the
// deckos_tidy_panel.js update script, which did this once for existing panels.
var tray = panel.addWidget("org.kde.plasma.systemtray");
tray.currentConfigGroup = ["General"];
tray.writeConfig("hiddenItems", [
    "org.kde.plasma.networkmanagement", "org.kde.plasma.volume", "org.kde.plasma.bluetooth",
    "org.kde.plasma.brightness", "org.kde.plasma.battery", "org.kde.plasma.mediacontroller",
    "org.kde.plasma.vault", "org.kde.kdeconnect", "org.kde.plasma.clipboard", "org.kde.kupapplet",
    "org.kde.plasma.weather", "org.kde.plasma.printmanager", "org.kde.plasma.dwellclicker",
    "org.kde.plasma.manage-inputmethod", "org.kde.kscreen", "org.kde.plasma.keyboardindicator"
]);
var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", "true");
clock.writeConfig("dateFormat", "isoDate");

var all = desktops();
for (var i = 0; i < all.length; i++) {
    var d = all[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/DeckOS/");
    if (i == 0) {
        // DecKoOS Performance in the top right of the first screen, clear of the desktop icons
        var g = screenGeometry(d.screen);
        d.addWidget("org.deckos.perfgraphs", g.width - 360, 40, 320, 470);
    }
}
