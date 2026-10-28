// Cozy: pines at dusk with the last light in the gap, and the music lives in the forest. Fireflies drift in the dark
// and flash together on the beat (real fireflies do sync up), more of them come out as the song builds, the last
// light in the gap breathes with the bass, and ground mist rolls with the energy. On its own time: the afterglow
// fades into night and the moon comes up in the gap, and now and then a breeze pushes the mist through.
// Positions are fractions of the photo (credits in images/CREDITS.md).
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#F5B84B"
    property color colorB: "#3DD68C"
    property real bass: 0
    property real mid: 0
    property real high: 0
    property real energy: 0
    property int beats: 0

    property int hour: new Date().getHours()
    readonly property bool night: hour >= 22 || hour < 5
    property real tick: 0
    property real flash: 0  // the fireflies' shared blink, set by each beat and fading
    property real breeze: 0
    Timer {
        interval: 60000; repeat: true; running: scene.running; triggeredOnStart: true
        onTriggered: scene.hour = new Date().getHours()
    }
    Timer {
        interval: 50; repeat: true; running: scene.running
        onTriggered: {
            scene.tick += 0.05;
            scene.flash *= 0.9;
            scene.breeze *= 0.995;
        }
    }
    Timer {  // a breeze through the trees, every few minutes
        interval: 120000 + Math.random() * 180000; repeat: true; running: scene.running
        onTriggered: scene.breeze = 1
    }
    onBeatsChanged: flash = 1

    Image {
        anchors.fill: parent
        source: "../images/cozy.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle { anchors.fill: parent; color: "#050812"; opacity: scene.night ? 0.35 : 0.1 }

    // ---- the last light in the gap, breathing with the bass (gone at night: the moon takes over)
    Glow {
        x: scene.width * 0.5 - width / 2; y: scene.height * 0.8 - height / 2
        width: scene.height * 0.75; height: width * 0.8
        tint: scene.colorA
        core: 0.3
        opacity: (scene.night ? 0.05 : 0.25) + 0.35 * scene.bass
    }
    Glow {  // the moon, risen in the gap at night
        x: scene.width * 0.53 - width / 2; y: scene.height * 0.42 - height / 2
        width: scene.height * 0.16; height: width
        tint: "#EAF0FF"
        core: 0.12
        opacity: scene.night ? 0.85 : 0
        Behavior on opacity { NumberAnimation { duration: 8000 } }
    }

    // ---- fireflies: wandering in the dark, flashing together on the beat; more come out as the song builds
    Repeater {
        model: 46
        Glow {
            id: fly
            required property int index
            readonly property real r: ((index * 7919) % 1000) / 1000
            readonly property real r2: ((index * 104729) % 1000) / 1000
            readonly property real r3: ((index * 3571) % 1000) / 1000
            // Drift: each on its own slow loop, kept out of the bright gap in the trees
            readonly property real fx: (r < 0.5 ? r * 0.76 : 0.62 + (r - 0.5) * 0.76) + 0.04 * Math.sin(scene.tick * (0.3 + r2 * 0.4) + index)
            readonly property real fy: 0.55 + r2 * 0.4 + 0.03 * Math.cos(scene.tick * (0.25 + r3 * 0.35) + index * 2)
            readonly property bool out: index / 46 < 0.35 + 0.65 * scene.energy
            x: fx * scene.width - width / 2; y: fy * scene.height - height / 2
            width: scene.height * (0.018 + 0.02 * r3); height: width
            tint: index % 4 === 0 ? scene.colorB : "#E8FF7A"
            core: 0.2
            // Their own slow glow, and every one lights up at once on the beat
            opacity: out ? Math.min(1, 0.15 + 0.35 * (0.5 + 0.5 * Math.sin(scene.tick * 1.7 + index * 1.3))
                                       + 0.8 * scene.flash * (0.6 + 0.4 * r)) : 0
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }
    }

    // ---- ground mist rolling across, thicker with the energy, pushed along by a breeze
    Repeater {
        model: 4
        Glow {
            required property int index
            x: scene.width * ((index * 0.31 + scene.tick * (0.004 + 0.02 * scene.breeze) * (1 + index * 0.3)) % 1.5 - 0.25) - width / 2
            y: scene.height * (0.9 + (index % 2) * 0.05) - height / 2
            width: scene.width * 0.8; height: scene.height * 0.22
            tint: scene.night ? "#9FB3D9" : "#C8B8C8"
            core: 0.5
            opacity: 0.06 + 0.16 * scene.energy + 0.1 * scene.breeze
        }
    }

    Vignette { anchors.fill: parent; strength: 0.6 }
    Grain { anchors.fill: parent; running: scene.running; strength: 0.05 }
}
