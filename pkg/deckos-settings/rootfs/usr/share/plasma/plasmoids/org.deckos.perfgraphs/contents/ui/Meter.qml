// A meter row: its name, lit segments, the value
import QtQuick
import QtQuick.Layouts
import org.deckos.vibes as Vibes

RowLayout {
    id: meter
    required property var look
    property string label
    property real value: 0
    property string valueText
    spacing: 12
    Vibes.Hud { look: meter.look; text: meter.label; Layout.preferredWidth: 46 }
    Vibes.Segments { look: meter.look; value: meter.value; plain: true; count: 20; Layout.fillWidth: true }
    Text {
        text: meter.valueText
        color: meter.look.text
        font.family: meter.look.hud
        font.weight: Font.Medium
        font.pixelSize: 14
        horizontalAlignment: Text.AlignRight
        Layout.preferredWidth: 110
    }
}
