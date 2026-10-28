// Darker corners, like a lens: it pulls the eye in and makes a picture feel photographed. Drawn once per size.
import QtQuick

Canvas {
    property real strength: 0.55
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    Component.onCompleted: requestPaint()
    onPaint: {
        const ctx = getContext("2d");
        ctx.clearRect(0, 0, width, height);
        const g = ctx.createRadialGradient(width / 2, height / 2, height * 0.35, width / 2, height / 2, width * 0.7);
        g.addColorStop(0, "rgba(0,0,0,0)");
        g.addColorStop(1, "rgba(0,0,0," + strength + ")");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, width, height);
    }
}
