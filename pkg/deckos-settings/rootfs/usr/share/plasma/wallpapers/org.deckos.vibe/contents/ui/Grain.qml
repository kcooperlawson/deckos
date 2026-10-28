// Film grain over a scene: a small noise tile (images/grain.png), repeated across the screen and nudged a few times
// a second so it shimmers like film. It's what makes a clean render look photographed. Cheap: one texture, moved.
// The tile ships as a file: drawing it at runtime (a hidden Canvas turned into a data URL) pinned plasmashell's main
// thread after every Vibe switch, freezing the taskbar and widgets with it.
import QtQuick

Item {
    id: grain
    property bool running: true
    property real strength: 0.06
    clip: true

    Image {
        id: tile
        x: -256; y: -256
        width: grain.width + 512; height: grain.height + 512
        source: "../images/grain.png"
        fillMode: Image.Tile
        opacity: grain.strength
        smooth: false
    }
    Timer {
        interval: 120; repeat: true; running: grain.running
        onTriggered: { tile.x = -Math.floor(Math.random() * 256); tile.y = -Math.floor(Math.random() * 256); }
    }
}
