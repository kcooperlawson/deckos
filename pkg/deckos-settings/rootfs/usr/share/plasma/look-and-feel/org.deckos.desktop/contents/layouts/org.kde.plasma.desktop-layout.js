// DeckOS default desktop: one floating dock-style panel, DeckOS wallpaper on every screen.

var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.6 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";

var menu = panel.addWidget("org.deckos.menu");  // DeckOS Menu (replaces Kickoff; Meta opens it)
menu.currentConfigGroup = ["General"];
menu.writeConfig("icon", "deckos");

var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "preferred://filemanager",
    "applications:org.kde.konsole.desktop",
    "preferred://browser",
    "applications:steam.desktop",
    "applications:code.desktop",
    "applications:deckos-hub.desktop",
    "applications:deckos-store.desktop"
].join(","));

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
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
}
