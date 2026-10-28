// Play, skip, how far in, and the library: fade in when the mouse moves, out after a few seconds.
import QtQuick

Column {
    id: controls
    property bool shown: false
    signal library()
    signal look()

    spacing: 18
    opacity: shown ? 1 : 0
    enabled: shown
    Behavior on opacity { NumberAnimation { duration: 350 } }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 22
        IconButton { icon: "music"; anchors.verticalCenter: parent.verticalCenter; onClicked: controls.library() }
        IconButton { icon: "previous"; anchors.verticalCenter: parent.verticalCenter; onClicked: engine.previous() }
        IconButton {
            icon: engine.playing ? "pause" : "play"
            size: 72
            filled: true
            onClicked: engine.playPause()
        }
        IconButton { icon: "next"; anchors.verticalCenter: parent.verticalCenter; onClicked: engine.next() }
        IconButton { icon: "appearance"; anchors.verticalCenter: parent.verticalCenter; onClicked: controls.look() }
    }

    Item {  // how far in; click to jump
        id: seek
        width: 520
        height: 22
        anchors.horizontalCenter: parent.horizontalCenter
        visible: engine.length > 0
        property real pos: 0
        Timer {
            interval: 500; repeat: true; triggeredOnStart: true
            running: controls.shown && seek.visible
            onTriggered: seek.pos = engine.position()
        }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            height: 4
            radius: 2
            color: Qt.rgba(1, 1, 1, 0.18)
            Rectangle {
                height: parent.height
                radius: 2
                width: parent.width * Math.min(1, seek.pos / Math.max(1, engine.length))
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: engine.accent }
                    GradientStop { position: 1; color: engine.second }
                }
            }
        }
        TapHandler {
            onTapped: point => {
                seek.pos = engine.length * point.position.x / seek.width;
                engine.seek(seek.pos);
            }
        }
    }
}
