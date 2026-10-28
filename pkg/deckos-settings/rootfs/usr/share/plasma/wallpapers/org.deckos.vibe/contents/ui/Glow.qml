// A soft light, drawn once into a small texture and then only moved, scaled and faded: lamps, reflections, stars,
// fireflies, headlights, haze. Round in a square, an ellipse in a long one, and always fading to nothing at its edge.
// The texture is a fixed 128 px and stretched to the box: scenes change sizes with the music every frame, and a
// Canvas that repainted on each change kept plasmashell (and with it the taskbar) busy.
import QtQuick

Item {
    id: glow
    property color tint: "#FFD9A0"
    property real core: 0.25  // how far the bright middle reaches before it fades
    width: 200; height: 200

    Canvas {
        id: tex
        width: 128; height: 128
        transform: Scale { xScale: glow.width / 128; yScale: glow.height / 128 }
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, 128, 128);
            const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
            g.addColorStop(0, Qt.rgba(glow.tint.r, glow.tint.g, glow.tint.b, 0.9));
            g.addColorStop(glow.core, Qt.rgba(glow.tint.r, glow.tint.g, glow.tint.b, 0.35));
            g.addColorStop(1, Qt.rgba(glow.tint.r, glow.tint.g, glow.tint.b, 0));
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, 128, 128);
        }
        Component.onCompleted: requestPaint()  // a Canvas draws only when asked
    }
    onTintChanged: tex.requestPaint()
    onCoreChanged: tex.requestPaint()
}
