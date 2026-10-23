import QtQuick
import QtQuick.Layouts

// A toggle tile: icon chip, title and status. Clicking toggles; the chevron (when `hasMore`)
// opens the matching settings page instead.
Rectangle {
    id: tile
    property string icon
    property string title
    property string subtitle
    property bool checked: false
    property bool busy: false
    property bool hasMore: false
    signal toggled()
    signal more()

    Layout.fillWidth: true
    implicitHeight: 58
    radius: Deck.radius
    color: main.pressed ? Deck.pressed : main.containsMouse ? Deck.hover : checked ? Deck.tint : Deck.raised
    border.width: 1
    border.color: checked ? Qt.rgba(Deck.accent.r, Deck.accent.g, Deck.accent.b, 0.55) : Deck.border
    Behavior on color { ColorAnimation { duration: 120 } }

    Accessible.role: Accessible.CheckBox
    Accessible.name: title
    Accessible.description: subtitle
    Accessible.checked: checked
    Accessible.onToggleAction: toggled()
    Accessible.onPressAction: toggled()
    activeFocusOnTab: true
    Keys.onSpacePressed: toggled()
    Keys.onReturnPressed: toggled()

    MouseArea {
        id: main
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tile.toggled()
    }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: tile.hasMore ? 4 : 10
        spacing: 10
        Rectangle {
            implicitWidth: 34
            implicitHeight: 34
            radius: 9
            color: Deck.surface
            gradient: tile.checked ? chipGrad : null
            Gradient {
                id: chipGrad
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Deck.accent }
                GradientStop { position: 1; color: Deck.accentB }
            }
            DeckIcon {
                anchors.centerIn: parent
                width: 18
                height: 18
                name: tile.icon
                color: tile.checked ? "white" : Deck.subtext
                opacity: tile.busy ? 0.4 : 1
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            DeckText {
                Layout.fillWidth: true
                text: tile.title
                font.weight: Font.DemiBold
            }
            DeckText {
                Layout.fillWidth: true
                sub: true
                text: tile.busy ? "Working…" : tile.subtitle
                color: tile.checked ? Qt.lighter(Deck.accent, 1.35) : Deck.subtext
            }
        }
        Rectangle {
            visible: tile.hasMore
            implicitWidth: 26
            Layout.fillHeight: true
            Layout.topMargin: 6
            Layout.bottomMargin: 6
            radius: 7
            color: moreMouse.containsMouse ? Deck.pressed : "transparent"
            DeckIcon {
                anchors.centerIn: parent
                width: 14
                height: 14
                name: "chevron"
                color: Deck.subtext
            }
            MouseArea {
                id: moreMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: tile.more()
            }
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
