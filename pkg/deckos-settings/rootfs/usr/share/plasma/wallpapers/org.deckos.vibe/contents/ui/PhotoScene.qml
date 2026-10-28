// Your own photo, alive: the lights you placed in it (DecKoOS Hub's Vibe editor) glow with the part of the music you
// gave each one (bass, melody or highs), a beat brightens the picture a touch, and, if you like, its colour follows
// the time of day. Finished with grain and a vignette like DecKoOS's own scenes. Positions are fractions of the
// picture as shown (cropped to fill the screen, like the editor shows it).
import QtQuick

Item {
    id: scene
    property bool running: true
    property color colorA: "#FF9E7A"
    property color colorB: "#B36BFF"
    property real bass: 0
    property real mid: 0
    property real high: 0
    property real energy: 0
    property int beats: 0
    // From the Vibe (main.qml binds these from the wallpaper's settings)
    property string photo: ""
    property var lights: []  // [[x, y, size, "bass"|"mid"|"high"], …]
    property real grain: 0.05
    property real vignette: 0.5
    property bool clock: true

    property int hour: new Date().getHours()
    property real flash: 0
    Timer {
        interval: 60000; repeat: true; running: scene.running; triggeredOnStart: true
        onTriggered: scene.hour = new Date().getHours()
    }
    Timer {
        interval: 50; repeat: true; running: scene.running && scene.flash > 0.01
        onTriggered: scene.flash *= 0.85
    }
    onBeatsChanged: flash = 1

    Image {
        anchors.fill: parent
        source: scene.photo ? "file://" + scene.photo : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 3840
    }
    Rectangle { anchors.fill: parent; color: "black"; opacity: 0.1 }

    // ---- the lights you placed, each answering to its part of the music
    Repeater {
        model: scene.lights
        Glow {
            required property var modelData
            readonly property real v: modelData[3] === "bass" ? scene.bass : modelData[3] === "mid" ? scene.mid
                                                                                                   : scene.high
            x: modelData[0] * scene.width - width / 2
            y: modelData[1] * scene.height - height / 2
            width: scene.height * modelData[2] * 2 * (1 + 0.5 * v); height: width  // size: the light's reach
            tint: modelData[3] === "bass" ? scene.colorA : modelData[3] === "mid" ? scene.colorB : "#F4F6FF"
            core: 0.22
            opacity: 0.18 + 0.75 * v
        }
    }
    // A beat brightens the whole picture, just a touch
    Rectangle { anchors.fill: parent; color: scene.colorA; opacity: 0.05 * scene.flash }
    // The time of day, if wanted: deep blue at night, amber in the evening, pink at dawn
    Rectangle {
        anchors.fill: parent
        visible: scene.clock
        color: scene.hour >= 22 || scene.hour < 5 ? "#0A1840" : scene.hour < 7 ? "#5A2E4A" : scene.hour < 17
                                                                                  ? "#9AA8B8" : "#6A3A10"
        opacity: scene.hour >= 22 || scene.hour < 5 ? 0.25 : scene.hour >= 7 && scene.hour < 17 ? 0.05 : 0.12
        Behavior on color { ColorAnimation { duration: 20000 } }
    }
    Vignette { anchors.fill: parent; strength: scene.vignette; visible: scene.vignette > 0 }
    Grain { anchors.fill: parent; running: scene.running; strength: scene.grain; visible: scene.grain > 0 }
}
