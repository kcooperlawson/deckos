// Play, skip, how far in, and the library: fade in when the mouse moves, out after a few seconds.
import QtQuick
import org.deckos.vibes as Vibes

Column {
    id: controls
    property bool shown: false
    signal library()
    signal look()
    Vibes.Look { id: dlook; colorA: engine.accent; colorB: engine.second }

    spacing: 18
    opacity: shown ? 1 : 0
    enabled: shown
    Behavior on opacity { NumberAnimation { duration: 350 } }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 14
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
        width: 560
        height: 22
        anchors.horizontalCenter: parent.horizontalCenter
        visible: engine.length > 0
        property real pos: 0
        Timer {
            interval: 500; repeat: true; triggeredOnStart: true
            running: controls.shown && seek.visible
            onTriggered: seek.pos = engine.position()
        }
        Vibes.Segments {  // how far in, in lit segments like the Spectrum look
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            look: dlook
            plain: true
            count: 60
            spacing: 2
            segmentHeight: 6
            value: seek.pos / Math.max(1, engine.length)
        }
        TapHandler {
            onTapped: point => {
                seek.pos = engine.length * point.position.x / seek.width;
                engine.seek(seek.pos);
            }
        }
    }
}
