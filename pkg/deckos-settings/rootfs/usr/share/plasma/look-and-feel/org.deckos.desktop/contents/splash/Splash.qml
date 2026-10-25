// DecKoOS login splash: the same wordmark as the Plymouth boot splash, its oO as a pair of eyes that
// glance left, then right, then blink, so the animation carries on from boot into Plasma instead of a
// plain KDE logo. The timing is shared with deckos.script and assets/boot_movie.py: change all three.
import QtQuick

Rectangle {
    id: root
    color: "#0f1115"

    property int stage

    readonly property string branding: "file:///usr/share/deckos/branding/"
    readonly property real s: Math.min(width * 0.4, 1008) / 1008

    // One 4 s loop drives both eyes
    property real t: 0
    NumberAnimation on t { from: 0; to: 4; duration: 4000; loops: Animation.Infinite; running: true }

    function ease(a, b, x) {
        const k = Math.min(1, Math.max(0, (x - a) / (b - a)));
        return k * k * (3 - 2 * k);
    }
    // Glance: -1 (left) .. 1 (right), in steps with holds
    readonly property real look: -ease(0.6, 0.9, t) + 2 * ease(1.5, 1.9, t) - ease(2.5, 2.8, t)
    // Blink: pupils squash shut for about a quarter second
    readonly property real lid: 1 - 0.92 * (ease(3.2, 3.32, t) - ease(3.32, 3.44, t))

    Image {
        id: word
        anchors.centerIn: parent
        source: root.branding + "wordmark-bare.svg"
        sourceSize.width: 1008 * root.s
        width: 1008 * root.s
        height: 194 * root.s
    }

    // Centres from assets/generate.py's output (eye centres in wordmark.svg)
    Repeater {
        model: [["eye-stick.svg", 625.5, 117.4], ["eye-buttons.svg", 766.3, 97.0]]
        Image {
            required property var modelData
            source: root.branding + modelData[0]
            width: 100 * root.s
            height: 100 * root.s
            sourceSize.width: width
            x: word.x + (modelData[1] + 5 * root.look) * root.s - width / 2
            y: word.y + (modelData[2] + 2 * Math.abs(root.look)) * root.s - height / 2
            transform: Scale { origin.x: width / 2; origin.y: height / 2; yScale: root.lid }
        }
    }
}
