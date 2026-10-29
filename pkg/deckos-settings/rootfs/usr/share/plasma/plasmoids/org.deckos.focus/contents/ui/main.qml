// DecKoOS Focus: a focus timer (25 minutes of work, 5 of rest, by default) as a ring that fills, a soft DecKoOS
// chime between the two. Click to start or pause; right-click to start over. Ticks only while running.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: pomo

    Vibes.Look {
        id: look
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    property bool resting: false
    property bool ticking: false
    readonly property int total: (resting ? Plasmoid.configuration.breakMinutes : Plasmoid.configuration.workMinutes) * 60
    property int remaining: Plasmoid.configuration.workMinutes * 60

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 180
    Layout.preferredWidth: 220
    Layout.preferredHeight: 240
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    P5Support.DataSource {  // the chime: DecKoOS's own sounds, through PipeWire
        id: sound
        engine: "executable"
        onNewData: source => disconnectSource(source)
    }
    function chime(name) {
        sound.connectSource("pw-play /usr/share/sounds/deckos/stereo/" + name + ".oga");
    }

    Timer {
        interval: 1000
        repeat: true
        running: pomo.ticking
        onTriggered: {
            pomo.remaining--;
            if (pomo.remaining > 0)
                return;
            pomo.chime(pomo.resting ? "message-new-instant" : "completion-success");
            pomo.resting = !pomo.resting;
            pomo.remaining = pomo.total;
        }
    }
    function reset() {
        ticking = false;
        resting = false;
        remaining = Plasmoid.configuration.workMinutes * 60;
    }

    Vibes.Plate { anchors.fill: parent; look: look; visible: look.plate }

    Canvas {  // the ring: how much of this stretch is done
        id: ring
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -10
        width: Math.max(40, Math.min(parent.width, parent.height) - 60)  // never negative while the widget has no size yet
        height: width
        property real done: pomo.total > 0 ? 1 - pomo.remaining / pomo.total : 0
        onDoneChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            const r = width / 2 - 6;
            ctx.lineWidth = 8;
            ctx.lineCap = "round";
            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.12);
            ctx.beginPath();
            ctx.arc(width / 2, height / 2, r, 0, 2 * Math.PI);
            ctx.stroke();
            const g = ctx.createLinearGradient(0, 0, width, height);
            g.addColorStop(0, pomo.resting ? look.colorB : look.colorA);
            g.addColorStop(1, pomo.resting ? look.colorA : look.colorB);
            ctx.strokeStyle = g;
            ctx.beginPath();
            ctx.arc(width / 2, height / 2, r, -Math.PI / 2, -Math.PI / 2 + done * 2 * Math.PI);
            ctx.stroke();
        }
        Column {
            anchors.centerIn: parent
            Vibes.VibeText {
                look: look
                anchors.horizontalCenter: parent.horizontalCenter
                text: Math.floor(pomo.remaining / 60) + ":" + String(pomo.remaining % 60).padStart(2, "0")
                font.pixelSize: 34
                font.family: look.hud  // numbers in the DecKo type
            }
            Vibes.VibeText {
                look: look
                soft: true
                anchors.horizontalCenter: parent.horizontalCenter
                text: pomo.resting ? "Rest" : pomo.ticking ? "Focus" : "Click to start"
                font.pixelSize: 13
            }
        }
    }
    Vibes.VibeText {
        look: look
        soft: true
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        anchors.horizontalCenter: parent.horizontalCenter
        text: pomo.ticking ? "Click to pause" : "Right-click to start over"
        font.pixelSize: 11
    }
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => mouse.button === Qt.RightButton ? pomo.reset() : (pomo.ticking = !pomo.ticking)
    }
}
