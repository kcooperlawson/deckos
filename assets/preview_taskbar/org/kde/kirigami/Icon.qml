import QtQuick
// Stand-in for Kirigami.Icon: preview_taskbar.py draws a coloured app tile with a DecKoOS line icon.
Item {
    property var source: ""
    property bool active
    Image { anchors.fill: parent; sourceSize: Qt.size(96, 96); source: parent.source ? "image://app/" + parent.source : "" }
}
