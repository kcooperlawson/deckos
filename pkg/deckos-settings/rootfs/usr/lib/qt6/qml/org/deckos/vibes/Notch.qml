// The DecKo card: the wordmark's notch cut into the top right and bottom left corners, a dark glass ground, and a
// 1 px edge lit by the Vibe's colours (colorA at the top left fading out, colorB coming back at the bottom right).
import QtQuick
import QtQuick.Shapes

Item {
    id: notch
    property var look
    property real cut: look ? look.cut : 14
    property color fill: look ? look.glass : Qt.rgba(0.05, 0.06, 0.09, 0.84)
    property bool lit: true  // the gradient edge; off, a plain faint line
    property real edge: 1     // its width
    property bool gradientFill: false  // the inside in the Vibe's colours (an active chip, a primary button)
    property LinearGradient insideGradient: LinearGradient {
        x1: 0; y1: 0; x2: notch.width; y2: notch.height
        GradientStop { position: 0; color: notch.look ? notch.look.colorA : "#4C8DFF" }
        GradientStop { position: 1; color: notch.look ? notch.look.colorB : "#7A5CFF" }
    }

    function outline(i) {  // the notched outline, inset by i
        return [Qt.point(i, i), Qt.point(width - cut - i * 0.41, i), Qt.point(width - i, cut + i * 0.41),
                Qt.point(width - i, height - i), Qt.point(cut + i * 0.41, height - i), Qt.point(i, height - cut - i * 0.41)];
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {  // the edge: the outline minus the inside, so a see-through fill stays see-through
            strokeColor: "transparent"
            fillRule: ShapePath.OddEvenFill
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: notch.width; y2: notch.height
                GradientStop { position: 0; color: notch.lit && notch.look ? notch.look.colorA : Qt.rgba(1, 1, 1, 0.14) }
                GradientStop { position: 0.32; color: Qt.rgba(1, 1, 1, 0.13) }
                GradientStop { position: 0.68; color: Qt.rgba(1, 1, 1, 0.09) }
                GradientStop { position: 1; color: notch.lit && notch.look ? notch.look.colorB : Qt.rgba(1, 1, 1, 0.14) }
            }
            PathMultiline { paths: [notch.outline(0), notch.outline(notch.edge)] }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: notch.fill
            fillGradient: notch.gradientFill ? notch.insideGradient : null
            PathPolyline { path: notch.outline(notch.edge) }
        }
    }
}
