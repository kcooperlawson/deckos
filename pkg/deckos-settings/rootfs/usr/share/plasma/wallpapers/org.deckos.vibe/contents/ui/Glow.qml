// A soft light, drawn once into a texture and then only moved, scaled and faded: lamps, reflections, stars,
// fireflies, headlights, haze. Round in a square, an ellipse in a long one, and always fading to nothing at its edge
// (a gradient sized to the width alone left hard edges on wide glows). Shared by the scenes.
import QtQuick

Canvas {
    property color tint: "#FFD9A0"
    property real core: 0.25  // how far the bright middle reaches before it fades
    width: 200; height: 200
    onPaint: {
        const ctx = getContext("2d");
        ctx.clearRect(0, 0, width, height);
        if (width <= 0 || height <= 0)
            return;
        ctx.save();
        ctx.translate(width / 2, height / 2);
        ctx.scale(1, height / width);  // a circle in a square, stretched to fill the box exactly
        const r = width / 2;
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
        g.addColorStop(0, Qt.rgba(tint.r, tint.g, tint.b, 0.9));
        g.addColorStop(core, Qt.rgba(tint.r, tint.g, tint.b, 0.35));
        g.addColorStop(1, Qt.rgba(tint.r, tint.g, tint.b, 0));
        ctx.fillStyle = g;
        ctx.fillRect(-r, -r, 2 * r, 2 * r);
        ctx.restore();
    }
    onTintChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    Component.onCompleted: requestPaint()  // a Canvas draws only when asked
}
