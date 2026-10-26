// DecKoOS Clock: a big clock, a greeting and the date on the desktop, in the Vibe's type (light italic for Lo-fi,
// a glowing mono for Neon, hairline for Midnight). One timer, on the minute (or second, if asked for).
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: clock

    Vibes.Look {
        id: look
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    property date now: new Date()
    readonly property bool seconds: Plasmoid.configuration.seconds === true
    readonly property string name: Plasmoid.configuration.name || ""

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 320
    Layout.preferredWidth: 460
    Layout.preferredHeight: column.implicitHeight + 36
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    // Wakes on the next minute (or second). The wait is worked out each time it fires, not kept as a binding on
    // `now`: that restarted the timer every time it fired, and with triggeredOnStart it never stopped
    Timer {
        id: tick
        running: clock.visible
        onTriggered: {
            clock.now = new Date();
            interval = clock.seconds ? 1000 - clock.now.getMilliseconds()
                                     : 60000 - clock.now.getSeconds() * 1000 - clock.now.getMilliseconds();
            restart();
        }
        Component.onCompleted: triggered()
    }

    function greeting() {
        const h = now.getHours();
        const part = h < 5 ? "Good night" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
        return name ? `${part}, ${name}` : part;
    }

    Vibes.Plate { anchors.fill: parent; look: look; visible: look.plate }

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 18
        spacing: 2
        Vibes.VibeText {
            look: look
            soft: true
            text: clock.greeting()
            font.pixelSize: 20
        }
        Vibes.VibeText {
            look: look
            text: Qt.formatTime(clock.now, clock.seconds ? "hh:mm:ss" : Qt.locale().timeFormat(Locale.ShortFormat))
            font.pixelSize: look.style === "midnight" ? 104 : 92
            font.letterSpacing: look.style === "neon" ? 2 : -2
        }
        Vibes.VibeText {
            look: look
            soft: true
            text: clock.now.toLocaleDateString(Qt.locale(), "dddd, d MMMM")
            font.pixelSize: 20
        }
    }
}
