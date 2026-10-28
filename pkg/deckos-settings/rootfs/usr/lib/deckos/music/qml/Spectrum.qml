// The 2000s spectrum analyzer across every screen (spectrum.frag).
import QtQuick

ShaderEffect {
    id: spectrum
    required property real originX
    required property real originY
    required property real kick
    required property real stageT
    required property real stageReveal
    fragmentShader: "spectrum.frag.qsb"
    readonly property Bars data: Bars {}
    property size world: Qt.size(engine.worldWidth, engine.worldHeight)
    property point origin: Qt.point(originX, originY)
    property size view: Qt.size(width, height)
    property point cover: engine.cover
    property real t: stageT
    property real bass: engine.bass
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
    property vector4d p0: data.v(data.peaks, 0)
    property vector4d p1: data.v(data.peaks, 1)
    property vector4d p2: data.v(data.peaks, 2)
    property vector4d p3: data.v(data.peaks, 3)
    property vector4d p4: data.v(data.peaks, 4)
    property vector4d p5: data.v(data.peaks, 5)
    property vector4d p6: data.v(data.peaks, 6)
    property vector4d p7: data.v(data.peaks, 7)
    property vector4d p8: data.v(data.peaks, 8)
    property vector4d p9: data.v(data.peaks, 9)
    property vector4d p10: data.v(data.peaks, 10)
    property vector4d p11: data.v(data.peaks, 11)
    property vector4d p12: data.v(data.peaks, 12)
    property vector4d p13: data.v(data.peaks, 13)
    property vector4d p14: data.v(data.peaks, 14)
    property vector4d p15: data.v(data.peaks, 15)
}
