// Neon: Manhattan across the river under a violet sky, and the city plays along. The reflections on the water shimmer
// with the song, low notes on the left to high on the right; the Empire State's spire and the gold dome breathe with
// the bass, the blue mast with the melody, the Chrysler crown glints with the highs. On its own time: the sky's colour
// follows the hour, a plane crosses now and then, and the masts' warning lights blink. Positions are fractions of the
// photo (credits in images/CREDITS.md).
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#FF4FD8"
    property color colorB: "#3DE0FF"
    property real bass: 0
    property real mid: 0
    property real high: 0
    property real energy: 0
    property int beats: 0
    property var levels: []

    property real tick: 0
    property int hour: new Date().getHours()
    readonly property real water: 0.805  // the waterline

    // The landmarks: [x, y, size, part of the music, colour]
    readonly property var lights: [[0.342, 0.325, 0.07, "bass", "#FFF2CF"], [0.342, 0.47, 0.16, "bass", "#FFE7A8"],
        [0.117, 0.565, 0.07, "bass", "#FFC23A"], [0.587, 0.455, 0.06, "mid", "#7AA8FF"],
        [0.548, 0.5, 0.05, "mid", "#5CFFB0"], [0.928, 0.47, 0.06, "high", "#F2F5FF"]]

    function level(frac) {  // the music under a point of the river (0 left .. 1 right)
        const n = levels.length;
        if (!n)
            return 0.15 * energy;
        return levels[Math.min(n - 1, Math.floor(frac * n))] || 0;
    }

    Timer {
        interval: 50; repeat: true; running: scene.running
        onTriggered: scene.tick += 0.05
    }
    Timer {
        interval: 60000; repeat: true; running: scene.running; triggeredOnStart: true
        onTriggered: scene.hour = new Date().getHours()
    }
    Timer {  // a plane now and then
        interval: 120000 + Math.random() * 180000; repeat: true; running: scene.running
        onTriggered: plane.go()
    }

    Image {
        anchors.fill: parent
        source: "../images/neon.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    // The sky's colour through the night: violet in the evening, deep blue in the small hours, pink toward dawn
    Rectangle {
        anchors.fill: parent
        color: scene.hour >= 1 && scene.hour < 5 ? "#0A1640" : scene.hour >= 5 && scene.hour < 8 ? "#6A2A5A" : scene.colorA
        opacity: scene.hour >= 1 && scene.hour < 5 ? 0.3 : 0.08
        Behavior on color { ColorAnimation { duration: 20000 } }
    }

    // ---- the landmarks breathe with their part of the music
    Repeater {
        model: scene.lights
        Glow {
            required property var modelData
            readonly property real v: modelData[3] === "bass" ? scene.bass : modelData[3] === "mid" ? scene.mid : scene.high
            x: modelData[0] * scene.width - width / 2
            y: modelData[1] * scene.height - height / 2
            width: scene.height * modelData[2] * (1 + 0.6 * v); height: width * (modelData[2] > 0.1 ? 1.6 : 1)
            tint: modelData[4]
            core: 0.2
            opacity: 0.15 + 0.7 * v
        }
    }
    // ---- the river: the city's reflections shimmer with the song, across the water from low to high
    Repeater {
        model: 28
        Glow {
            required property int index
            readonly property real fx: (index + 0.5) / 28
            readonly property real v: scene.level(fx)
            readonly property real wobble: Math.sin(scene.tick * (1.1 + index % 5 * 0.3) + index * 1.7)
            x: fx * scene.width - width / 2 + wobble * scene.width * 0.003
            y: scene.height * (scene.water + 0.005)
            width: scene.width / 28 * 0.9; height: scene.height * (0.08 + 0.12 * v)
            tint: index % 3 === 0 ? scene.colorA : index % 3 === 1 ? "#FFD9A0" : scene.colorB
            core: 0.15
            opacity: 0.1 + 0.6 * v
        }
    }
    // ---- a plane, blinking across
    Item {
        id: plane
        property real t: -1
        function go() { if (!flight.running) flight.start(); }
        NumberAnimation { id: flight; target: plane; property: "t"; from: 0; to: 1; duration: 45000 }
        visible: t >= 0 && t <= 1
        x: (1.02 - t * 1.04) * scene.width; y: scene.height * (0.12 + t * 0.06)
        Glow { x: -width / 2; y: -height / 2; width: 10; height: 10; tint: "#FFFFFF"; opacity: 0.9 }
        Glow {
            x: 8 - width / 2; y: -height / 2; width: 14; height: 14; tint: "#FF4040"
            opacity: Math.sin(scene.tick * 6) > 0.6 ? 1 : 0.1
        }
    }
    // ---- warning lights on the masts, blinking slowly
    Repeater {
        model: [[0.342, 0.315], [0.548, 0.475], [0.587, 0.448]]
        Glow {
            required property var modelData
            required property int index
            x: modelData[0] * scene.width - width / 2; y: modelData[1] * scene.height - height / 2
            width: scene.height * 0.018; height: width
            tint: "#FF3A3A"
            opacity: Math.sin(scene.tick * 1.3 + index * 2) > 0.3 ? 0.9 : 0.1
        }
    }

    Vignette { anchors.fill: parent; strength: 0.5 }
    Grain { anchors.fill: parent; running: scene.running; strength: 0.05 }
}
