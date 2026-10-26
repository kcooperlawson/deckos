// Lo-fi: a warm dusk over a city skyline, seen through a rainy window. Raindrops run down the glass.
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#FF9E7A"
    property color colorB: "#B36BFF"

    Rectangle {  // dusk sky
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#1B1730" }
            GradientStop { position: 0.55; color: Qt.darker(scene.colorB, 2.6) }
            GradientStop { position: 0.85; color: Qt.darker(scene.colorA, 1.9) }
            GradientStop { position: 1.0; color: "#2A1C2E" }
        }
    }
    Rectangle {  // a low sun behind the haze
        width: parent.height * 0.28
        height: width
        radius: width / 2
        x: parent.width * 0.68
        y: parent.height * 0.52
        color: scene.colorA
        opacity: 0.35
    }
    Canvas {  // skyline with lit windows, drawn once (it doesn't move)
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            let seed = 7;
            const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
            let x = 0;
            while (x < width) {
                const w = width * (0.03 + rnd() * 0.05), h = height * (0.12 + rnd() * 0.3);
                ctx.fillStyle = "#120F1E";
                ctx.fillRect(x, height - h, w, h);
                ctx.fillStyle = "rgba(255, 196, 120, 0.55)";
                for (let wy = height - h + 10; wy < height - 12; wy += 14)
                    for (let wx = x + 6; wx < x + w - 6; wx += 11)
                        if (rnd() < 0.18)
                            ctx.fillRect(wx, wy, 4, 6);
                x += w + 2;
            }
        }
    }
    Image {  // Lisbon in the night rain (the drawing above shows only if the photo can't load; credits in images/CREDITS.md)
        anchors.fill: parent
        source: "../images/lofi.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle {  // a little darker, so the visualizer and desktop icons stand out
        anchors.fill: parent
        color: "black"
        opacity: 0.25
    }
    Rectangle {  // the glass: a soft haze over everything
        anchors.fill: parent
        color: Qt.rgba(scene.colorB.r, scene.colorB.g, scene.colorB.b, 0.08)
    }
    Repeater {  // rain on the glass
        model: 70
        Rectangle {
            id: drop
            required property int index
            readonly property real r: ((index * 7919) % 1000) / 1000
            readonly property real r2: ((index * 104729) % 1000) / 1000
            x: r * scene.width
            width: 2 + r2 * 2
            height: 14 + r2 * 26
            radius: width / 2
            color: "#DDE6FF"
            opacity: 0.18 + r2 * 0.2
            NumberAnimation on y {
                from: -60 - drop.r2 * scene.height
                to: scene.height + 40
                duration: 2600 + drop.r * 3400
                loops: Animation.Infinite
                running: scene.running
            }
        }
    }
}
