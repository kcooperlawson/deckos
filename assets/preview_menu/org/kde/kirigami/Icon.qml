// Stand-in for Kirigami.Icon: DeckOS line icons through the preview's recolouring provider; app
// icons (names from the canned models) as coloured tiles with a line icon, like the mock.
import QtQuick
Item {
    id: root
    property var source
    property color color: "#E8EAF0"
    property bool isMask: false
    property bool active: false
    property bool roundToIconSize: true
    readonly property string src: source ? String(source) : ""
    readonly property bool line: src.indexOf("deckos/icons/") >= 0
    readonly property var app: previewIcons[src] || null
    readonly property bool valid: line || app !== null
    Image {
        anchors.fill: parent
        visible: root.line
        sourceSize: Qt.size(root.width * 2, root.height * 2)
        source: root.line ? "image://ic/" + root.src.split("/").pop().replace(".svg", "") + "?" + (root.isMask ? root.color : "#000") : ""
    }
    Rectangle {
        anchors.fill: parent
        visible: root.app !== null
        radius: width * 0.24
        color: root.app ? root.app[1] : "transparent"
        border.color: Qt.lighter(color, 1.3)
        Image {
            anchors.centerIn: parent
            width: parent.width * 0.55; height: width
            sourceSize: Qt.size(width * 2, height * 2)
            source: root.app ? "image://ic/" + root.app[0] + "?#FFFFFF" : ""
        }
    }
}
