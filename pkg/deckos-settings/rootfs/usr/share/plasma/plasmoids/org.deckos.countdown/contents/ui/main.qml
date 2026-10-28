// DecKoOS Countdown: days to something you're looking forward to, in big type. Click it to say what and when; on the
// day it says so, and after that it asks for the next one.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: count

    Vibes.Look {
        id: vibe
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    property date now: new Date()
    readonly property var when: {  // "YYYY-MM-DD" as a local date, or null
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(Plasmoid.configuration.date);
        return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
    }
    readonly property int daysLeft: when ? Math.round((when - new Date(now.getFullYear(), now.getMonth(), now.getDate()))
                                                  / 86400000) : -1
    property bool editing: false

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 200
    Layout.preferredWidth: 260
    Layout.preferredHeight: 170
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    Timer {
        interval: 60000; repeat: true; running: true
        onTriggered: count.now = new Date()
    }

    Vibes.Plate { anchors.fill: parent; look: vibe }

    ColumnLayout {  // the count
        visible: !count.editing
        anchors.fill: parent
        anchors.margins: 16
        spacing: 2
        Vibes.VibeText {
            look: vibe
            text: !count.when || count.daysLeft < 0 ? "—" : count.daysLeft === 0 ? "Today!" : count.daysLeft
            font.pixelSize: count.daysLeft === 0 ? 46 : 64
        }
        Vibes.VibeText {
            look: vibe
            visible: count.daysLeft > 0
            text: count.daysLeft === 1 ? "day to go" : "days to go"
            font.pixelSize: 14
        }
        Vibes.VibeText {
            look: vibe
            soft: true
            Layout.fillWidth: true
            elide: Text.ElideRight
            text: !count.when ? "Click to count down to something"
                 : count.daysLeft < 0 ? "That's been. Click for the next one" : Plasmoid.configuration.title
            font.pixelSize: 15
        }
        Item { Layout.fillHeight: true }
    }
    MouseArea {
        anchors.fill: parent
        visible: !count.editing
        onClicked: { what.text = Plasmoid.configuration.title; day.text = Plasmoid.configuration.date; count.editing = true; }
    }

    ColumnLayout {  // what and when
        visible: count.editing
        anchors.fill: parent
        anchors.margins: 16
        spacing: 6
        Repeater {
            model: [["What's happening?", "what"], ["When? (2026-12-25)", "day"]]
            Vibes.VibeText {
                required property var modelData
                look: vibe
                soft: true
                text: modelData[0]
                font.pixelSize: 12
            }
        }
        TextInput {
            id: what
            Layout.fillWidth: true
            color: vibe.text
            font.family: vibe.family
            font.pixelSize: 16
            maximumLength: 60
            selectByMouse: true
            onAccepted: day.forceActiveFocus()
        }
        TextInput {
            id: day
            Layout.fillWidth: true
            color: vibe.text
            font.family: vibe.family
            font.pixelSize: 16
            inputMask: "9999-99-99"
            selectByMouse: true
            onAccepted: {
                Plasmoid.configuration.title = what.text;
                Plasmoid.configuration.date = /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
                count.editing = false;
            }
        }
        Vibes.VibeText { look: vibe; soft: true; text: "Enter to save"; font.pixelSize: 11 }
    }
}
