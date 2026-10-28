// A round button with a DecKoOS line icon (image://deckos/icon/NAME/COLOUR).
import QtQuick

Rectangle {
    id: button
    property string icon
    property real size: 52
    property bool filled: false
    signal clicked()

    width: size
    height: size
    radius: size / 2
    color: filled ? "white" : hover.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)
    border.color: Qt.rgba(1, 1, 1, filled ? 0 : 0.14)
    scale: tap.pressed ? 0.92 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }

    Image {
        anchors.centerIn: parent
        width: button.size * 0.46
        height: width
        source: "image://deckos/icon/" + button.icon + "/" + (button.filled ? "0F1115" : "FFFFFF")
        sourceSize: Qt.size(96, 96)
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: button.clicked() }
}
