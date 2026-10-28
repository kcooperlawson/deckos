// Choosing how Vibe mode looks: follow your Vibe, or pick a stage; and your Vibe's colours or the album cover's.
// Remembered (looks.py). V cycles the stages without opening this.
import QtQuick

Rectangle {
    id: picker
    property bool open: false
    width: column.width + 48
    height: column.height + 40
    radius: 22
    color: Qt.rgba(0.04, 0.05, 0.08, 0.94)
    border.color: Qt.rgba(1, 1, 1, 0.12)
    opacity: open ? 1 : 0
    visible: opacity > 0
    scale: open ? 1 : 0.96
    Behavior on opacity { NumberAnimation { duration: 200 } }
    Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    component Chip: Rectangle {
        id: chip
        property string label
        property bool on: false
        signal picked()
        width: text.implicitWidth + 32
        height: 38
        radius: 19
        color: on ? engine.accent : hover.hovered ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.06)
        border.color: Qt.rgba(1, 1, 1, on ? 0 : 0.12)
        Text {
            id: text
            anchors.centerIn: parent
            text: chip.label
            color: chip.on ? "#0F1115" : "white"
            font.pixelSize: 15
            font.weight: chip.on ? Font.DemiBold : Font.Normal
        }
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: chip.picked() }
    }
    component Label: Text {
        color: Qt.rgba(1, 1, 1, 0.55)
        font.pixelSize: 12
        font.letterSpacing: 1.5
        font.capitalization: Font.AllUppercase
    }

    Column {
        id: column
        anchors.centerIn: parent
        spacing: 12
        Label { text: "Look" }
        Row {
            spacing: 8
            Chip {
                label: engine.vibeName ? "Like " + engine.vibeName + " (" + engine.vibeStyle + ")" : "Automatic"
                on: engine.styleChoice === "auto"
                onPicked: engine.setStyle("auto")
            }
            Repeater {
                model: [["aurora", "Aurora"], ["spectrum", "Spectrum"], ["trails", "Trails"], ["glow", "Glow"]]
                Chip {
                    required property var modelData
                    label: modelData[1]
                    on: engine.styleChoice === modelData[0]
                    onPicked: engine.setStyle(modelData[0])
                }
            }
        }
        Label { text: "Colours"; visible: engine.vibeName !== "" }
        Row {
            spacing: 8
            visible: engine.vibeName !== ""
            Chip { label: engine.vibeName; on: engine.colourChoice === "vibe"; onPicked: engine.setColours("vibe") }
            Chip { label: "Album cover"; on: engine.colourChoice === "cover"; onPicked: engine.setColours("cover") }
        }
    }
}
