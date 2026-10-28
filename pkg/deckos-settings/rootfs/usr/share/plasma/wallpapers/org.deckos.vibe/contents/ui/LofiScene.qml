// Rainy street (Lo-fi): Lisbon at night in the rain, and the music lives in it. The streetlights swell with the bass
// and their reflections pulse on the wet road, the shop sign buzzes with the mids, every beat drops a ripple in a
// puddle, and loud parts bring heavier rain. It also lives on its own time: showers come and go, the traffic lights
// change, now and then a tram comes up the tracks, and the light follows the time of day.
// Positions are fractions of the photo (16:9, cropped to fill). Credits in images/CREDITS.md.
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#FF9E7A"
    property color colorB: "#B36BFF"
    // The music (MusicFeed): main.qml binds these; the preview feeds made-up ones
    property real bass: 0
    property real mid: 0
    property real high: 0
    property real energy: 0
    property int beats: 0

    readonly property var lamps: [[0.093, 0.10, 1.0], [0.11, 0.18, 0.9], [0.122, 0.26, 0.7], [0.132, 0.305, 0.55],
        [0.138, 0.33, 0.45], [0.293, 0.23, 0.9], [0.256, 0.29, 0.7], [0.232, 0.33, 0.5], [0.225, 0.335, 0.45]]
    readonly property var stops: [[0.12, 0.41], [0.235, 0.40], [0.285, 0.41], [0.3, 0.405]]

    // ---- time: the hour (a minute at a time), showers, and the street's own little events
    property int hour: new Date().getHours()
    property real rain: 0.6  // how hard it's raining, drifting between showers and drizzle
    property real rainTarget: 0.6
    property bool green: false  // the traffic lights
    Timer {
        interval: 60000; repeat: true; running: scene.running; triggeredOnStart: true
        onTriggered: {
            scene.hour = new Date().getHours();
            if (Math.random() < 0.2)
                scene.rainTarget = 0.15 + Math.random() * 0.85;  // a shower comes, or eases off
        }
    }
    Timer {  // rain moves toward its target over a couple of minutes
        interval: 1000; repeat: true; running: scene.running
        onTriggered: scene.rain += (scene.rainTarget - scene.rain) * 0.02
    }
    Timer {  // the lights change, on their own slow cycle
        interval: scene.green ? 25000 : 70000 + Math.random() * 60000; repeat: true; running: scene.running
        onTriggered: scene.green = !scene.green
    }
    Timer {  // a tram every few minutes
        interval: 180000 + Math.random() * 240000; repeat: true; running: scene.running
        onTriggered: tram.go()
    }
    // The colour of the hour: deep blue at night, amber at dusk, pink at dawn, washed out by day
    readonly property color grade: hour >= 22 || hour < 5 ? "#0A1840" : hour < 7 ? "#5A2E4A" : hour < 17 ? "#9AA8B8"
                                                                        : "#6A3A10"
    readonly property real gradeAmount: hour >= 22 || hour < 5 ? 0.38 : hour < 7 ? 0.2 : hour < 17 ? 0.12 : 0.18
    readonly property real lampPower: hour >= 7 && hour < 17 ? 0.45 : 1.0  // by day the lights matter less

    Image {
        id: photo
        anchors.fill: parent
        source: "../images/lofi.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle { anchors.fill: parent; color: "black"; opacity: 0.22 }

    // A soft round light, drawn once and reused: lamps, reflections, the tram's lights
    component Glow: Canvas {
        property color tint: "#FFD9A0"
        width: 200; height: 200
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            const g = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, width / 2);
            g.addColorStop(0, Qt.rgba(tint.r, tint.g, tint.b, 0.9));
            g.addColorStop(0.25, Qt.rgba(tint.r, tint.g, tint.b, 0.35));
            g.addColorStop(1, Qt.rgba(tint.r, tint.g, tint.b, 0));
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, width, height);
        }
        onTintChanged: requestPaint()
        Component.onCompleted: requestPaint()  // a Canvas draws only when asked
    }

    // ---- the lamps, and their reflections down the wet road
    Repeater {
        model: scene.lamps
        Item {
            id: lamp
            required property var modelData
            required property int index
            readonly property real near: modelData[2]
            Glow {
                x: lamp.modelData[0] * scene.width - width / 2
                y: lamp.modelData[1] * scene.height - height / 2
                width: scene.height * 0.24 * lamp.near; height: width
                tint: "#FFD39A"
                scale: 1 + 0.55 * scene.bass * lamp.near
                opacity: (0.3 + 0.7 * scene.bass) * scene.lampPower
                Behavior on scale { NumberAnimation { duration: 90 } }
            }
            Glow {  // the reflection: a tall soft streak on the road below the lamp
                x: lamp.modelData[0] * scene.width - width / 2
                y: scene.height * (0.55 + 0.08 * (1 - lamp.near))
                width: scene.height * 0.09 * lamp.near; height: scene.height * (0.45 - 0.05 * (1 - lamp.near))
                tint: "#FFC27A"
                opacity: (0.18 + 0.6 * scene.bass) * scene.lampPower * (0.6 + 0.4 * scene.rain)
            }
        }
    }
    // ---- traffic lights: red, and now and then green
    Repeater {
        model: scene.stops
        Glow {
            required property var modelData
            x: modelData[0] * scene.width - width / 2
            y: modelData[1] * scene.height - height / 2
            width: scene.height * 0.05; height: width
            tint: scene.green ? "#5CFF9A" : "#FF3A3A"
            opacity: 0.55 + 0.25 * scene.mid
            Behavior on tint { ColorAnimation { duration: 600 } }
        }
    }
    // ---- the shop sign buzzes with the mids, and flickers on a sharp hi-hat
    Glow {
        id: sign
        x: 0.682 * scene.width - width / 2
        y: 0.245 * scene.height - height / 2
        width: scene.height * 0.2; height: width * 0.7
        tint: scene.colorB
        property real flick: 1
        opacity: (0.2 + 0.6 * scene.mid) * flick
        Connections {
            target: scene
            function onHighChanged() { if (scene.high > 0.62 && Math.random() < 0.3) sign.flick = 0.25; else sign.flick = 1; }
        }
    }
    // ---- a tram coming up the tracks: two headlights growing as it nears, their light on the wet road
    Item {
        id: tram
        property real t: 0  // 0: far up the street, 1: gone past
        visible: t > 0 && t < 1
        function go() { if (!run.running) run.start(); }
        NumberAnimation { id: run; target: tram; property: "t"; from: 0; to: 1; duration: 14000; easing.type: Easing.InQuad }
        Repeater {
            model: 2
            Glow {
                required property int index
                readonly property real s: 0.02 + tram.t * 0.22
                x: (0.27 + tram.t * 0.36 + (index ? 1 : -1) * tram.t * 0.06) * scene.width - width / 2
                y: (0.42 + tram.t * 0.5) * scene.height - height / 2
                width: scene.height * s; height: width
                tint: "#FFF4DA"
                opacity: 0.9
            }
        }
    }
    // ---- a ripple in a puddle on every beat
    Repeater {
        id: ripples
        model: 8
        Rectangle {
            property real life: 1
            property real px: 0.2
            property real py: 0.8
            readonly property real persp: 0.4 + (py - 0.6) * 1.5  // nearer ripples are bigger
            x: px * scene.width - width / 2; y: py * scene.height - height / 2
            width: scene.height * 0.12 * life * persp; height: width * 0.28
            radius: height / 2
            color: "transparent"
            border.color: "#FFE2B0"
            border.width: 2
            opacity: (1 - life) * 0.7
            NumberAnimation on life { id: grow; from: 0; to: 1; duration: 1400; running: false; easing.type: Easing.OutQuad }
            function drop() { px = 0.06 + Math.random() * 0.4; py = 0.66 + Math.random() * 0.3; grow.restart(); }
        }
    }
    property int nextRipple: 0
    onBeatsChanged: {
        const r = ripples.itemAt(nextRipple);
        if (r)
            r.drop();
        nextRipple = (nextRipple + 1) % 8;
    }

    // ---- the rain itself, slanting a little; heavier in showers and in loud parts
    Repeater {
        model: 110
        Rectangle {
            id: drop
            required property int index
            readonly property real r: ((index * 7919) % 1000) / 1000
            readonly property real r2: ((index * 104729) % 1000) / 1000
            x: r * scene.width * 1.1 - scene.width * 0.05
            width: 1.2 + r2
            height: scene.height * (0.03 + r2 * 0.05)
            rotation: 8
            color: "#DDE6FF"
            opacity: (index / 110 < scene.rain * 0.7 + scene.energy * 0.4) ? 0.12 + r2 * 0.18 : 0
            NumberAnimation on y {
                from: -scene.height * 0.1 - drop.r2 * scene.height
                to: scene.height * 1.05
                duration: 900 + drop.r * 900
                loops: Animation.Infinite
                running: scene.running
            }
        }
    }

    // ---- the finish: the hour's colour, a vignette, and film grain
    Rectangle { anchors.fill: parent; color: scene.grade; opacity: scene.gradeAmount }
    Canvas {
        anchors.fill: parent
        onWidthChanged: requestPaint()
        Component.onCompleted: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            const g = ctx.createRadialGradient(width / 2, height / 2, height * 0.35, width / 2, height / 2, width * 0.7);
            g.addColorStop(0, "rgba(0,0,0,0)");
            g.addColorStop(1, "rgba(0,0,0,0.55)");
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, width, height);
        }
    }
    Grain { anchors.fill: parent; running: scene.running }
}
