// Midnight: the Milky Way over a Joshua tree, and the music lives in the sky. The brightest stars glint with the
// highs, the Milky Way breathes with the bass, a faint green airglow along the horizon moves with the melody, and a
// big hit sends a shooting star across. On its own time: a satellite crosses now and then, more shooting stars late
// at night, and the horizon warms at dawn and cools at dusk. Positions are fractions of the photo (credits in
// images/CREDITS.md).
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#8FA8FF"
    property color colorB: "#4C8DFF"
    property real bass: 0
    property real mid: 0
    property real high: 0
    property real energy: 0
    property int beats: 0

    readonly property var bright: [[0.525, 0.31, 1.0], [0.67, 0.21, 0.7], [0.24, 0.45, 0.8], [0.49, 0.36, 0.6],
        [0.96, 0.38, 0.6], [0.845, 0.68, 0.5], [0.13, 0.08, 0.5]]
    property int hour: new Date().getHours()
    property real tick: 0  // slow time, for the twinkle and the airglow's drift
    Timer {
        interval: 60000; repeat: true; running: scene.running; triggeredOnStart: true
        onTriggered: scene.hour = new Date().getHours()
    }
    Timer {
        interval: 100; repeat: true; running: scene.running
        onTriggered: scene.tick += 0.1
    }
    Timer {  // a satellite, every few minutes
        interval: 150000 + Math.random() * 200000; repeat: true; running: scene.running
        onTriggered: satellite.go()
    }
    Timer {  // shooting stars on their own, more of them in the small hours
        interval: (scene.hour >= 1 && scene.hour < 5 ? 60000 : 200000) + Math.random() * 120000
        repeat: true; running: scene.running
        onTriggered: meteor.go(0.6)
    }
    property double lastMeteor: 0
    onBeatsChanged: {
        // Only the big hits, and not too often, or it stops being special
        if (bass > 0.75 && Date.now() - lastMeteor > 20000) {
            lastMeteor = Date.now();
            meteor.go(1.0);
        }
    }

    Image {
        anchors.fill: parent
        source: "../images/midnight.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle { anchors.fill: parent; color: "black"; opacity: 0.12 }

    // ---- the Milky Way breathing with the bass: a long soft light laid along the band
    Glow {
        x: scene.width * 0.35 - width / 2
        y: scene.height * 0.4 - height / 2
        width: scene.width * 0.9; height: scene.height * 0.22
        rotation: -38
        tint: Qt.lighter(scene.colorA, 1.3)
        core: 0.4
        opacity: 0.06 + 0.22 * scene.bass
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }
    // ---- the horizon: green airglow moving with the melody, warm at dawn, blue at dusk
    Repeater {
        model: 3
        Glow {
            required property int index
            x: scene.width * (((index * 0.37 + scene.tick * 0.004 * (index + 1)) % 1.4) - 0.2) - width / 2
            y: scene.height * (0.86 + index * 0.03) - height / 2
            width: scene.width * 0.7; height: scene.height * 0.18
            tint: index === 1 ? scene.colorB : "#5CFFB0"
            core: 0.5
            opacity: 0.05 + 0.3 * scene.mid
        }
    }
    Glow {
        x: scene.width * 0.5 - width / 2; y: scene.height * 1.02 - height / 2
        width: scene.width * 1.6; height: scene.height * 0.5
        tint: scene.hour >= 5 && scene.hour < 8 ? "#FF9A5A" : "#3A6CFF"
        core: 0.45
        opacity: scene.hour >= 5 && scene.hour < 8 ? 0.45 : scene.hour >= 18 && scene.hour < 22 ? 0.3 : 0
        Behavior on opacity { NumberAnimation { duration: 5000 } }
    }
    // ---- the brightest stars glint with the highs, each on its own breath
    Repeater {
        model: scene.bright
        Item {
            id: star
            required property var modelData
            required property int index
            readonly property real twinkle: 0.5 + 0.5 * Math.sin(scene.tick * (1.3 + index * 0.4) + index)
            readonly property real size: scene.height * 0.012 * modelData[2] * (1 + 2.2 * scene.high * twinkle)
            x: modelData[0] * scene.width; y: modelData[1] * scene.height
            Glow {
                x: -width / 2; y: -height / 2
                width: star.size * 6; height: width
                tint: "#DDE8FF"
                opacity: 0.35 + 0.6 * star.twinkle * (0.4 + scene.high)
            }
            Rectangle {  // the spikes a bright star makes through a lens
                x: -width / 2; y: -height / 2
                width: star.size * 7; height: 1.2
                color: "#E8F0FF"
                opacity: 0.25 + 0.6 * scene.high * star.twinkle
            }
            Rectangle {
                x: -width / 2; y: -height / 2
                width: 1.2; height: star.size * 7
                color: "#E8F0FF"
                opacity: 0.25 + 0.6 * scene.high * star.twinkle
            }
        }
    }
    // ---- a shooting star
    Item {
        id: meteor
        property real t: 0
        property real sx: 0.1
        property real sy: 0.1
        property real power: 1
        visible: t > 0 && t < 1
        function go(p) {
            if (fly.running)
                return;
            power = p;
            sx = 0.05 + Math.random() * 0.5;
            sy = 0.03 + Math.random() * 0.2;
            fly.start();
        }
        NumberAnimation { id: fly; target: meteor; property: "t"; from: 0; to: 1; duration: 900; easing.type: Easing.OutQuad }
        Rectangle {
            x: (meteor.sx + meteor.t * 0.32) * scene.width
            y: (meteor.sy + meteor.t * 0.18) * scene.height
            width: scene.width * 0.12 * meteor.power; height: 2
            rotation: 29
            transformOrigin: Item.Right
            opacity: Math.sin(meteor.t * Math.PI)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 1; color: "#FFFFFF" }
            }
        }
    }
    // ---- a satellite: a steady dot crossing slowly, the kind you only notice if you look
    Rectangle {
        id: satellite
        property real t: -1
        function go() { if (!cross.running) cross.start(); }
        NumberAnimation { id: cross; target: satellite; property: "t"; from: 0; to: 1; duration: 60000 }
        visible: t >= 0 && t <= 1
        x: (0.02 + t * 0.96) * scene.width; y: (0.12 + t * 0.1) * scene.height
        width: 2.5; height: 2.5; radius: 1.25
        color: "#F4F8FF"
        opacity: 0.7
    }

    Vignette { anchors.fill: parent }
    Grain { anchors.fill: parent; running: scene.running; strength: 0.05 }
}
