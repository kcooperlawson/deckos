// One stage shader with everything the newer looks read (the shader takes what it declares, by name): the world,
// this screen's part of it, the clock, the beat, the music's levels and 64 bars, the colours.
import QtQuick

ShaderEffect {
    id: sky
    required property real originX
    required property real originY
    required property size viewSize  // this screen's part of the world, in world units
    required property real stageT
    required property real stageKick
    required property real stageReveal
    readonly property Bars data: Bars {}
    property size world: Qt.size(engine.worldWidth, engine.worldHeight)
    property point origin: Qt.point(originX, originY)
    property size view: viewSize
    property point cover: engine.cover
    property real t: stageT
    property real travel: engine.travel
    property real bass: engine.bass
    property real mid: engine.mid
    property real high: engine.high
    property real energy: engine.energy
    property real kick: stageKick
    property real reveal: stageReveal
    property color base: engine.base
    property color accent: engine.accent
    property color second: engine.second
    property vector4d b0: data.v(data.bars, 0)
    property vector4d b1: data.v(data.bars, 1)
    property vector4d b2: data.v(data.bars, 2)
    property vector4d b3: data.v(data.bars, 3)
    property vector4d b4: data.v(data.bars, 4)
    property vector4d b5: data.v(data.bars, 5)
    property vector4d b6: data.v(data.bars, 6)
    property vector4d b7: data.v(data.bars, 7)
    property vector4d b8: data.v(data.bars, 8)
    property vector4d b9: data.v(data.bars, 9)
    property vector4d b10: data.v(data.bars, 10)
    property vector4d b11: data.v(data.bars, 11)
    property vector4d b12: data.v(data.bars, 12)
    property vector4d b13: data.v(data.bars, 13)
    property vector4d b14: data.v(data.bars, 14)
    property vector4d b15: data.v(data.bars, 15)
}
