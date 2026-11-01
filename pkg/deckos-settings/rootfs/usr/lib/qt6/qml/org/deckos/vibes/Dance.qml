// Moving with the music, not just glowing with it. Each thing dances to one `part` of the song, so a row of them
// isn't all doing the same:
//   kick     on each of the visualizer's beats, a hop up (higher with more bass) and a tilt that swings left on one
//            beat and right on the next, then a springy landing
//   groove   rides the mids (voice, synths, the snare): rises and leans with them, smoothly, between the beats too
//   sparkle  the highs (hi-hats, cymbals): a quick little swell in size
// `index` staggers the kick, so a row hopping one after another is a wave, and turns the groove's lean the other way
// on every other one. Put `moves` in the thing's transform list; `origin` is what it tilts and swells around (its
// bottom middle).
import QtQuick

QtObject {
    id: dance
    property var levels: null       // a Vibes.Levels
    property bool enabled: true     // motion on, and the music reacting
    property string part: "kick"    // kick, groove or sparkle
    property int index: 0
    property real height: 8         // the highest hop or rise, in pixels
    property real tilt: 6           // degrees
    property real swell: 0.1        // sparkle: the most it grows (0.1 = 10%)
    property point origin: Qt.point(0, 0)

    readonly property bool _on: enabled && !!levels
    readonly property Translate hop: Translate {}
    readonly property Translate lift: Translate {
        y: dance._on && dance.part === "groove" ? -dance.height * 0.8 * Math.min(1, dance.levels.mid * 1.4) : 0
        Behavior on y { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
    }
    readonly property Rotation sway: Rotation { origin.x: dance.origin.x; origin.y: dance.origin.y }
    readonly property Rotation lean: Rotation {
        origin.x: dance.origin.x
        origin.y: dance.origin.y
        angle: dance._on && dance.part === "groove"
               ? ((dance.levels.beats + dance.index) % 2 ? 1 : -1) * dance.tilt * 0.7 * Math.min(1, dance.levels.mid * 1.5) : 0
        Behavior on angle { NumberAnimation { duration: 260; easing.type: Easing.InOutSine } }
    }
    readonly property Scale pop: Scale {
        origin.x: dance.origin.x
        origin.y: dance.origin.y
        readonly property real s: 1 + (dance._on && dance.part === "sparkle" ? dance.swell * Math.min(1, dance.levels.high * 1.8) : 0)
        xScale: s
        yScale: s
    }
    readonly property list<QtObject> moves: [hop, lift, sway, lean, pop]

    property real _up: 0
    property real _tip: 0
    property Connections _beat: Connections {
        target: dance.levels
        enabled: dance._on && dance.part === "kick"
        function onBeatsChanged() {
            const kick = Math.max(0.35, Math.min(1, dance.levels.bass * 1.2));
            dance._up = -dance.height * kick;
            dance._tip = ((dance.levels.beats + dance.index) % 2 ? 1 : -1) * dance.tilt * kick;
            _move.restart();
        }
    }
    property SequentialAnimation _move: SequentialAnimation {
        PauseAnimation { duration: Math.max(0, Math.min(8, dance.index)) * 28 }  // (-1: a tile not placed yet)
        ParallelAnimation {
            NumberAnimation { target: dance.hop; property: "y"; to: dance._up; duration: 85; easing.type: Easing.OutQuad }
            NumberAnimation { target: dance.sway; property: "angle"; to: dance._tip; duration: 85; easing.type: Easing.OutQuad }
        }
        ParallelAnimation {
            NumberAnimation { target: dance.hop; property: "y"; to: 0; duration: 320; easing.type: Easing.OutBounce }
            NumberAnimation { target: dance.sway; property: "angle"; to: 0; duration: 360; easing.type: Easing.OutBack }
        }
    }
    on_OnChanged: if (!_on) { _move.stop(); hop.y = 0; sway.angle = 0; }
}
