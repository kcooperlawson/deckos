// Cozy / Forest: layered hills of pine at dusk, with fireflies wandering and glowing.
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#F2C46D"
    property color colorB: "#6FBF8E"

    Rectangle {  // evening sky
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#14211F" }
            GradientStop { position: 0.6; color: "#2C3B2C" }
            GradientStop { position: 1.0; color: "#3E3324" }
        }
    }
    Canvas {  // three ridges of pines, nearer ones darker (drawn once)
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            const ridges = [[0.55, "#24372B"], [0.68, "#1A2A20"], [0.8, "#111C15"]];
            let seed = 11;
            const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
            for (const [base, colour] of ridges) {
                ctx.fillStyle = colour;
                ctx.beginPath();
                ctx.moveTo(0, height);
                for (let x = 0; x <= width; x += width / 60) {
                    const top = height * base - Math.sin(x / width * 6 + base * 9) * height * 0.03;
                    const tree = height * (0.03 + rnd() * 0.05);
                    ctx.lineTo(x, top);
                    ctx.lineTo(x + width / 120, top - tree);
                }
                ctx.lineTo(width, height);
                ctx.closePath();
                ctx.fill();
            }
        }
    }
    Image {  // pines at dusk (the drawing above shows only if the photo can't load; credits in images/CREDITS.md)
        anchors.fill: parent
        source: "../images/cozy.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle {  // a little darker, so the visualizer and desktop icons stand out
        anchors.fill: parent
        color: "black"
        opacity: 0.15
    }
    Repeater {  // fireflies
        model: 28
        Rectangle {
            id: fly
            required property int index
            readonly property real r: ((index * 7919) % 1000) / 1000
            readonly property real r2: ((index * 104729) % 1000) / 1000
            width: 4
            height: 4
            radius: 2
            color: scene.colorA
            x: r * scene.width
            y: scene.height * (0.55 + r2 * 0.4)
            Rectangle {  // the glow
                anchors.centerIn: parent
                width: 18
                height: 18
                radius: 9
                color: scene.colorA
                opacity: 0.18
            }
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: scene.running
                NumberAnimation { to: 1; duration: 1200 + fly.r * 2000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.1; duration: 1600 + fly.r2 * 2400; easing.type: Easing.InOutSine }
            }
            SequentialAnimation on x {
                loops: Animation.Infinite
                running: scene.running
                NumberAnimation { to: fly.r * scene.width + 60; duration: 7000 + fly.r2 * 5000; easing.type: Easing.InOutSine }
                NumberAnimation { to: fly.r * scene.width - 40; duration: 8000 + fly.r * 5000; easing.type: Easing.InOutSine }
            }
        }
    }
}
