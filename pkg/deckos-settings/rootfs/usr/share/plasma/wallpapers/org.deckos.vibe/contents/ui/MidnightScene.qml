// Midnight minimal: near-black, a few stars breathing, and thin lines of light drifting slowly across.
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#8FA8FF"
    property color colorB: "#4C8DFF"

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#05060A" }
            GradientStop { position: 1.0; color: "#0B0E16" }
        }
    }
    Image {  // the Milky Way over a Joshua tree (the drawing above shows only if the photo can't load; credits in images/CREDITS.md)
        anchors.fill: parent
        source: "../images/midnight.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle {  // a little darker, so the visualizer and desktop icons stand out
        anchors.fill: parent
        color: "black"
        opacity: 0.2
    }
    Repeater {  // a few stars breathing over the photo's own
        model: 40
        Rectangle {
            id: star
            required property int index
            readonly property real r: ((index * 7919) % 1000) / 1000
            readonly property real r2: ((index * 104729) % 1000) / 1000
            x: r * scene.width
            y: r2 * scene.height
            width: 1 + (index % 3)
            height: width
            radius: width / 2
            color: index % 5 ? "#C9D3F0" : scene.colorA
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: scene.running
                NumberAnimation { from: 0.15; to: 0.8; duration: 2500 + star.r * 4000; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.8; to: 0.15; duration: 2500 + star.r2 * 4000; easing.type: Easing.InOutSine }
            }
        }
    }
    Repeater {  // drifting lines of light
        model: 5
        Rectangle {
            id: beam
            required property int index
            width: scene.width * (0.25 + index * 0.08)
            height: 1
            y: scene.height * (0.2 + index * 0.15)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: index % 2 ? scene.colorA : scene.colorB }
                GradientStop { position: 1.0; color: "transparent" }
            }
            opacity: 0.45
            NumberAnimation on x {
                from: -beam.width
                to: scene.width
                duration: 26000 + beam.index * 7000
                loops: Animation.Infinite
                running: scene.running
            }
        }
    }
}
