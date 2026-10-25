import QtQuick
import QtQuick.Layouts

// The DecKoOS row's tiles: icon on top, name, status. `tone` colours the status (ok/warn/bad).
Rectangle {
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
    radius: Deck.radius
    color: mouse.pressed ? Deck.pressed : mouse.containsMouse ? Deck.hover : active ? Deck.tint : Deck.raised
    border.width: 1
    border.color: active ? Qt.rgba(Deck.accent.r, Deck.accent.g, Deck.accent.b, 0.55) : Deck.border
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
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: parent.radius + 2
        color: "transparent"
        border.color: Deck.accent
        border.width: 2
        visible: tile.activeFocus
    }
}
