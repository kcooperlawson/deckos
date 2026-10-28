// Film grain over a scene: noise drawn once into a small tile, repeated across the screen and nudged a few times a
// second so it shimmers like film. It's what makes a clean render look photographed. Cheap: one texture, moved.
import QtQuick

Item {
    id: grain
    property bool running: true
    property real strength: 0.06
    clip: true

    Canvas {
        id: noise
        width: 256; height: 256
        visible: false
        onPaint: {
            const ctx = getContext("2d");
            const img = ctx.createImageData(width, height);
            for (let i = 0; i < img.data.length; i += 4) {
                const v = Math.random() * 255;
                img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
                img.data[i + 3] = 255;
            }
            ctx.putImageData(img, 0, 0);
            tile.source = toDataURL("image/png");
        }
        Component.onCompleted: requestPaint()
    }
    Image {
        id: tile
        x: -256; y: -256
        width: grain.width + 512; height: grain.height + 512
        fillMode: Image.Tile
        opacity: grain.strength
        smooth: false
    }
    Timer {
        interval: 120; repeat: true; running: grain.running
        onTriggered: { tile.x = -Math.floor(Math.random() * 256); tile.y = -Math.floor(Math.random() * 256); }
    }
}
