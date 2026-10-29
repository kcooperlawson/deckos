// Trails' feedback loop: `canvas` draws the last frame (`feedback`) warped, with the new ring on it; `feedback`
// keeps what it drew for the next frame; and the window shows it through trails_show.frag. Half resolution: the
// trails are soft anyway, and it keeps the graphics card's work small.
import QtQuick

Item {
    id: trails
    required property real originX
    required property real originY
    required property real t
    required property real kick
    required property real reveal
    required property size viewSize  // this screen's part of the world, in world units
    Bars { id: bars }

    Item {
        id: canvas
        anchors.fill: parent
        ShaderEffect {
            anchors.fill: parent
            fragmentShader: "trails.frag.qsb"
            property var last: feedback
            property size world: Qt.size(engine.worldWidth, engine.worldHeight)
            property point origin: Qt.point(trails.originX, trails.originY)
            property size view: trails.viewSize
            property point cover: engine.cover
            property real t: trails.t
            property real bass: engine.bass
            property real mid: engine.mid
            property real kick: trails.kick
            property color accent: engine.accent
            property color second: engine.second
            property vector4d b0: bars.v(bars.bars, 0)
            property vector4d b1: bars.v(bars.bars, 1)
            property vector4d b2: bars.v(bars.bars, 2)
            property vector4d b3: bars.v(bars.bars, 3)
            property vector4d b4: bars.v(bars.bars, 4)
            property vector4d b5: bars.v(bars.bars, 5)
            property vector4d b6: bars.v(bars.bars, 6)
            property vector4d b7: bars.v(bars.bars, 7)
            property vector4d b8: bars.v(bars.bars, 8)
            property vector4d b9: bars.v(bars.bars, 9)
            property vector4d b10: bars.v(bars.bars, 10)
            property vector4d b11: bars.v(bars.bars, 11)
            property vector4d b12: bars.v(bars.bars, 12)
            property vector4d b13: bars.v(bars.bars, 13)
            property vector4d b14: bars.v(bars.bars, 14)
            property vector4d b15: bars.v(bars.bars, 15)
        }
    }
    ShaderEffectSource {
        id: feedback
        sourceItem: canvas
        recursive: true
        hideSource: true
        live: true
        textureSize: Qt.size(trails.width / 2, trails.height / 2)
        anchors.fill: parent
        visible: false
    }
    ShaderEffect {
        anchors.fill: parent
        fragmentShader: "trails_show.frag.qsb"
        property var picture: feedback
        property size world: Qt.size(engine.worldWidth, engine.worldHeight)
        property point origin: Qt.point(trails.originX, trails.originY)
        property size view: trails.viewSize
        property point cover: engine.cover
        property real reveal: trails.reveal
        property color base: engine.base
        property color accent: engine.accent
    }
}
