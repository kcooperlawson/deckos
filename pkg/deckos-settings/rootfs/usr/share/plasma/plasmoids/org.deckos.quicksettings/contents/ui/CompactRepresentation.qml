import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// The panel button: the sliders icon, with a badge when updates are waiting.
MouseArea {
    id: compact
    property var backend
    property bool expanded: false
    property bool vertical: false
    property bool wasExpanded: false
    signal activated(bool open)

    Layout.minimumWidth: vertical ? -1 : height
    Layout.minimumHeight: vertical ? width : -1
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton
    onPressed: wasExpanded = expanded
    onClicked: activated(!wasExpanded)

    Accessible.role: Accessible.Button
    Accessible.name: "Quick settings"
    Accessible.description: backend.updatesText

    DeckIcon {
        id: icon
        anchors.centerIn: parent
        readonly property int size: Math.min(compact.width, compact.height)
        width: size >= 32 ? 22 : 16  // icon sizes Plasma's own panel icons use
        height: width
        name: "sliders"
        color: compact.containsMouse || compact.expanded ? Deck.accent : Kirigami.Theme.textColor
    }
    Rectangle {
        visible: compact.backend.updateCount > 0
        anchors.left: icon.horizontalCenter
        anchors.bottom: icon.verticalCenter
        anchors.leftMargin: 2
        anchors.bottomMargin: 2
        height: 15
        width: Math.max(height, badgeText.implicitWidth + 8)
        color: Deck.accent
        border.width: 2
        border.color: Deck.bg
        Text {
            id: badgeText
            anchors.centerIn: parent
            text: compact.backend.updateCount > 99 ? "99+" : compact.backend.updateCount
            color: Deck.ink
            font.family: Deck.hud
            font.pixelSize: 10
            font.weight: Font.Bold
        }
    }
}
