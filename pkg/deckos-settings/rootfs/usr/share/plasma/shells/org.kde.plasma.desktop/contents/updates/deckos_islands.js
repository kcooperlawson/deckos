// DecKoOS 0.19: the dock floats as notched islands on a see-through panel (the Plasma style's translucent/ panel
// background), drawn by DecKoOS's menu, taskbar and Quick Settings, which reaches over the tray and clock after it.
// A panel those don't cover (spacers, other widgets, a tray without Quick Settings before it, Kid mode's) keeps
// its plate: it's set opaque. Once per user (Plasma records it in plasmashellrc [Updates]).
const covered = ["org.deckos.menu", "org.deckos.taskbar", "org.deckos.quicksettings", "org.kde.plasma.systemtray",
                 "org.kde.plasma.digitalclock", "org.kde.plasma.marginsseparator"];
const all = panels();
for (var i = 0; i < all.length; i++) {
    const p = all[i];
    const types = p.widgets().map(function (w) { return w.type; });
    const stock = types.filter(function (t) { return t.indexOf("org.deckos.") !== 0 && t != "org.kde.plasma.marginsseparator"; });
    const ready = types.every(function (t) { return covered.indexOf(t) !== -1; })
        && (stock.length === 0 || types.indexOf("org.deckos.quicksettings") !== -1);
    if (!ready)
        p.opacity = "opaque";
}
