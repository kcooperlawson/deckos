// DecKoOS 0.22: the Desktop shelf (org.deckos.shelf) takes over from Plasma's icon grid on PCs set up before it:
// added down the left of the first screen's desktop, and the grid hidden by a filter nothing matches, so the desktop
// is still the Desktop folder (dropping on the wallpaper saves there, and the shelf shows it). `deckos vibe widget
// org.deckos.shelf off` brings the icons back. Once per user (Plasma records it in plasmashellrc [Updates]).
const kid = panels().some(function (p) { return p.widgets("org.deckos.kidtime").length > 0; });  // Kid mode's own
const all = kid ? [] : desktops();
for (var i = 0; i < all.length; i++) {
    const d = all[i];
    if (d.type !== "org.kde.plasma.folder")
        continue;
    if (d.screen === 0 && d.widgets("org.deckos.shelf").length === 0) {
        const g = screenGeometry(d.screen);
        d.addWidget("org.deckos.shelf", 40, 40, 420, Math.min(760, g.height - 190));
    }
    if (d.widgets("org.deckos.shelf").length > 0) {
        d.currentConfigGroup = ["General"];
        d.writeConfig("filterMode", 1);
        d.writeConfig("filterPattern", "deckos-shelf-shows-these");
    }
}
