import QtQuick
// Stand-in for Kirigami.Icon: the preview's image provider recolours masks and maps /usr/share/deckos.
Item {
    property var source: ""
    property bool isMask: false
    property color color: "black"
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(parent.width * 2, parent.height * 2)
        source: parent.source ? "image://deck/" + (parent.isMask ? String(parent.color).slice(1) : "none") + "/"
                                + encodeURIComponent(String(parent.source)) : ""
    }
}
