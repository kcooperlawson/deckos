// Kid mode (a child's first desktop, and deckos-kids puts it back if it's changed): no menu, since the menu shows
// every app. The child's approved apps and My games are pinned (deckos-kids --session sets them at each login)
// and on the desktop. Widgets can't be changed.
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
tasks.writeConfig("lockedPins", "true");  // no pinning, unpinning or dropping apps on
panel.addWidget("org.deckos.kidtime");  // the minutes left today, and I'm done
panel.addWidget("org.kde.plasma.volume");
var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", "false");
locked = true;
