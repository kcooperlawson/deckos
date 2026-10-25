// DeckOS Performance: live graphs of the processor, graphics card, memory and network on the desktop,
// in the DeckOS look (a bolted slate plate, accent area charts). Values come from ksystemstats through
// Plasma's sensor module, the same source as Plasma's System Monitor widgets, at one update a second;
// the widget runs nothing of its own. Each graph has its own scale: no shared or second axis.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.ksysguard.sensors as Sensors

PlasmoidItem {
    id: deckPerf

    readonly property color plate: "#171A21"
    readonly property color raised: "#1E222B"
    readonly property color border: "#262B36"
    readonly property color text: "#E8EAF0"
    readonly property color subtext: "#8C94A6"
    readonly property color muted: "#5A6172"
    readonly property color accent: "#4C8DFF"
    readonly property color accentB: "#7A5CFF"
    readonly property color upload: "#0EA08E"  // validated against the plate with the accent (dataviz)

    readonly property int samples: Plasmoid.configuration.seconds
    readonly property int rate: 1000

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 260
    Layout.minimumHeight: column.implicitHeight + 32
    Layout.preferredWidth: 320
    Layout.preferredHeight: column.implicitHeight + 32
    // The plate below is the background (assigned here rather than attached, so the preview's stand-ins work)
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    // ---- which graphics card: the configured one, else the one with the most video memory, so a
    // Ryzen's built-in graphics never stands in for the real card
    property string bestGpu: "gpu/gpu0"
    readonly property string gpu: Plasmoid.configuration.gpu !== "auto" ? Plasmoid.configuration.gpu : bestGpu
    Instantiator {
        id: vramProbe
        model: 4
        delegate: Sensors.Sensor {
            sensorId: "gpu/gpu" + index + "/totalVram"
            updateRateLimit: 60000
            onValueChanged: deckPerf.pickGpu()
        }
    }
    function pickGpu() {
        let best = -1, most = 0;
        for (let i = 0; i < vramProbe.count; ++i) {
            const v = vramProbe.objectAt(i)?.value || 0;
            if (v > most) { most = v; best = i; }
        }
        if (best >= 0)
            bestGpu = "gpu/gpu" + best;
    }

    // One clock for every graph, so they share a timeline; only while the widget is shown
    signal tick()
    Timer {
        interval: deckPerf.rate
        repeat: true
        running: deckPerf.visible
        onTriggered: deckPerf.tick()
    }

    function gib(bytes) {
        return (bytes / 1073741824).toFixed(bytes >= 10737418240 ? 0 : 1);
    }
    function rate_(bytesPerSecond) {
        const units = ["B/s", "KB/s", "MB/s", "GB/s"];
        let v = bytesPerSecond, u = 0;
        while (v >= 1000 && u < units.length - 1) { v /= 1000; ++u; }
        return (v >= 100 || u === 0 ? Math.round(v) : v.toFixed(1)) + " " + units[u];
    }

    Sensors.Sensor { id: cpuUsage; sensorId: "cpu/all/usage"; updateRateLimit: deckPerf.rate }
    Sensors.Sensor { id: cpuTemp; sensorId: "cpu/all/averageTemperature"; updateRateLimit: deckPerf.rate }
    Sensors.Sensor { id: gpuUsage; sensorId: deckPerf.gpu + "/usage"; updateRateLimit: deckPerf.rate }
    Sensors.Sensor { id: gpuTemp; sensorId: deckPerf.gpu + "/temperature"; updateRateLimit: deckPerf.rate }
    Sensors.Sensor { id: gpuMem; sensorId: deckPerf.gpu + "/usedVram"; updateRateLimit: deckPerf.rate }
    Sensors.Sensor { id: gpuMemTotal; sensorId: deckPerf.gpu + "/totalVram"; updateRateLimit: 60000 }
    Sensors.Sensor { id: ram; sensorId: "memory/physical/used"; updateRateLimit: deckPerf.rate }
    Sensors.Sensor { id: ramTotal; sensorId: "memory/physical/total"; updateRateLimit: 60000 }
    Sensors.Sensor { id: down; sensorId: "network/all/download"; updateRateLimit: deckPerf.rate
                     enabled: Plasmoid.configuration.showNetwork }
    Sensors.Sensor { id: up; sensorId: "network/all/upload"; updateRateLimit: deckPerf.rate
                     enabled: Plasmoid.configuration.showNetwork }

    // ---- the plate

    Rectangle {
        anchors.fill: parent
        radius: 14
        color: Qt.rgba(0.09, 0.10, 0.13, 0.92)
        border.color: deckPerf.border

        // Bolted plates: a screw head in each corner (the DeckOS motif)
        Repeater {
            model: 4
            Rectangle {
                required property int index
                width: 6; height: 6; radius: 3
                x: index % 2 ? parent.width - 13 : 7
                y: index < 2 ? 7 : parent.height - 13
                color: deckPerf.raised
                border.color: deckPerf.border
                Rectangle { anchors.centerIn: parent; width: 4; height: 1; color: deckPerf.muted; rotation: 45 + index * 20 }
            }
        }

        ColumnLayout {
            id: column
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "PERFORMANCE"
                    color: deckPerf.muted
                    font.family: "Inter"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    font.letterSpacing: 1.4
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "last " + deckPerf.samples + " s"
                    color: deckPerf.muted
                    font.family: "Inter"
                    font.pixelSize: 10
                }
            }

            Graph {
                title: "Processor"
                value: cpuUsage.value
                valueText: Math.round(cpuUsage.value || 0) + "%"
                detail: cpuTemp.value > 0 ? Math.round(cpuTemp.value) + " °C" : ""
                maximum: 100
            }
            Graph {
                title: "Graphics card"
                value: gpuUsage.value
                valueText: Math.round(gpuUsage.value || 0) + "%"
                detail: gpuTemp.value > 0 ? Math.round(gpuTemp.value) + " °C" : ""
                maximum: 100
                visible: gpuUsage.status === Sensors.Sensor.Ready || gpuUsage.value > 0
            }
            Graph {
                title: "Video memory"
                value: gpuMem.value
                valueText: deckPerf.gib(gpuMem.value || 0) + " GB"
                detail: gpuMemTotal.value > 0 ? "of " + deckPerf.gib(gpuMemTotal.value) + " GB" : ""
                maximum: gpuMemTotal.value || 1
                visible: gpuMemTotal.value > 0
            }
            Graph {
                title: "Memory"
                value: ram.value
                valueText: deckPerf.gib(ram.value || 0) + " GB"
                detail: ramTotal.value > 0 ? "of " + deckPerf.gib(ramTotal.value) + " GB" : ""
                maximum: ramTotal.value || 1
            }
            Graph {
                title: "Network"
                visible: Plasmoid.configuration.showNetwork
                value: down.value
                second: up.value
                valueText: "↓ " + deckPerf.rate_(down.value || 0)
                detail: "↑ " + deckPerf.rate_(up.value || 0)
                maximum: -1  // scales to the busiest moment shown
            }
        }
    }
}
