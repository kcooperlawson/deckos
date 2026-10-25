// One metric: its name, the value now, and an area chart of the last minute on its own scale.
// `second` adds a second line (network upload), told apart by colour, a legend swatch and its arrow.
// Hover for the value at any moment.
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes

ColumnLayout {
    id: graph
    Layout.fillWidth: true
    spacing: 6

    property string title
    property real value
    property real second: NaN
    property string valueText
    property string detail
    property real maximum: 100  // -1: scale to the busiest moment shown

    readonly property bool twoSeries: !isNaN(second)
    property var history: []
    property var history2: []

    readonly property real scaleMax: {
        if (maximum > 0)
            return maximum;
        let m = 0;
        for (const v of history) m = Math.max(m, v);
        for (const v of history2) m = Math.max(m, v);
        return Math.max(1000, m * 1.15);
    }

    Connections {
        target: deckPerf
        function onTick() {
            const keep = deckPerf.samples;
            graph.history = graph.history.concat([graph.value || 0]).slice(-keep);
            if (graph.twoSeries)
                graph.history2 = graph.history2.concat([graph.second || 0]).slice(-keep);
        }
    }

    function points(list, w, h) {
        const n = deckPerf.samples;
        const out = [];
        for (let i = 0; i < list.length; ++i) {
            const x = w * (n - list.length + i) / (n - 1);
            out.push(Qt.point(x, h - 1 - (h - 2) * Math.min(1, Math.max(0, list[i] / graph.scaleMax))));
        }
        return out;
    }

    // The line's points closed down to the baseline at both ends: one polyline, since each
    // PathPolyline starts its own subpath and wouldn't join a separate start point
    function area(list, w, h) {
        const line = points(list, w, h);
        return line.length ? [Qt.point(line[0].x, h)].concat(line, [Qt.point(line[line.length - 1].x, h)]) : [];
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        Text {
            text: graph.title
            color: deckPerf.subtext
            font.family: "Inter"
            font.pixelSize: 12
        }
        Item { Layout.fillWidth: true }
        Rectangle {  // legend swatches only when two lines share the chart
            visible: graph.twoSeries
            width: 8; height: 8; radius: 2
            color: deckPerf.accent
        }
        Text {
            text: graph.valueText
            color: deckPerf.text
            font.family: "Inter Display"
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
        Rectangle {
            visible: graph.twoSeries && graph.detail !== ""
            width: 8; height: 8; radius: 2
            color: deckPerf.upload
        }
        Text {
            visible: graph.detail !== ""
            text: graph.detail
            color: deckPerf.subtext
            font.family: "Inter"
            font.pixelSize: 12
        }
    }

    Item {
        id: plot
        Layout.fillWidth: true
        Layout.preferredHeight: 40

        // recessive baseline
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: deckPerf.border }

        Shape {
            antialiasing: true
            anchors.fill: parent
            // area under the main line: the accent fading to nothing
            ShapePath {
                strokeColor: "transparent"
                fillRule: ShapePath.WindingFill
                fillGradient: LinearGradient {
                    y1: 0; y2: plot.height
                    GradientStop { position: 0; color: Qt.rgba(deckPerf.accent.r, deckPerf.accent.g, deckPerf.accent.b, 0.32) }
                    GradientStop { position: 1; color: Qt.rgba(deckPerf.accentB.r, deckPerf.accentB.g, deckPerf.accentB.b, 0.0) }
                }
                PathPolyline { path: graph.area(graph.history, plot.width, plot.height) }
            }
            ShapePath {
                strokeColor: deckPerf.accent
                strokeWidth: 2
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                capStyle: ShapePath.RoundCap
                PathPolyline { path: graph.points(graph.history, plot.width, plot.height) }
            }
            ShapePath {
                strokeColor: graph.twoSeries ? deckPerf.upload : "transparent"
                strokeWidth: 2
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                capStyle: ShapePath.RoundCap
                PathPolyline { path: graph.twoSeries ? graph.points(graph.history2, plot.width, plot.height) : [] }
            }
        }

        // ---- hover: a crosshair and the value at that moment
        HoverHandler { id: hover }
        readonly property int at: {
            const n = deckPerf.samples;
            const i = Math.round(hover.point.position.x / plot.width * (n - 1)) - (n - graph.history.length);
            return hover.hovered && i >= 0 && i < graph.history.length ? i : -1;
        }
        Rectangle {
            visible: plot.at >= 0
            x: plot.width * (deckPerf.samples - graph.history.length + plot.at) / (deckPerf.samples - 1)
            width: 1; height: parent.height
            color: deckPerf.subtext
            opacity: 0.6
        }
        Rectangle {
            visible: plot.at >= 0
            radius: 6
            color: deckPerf.raised
            border.color: deckPerf.border
            width: tip.implicitWidth + 14
            height: tip.implicitHeight + 8
            y: -height - 4
            x: Math.min(plot.width - width, Math.max(0, hover.point.position.x - width / 2))
            Text {
                id: tip
                anchors.centerIn: parent
                color: deckPerf.text
                font.family: "Inter"
                font.pixelSize: 11
                text: {
                    if (plot.at < 0)
                        return "";
                    const ago = graph.history.length - 1 - plot.at;
                    const fmt = v => graph.maximum === 100 ? Math.round(v) + "%"
                        : graph.maximum > 0 ? deckPerf.gib(v) + " GB" : deckPerf.rate_(v);
                    return fmt(graph.history[plot.at]) + (graph.twoSeries ? "  ↑ " + fmt(graph.history2[plot.at] || 0) : "")
                        + "  ·  " + (ago === 0 ? "now" : ago + " s ago");
                }
            }
        }
    }
}
