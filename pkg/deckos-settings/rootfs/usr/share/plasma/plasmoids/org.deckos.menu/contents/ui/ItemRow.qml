// One row in a list (recent items, an app category, search results): icon, name, a muted second
// line. A view with `keepCurrent: true` (search) lights its current row while the search field
// keeps the keyboard.
import QtQuick
import org.deckos.vibes as Vibes
import org.kde.kirigami as Kirigami

Item {
    id: row

    required property var model
    required property int index
    readonly property ListView view: ListView.view
    readonly property bool cursor: ListView.isCurrentItem && (view.activeFocus || view.keepCurrent === true)
    readonly property bool lit: cursor || mouse.containsMouse
    readonly property string subtitle: model.description && model.description !== model.display ? model.description : ""

    width: view.width
    height: 44
    Accessible.role: Accessible.ListItem
    Accessible.name: model.display

    Vibes.Notch {

        pulse: deckMenu.pulse  // the music's beat (deckos vibe react on)
        anchors.fill: parent
        anchors.topMargin: 1
        anchors.bottomMargin: 1
        visible: row.lit || row.cursor
        look: deckMenu.look
        cut: 8
        lit: row.cursor
        fill: row.lit ? deckMenu.hot : "transparent"
    }

    Kirigami.Icon {
        x: 8
        anchors.verticalCenter: parent.verticalCenter
        width: 30
        height: 30
        source: row.model.decoration
    }

    Column {
        x: 48
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - (hint.visible ? hint.width + 16 : 10)
        spacing: 1
        Text {
            width: parent.width
            text: row.model.display
            color: deckMenu.text
            font.pixelSize: 13
            elide: Text.ElideRight
            maximumLineCount: 1
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: row.subtitle
            color: deckMenu.subtext
            font.pixelSize: 11
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
    }

    Text {
        id: hint
        visible: row.cursor && row.view.keepCurrent === true
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: "Enter"
        color: deckMenu.subtext
        font.pixelSize: 11
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onEntered: {
            if (row.view.keepCurrent !== true) {
                row.view.currentIndex = row.index;
            }
        }
        onClicked: event => {
            if (event.button === Qt.RightButton) {
                deckMenu.showActions(row.view.model, row.index, row.model, row, false);
            } else {
                deckMenu.activate(row.view.model, row.index);
            }
        }
    }
}
