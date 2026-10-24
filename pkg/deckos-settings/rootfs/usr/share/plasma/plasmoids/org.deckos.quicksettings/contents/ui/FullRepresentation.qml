import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// The popup. Each piece that talks to a Plasma service (plasma-nm, bluedevil, plasma-pa,
// powerdevil, KWin) sits in its own Loader: if one is missing, only that piece disappears.
Item {
    id: full
    property var backend
    property bool displayOpen: false

    Layout.preferredWidth: 400
    Layout.minimumWidth: 400
    Layout.maximumWidth: 400
    Layout.preferredHeight: column.implicitHeight
    Layout.minimumHeight: column.implicitHeight
    Layout.maximumHeight: column.implicitHeight
    implicitWidth: 400
    implicitHeight: column.implicitHeight

    Binding {
        target: Deck
        property: "accent"
        value: Kirigami.Theme.highlightColor
    }

    component Piece: Loader {
        required property string file
        Layout.fillWidth: true
        Layout.preferredWidth: 1  // equal grid columns
        // `available`, not `visible`: a hidden parent would make an item's own visible false too.
        readonly property bool shown: status === Loader.Ready && item.available !== false
        source: Qt.resolvedUrl(file)
        visible: shown
        onStatusChanged: if (status === Loader.Error) console.warn("DeckOS Quick Settings:", file, "is unavailable")
    }

    ColumnLayout {
        id: column
        width: parent.width
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 4
            spacing: 8
            Kirigami.Icon {
                source: Deck.share + "branding/logo.svg"
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
            }
            DeckText {
                Layout.fillWidth: true
                text: "Quick settings"
                font.pixelSize: 15
                font.weight: Font.Bold
            }
            DeckButton {
                round: true
                flat: true
                icon: "ai"
                tip: "Ask DeckOS Assistant (Meta+Space)"
                onClicked: full.backend.launch("deckos-assistant")  // the popup closes as the chat box takes focus
            }
            DeckButton {
                round: true
                flat: true
                icon: "system"
                tip: "Open DeckOS Hub"
                onClicked: full.backend.openHub("home", false)
            }
            DeckButton {
                round: true
                flat: true
                icon: "sliders"
                tip: "System Settings"
                onClicked: full.backend.launch("systemsettings")
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Deck.spacing
            rowSpacing: Deck.spacing
            Piece { file: "NetworkTile.qml" }
            Piece { file: "BluetoothTile.qml" }
            Piece { file: "DndTile.qml" }
            Piece { file: "NightLightTile.qml" }
        }

        Section {
            visible: volume.shown || brightness.shown
            Piece { id: volume; file: "VolumeSection.qml" }
            Piece { id: brightness; file: "BrightnessSection.qml" }
        }

        Piece {
            file: "MediaCard.qml"
            onLoaded: item.expanded = Qt.binding(() => full.backend.expanded)
        }

        Section {
            kicker: "DECKOS"
            RowLayout {
                Layout.fillWidth: true
                spacing: Deck.spacing
                SmallTile {
                    visible: full.backend.gamingAvailable
                    icon: "gaming"
                    title: "Gaming Mode"
                    subtitle: "Switch to Steam"
                    onClicked: full.backend.launch("deckos session gaming --ask")
                }
                SmallTile {
                    icon: "display"
                    title: "Display fix"
                    subtitle: full.backend.displayLevel < 0 ? "…" : "Level " + full.backend.displayLevel
                    active: full.displayOpen
                    onClicked: full.displayOpen = !full.displayOpen
                }
                Piece {
                    file: "FirewallTile.qml"
                    visible: shown && full.backend.firewallInstalled
                    onLoaded: item.backend = full.backend
                }
            }
            DisplayPicker {
                visible: full.displayOpen
                Layout.fillWidth: true
                backend: full.backend
            }
            Piece { id: power; file: "PowerRow.qml" }
            ModeRow {
                Layout.fillWidth: true
                backend: full.backend
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: Deck.border
            }
            UpdatesRow {
                Layout.fillWidth: true
                backend: full.backend
            }
        }
    }
}
