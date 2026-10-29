// A notched DecKo button with a DecKoOS line icon (image://deckos/icon/NAME/COLOUR); `filled` is the one button
// filled with the gradient (play/pause).
import QtQuick
import org.deckos.vibes as Vibes

Item {
    id: button
    property string icon
    property real size: 52
    property bool filled: false
    signal clicked()

    width: size
    height: size
    scale: tap.pressed ? 0.92 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }

    Vibes.Look { id: look; colorA: engine.accent; colorB: engine.second }
    Vibes.Notch {
        anchors.fill: parent
        look: look
        cut: button.size * 0.19
        lit: false
        edge: button.filled ? 0 : 1
        fill: hover.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)
        gradientFill: button.filled
        opacity: button.filled && hover.hovered ? 0.9 : 1
    }
    Image {
        anchors.centerIn: parent
        width: button.size * 0.46
        height: width
        source: "image://deckos/icon/" + button.icon + "/" + (button.filled ? "0B0D16" : "FFFFFF")
        sourceSize: Qt.size(96, 96)
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: button.clicked() }
}
