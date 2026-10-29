// DecKoOS 0.19: the panel clock in the DecKo type (Chakra Petch, a little under half the panel's height), once per user (Plasma
// records it in plasmashellrc [Updates]). Only clocks still on Plasma's automatic font: a font someone picked stays.
const all = panels();
for (var i = 0; i < all.length; i++) {
    const clocks = all[i].widgets("org.kde.plasma.digitalclock");
    for (var j = 0; j < clocks.length; j++) {
        const c = clocks[j];
        c.currentConfigGroup = ["Appearance"];
        if (String(c.readConfig("autoFontAndSize", true)) == "false")
            continue;
        c.writeConfig("autoFontAndSize", "false");
        c.writeConfig("fontFamily", "Chakra Petch");
        c.writeConfig("fontStyleName", "SemiBold");
        c.writeConfig("fontWeight", "600");
        c.writeConfig("fontSize", "24");
    }
}
