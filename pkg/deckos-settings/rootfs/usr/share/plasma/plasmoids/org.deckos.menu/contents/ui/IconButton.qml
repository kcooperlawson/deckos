// Notched outlined button with a line icon (power actions). `tip` shows in the footer on hover.
import QtQuick
import org.deckos.vibes as Vibes

Item {
    id: root

    property string icon
    property string tip
    readonly property bool hovered: mouse.containsMouse
    signal clicked()

    width: 36
    height: 36
    Vibes.Notch {
        pulse: deckMenu.pulse  // the music's beat (deckos vibe react on)
        anchors.fill: parent
        look: deckMenu.look
        cut: 8
        lit: root.activeFocus
        fill: mouse.pressed ? deckMenu.border : root.hovered || root.activeFocus ? deckMenu.raised : "transparent"
    }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: tip
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onSpacePressed: clicked()

    LineIcon {
        anchors.centerIn: parent
        name: root.icon
        tint: root.hovered || root.activeFocus ? deckMenu.text : Qt.tint(deckMenu.text, Qt.rgba(deckMenu.subtext.r, deckMenu.subtext.g, deckMenu.subtext.b, 0.4))
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.clicked()
    }
}
