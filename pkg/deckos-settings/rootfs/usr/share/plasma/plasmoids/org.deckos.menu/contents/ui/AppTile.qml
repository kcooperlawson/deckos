// One app in the pinned grid: icon over its name, lit when hovered or picked with the keyboard.
import QtQuick
import org.deckos.vibes as Vibes
import org.kde.kirigami as Kirigami

Item {
    id: tile

    required property var model
    required property int index
    readonly property GridView view: GridView.view
    readonly property bool lit: GridView.isCurrentItem && (view.activeFocus || mouse.containsMouse)

    width: view.cellWidth
    height: view.cellHeight
    Accessible.role: Accessible.ListItem
    Accessible.name: model.display

    Vibes.Notch {  // lit: a notched tile with the gradient edge

        pulse: deckMenu.pulse  // the music's beat (deckos vibe react on)
        anchors.fill: parent
        anchors.margins: 2
        visible: tile.lit
        look: deckMenu.look
        cut: 10
        fill: deckMenu.hot
    }

    Kirigami.Icon {
        id: icon
        anchors.horizontalCenter: parent.horizontalCenter
        y: 12
        width: 44
        height: 44
        source: tile.model.decoration
    }

    Text {
        x: 6
        width: parent.width - 12
        anchors.top: icon.bottom
        anchors.topMargin: 8
        text: tile.model.display
        color: deckMenu.text
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }

    Rectangle {  // newly installed
        visible: tile.model.isNewlyInstalled === true
        x: icon.x + icon.width - 5
        y: icon.y - 3
        width: 10
        height: 10
        radius: 5
        color: deckMenu.accent
        border.color: deckMenu.surface
        border.width: 2
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onEntered: tile.view.currentIndex = tile.index
        onClicked: event => {
            if (event.button === Qt.RightButton) {
                deckMenu.showActions(tile.view.model, tile.index, tile.model, tile, true);
            } else {
                deckMenu.activate(tile.view.model, tile.index);
            }
        }
    }
}
