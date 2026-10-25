// DecKoOS login splash: the same wordmark and circling thumbstick cap as the Plymouth boot splash,
// so the animation carries on from boot into Plasma instead of a plain KDE logo.
import QtQuick

Rectangle {
    id: root
    color: "#0f1115"

    property int stage

    readonly property string branding: "file:///usr/share/deckos/branding/"
    readonly property real s: Math.min(width * 0.4, 1008) / 1008

    Image {
        id: word
        anchors.centerIn: parent
        source: root.branding + "wordmark-bare.svg"
        sourceSize.width: 1008 * root.s
        width: 1008 * root.s
        height: 194 * root.s
    }

    Image {
        source: root.branding + "stick.svg"
        width: 109 * root.s
        height: 109 * root.s
        sourceSize.width: width
        x: word.x + 625.5 * root.s - width / 2
        y: word.y + 117.4 * root.s - height / 2
        RotationAnimator on rotation {
            from: 360; to: 0; duration: 2500
            loops: Animation.Infinite
            running: true
        }
    }
}
