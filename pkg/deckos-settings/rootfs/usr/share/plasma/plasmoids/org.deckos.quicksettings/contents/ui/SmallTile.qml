import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

// The DecKoOS row's tiles: icon on top, name, status. `tone` colours the status (ok/warn/bad).
Item {
    id: tile
    property string icon
    property string title
    property string subtitle
    property string tone: ""
    property bool active: false
    property bool busy: false
    signal clicked()

    Layout.fillWidth: true
    Layout.preferredWidth: 1  // equal widths in the row
    implicitHeight: 76
    Vibes.Notch {
        anchors.fill: parent
        look: Deck.look
        cut: 9
        lit: tile.active
        fill: mouse.pressed ? Deck.pressed : mouse.containsMouse ? Deck.hover : tile.active ? Deck.tint : Deck.raised
    }
    readonly property color toneColor: tone === "ok" ? Deck.success : tone === "warn" ? Deck.warning
                                     : tone === "bad" ? Deck.danger : Deck.subtext

    Accessible.role: Accessible.Button
    Accessible.name: title
    Accessible.description: subtitle
    Accessible.onPressAction: clicked()
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tile.clicked()
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 2
        DeckIcon {
            name: tile.icon
            implicitWidth: 20
            implicitHeight: 20
            color: tile.active ? Deck.accent : Deck.text
            opacity: tile.busy ? 0.4 : 1
        }
        Item { Layout.fillHeight: true }
        DeckText {
            Layout.fillWidth: true
            text: tile.title
            font.weight: Font.DemiBold
        }
        DeckText {
            Layout.fillWidth: true
            sub: true
            text: tile.busy ? "Working…" : tile.subtitle
            color: tile.toneColor
        }
    }
    Rectangle {  // keyboard focus
        anchors.fill: parent
        anchors.margins: -2
        color: "transparent"
        border.color: Deck.accent
        border.width: 2
        visible: tile.activeFocus
    }
}
