// DecKoOS: Konsole's dock pin becomes DecKoOS Terminal's, once per user (DecKoOS 0.3.17, when DecKoOS
// Terminal became the default terminal). Konsole stays installed and in the app menu.
const konsole = "applications:org.kde.konsole.desktop";
const terminal = "applications:org.deckos.terminal.desktop";

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
        if (w.type != "org.kde.plasma.icontasks" && w.type != "org.kde.plasma.taskmanager") continue;
        w.currentConfigGroup = ["General"];
        const launchers = list(w.readConfig("launchers"));
        const at = launchers.indexOf(konsole);
        if (at < 0) continue;
        if (launchers.indexOf(terminal) < 0) launchers[at] = terminal;
        else launchers.splice(at, 1);
        w.writeConfig("launchers", launchers);
    }
}
