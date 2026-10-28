// The cover at the heart of the world: a spectrum ring around it (the sky glows behind it), a kick on every
// beat, and the song and artist under it. It grows out of nothing on the way in and shrinks back on the way out.
import QtQuick
import QtQuick.Effects

Item {
    id: block
    property real screenHeight: 1080
    property real reveal: 1
    property real kick: 0
    property real t: 0
    readonly property real size: screenHeight * 0.34

    x: engine.cover.x
    y: engine.cover.y

    Item {  // centred on the cover's point
        id: heart
        scale: (0.35 + 0.65 * block.reveal) * (1 + 0.035 * engine.bass + 0.04 * block.kick)

        Repeater {  // the spectrum ring
            model: 64
            Rectangle {
                required property int index
                readonly property real level: engine.bars[index < 32 ? index : 63 - index] ?? 0
                width: 4
                height: 8 + block.size * 0.22 * level
                radius: 2
                color: Qt.lighter(index % 2 ? engine.second : engine.accent, 1.2)
                opacity: 0.5 + 0.5 * level
                x: -width / 2
                y: -block.size * 0.8 - height
                transformOrigin: Item.Bottom
                transform: Rotation { origin.x: 2; origin.y: block.size * 0.8 + height; angle: index * 360 / 64 + block.t * 4 }
            }
        }

        Image {
            id: art
            source: engine.art
            width: block.size
            height: block.size
            x: -width / 2
            y: -height / 2
            fillMode: Image.PreserveAspectCrop
            sourceSize: Qt.size(1024, 1024)
            visible: false
        }
        Rectangle {
            id: roundMask
            width: art.width
            height: art.height
            radius: 22
            visible: false
            layer.enabled: true
        }
        MultiEffect {
            source: art
            anchors.fill: art
            maskEnabled: true
            maskSource: roundMask
            shadowEnabled: true
            shadowBlur: 0.8
            shadowOpacity: 0.6
            shadowVerticalOffset: 12
        }
    }

    Column {
        y: block.size * 0.8 + 50
        x: -width / 2
        width: block.size * 2
        spacing: 6
        opacity: Math.max(0, block.reveal * 1.4 - 0.4)
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: engine.title || "Nothing playing"
            color: "white"
            font.family: "Inter Display"
            font.weight: Font.Bold
            font.pixelSize: block.screenHeight * 0.042
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: engine.artist
            color: Qt.rgba(1, 1, 1, 0.7)
            font.family: "Inter"
            font.pixelSize: block.screenHeight * 0.024
            elide: Text.ElideRight
        }
    }
}
