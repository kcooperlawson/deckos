// Square outlined button with a line icon (power actions). `tip` shows in the footer on hover.
import QtQuick

Rectangle {
    id: root

    property string icon
    property string tip
    readonly property bool hovered: mouse.containsMouse
    signal clicked()

    width: 36
    height: 36
    radius: 9
    color: mouse.pressed ? deckMenu.border : hovered || activeFocus ? deckMenu.raised : "transparent"
    border.color: activeFocus ? deckMenu.accent : deckMenu.border
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: tip
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onSpacePressed: clicked()

    LineIcon {
        anchors.centerIn: parent
        name: root.icon
        tint: root.hovered || root.activeFocus ? deckMenu.text : "#C9CEDA"
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.clicked()
    }
}
