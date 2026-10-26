// Kid mode (deckos-kids applies it at a child's first login): no menu, since the menu shows every app; the
// child's apps are on the Kid mode tiles, which the taskbar keeps one click away. Widgets can't be changed.
var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 3 / 2);
panel.floating = true;
panel.lengthMode = "fit";
panel.alignment = "center";
var tasks = panel.addWidget("org.deckos.taskbar");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", ["applications:deckos-kids.desktop"]);
tasks.writeConfig("showLabels", "false");
panel.addWidget("org.kde.plasma.volume");
var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", "false");
locked = true;
