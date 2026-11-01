// DecKoOS 0.23.4: the layouts (deckos layout set) put Plasma's own clock back, with the date stacked under the time
// in the automatic font, spilling past the plate's outline. Once per user, like deckos_dock_clock.js: clocks still on
// the automatic font get the DecKo type sized to their panel, and the time only (a top bar keeps its one-line date).
const all = panels();
for (var i = 0; i < all.length; i++) {
    const p = all[i], clocks = p.widgets("org.kde.plasma.digitalclock");
    for (var j = 0; j < clocks.length; j++) {
        const c = clocks[j];
        c.currentConfigGroup = ["Appearance"];
        if (String(c.readConfig("autoFontAndSize", true)) == "false")
            continue;
        if (p.location != "top")
            c.writeConfig("showDate", "false");
        c.writeConfig("autoFontAndSize", "false");
        c.writeConfig("fontFamily", "Chakra Petch");
        c.writeConfig("fontStyleName", "SemiBold");
        c.writeConfig("fontWeight", "600");
        c.writeConfig("fontSize", String(Math.max(11, Math.min(28, Math.round(p.height * 0.4)))));
    }
}
