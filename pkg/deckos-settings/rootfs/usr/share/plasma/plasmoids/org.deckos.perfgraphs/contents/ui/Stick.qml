// A gauge like the logo's stick eye: a ring that fills with the load, and the stick's cap leaning toward it
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.deckos.vibes as Vibes

RowLayout {
    id: stick
    required property var look
    property real value: 0  // 0..1
    property string label
    property string temp
    spacing: 12
    Item {
        Layout.preferredWidth: 72
        Layout.preferredHeight: 72
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: stick.look.off
                strokeWidth: 5
                fillColor: "transparent"
                PathAngleArc { centerX: 36; centerY: 36; radiusX: 30; radiusY: 30; startAngle: 0; sweepAngle: 360 }
            }
            ShapePath {
                strokeColor: stick.look.mix(stick.value)
                strokeWidth: 5
                capStyle: ShapePath.FlatCap
                fillColor: "transparent"
                PathAngleArc { centerX: 36; centerY: 36; radiusX: 30; radiusY: 30; startAngle: -90
                               sweepAngle: 360 * Math.max(0.01, Math.min(1, stick.value)) }
            }
        }
        Rectangle {  // the cap
            readonly property real a: (-90 + 360 * Math.min(1, stick.value)) * Math.PI / 180
            width: 22
            height: 16
            radius: 8
            color: stick.look.text
            opacity: 0.92
            x: 36 + 7 * Math.cos(a) - width / 2
            y: 36 + 7 * Math.sin(a) - height / 2
            Behavior on x { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
        }
    }
    ColumnLayout {
        spacing: 4
        Row {
            Vibes.Hud { look: stick.look; strong: true; text: String(Math.round(stick.value * 100)).padStart(2, "0") }
            Vibes.Hud { look: stick.look; text: "%"; font.pixelSize: 14; font.letterSpacing: 0; anchors.baseline: parent.children[0].baseline; leftPadding: 2 }
        }
        Vibes.Hud { look: stick.look; text: stick.label + (stick.temp ? " · " + stick.temp : "") }
    }
}
