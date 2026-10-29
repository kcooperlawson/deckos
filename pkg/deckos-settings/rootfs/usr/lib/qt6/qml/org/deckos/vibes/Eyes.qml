// The DecKoOS mark as line art: the stick eye and the button eye (the logo's two rings), the stick's cap and the
// four face buttons in the Vibe's colours. Drawn from the logo's own geometry (branding/logo.svg), 190 x 72.
import QtQuick
import QtQuick.Shapes

Item {
    id: eyes
    property var look
    property color line: look ? look.text : "#F2F3F7"
    implicitWidth: 58
    implicitHeight: implicitWidth * 72 / 190
    readonly property real k: width / 190
    readonly property color a: look ? look.colorA : "#4C8DFF"
    readonly property color b: look ? look.colorB : "#7A5CFF"

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {  // the stick eye
            strokeColor: eyes.line; strokeWidth: 14 * eyes.k; fillColor: "transparent"
            PathAngleArc { centerX: 39.3 * eyes.k; centerY: 50.9 * eyes.k; radiusX: 29.8 * eyes.k; radiusY: 29.8 * eyes.k; sweepAngle: 360 }
        }
        ShapePath {  // the button eye
            strokeColor: eyes.line; strokeWidth: 14 * eyes.k; fillColor: "transparent"
            PathAngleArc { centerX: 141.7 * eyes.k; centerY: 36 * eyes.k; radiusX: 44.7 * eyes.k; radiusY: 44.7 * eyes.k; sweepAngle: 360 }
        }
    }
    Rectangle {  // the stick's cap
        x: (41.6 - 13.8) * eyes.k; y: (44.8 - 9.6) * eyes.k
        width: 27.6 * eyes.k; height: 19.2 * eyes.k; radius: height / 2
        color: eyes.a
    }
    Repeater {  // the face buttons
        model: [[141.7, 20, 0], [157.7, 36, 1], [141.7, 52, 0], [125.7, 36, 1]]
        Rectangle {
            required property var modelData
            x: (modelData[0] - 8) * eyes.k; y: (modelData[1] - 8) * eyes.k
            width: 16 * eyes.k; height: width; radius: width / 2
            color: modelData[2] ? eyes.b : eyes.a
        }
    }
}
