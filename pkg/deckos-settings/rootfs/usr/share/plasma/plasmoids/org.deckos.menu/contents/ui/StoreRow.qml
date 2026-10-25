// An app from the DecKoOS Store that isn't installed: icon, name, what it is and where it comes from,
// and "Get it", which opens the Store on it. With `line` set it's a plain link row instead.
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: row

    property var app: ({})
    property string line: ""  // a DecKoOS line icon instead of the app's icon, and no button
    property bool cursor: false
    readonly property bool lit: cursor || mouse.containsMouse
    signal chosen()

    height: 44
    Accessible.role: Accessible.Button
    Accessible.name: line ? app.name : "Get " + app.name

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 1
        anchors.bottomMargin: 1
        radius: 9
        color: row.lit ? deckMenu.hot : "transparent"
        border.color: row.cursor ? deckMenu.hotBorder : "transparent"
    }

    Rectangle {
        x: 8
        anchors.verticalCenter: parent.verticalCenter
        width: 30
        height: 30
        radius: 8
        color: row.line || !appIcon.valid ? deckMenu.raised : "transparent"
        border.color: row.line || !appIcon.valid ? deckMenu.border : "transparent"

        Kirigami.Icon {
            id: appIcon
            anchors.fill: parent
            visible: !row.line && valid
            source: row.app.icon || ""
        }
        LineIcon {
            anchors.centerIn: parent
            visible: !appIcon.visible
            name: row.line || "package"
            tint: deckMenu.accent
        }
    }

    Column {
        x: 48
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - (button.visible ? button.width + 20 : 10)
        spacing: 1
        Text {
            width: parent.width
            text: row.app.name || ""
            color: deckMenu.text
            font.pixelSize: 13
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: [row.app.summary, row.app.source].filter(s => !!s).join(" · ")
            color: deckMenu.subtext
            font.pixelSize: 11
            elide: Text.ElideRight
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: row.chosen()
    }

    Rectangle {
        id: button
        visible: !row.line
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        width: getRow.width + 22
        height: 30
        radius: 8
        color: buttonMouse.containsMouse ? Qt.rgba(0.30, 0.55, 1, 0.12) : "transparent"
        border.color: deckMenu.accent

        Row {
            id: getRow
            anchors.centerIn: parent
            spacing: 5
            LineIcon {
                name: "download"
                width: 14
                height: 14
                tint: deckMenu.accent
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: "Get it"
                color: deckMenu.accent
                font.pixelSize: 12
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            id: buttonMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: row.chosen()
        }
    }
}
