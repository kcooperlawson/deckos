import QtQuick

// A slim slider in the DecKoOS look. `value` is bound from outside (the volume, the brightness);
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

    Rectangle {
        id: track
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        height: 6
        radius: 3
        color: Deck.border
        Rectangle {
            width: Math.max(height, slider.ratio * parent.width)
            height: parent.height
            radius: 3
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Deck.accent }
                GradientStop { position: 1; color: Deck.accentB }
            }
        }
    }
    Rectangle {
        x: slider.ratio * (slider.width - width)
        anchors.verticalCenter: parent.verticalCenter
        width: slider.pressed || mouse.containsMouse || slider.activeFocus ? 16 : 14
        height: width
        radius: width / 2
        color: Deck.text
        border.color: slider.activeFocus ? Deck.accent : Deck.bg
        border.width: 2
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
