// DeckOS: tidy panels made before 0.3.17, once per user (Plasma records it in plasmashellrc [Updates]).
// The tray hides what Quick Settings already does and the rarely used (same list as the DeckOS layout);
// the dock drops the Store launcher, since DeckOS Menu's search offers Store apps. Items someone shows
// again later stay shown: this never runs twice.
const hide = [
    "org.kde.plasma.networkmanagement", "org.kde.plasma.volume", "org.kde.plasma.bluetooth",
    "org.kde.plasma.brightness", "org.kde.plasma.battery", "org.kde.plasma.mediacontroller",
    "org.kde.plasma.vault", "org.kde.kdeconnect", "org.kde.plasma.clipboard", "org.kde.kupapplet",
    "org.kde.plasma.weather", "org.kde.plasma.printmanager", "org.kde.plasma.dwellclicker",
    "org.kde.plasma.manage-inputmethod", "org.kde.kscreen", "org.kde.plasma.keyboardindicator"
];

// readConfig gives a list or a comma-joined string; write lists back: a joined string written to a
// running task manager drops launchers
function list(value) {
    if (!value) return [];
    return (typeof value == "string" ? value.split(",") : Array.from(value)).filter(function (s) { return s; });
}

const all = panels();
for (var i = 0; i < all.length; i++) {
    const widgets = all[i].widgets();
    for (var j = 0; j < widgets.length; j++) {
        const w = widgets[j];
        if (w.type == "org.kde.plasma.icontasks" || w.type == "org.kde.plasma.taskmanager") {
            w.currentConfigGroup = ["General"];
            const launchers = list(w.readConfig("launchers"));
            const kept = launchers.filter(function (l) { return l != "applications:deckos-store.desktop"; });
            if (kept.length != launchers.length) w.writeConfig("launchers", kept);
        } else if (w.type == "org.kde.plasma.systemtray") {
            // Plasma 6 keeps the tray's settings on the tray widget itself
            w.currentConfigGroup = ["General"];
            const hidden = list(w.readConfig("hiddenItems"));
            hide.forEach(function (id) { if (hidden.indexOf(id) < 0) hidden.push(id); });
            w.writeConfig("hiddenItems", hidden);
            const shown = list(w.readConfig("shownItems"));
            w.writeConfig("shownItems", shown.filter(function (id) { return hide.indexOf(id) < 0; }));
        }
    }
}
