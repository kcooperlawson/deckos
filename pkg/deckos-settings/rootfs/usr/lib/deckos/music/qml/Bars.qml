// The 64 bars and their falling caps as the vec4 uniforms the spectrum and trails shaders take (b0..b15,
// p0..p15): engine.bars is read once a frame here, not once per uniform.
import QtQuick

QtObject {
    readonly property var bars: engine.bars
    readonly property var peaks: engine.peaks
    function v(list, k) { return Qt.vector4d(list[4 * k] ?? 0, list[4 * k + 1] ?? 0, list[4 * k + 2] ?? 0, list[4 * k + 3] ?? 0); }
}
