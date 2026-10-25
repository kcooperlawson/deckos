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
    Layout.preferredWidth: vertical ? -1 : strip.implicitWidth
    Layout.preferredHeight: vertical ? strip.implicitHeight : -1
    Layout.minimumWidth: vertical ? -1 : Math.min(strip.implicitWidth, tile * 3)

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

    function pinned(url) {
        return deckModel.launcherPosition(url) !== -1;
    }
    function togglePin(url) {
        if (pinned(url))
            deckModel.requestRemoveLauncher(url);
        else
            deckModel.requestAddLauncher(url);
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
}
