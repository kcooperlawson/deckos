import QtQuick
import org.deckos.vibes as Vibes

// A slider in the DecKo look: a segmented meter (a marker shows while you point at it). `value` is bound from outside (the volume, the brightness);
// dragging shows its own value until release, so slow round trips through PipeWire or DDC don't
// make the handle jump back.
Item {
    id: slider
    property real from: 0
    property real to: 100
    property real value: 0
    property real stepSize: (to - from) / 100
    property real dragValue: 0
    readonly property bool pressed: mouse.pressed
    readonly property real shown: pressed ? dragValue : Math.max(from, Math.min(to, value))
    readonly property real ratio: to > from ? (shown - from) / (to - from) : 0
    signal moved(real value)
    signal released(real value)  // end of a drag

    implicitHeight: 22
    implicitWidth: 160
    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Keys.onLeftPressed: step(-1)
    Keys.onRightPressed: step(1)

    function set(v: real): void {
        v = Math.max(from, Math.min(to, Math.round(v / stepSize) * stepSize));
        dragValue = v;
        moved(v);
    }
    function step(n: int): void {
        set(value + n * stepSize * 5);
    }

    Vibes.Segments {  // the DecKo meter: lit segments through the accent's gradient
        id: track
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        look: Deck.look
        value: slider.ratio
        count: 24
        segmentHeight: 12
    }
    Rectangle {  // where it is: a thin bar, taller while held
        x: Math.max(0, slider.ratio * slider.width - width / 2)
        anchors.verticalCenter: parent.verticalCenter
        width: 3
        height: slider.pressed || mouse.containsMouse || slider.activeFocus ? 20 : 16
        color: slider.activeFocus ? Deck.accent : Deck.text
        visible: slider.pressed || mouse.containsMouse || slider.activeFocus
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        anchors.topMargin: -4
        anchors.bottomMargin: -4
        hoverEnabled: true
        preventStealing: true
        function at(x: real): real {
            return slider.from + Math.max(0, Math.min(1, x / slider.width)) * (slider.to - slider.from);
        }
        onPressed: mouseEvent => slider.set(at(mouseEvent.x))
        onPositionChanged: mouseEvent => { if (pressed) slider.set(at(mouseEvent.x)); }
        onReleased: slider.released(slider.dragValue)
        onWheel: wheel => slider.step(wheel.angleDelta.y > 0 ? 1 : -1)
    }
}
