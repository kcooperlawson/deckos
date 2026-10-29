// DecKoOS Clock: the time floating big on the desktop in the DecKo type (Chakra Petch, the colon lit in the Vibe's
// colours), a greeting, the date, and the day as 24 hour ticks filling up. One timer, on the minute (or second).
import QtQuick
import QtQuick.Effects
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
    Layout.preferredHeight: column.implicitHeight + 24
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

    // 12 or 24 hours, as the locale has it: "7:50" and a small PM, or "19:50"
    readonly property bool twelve: /a/i.test(Qt.locale().timeFormat(Locale.ShortFormat))
    // (Qt only counts 1-12 when the format itself has AP in it)
    readonly property string hours: twelve ? Qt.formatTime(now, "h AP").split(" ")[0] : Qt.formatTime(now, "hh")
    readonly property string minutes: Qt.formatTime(now, seconds ? "mm:ss" : "mm")

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 0
        Vibes.Hud {
            look: look
            text: clock.greeting()
            font.pixelSize: 13
            Layout.bottomMargin: 2
        }
        Row {
            id: time
            spacing: 0
            layer.enabled: true  // the shadow that keeps it readable over any wallpaper
            layer.effect: MultiEffect { shadowEnabled: true; shadowOpacity: 0.55; shadowBlur: 0.7; shadowVerticalOffset: 2 }
            component Big: Text {
                color: look.text
                font.family: look.hud
                font.weight: Font.DemiBold
                font.pixelSize: 124
                font.letterSpacing: -2
                renderType: Text.QtRendering
            }
            Big { id: hoursText; text: clock.hours }
            Column {  // the colon: two notched dots in the Vibe's colours
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: 4
                leftPadding: 8
                rightPadding: 8
                spacing: 26
                Repeater {
                    model: 2
                    Rectangle {
                        required property int index
                        width: 13
                        height: 13
                        color: index ? look.colorB : look.colorA
                    }
                }
            }
            Big { text: clock.minutes }
            Vibes.Hud {
                visible: clock.twelve
                look: look
                strong: true
                text: Qt.formatTime(clock.now, "AP")
                font.pixelSize: 26
                anchors.baseline: hoursText.baseline
                leftPadding: 10
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            Vibes.Hud { look: look; text: clock.now.toLocaleDateString(Qt.locale(), "dddd"); font.pixelSize: 14; font.letterSpacing: 5 }
            Item { Layout.fillWidth: true }
            Vibes.Hud { look: look; text: clock.now.toLocaleDateString(Qt.locale(), "d · MMM"); font.pixelSize: 14; font.letterSpacing: 5 }
        }
        Row {  // the day so far: an hour a tick, the current one white
            Layout.fillWidth: true
            Layout.topMargin: 10
            spacing: 4
            Repeater {
                model: 24
                Rectangle {
                    required property int index
                    readonly property int hour: clock.now.getHours()
                    width: (parent.width - 23 * 4) / 24
                    height: 6
                    color: index === hour ? look.text : index < hour ? look.mix(index / 23) : look.off
                }
            }
        }
    }
}
