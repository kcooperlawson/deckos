// Kid mode's taskbar piece: the minutes left today (from kids.py, which reads the time service's count) and
// "I'm done", which logs out. Asks once a minute; shows nothing about time when there's no limit.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: kidTime

    property int minutesLeft: -1  // -1: no limit today
    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: row.implicitWidth
    Layout.preferredWidth: row.implicitWidth

    P5Support.DataSource {
        id: ask
        engine: "executable"
        onNewData: (source, data) => {
            const out = (data.stdout || "").trim();
            kidTime.minutesLeft = /^\d+$/.test(out) ? parseInt(out) : -1;
            disconnectSource(source);
        }
    }
    function check() {
        ask.connectSource("python3 /usr/lib/deckos/kids/kids.py check \"$(id -un)\"");
    }
    Timer {
        interval: 60000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: kidTime.check()
    }

    RowLayout {
        id: row
        anchors.fill: parent
        spacing: 8

        Rectangle {
            visible: kidTime.minutesLeft >= 0
            radius: height / 2
            color: kidTime.minutesLeft <= 5 ? "#F5B84B" : Qt.rgba(1, 1, 1, 0.12)
            Layout.preferredHeight: label.implicitHeight + 10
            Layout.preferredWidth: label.implicitWidth + 24
            Layout.alignment: Qt.AlignVCenter
            PlasmaComponents.Label {
                id: label
                anchors.centerIn: parent
                text: "🕒 " + kidTime.minutesLeft + " min left"
                font.bold: true
                color: kidTime.minutesLeft <= 5 ? "#1B1B1B" : "white"
            }
        }
        PlasmaComponents.Button {
            text: "I'm done"
            icon.name: "system-log-out"
            Layout.alignment: Qt.AlignVCenter
            onClicked: ask.connectSource("qdbus6 org.kde.Shutdown /Shutdown logout")
        }
    }
}
