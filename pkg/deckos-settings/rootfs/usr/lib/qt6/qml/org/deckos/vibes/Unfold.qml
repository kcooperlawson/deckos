// DecKoOS's one motion: how anything of the DecKo look arrives. A popup or card fades in while it grows out of the
// edge it comes from (the panel's, for popups: `transformOrigin`), quick and soft, the same everywhere: Quick
// Settings, the menu, the shelf's tiles. The Hub does the same in Python (hub_style.unfold). Set `open` (it plays
// each time it turns true) or call play(); `delay` staggers a row of cards.
import QtQuick

QtObject {
    id: unfold
    property Item target
    property bool open: false
    property int delay: 0
    property int duration: 190
    property int origin: Item.Bottom  // the edge it grows from

    function play() {
        if (!target)
            return;
        target.transformOrigin = origin;
        target.opacity = 0;
        target.scale = 0.965;
        anim.restart();
    }
    onOpenChanged: if (open) play()

    property SequentialAnimation anim: SequentialAnimation {
        PauseAnimation { duration: unfold.delay }
        ParallelAnimation {
            NumberAnimation { target: unfold.target; property: "opacity"; to: 1; duration: unfold.duration; easing.type: Easing.OutCubic }
            NumberAnimation { target: unfold.target; property: "scale"; to: 1; duration: unfold.duration + 40; easing.type: Easing.OutBack; easing.overshoot: 0.6 }
        }
    }
}
