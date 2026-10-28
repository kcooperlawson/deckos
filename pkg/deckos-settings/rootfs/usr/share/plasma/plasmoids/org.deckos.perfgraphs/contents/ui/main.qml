// DecKoOS Performance: live graphs of the processor, graphics card, memory and network on the desktop,
// in the DecKoOS look (a bolted slate plate, accent area charts). Values come from ksystemstats through
// Plasma's sensor module, the same source as Plasma's System Monitor widgets, at one update a second;
// the widget runs nothing of its own. Each graph has its own scale: no shared or second axis.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.ksysguard.sensors as Sensors
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: deckPerf

    // Colours from the active colour scheme and accent, so themes and the Hub's accent reach this widget;
    // the surfaces are the scheme's background lifted towards its text, like the DecKoOS slate steps.
    readonly property color text: Kirigami.Theme.textColor
    readonly property color subtext: Kirigami.Theme.disabledTextColor
    readonly property color accent: Kirigami.Theme.highlightColor
    // The gradient partner: the accent shifted towards violet, like the brand tile
    readonly property color accentB: Qt.hsva((accent.hsvHue + 32 / 360) % 1, Math.min(1, accent.hsvSaturation + 0.04),
                                             accent.hsvValue, 1)
    readonly property color plate: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.035))
    readonly property color raised: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.07))
    readonly property color border: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.12))
    readonly property color muted: Qt.tint(subtext, Qt.rgba(plate.r, plate.g, plate.b, 0.35))
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
        color: Qt.rgba(deckPerf.plate.r, deckPerf.plate.g, deckPerf.plate.b, 0.92)
        border.color: deckPerf.border

        // Bolted plates: a screw head in each corner (the DecKoOS motif)
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
                value: cpuUsage.value || 0
                valueText: Math.round(cpuUsage.value || 0) + "%"
                detail: cpuTemp.value > 0 ? Math.round(cpuTemp.value) + " °C" : ""
                maximum: 100
            }
            Graph {
                title: "Graphics card"
                value: gpuUsage.value || 0
                valueText: Math.round(gpuUsage.value || 0) + "%"
                detail: gpuTemp.value > 0 ? Math.round(gpuTemp.value) + " °C" : ""
                maximum: 100
                visible: gpuUsage.status === Sensors.Sensor.Ready || gpuUsage.value > 0
            }
            Graph {
                title: "Video memory"
                value: gpuMem.value || 0
                valueText: deckPerf.gib(gpuMem.value || 0) + " GB"
                detail: gpuMemTotal.value > 0 ? "of " + deckPerf.gib(gpuMemTotal.value) + " GB" : ""
                maximum: gpuMemTotal.value || 1
                visible: gpuMemTotal.value > 0
            }
            Graph {
                title: "Memory"
                value: ram.value || 0
                valueText: deckPerf.gib(ram.value || 0) + " GB"
                detail: ramTotal.value > 0 ? "of " + deckPerf.gib(ramTotal.value) + " GB" : ""
                maximum: ramTotal.value || 1
            }
            Graph {
                title: "Network"
                visible: Plasmoid.configuration.showNetwork
                value: down.value || 0
                second: up.value || 0
                valueText: "↓ " + deckPerf.rate_(down.value || 0)
                detail: "↑ " + deckPerf.rate_(up.value || 0)
                maximum: -1  // scales to the busiest moment shown
            }
        }
    }
}
