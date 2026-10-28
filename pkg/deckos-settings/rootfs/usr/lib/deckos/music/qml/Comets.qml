// A comet leaves the cover's ring on every beat, each in its own direction (from when the beat landed, so every screen
// agrees), and flies on across the monitors until it leaves the world.
import QtQuick

Item {
    id: comets
    property real t: 0
    readonly property real speed: Math.max(width, height) * 0.42  // pixels a second

    Repeater {
        model: 10
        Rectangle {
            required property int index
            readonly property real born: engine.beats.length > index ? engine.beats[engine.beats.length - 1 - index] : -100
            readonly property real age: comets.t - born
            readonly property real seed: Math.abs(Math.sin(born * 12.9898) * 43758.5453) % 1
            readonly property real angle: seed * Math.PI * 2
            readonly property real dist: engine.worldHeight * 0.3 + age * comets.speed * (0.8 + 0.4 * seed)
            visible: age >= 0 && age < 3.5
            width: 120 + 220 * seed
            height: 3
            radius: 1.5
            transformOrigin: Item.Right
            rotation: angle * 180 / Math.PI
            x: engine.cover.x + Math.cos(angle) * dist - width
            y: engine.cover.y + Math.sin(angle) * dist - height / 2
            opacity: Math.max(0, 1 - age / 3.5)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 0.7; color: engine.accent }
                GradientStop { position: 1; color: "white" }
            }
        }
    }
}
