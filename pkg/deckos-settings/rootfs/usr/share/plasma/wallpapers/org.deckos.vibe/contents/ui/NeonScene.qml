// Neon / Synthwave: a striped sun on the horizon and a glowing grid rolling towards you.
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#FF4FD8"
    property color colorB: "#3DE0FF"
    readonly property real horizon: height * 0.58

    Rectangle {  // night sky into a hot horizon
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#07041A" }
            GradientStop { position: 0.5; color: "#1A0838" }
            GradientStop { position: 0.58; color: Qt.darker(scene.colorA, 1.6) }
            GradientStop { position: 0.581; color: "#0A0418" }
            GradientStop { position: 1.0; color: "#05020E" }
        }
    }
    Item {  // the sun, cut by stripes
        width: scene.height * 0.42
        height: width
        x: (scene.width - width) / 2
        y: scene.horizon - height * 0.62
        clip: true
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#FFE36B" }
                GradientStop { position: 1.0; color: scene.colorA }
            }
        }
        Repeater {
            model: 6
            Rectangle {
                required property int index
                width: parent.width
                height: 3 + index * 2.2
                y: parent.height * 0.5 + index * parent.height * 0.08
                color: "#1A0838"
            }
        }
    }
    Item {  // the floor grid
        anchors.fill: parent
        clip: true
        Canvas {  // lines running to the vanishing point (still)
            anchors.fill: parent
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                const ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                ctx.strokeStyle = scene.colorB;
                ctx.globalAlpha = 0.45;
                ctx.lineWidth = 1.5;
                const vx = width / 2;
                for (let i = -24; i <= 24; i++) {
                    ctx.beginPath();
                    ctx.moveTo(vx + i * width * 0.012, scene.horizon);
                    ctx.lineTo(vx + i * width * 0.09, height);
                    ctx.stroke();
                }
            }
        }
        Repeater {  // lines across, rolling forward and spreading out as they come
            model: 12
            Rectangle {
                id: line
                required property int index
                property real t: index / 12
                width: scene.width
                height: 1.5 + t * 2.5
                y: scene.horizon + Math.pow(t, 2.2) * (scene.height - scene.horizon)
                color: scene.colorB
                opacity: 0.25 + t * 0.5
                NumberAnimation on t {
                    from: line.index / 12
                    to: line.index / 12 + 1 / 12
                    duration: 900
                    loops: Animation.Infinite
                    running: scene.running
                }
            }
        }
    }
    Rectangle {  // horizon glow
        width: parent.width
        height: 3
        y: scene.horizon - 1
        color: scene.colorA
        opacity: 0.9
    }
}
