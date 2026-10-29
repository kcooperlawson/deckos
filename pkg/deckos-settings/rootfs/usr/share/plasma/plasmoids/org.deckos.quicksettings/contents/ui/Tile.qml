import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

// A toggle tile (a DecKo notch, lit when on): icon chip, title and status. Clicking toggles; the chevron (when `hasMore`)
// opens the matching settings page instead.
Item {
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
    implicitHeight: 64

    Vibes.Notch {
        anchors.fill: parent
        look: Deck.look
        cut: 10
        lit: tile.checked
        fill: main.pressed ? Deck.pressed : main.containsMouse ? Deck.hover : tile.checked ? Deck.tint : Deck.raised
    }

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
        Vibes.Notch {
            implicitWidth: 38
            implicitHeight: 38
            look: Deck.look
            cut: 8
            lit: false
            edge: 0
            fill: Deck.surface
            gradientFill: tile.checked
            DeckIcon {
                anchors.centerIn: parent
                width: 18
                height: 18
                name: tile.icon
                color: tile.checked ? Deck.ink : Deck.subtext
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
    Rectangle {  // keyboard focus
        anchors.fill: parent
        anchors.margins: -2
        color: "transparent"
        border.color: Deck.accent
        border.width: 2
        visible: tile.activeFocus
    }
}
