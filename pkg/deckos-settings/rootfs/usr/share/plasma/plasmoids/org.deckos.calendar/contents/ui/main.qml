// DecKoOS Calendar: this month at a glance in the Vibe's type, today lit in its colour. Wheel or click the arrows to
// look at other months; it comes back to today at midnight.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: cal

    Vibes.Look {
        id: vibe
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    property date now: new Date()
    property int shift: 0  // months away from this one
    readonly property date shown: new Date(now.getFullYear(), now.getMonth() + shift, 1)
    readonly property bool monday: Plasmoid.configuration.mondayFirst
    readonly property int lead: (shown.getDay() + (monday ? 6 : 0)) % 7  // blanks before the 1st
    readonly property int days: new Date(shown.getFullYear(), shown.getMonth() + 1, 0).getDate()

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 240
    Layout.preferredWidth: 300
    Layout.preferredHeight: 280
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    Timer {  // once a minute is plenty to notice midnight
        interval: 60000; repeat: true; running: true
        onTriggered: if (new Date().getDate() !== cal.now.getDate()) { cal.now = new Date(); cal.shift = 0; }
    }

    Vibes.Plate { anchors.fill: parent; look: vibe }

    WheelHandler { onWheel: event => cal.shift += event.angleDelta.y > 0 ? -1 : 1 }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8
        RowLayout {
            Vibes.VibeText {
                look: vibe
                Layout.fillWidth: true
                text: cal.shown.toLocaleDateString(Qt.locale(), "MMMM yyyy")
                font.pixelSize: 20
            }
            Repeater {
                model: [["‹", -1], ["›", 1]]
                Vibes.VibeText {
                    required property var modelData
                    look: vibe
                    soft: true
                    text: modelData[0]
                    font.pixelSize: 22
                    MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: cal.shift += parent.modelData[1] }
                }
            }
        }
        GridLayout {
            columns: 7
            rowSpacing: 2
            columnSpacing: 2
            Layout.fillWidth: true
            Layout.fillHeight: true
            Repeater {
                model: 7
                Vibes.VibeText {
                    required property int index
                    look: vibe
                    soft: true
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.locale().dayName((index + (cal.monday ? 1 : 0)) % 7, Locale.NarrowFormat)
                    font.pixelSize: 11
                }
            }
            Repeater {
                model: cal.lead + cal.days
                Item {
                    id: cell
                    required property int index
                    readonly property int day: index - cal.lead + 1
                    readonly property bool today: cal.shift === 0 && day === cal.now.getDate()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Rectangle {
                        anchors.centerIn: parent
                        width: Math.min(parent.width, parent.height); height: width; radius: width / 2
                        visible: cell.today
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: vibe.colorA }
                            GradientStop { position: 1; color: vibe.colorB }
                        }
                    }
                    Vibes.VibeText {
                        anchors.centerIn: parent
                        look: vibe
                        visible: cell.day > 0
                        text: cell.day
                        font.pixelSize: 14
                        font.bold: cell.today
                    }
                }
            }
        }
    }
}
