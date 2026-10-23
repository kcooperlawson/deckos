import QtQuick
import QtQuick.Layouts
import org.kde.plasma.private.brightnesscontrolplugin

// Brightness through powerdevil: one slider per screen it can dim (laptop panels, and monitors
// over DDC/CI), labelled when there's more than one.
ColumnLayout {
    id: section
    readonly property bool available: control.isBrightnessAvailable && screens.count > 0
    spacing: 6

    ScreenBrightnessControl {
        id: control
        isSilent: true  // no OSD for changes made here; the slider is feedback enough
    }

    Repeater {
        id: screens
        model: control.displays
        delegate: ColumnLayout {
            id: row
            required property string displayName
            required property string label
            required property int brightness
            required property int maxBrightness
            Layout.fillWidth: true
            spacing: 2
            DeckText {
                visible: screens.count > 1
                Layout.leftMargin: 4
                sub: true
                text: row.label
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Item {
                    implicitWidth: 30
                    implicitHeight: 30
                    DeckIcon {
                        anchors.centerIn: parent
                        width: 16
                        height: 16
                        name: "sun"
                    }
                }
                DeckSlider {
                    Layout.fillWidth: true
                    from: 1  // 0 would turn some panels off
                    to: row.maxBrightness
                    stepSize: Math.max(1, row.maxBrightness / 100)
                    value: row.brightness
                    Accessible.name: "Brightness of " + row.label
                    onMoved: v => control.setBrightness(row.displayName, Math.round(v))
                }
                DeckText {
                    Layout.preferredWidth: 36
                    horizontalAlignment: Text.AlignRight
                    sub: true
                    text: row.maxBrightness ? Math.round(100 * row.brightness / row.maxBrightness) + "%" : ""
                }
                Item { implicitWidth: 30 }
            }
        }
    }
}
