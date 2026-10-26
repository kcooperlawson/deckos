// DecKoOS Vibe wallpaper: an animated scene (Lo-fi rain, Neon grid, Midnight stars, Cozy forest) and, on top, the
// music visualizer, fed by deckos-visualizer.service over a local WebSocket. It's the wallpaper, so it sits under
// every window and clicks go to the desktop. Everything stops while a window is full screen (games, videos) and
// the visualizer only connects while it's shown. `deckos vibe` writes the configuration.
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager

WallpaperItem {
    id: root

    readonly property string scene: root.configuration.Scene || "lofi"
    readonly property string visualizer: root.configuration.Visualizer || "none"
    readonly property color colorA: root.configuration.ColorA
    readonly property color colorB: root.configuration.ColorB
    // Moving only while someone can see it: no full-screen window on this screen, animation not turned off
    readonly property bool running: root.configuration.Animate !== false && fullScreen.count === 0 && visible

    // Full-screen windows (a game, a video): counted from Plasma's own task list, no polling
    TaskManager.TasksModel {
        id: tasks
        filterByScreen: true
        screenGeometry: root.parent ? Qt.rect(0, 0, root.width, root.height) : Qt.rect(0, 0, 0, 0)
        filterMinimized: true
    }
    Instantiator {
        id: fullScreen
        property int count: 0
        model: tasks
        delegate: QtObject {
            required property bool IsFullScreen
            Component.onCompleted: if (IsFullScreen) fullScreen.count++
            Component.onDestruction: if (IsFullScreen) fullScreen.count--
            onIsFullScreenChanged: fullScreen.count += IsFullScreen ? 1 : -1
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
