// A meter in lit segments, like the Spectrum look's LED bars: memory, network, progress, volume. The lit ones run
// through the Vibe's colours (or plain text colour with `plain`).
import QtQuick

Row {
    id: meter
    property var look
    property real value: 0      // 0..1
    property int count: 20
    property bool plain: false
    property real segmentHeight: 8
    spacing: 3
    readonly property int lit: Math.round(Math.max(0, Math.min(1, value)) * count)

    Repeater {
        model: meter.count
        Rectangle {
            required property int index
            width: (meter.width - meter.spacing * (meter.count - 1)) / meter.count
            height: meter.segmentHeight
            color: !meter.look ? "transparent" : index < meter.lit
                   ? (meter.plain ? meter.look.text : meter.look.mix(index / Math.max(1, meter.count - 1))) : meter.look.off
            opacity: index < meter.lit && meter.plain ? 0.85 : 1
        }
    }
}
