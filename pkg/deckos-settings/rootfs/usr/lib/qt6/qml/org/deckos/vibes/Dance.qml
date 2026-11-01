// Moving with the music, not just glowing with it: on each of the visualizer's beats (a Levels' `beats`), a hop up
// (higher with more bass) and a tilt that swings left on one beat and right on the next, then a springy landing.
// `index` staggers it: a row of things hopping one after another is a wave across the dock. Put it in the thing's
// transform list (transform: [dance.hop, dance.sway]); `origin` is where it tilts from (its bottom middle).
import QtQuick

QtObject {
    id: dance
    property var levels: null       // a Vibes.Levels
    property bool enabled: true     // motion on, and the music reacting
    property int index: 0
    property real height: 8         // the highest hop, in pixels, on a heavy kick
    property real tilt: 6           // degrees
    property point origin: Qt.point(0, 0)

    readonly property Translate hop: Translate {}
    readonly property Rotation sway: Rotation { origin.x: dance.origin.x; origin.y: dance.origin.y }

    property real _up: 0
    property real _lean: 0
    property Connections _beat: Connections {
        target: dance.levels
        enabled: dance.enabled && !!dance.levels
        function onBeatsChanged() {
            const kick = Math.max(0.35, Math.min(1, dance.levels.bass * 1.2));
            dance._up = -dance.height * kick;
            dance._lean = ((dance.levels.beats + dance.index) % 2 ? 1 : -1) * dance.tilt * kick;
            _move.restart();
        }
    }
    property SequentialAnimation _move: SequentialAnimation {
        PauseAnimation { duration: Math.min(8, dance.index) * 28 }
        ParallelAnimation {
            NumberAnimation { target: dance.hop; property: "y"; to: dance._up; duration: 85; easing.type: Easing.OutQuad }
            NumberAnimation { target: dance.sway; property: "angle"; to: dance._lean; duration: 85; easing.type: Easing.OutQuad }
        }
        ParallelAnimation {
            NumberAnimation { target: dance.hop; property: "y"; to: 0; duration: 320; easing.type: Easing.OutBounce }
            NumberAnimation { target: dance.sway; property: "angle"; to: 0; duration: 360; easing.type: Easing.OutBack }
        }
    }
    onEnabledChanged: if (!enabled) { _move.stop(); hop.y = 0; sway.angle = 0; }
}
