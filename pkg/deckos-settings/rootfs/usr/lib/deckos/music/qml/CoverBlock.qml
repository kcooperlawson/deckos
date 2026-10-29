// The cover at the heart of the world: a spectrum ring around it (the sky glows behind it), a kick on every
// beat, and the song and artist under it. It grows out of nothing on the way in and shrinks back on the way out.
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import org.deckos.vibes as Vibes

Item {
    id: block
    property real screenHeight: 1080
    property real reveal: 1
    property real kick: 0
    property real t: 0
    property bool ring: true  // the stages that draw their own sound around it turn this off
    property bool quiet: false  // the title steps back while the look picker is over it
    readonly property var look: Vibes.Look { colorA: engine.accent; colorB: engine.second }
    readonly property real size: screenHeight * 0.34

    x: engine.cover.x
    y: engine.cover.y

    Item {  // centred on the cover's point
        id: heart
        scale: (0.35 + 0.65 * block.reveal) * (1 + 0.035 * engine.bass + 0.04 * block.kick)

        Repeater {  // the spectrum ring
            model: block.ring ? 64 : 0
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
        Vibes.Notch {  // the cover's lit edge, just outside it
            x: art.x - 2
            y: art.y - 2
            width: art.width + 4
            height: art.height + 4
            look: block.look
            cut: block.size * 0.08 + 1
            edge: 2
            fill: "transparent"
        }
        Shape {  // the cover notched like the DecKo cards
            id: roundMask
            width: art.width
            height: art.height
            visible: false
            layer.enabled: true
            layer.samples: 4
            readonly property real c: block.size * 0.08
            ShapePath {
                strokeColor: "transparent"
                fillColor: "white"
                PathPolyline { path: [Qt.point(0, 0), Qt.point(roundMask.width - roundMask.c, 0), Qt.point(roundMask.width, roundMask.c),
                                      Qt.point(roundMask.width, roundMask.height), Qt.point(roundMask.c, roundMask.height),
                                      Qt.point(0, roundMask.height - roundMask.c)] }
            }
        }
        Item {  // the shadow goes on the notched cover: one effect can't mask and shadow at once (the shadow wins)
            x: art.x
            y: art.y
            width: art.width
            height: art.height
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowBlur: 0.8; shadowOpacity: 0.6; shadowVerticalOffset: 12 }
            MultiEffect {
                source: art
                anchors.fill: parent
                maskEnabled: true
                maskThresholdMin: 0.5  // without a threshold every pixel passes and nothing is masked
                maskSpreadAtMin: 1.0
                maskSource: roundMask
            }
        }
    }

    Vibes.Notch {  // without the ring, the title sits closer, on a notched plate so bars and trails don't run through it
        visible: engine.style === "spectrum" || engine.style === "trails"
        anchors.centerIn: info
        width: Math.min(info.width, Math.max(titleText.contentWidth, artistText.contentWidth) + 64)
        height: info.height + 30
        look: block.look
        cut: 14
        fill: Qt.rgba(engine.base.r * 0.5, engine.base.g * 0.5, engine.base.b * 0.5, 0.82)
        opacity: info.opacity
    }
    Column {
        id: info
        y: block.ring ? block.size * 0.8 + 50 : block.size * 0.5 + 40
        x: -width / 2
        width: block.size * 2
        spacing: 6
        opacity: Math.max(0, block.reveal * 1.4 - 0.4) * (block.quiet ? 0 : 1)
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            id: titleText
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: engine.title || "Nothing playing"
            color: "white"
            font.family: "Chakra Petch"
            font.weight: Font.DemiBold
            font.pixelSize: block.screenHeight * 0.044
            elide: Text.ElideRight
        }
        Text {
            id: artistText
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
