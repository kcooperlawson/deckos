// The music visualizer on top of the scene: bars along the bottom, a wave, or a ring in the middle. Optional: the
// scenes react to the music themselves. Its levels come from MusicFeed (main.qml), the one connection to
// deckos-visualizer.
import QtQuick

Item {
    id: vis

    property string style: "bars"
    property color colorA: "#FF9E7A"
    property color colorB: "#B36BFF"
    property var levels: []
    readonly property int count: 48

    onLevelsChanged: if (style === "wave") wave.requestPaint()

    // ---- bars: along the bottom, the gradient running across them
    Row {
        visible: vis.style === "bars"
        anchors.bottom: parent.bottom
        anchors.bottomMargin: parent.height * 0.08
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: parent.width * 0.004
        Repeater {
            model: vis.count
            Rectangle {
                required property int index
                width: vis.width * 0.6 / vis.count - parent.spacing
                height: Math.max(width * 0.5, (vis.levels[index] || 0) * vis.height * 0.22)
                anchors.bottom: parent.bottom
                radius: width / 2
                opacity: 0.75
                color: Qt.tint(vis.colorA, Qt.rgba(vis.colorB.r, vis.colorB.g, vis.colorB.b, index / vis.count))
            }
        }
    }

    // ---- wave: one soft line across the lower third
    Canvas {
        id: wave
        visible: vis.style === "wave"
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            const n = vis.levels.length;
            if (!n)
                return;
            const g = ctx.createLinearGradient(0, 0, width, 0);
            g.addColorStop(0, vis.colorA);
            g.addColorStop(1, vis.colorB);
            ctx.strokeStyle = g;
            ctx.lineWidth = 2.5;
            // A smooth curve through the levels (bass in the middle, mirrored out to both sides), and its
            // reflection underneath, fainter: calm, not jagged
            const mid = height * 0.8, amp = height * 0.11;
            const pts = [];
            for (let i = 0; i < n; i++) {
                const v = vis.levels[n - 1 - i] || 0;
                pts.push(v);
            }
            const all = pts.concat(pts.slice().reverse());
            const step = width * 0.8 / (all.length - 1);
            for (const [sign, alpha] of [[1, 0.85], [-1, 0.25]]) {
                ctx.globalAlpha = alpha;
                ctx.beginPath();
                ctx.moveTo(width * 0.1, mid);
                for (let i = 1; i < all.length; i++) {
                    const x0 = width * 0.1 + (i - 1) * step, x1 = width * 0.1 + i * step;
                    const y0 = mid - sign * all[i - 1] * amp, y1 = mid - sign * all[i] * amp;
                    ctx.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2);
                }
                ctx.lineTo(width * 0.9, mid);
                ctx.stroke();
            }
        }
    }

    // ---- ring: bars around a circle in the middle
    Item {
        visible: vis.style === "ring"
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.32
        height: width
        Repeater {
            model: vis.count
            Rectangle {
                required property int index
                readonly property real len: 6 + (vis.levels[index] || 0) * parent.width * 0.35
                x: parent.width / 2 - width / 2
                y: parent.height / 2 - parent.width / 2 - len
                width: 4
                height: len
                radius: 2
                opacity: 0.8
                color: Qt.tint(vis.colorA, Qt.rgba(vis.colorB.r, vis.colorB.g, vis.colorB.b, index / vis.count))
                transform: Rotation {
                    origin.x: 2
                    origin.y: parent.width / 2 + len
                    angle: index * 360 / vis.count
                }
            }
        }
    }
}
