// A widget's card: a translucent slate plate (or nothing, when the Vibe floats its text on the scene)
import QtQuick

Rectangle {
    property var look
    radius: look ? look.radius : 14
    color: look && look.plate ? Qt.rgba(0.05, 0.06, 0.09, 0.55) : "transparent"
    border.width: look && look.plate ? 1 : 0
    border.color: Qt.rgba(1, 1, 1, 0.08)
}
