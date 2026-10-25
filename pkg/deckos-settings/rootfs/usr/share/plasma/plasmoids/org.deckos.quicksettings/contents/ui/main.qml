import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid

// DeckOS Quick Settings: the everyday controls in one panel popup. The popup is built on first
// open and kept; Plasma's models behind it are signal-driven, and the only timers (the media clock)
// run while it's open. The update count is checked in the background every few hours.
PlasmoidItem {
    id: root

    Backend {
        // Not "backend": inside the representations below that name is their own property, so
        // "backend: backend" bound it to itself and every DeckOS control got undefined
        id: deckBackend
        expanded: root.expanded
    }

    toolTipMainText: "Quick settings"
    toolTipSubText: deckBackend.updatesText || "Wi-Fi, sound, brightness, Gaming Mode and more"
    preferredRepresentation: compactRepresentation

    compactRepresentation: CompactRepresentation {
        backend: deckBackend
        expanded: root.expanded
        vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
        onActivated: open => root.expanded = open
    }
    fullRepresentation: FullRepresentation {
        backend: deckBackend
    }
}
