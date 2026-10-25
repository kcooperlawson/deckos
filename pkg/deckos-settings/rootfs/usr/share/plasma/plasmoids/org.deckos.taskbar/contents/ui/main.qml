// DeckOS Taskbar: pinned apps and open windows in the DeckOS look (slate tiles, accent gradient
// pill under the active app, dots for open windows). Windows, launchers, grouping and ordering
// all come from Plasma's own TasksModel, as the stock task managers get them; this file only
// decides how they look and what a click does. Event-driven: no timers, nothing polled.
// The other files reach the model and palette through the `deckTasks` id.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.taskmanager as TaskManager
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: deckTasks

    readonly property color raised: "#1E222B"
    readonly property color border: "#262B36"
    readonly property color text: "#E8EAF0"
    readonly property color subtext: "#8C94A6"
    readonly property color accent: "#4C8DFF"
    readonly property color accentB: "#7A5CFF"
    readonly property color attention: "#F5A524"

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool labels: Plasmoid.configuration.showLabels && !vertical
    // A square tile per app, as tall as the panel is thick
    readonly property real tile: Math.max(24, vertical ? width : height)
    // With titles, apps share the panel: up to 220 px each, never narrower than an icon and a few letters
    readonly property real labelWidth: Math.max(tile * 3, Math.min(220, (width - 4 * repeater.count) / Math.max(1, repeater.count)))

    preferredRepresentation: fullRepresentation
    Component.onCompleted: Plasmoid.constraintHints = Plasmoid.CanFillArea
    Layout.fillWidth: !vertical && labels
    Layout.fillHeight: vertical
    // The strip of apps, then the + tile
    Layout.preferredWidth: vertical ? -1 : strip.implicitWidth + Math.round(tile * 0.7)
    Layout.preferredHeight: vertical ? strip.implicitHeight + Math.round(tile * 0.7) : -1
    Layout.minimumWidth: vertical ? -1 : Math.min(strip.implicitWidth, tile * 3) + Math.round(tile * 0.7)

    TaskManager.VirtualDesktopInfo { id: desktopInfo }
    TaskManager.ActivityInfo { id: activityInfo }

    TaskManager.TasksModel {
        id: deckModel
        sortMode: TaskManager.TasksModel.SortManual
        groupMode: TaskManager.TasksModel.GroupApplications
        groupInline: false
        separateLaunchers: false
        launchInPlace: true
        hideActivatedLaunchers: true
        filterByVirtualDesktop: true
        filterByActivity: true
        filterByScreen: Plasmoid.configuration.onlyThisScreen
        filterHidden: true
        virtualDesktop: desktopInfo.currentDesktop
        activity: activityInfo.currentActivity
        screenGeometry: Plasmoid.containment.screenGeometry
        launcherList: Plasmoid.configuration.launchers
        // Pinning, unpinning and dragging change the model's list; keep the config in step
        onLauncherListChanged: if (String(launcherList) !== String(Plasmoid.configuration.launchers))
            Plasmoid.configuration.launchers = launcherList
    }

    // What Plasma's menus call on a task manager to pin an app (used if they ever recognise this one)
    function addLauncher(url) {
        deckModel.requestAddLauncher(url);
    }
    function hasLauncher(url) {
        return pinned(url);
    }

    function pinned(url) {
        return deckModel.launcherPosition(url) !== -1;
    }
    function togglePin(url) {
        if (pinned(url))
            deckModel.requestRemoveLauncher(url);
        else
            deckModel.requestAddLauncher(url);
    }

    // Empty taskbar space: right-click to pin an app, or drop one here from the menu or a folder
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: barMenu.openRelative()
    }
    // Any type filter here let the panel take the drop instead (it then failed to add an icon widget)
    DropArea {
        anchors.fill: parent
        onEntered: drag => drag.accepted = drag.hasUrls
        onDropped: drop => {
            for (const u of drop.urls) {
                const url = String(u);
                if (url.endsWith(".desktop") || url.startsWith("applications:"))
                    deckModel.requestAddLauncher(url);
            }
            drop.accept(Qt.CopyAction);
        }
    }
    PlasmaExtras.Menu {
        id: barMenu
        visualParent: deckTasks
        PlasmaExtras.MenuItem {
            text: "Pin an app…"
            icon: "list-add"
            onClicked: deckTasks.pickApp()
        }
        PlasmaExtras.MenuItem {
            text: Plasmoid.configuration.showLabels ? "Icons only" : "Show window titles"
            icon: "view-list-text"
            onClicked: Plasmoid.configuration.showLabels = !Plasmoid.configuration.showLabels
        }
    }
    function pickApp() {
        picker.connectSource("kdialog --title 'Pin an app' --getopenfilename /usr/share/applications '*.desktop'");
    }
    P5Support.DataSource {
        id: picker
        engine: "executable"
        onNewData: (source, data) => {
            const path = String(data.stdout || "").trim();
            if (path.endsWith(".desktop"))
                deckModel.requestAddLauncher("file://" + path);
            disconnectSource(source);
        }
    }

    Grid {
        id: strip
        anchors.left: deckTasks.vertical ? undefined : parent.left
        anchors.top: deckTasks.vertical ? parent.top : undefined
        anchors.verticalCenter: deckTasks.vertical ? undefined : parent.verticalCenter
        anchors.horizontalCenter: deckTasks.vertical ? parent.horizontalCenter : undefined
        rows: deckTasks.vertical ? -1 : 1
        columns: deckTasks.vertical ? 1 : -1
        spacing: 4
        move: Transition {
            NumberAnimation { properties: "x,y"; duration: 160; easing.type: Easing.OutCubic }
        }

        Repeater {
            id: repeater
            model: deckModel
            delegate: Task {}
        }
    }

    // The way to pin an app that isn't open: a fitted dock has no empty space to right-click
    Item {
        id: addTile
        x: deckTasks.vertical ? 0 : strip.x + strip.width
        y: deckTasks.vertical ? strip.y + strip.height : 0
        width: deckTasks.vertical ? deckTasks.width : Math.round(deckTasks.tile * 0.7)
        height: deckTasks.vertical ? Math.round(deckTasks.tile * 0.7) : deckTasks.tile
        Rectangle {
            anchors.centerIn: parent
            width: Math.round(deckTasks.tile * 0.5)
            height: width
            radius: 8
            color: addArea.containsMouse ? deckTasks.raised : "transparent"
            border.width: 1
            border.color: addArea.containsMouse ? deckTasks.border : "transparent"
            Text {
                anchors.centerIn: parent
                text: "+"
                color: addArea.containsMouse ? deckTasks.text : deckTasks.subtext
                opacity: addArea.containsMouse ? 1 : 0.6
                font.pixelSize: Math.round(deckTasks.tile * 0.36)
            }
        }
        MouseArea {
            id: addArea
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: e => e.button === Qt.RightButton ? barMenu.openRelative() : deckTasks.pickApp()
        }
        PlasmaCore.ToolTipArea {
            anchors.fill: parent
            mainText: "Pin an app"
            subText: "Or drag one here from the menu"
        }
    }
}
