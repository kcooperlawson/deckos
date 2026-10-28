// One monitor's view of the stage. The world (every monitor, laid out as the desktop has them) is drawn at
// -origin, so whatever lives in it (waves, comets, the horizon, the title) runs on into the next screen. The time
// comes from the shared clock, never from this window, so all of them move together.
import QtQuick
import QtQuick.Window

Window {
    id: win
    objectName: "stage"
    required property var info
    readonly property real originX: info.x
    readonly property real originY: info.y
    readonly property bool home: info.index === engine.home

    // ---- the shared clock, and the way in and out worked out from it
    property real t: (Date.now() - engine.startMs) / 1000
    FrameAnimation {
        running: win.visible
        onTriggered: win.t = (Date.now() - engine.startMs) / 1000
    }
    function ease(x) { return 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3); }
    readonly property real reveal: engine.mode === "leaving" ? 1 - ease((t - engine.leaveAt) / 1.0)
                                                             : ease((t - engine.enterAt) / 1.6)
    readonly property real lastBeat: engine.beats.length ? engine.beats[engine.beats.length - 1] : -10
    readonly property real kick: Math.exp(-Math.max(0, t - lastBeat) * 7)
    readonly property bool controlsShown: t - engine.pokedAt < 3 || drawer.open

    screen: engine.fake ? Qt.application.screens[0] : (Qt.application.screens[info.index] ?? Qt.application.screens[0])
    x: engine.fake ? info.x : screen.virtualX
    y: engine.fake ? info.y : screen.virtualY
    width: info.width
    height: info.height
    visibility: engine.fake ? Window.Windowed : Window.FullScreen
    visible: engine.mode !== "mini"
    flags: Qt.FramelessWindowHint
    color: "transparent"
    title: "DecKoOS Music"

    // ---- the sky: one shader, world coordinates (stage.frag)
    ShaderEffect {
        anchors.fill: parent
        fragmentShader: "stage.frag.qsb"
        property size world: Qt.size(engine.worldWidth, engine.worldHeight)
        property point origin: Qt.point(win.originX, win.originY)
        property size view: Qt.size(win.width, win.height)
        property point cover: engine.cover
        property real t: win.t
        property real travel: engine.travel
        property real bass: engine.bass
        property real mid: engine.mid
        property real high: engine.high
        property real energy: engine.energy
        property real reveal: win.reveal
        // the last eight beats, oldest first (-10: none yet)
        function beat(k) { const b = engine.beats; return b.length > k ? b[b.length - 1 - k] : -10; }
        property vector4d beats: Qt.vector4d(beat(7), beat(6), beat(5), beat(4))
        property vector4d beats2: Qt.vector4d(beat(3), beat(2), beat(1), beat(0))
        property color base: engine.base
        property color accent: engine.accent
        property color second: engine.second
    }

    // ---- everything that lives in the world
    Item {
        id: worldItem
        x: -win.originX
        y: -win.originY
        width: engine.worldWidth
        height: engine.worldHeight
        opacity: win.reveal

        // The song's title, huge and hollow, crossing every screen from right to left
        Text {
            id: marquee
            text: engine.title
            font.family: "Inter Display"
            font.weight: Font.Black
            font.pixelSize: engine.worldHeight * 0.3
            color: "transparent"
            style: Text.Outline
            styleColor: engine.accent
            opacity: 0.12 + 0.16 * engine.bass
            y: engine.worldHeight * 0.66 - height / 2
            x: engine.worldWidth - ((win.t * 70) % (engine.worldWidth + width))
        }

        Horizon {
            anchors.fill: parent
            t: win.t
        }

        Comets {
            anchors.fill: parent
            t: win.t
        }

        CoverBlock {
            visible: win.home
            screenHeight: win.info.height
            reveal: win.reveal
            kick: win.kick
            t: win.t
        }
    }

    // ---- the controls, on the cover's screen, when the mouse moves
    Controls {
        visible: win.home
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.height * 0.07
        shown: win.controlsShown && win.reveal > 0.9
        onLibrary: drawer.open = !drawer.open
    }
    IconButton {  // out of the stage
        icon: "close"
        visible: win.home
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 24
        opacity: win.controlsShown && win.reveal > 0.9 ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 300 } }
        onClicked: engine.leave()
    }
    Drawer {
        id: drawer
        visible: win.home
        height: parent.height
    }

    MouseArea {  // any movement on any screen brings the controls back; clicks fall through to them
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        onPositionChanged: engine.poke()
    }
    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: event => {
            engine.poke();
            if (event.key === Qt.Key_Escape) {
                if (drawer.open) drawer.open = false; else engine.leave();
            } else if (event.key === Qt.Key_Space) engine.playPause();
            else if (event.key === Qt.Key_Right) engine.next();
            else if (event.key === Qt.Key_Left) engine.previous();
            else if (event.key === Qt.Key_L) drawer.open = !drawer.open;
            else return;
            event.accepted = true;
        }
    }
}
