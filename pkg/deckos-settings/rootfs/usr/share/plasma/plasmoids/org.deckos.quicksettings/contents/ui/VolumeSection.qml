import QtQuick
import QtQuick.Layouts
import org.kde.kcmutils as KCMUtils
import org.kde.plasma.private.volume

// Volume through plasma-pa: the default output, and with the chevron every output with its own
// slider (click a name to make it the default).
ColumnLayout {
    id: section
    property bool showAll: false
    readonly property bool available: sinks.count > 0
    readonly property real normal: 65536  // PulseAudio's 100%

    spacing: 6

    PulseObjectFilterModel {
        id: sinks
        filterOutInactiveDevices: true
        filterVirtualDevices: true
        sourceModel: SinkModel {}
    }

    Repeater {
        model: sinks
        delegate: ColumnLayout {
            id: row
            required property var model
            readonly property var sink: model.PulseObject
            readonly property bool isDefault: !!sink && sink.default
            visible: isDefault || section.showAll
            Layout.fillWidth: true
            spacing: 2

            RowLayout {
                visible: section.showAll
                Layout.fillWidth: true
                Layout.leftMargin: 4
                spacing: 6
                Rectangle {
                    implicitWidth: 8
                    implicitHeight: 8
                    radius: 4
                    color: row.isDefault ? Deck.accent : "transparent"
                    border.width: row.isDefault ? 0 : 1
                    border.color: Deck.muted
                }
                DeckText {
                    Layout.fillWidth: true
                    sub: !row.isDefault
                    text: row.sink ? row.sink.description : ""
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: row.isDefault ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: row.sink.default = true
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                DeckButton {
                    round: true
                    flat: true
                    icon: row.sink && (row.sink.muted || row.sink.volume === 0) ? "volume-mute" : "volume"
                    tip: row.sink && row.sink.muted ? "Unmute" : "Mute"
                    onClicked: row.sink.muted = !row.sink.muted
                }
                DeckSlider {
                    Layout.fillWidth: true
                    to: section.normal
                    value: row.sink && !row.sink.muted ? row.sink.volume : 0
                    Accessible.name: "Volume"
                    onMoved: v => {
                        row.sink.volume = Math.round(v);
                        if (row.sink.muted && v > 0)
                            row.sink.muted = false;
                    }
                }
                DeckText {
                    Layout.preferredWidth: 36
                    horizontalAlignment: Text.AlignRight
                    sub: true
                    text: row.sink && !row.sink.muted ? Math.round(row.sink.volume / section.normal * 100) + "%" : "Muted"
                }
                DeckButton {
                    visible: row.isDefault
                    round: true
                    flat: true
                    icon: sinks.count > 1 ? "chevron" : "sliders"
                    tip: sinks.count > 1 ? "All outputs" : "Sound settings"
                    rotation: section.showAll ? 90 : 0
                    onClicked: {
                        if (sinks.count > 1)
                            section.showAll = !section.showAll;
                        else
                            KCMUtils.KCMLauncher.openSystemSettings("kcm_pulseaudio");
                    }
                }
                Item {  // keeps the sliders lined up when the chevron isn't there
                    visible: !row.isDefault
                    implicitWidth: 30
                }
            }
        }
    }
}
