// DecKoOS Vibe wallpaper: an animated scene (Lo-fi rain, Neon grid, Midnight stars, Cozy forest) and, on top, the
// music visualizer, fed by deckos-visualizer.service over a local WebSocket. It's the wallpaper, so it sits under
// every window and clicks go to the desktop. Everything stops while a full-screen or maximized window covers its
// screen (games, videos, work) and the visualizer only connects while it's shown. `deckos vibe` writes the
// configuration.
import QtQuick
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager

WallpaperItem {
    id: root

    readonly property string scene: root.configuration.Scene || "lofi"
    readonly property string visualizer: root.configuration.Visualizer || "none"
    readonly property color colorA: root.configuration.ColorA
    readonly property color colorB: root.configuration.ColorB
    // Moving only while someone can see it: no full-screen window on this screen, animation not turned off
    readonly property bool running: root.configuration.Animate !== false && fullScreen.covering === 0 && visible

    // Full-screen windows (a game, a video) on this wallpaper's screen only: a game on the other monitor (or one
    // being streamed) mustn't freeze this one. Counted from Plasma's own task list, no polling
    TaskManager.TasksModel {
        id: tasks
        filterMinimized: true
        filterByScreen: true
        screenGeometry: Qt.rect(root.Screen.virtualX, root.Screen.virtualY, root.Screen.width, root.Screen.height)
        groupMode: TaskManager.TasksModel.GroupDisabled
    }
    Instantiator {
        id: fullScreen
        property int covering: 0  // not `count`: that's the Instantiator's own number of objects
        model: tasks
        // QML properties can't start with a capital letter, so the role is read through `model`
        delegate: QtObject {
            required property var model
            // Full screen or maximized: either way the wallpaper behind it can't be seen, so it needn't move
            // (moving, it cost about 15% of a CPU core on two screens)
            readonly property bool full: model.IsFullScreen === true || model.IsMaximized === true
            onFullChanged: fullScreen.recount()
        }
        onObjectAdded: recount()
        onObjectRemoved: recount()
        function recount() {
            let n = 0;
            for (let i = 0; i < count; i++)
                if (objectAt(i) && objectAt(i).full)
                    n++;
            fullScreen.covering = n;
        }
    }

    Loader {
        anchors.fill: parent
        source: ({ lofi: "LofiScene.qml", neon: "NeonScene.qml", midnight: "MidnightScene.qml",
                   cozy: "CozyScene.qml" })[root.scene] || "LofiScene.qml"
        onLoaded: {
            item.running = Qt.binding(() => root.running);
            item.colorA = Qt.binding(() => root.colorA);
            item.colorB = Qt.binding(() => root.colorB);
        }
    }

    Visualizer {
        anchors.fill: parent
        visible: root.visualizer !== "none"
        style: root.visualizer
        active: visible && root.running
        colorA: root.colorA
        colorB: root.colorB
    }
}
