// The spectrum as a horizon along the bottom of the whole world: the bass stands under the cover and the highs
// run out to the farthest screens on both sides, so every monitor has its share of the song.
import QtQuick

Item {
    id: horizon
    property real t: 0
    readonly property int perSide: 32
    readonly property real cx: engine.cover.x

    Repeater {
        model: horizon.perSide * 2
        Rectangle {
            required property int index
            readonly property bool onRight: index >= horizon.perSide
            readonly property int k: index % horizon.perSide  // 0 is the bass, at the cover
            readonly property real span: onRight ? horizon.width - horizon.cx : horizon.cx
            readonly property real step: span / horizon.perSide
            readonly property real level: engine.bars[k * 2] ?? 0
            width: Math.max(3, step * 0.55)
            height: 6 + horizon.height * 0.2 * level * (1 - k / horizon.perSide * 0.35)
            radius: Math.min(width / 2, 8)
            x: (onRight ? horizon.cx + (k + 0.5) * step : horizon.cx - (k + 0.5) * step) - width / 2
            y: horizon.height - height
            opacity: 0.25 + 0.6 * level
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.lighter(engine.accent, 1.3) }
                GradientStop { position: 1; color: Qt.rgba(engine.second.r, engine.second.g, engine.second.b, 0) }
            }
        }
    }
}
