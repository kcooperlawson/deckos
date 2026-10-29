// DecKoOS Performance: the processor, graphics card, memory and network on a DecKo card. The processor and
// graphics card are gauges shaped like the logo's stick eye (the ring fills with load, the cap leans toward it);
// memory, video memory and network are lit segments. Values come from ksystemstats through Plasma's sensor module,
// the same source as Plasma's System Monitor widgets, at one update a second; the widget runs nothing of its own.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.ksysguard.sensors as Sensors
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: deckPerf

    Vibes.Look {
        id: look
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }
    readonly property int rate: 1000

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 340
    Layout.preferredWidth: 404
    Layout.minimumHeight: column.implicitHeight + 40
    Layout.preferredHeight: column.implicitHeight + 40
    // The card below is the background (assigned here rather than attached, so the preview's stand-ins work)
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

    // The network's scale: the busiest second of the last minute (so a download fills the meter, idle doesn't)
    property var netSeen: []
    readonly property real netPeak: Math.max(1e5, ...netSeen)
    Timer {
        interval: deckPerf.rate
        repeat: true
        running: deckPerf.visible && Plasmoid.configuration.showNetwork
        onTriggered: deckPerf.netSeen = deckPerf.netSeen.concat([(down.value || 0) + (up.value || 0)]).slice(-60)
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

    Vibes.Notch {  // hugs the content, whatever size the widget's box
        width: parent.width
        height: column.implicitHeight + 40
        look: look
    }

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 20
        spacing: 14

        Vibes.Hud { look: look; text: "Performance" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Stick {
                look: look
                Layout.fillWidth: true
                label: "CPU"
                value: (cpuUsage.value || 0) / 100
                temp: cpuTemp.value > 0 ? Math.round(cpuTemp.value) + "°" : ""
            }
            Stick {
                look: look
                Layout.fillWidth: true
                visible: gpuUsage.status === Sensors.Sensor.Ready || gpuUsage.value > 0
                label: "GPU"
                value: (gpuUsage.value || 0) / 100
                temp: gpuTemp.value > 0 ? Math.round(gpuTemp.value) + "°" : ""
            }
        }
        Meter {
            look: look
            Layout.fillWidth: true
            visible: gpuMemTotal.value > 0
            label: "VRAM"
            value: (gpuMem.value || 0) / (gpuMemTotal.value || 1)
            valueText: deckPerf.gib(gpuMem.value || 0) + " / " + deckPerf.gib(gpuMemTotal.value || 0) + " GB"
        }
        Meter {
            look: look
            Layout.fillWidth: true
            label: "MEM"
            value: (ram.value || 0) / (ramTotal.value || 1)
            valueText: deckPerf.gib(ram.value || 0) + " / " + deckPerf.gib(ramTotal.value || 0) + " GB"
        }
        Meter {
            look: look
            Layout.fillWidth: true
            visible: Plasmoid.configuration.showNetwork
            label: "NET"
            value: ((down.value || 0) + (up.value || 0)) / deckPerf.netPeak
            valueText: "↓ " + deckPerf.rate_(down.value || 0)
        }
    }
}
