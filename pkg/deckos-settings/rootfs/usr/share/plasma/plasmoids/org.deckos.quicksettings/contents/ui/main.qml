import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid

// DeckOS Quick Settings: the everyday controls in one panel popup. The popup is built on first
// open and kept; Plasma's models behind it are signal-driven, and the only timers (the media clock)
// run while it's open. The update count is checked in the background every few hours.
PlasmoidItem {
    id: root

    Backend {
        id: backend
        expanded: root.expanded
    }

    toolTipMainText: "Quick settings"
    toolTipSubText: backend.updatesText || "Wi-Fi, sound, brightness, Gaming Mode and more"
    preferredRepresentation: compactRepresentation

    compactRepresentation: CompactRepresentation {
        backend: backend
        expanded: root.expanded
        vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
        onActivated: open => root.expanded = open
    }
    fullRepresentation: FullRepresentation {
        backend: backend
    }
}
