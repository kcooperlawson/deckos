// DecKoOS Taskbar: pinned apps and open windows in the DecKoOS look (slate tiles, accent gradient
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
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: deckTasks

    // Colours from the active colour scheme and accent, so themes and the Hub's accent reach this widget;
    // the surfaces are the scheme's background lifted towards its text, like the DecKoOS slate steps.
    readonly property color text: Kirigami.Theme.textColor
    readonly property color subtext: Kirigami.Theme.disabledTextColor
    readonly property color accent: Kirigami.Theme.highlightColor
    // The gradient partner: the accent shifted towards violet, like the brand tile
    readonly property color accentB: Qt.hsva((accent.hsvHue + 32 / 360) % 1, Math.min(1, accent.hsvSaturation + 0.04),
                                             accent.hsvValue, 1)
    readonly property color raised: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.08))
    readonly property color border: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.13))
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

    // `deckos accent` bumps iconEpoch after it recolours the icons: the tiles keep the icons they were
    // made with, so they're made again (no restart of Plasma needed)
    readonly property int iconEpoch: Plasmoid.configuration.iconEpoch
    onIconEpochChanged: {
        repeater.model = null;
        repeater.model = deckModel;
    }

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
        virtualDesktop: desktopInfo.currentDesktop
        activity: activityInfo.currentActivity
        screenGeometry: Plasmoid.containment.screenGeometry
        launcherList: Plasmoid.configuration.launchers
        // Pinning, unpinning and dragging change the model's list; keep the config in step
        onLauncherListChanged: {
            if (String(launcherList) !== String(Plasmoid.configuration.launchers))
                Plasmoid.configuration.launchers = launcherList;
            Qt.callLater(deckTasks.keepPinnedOrder);
        }
        onRowsInserted: Qt.callLater(deckTasks.keepPinnedOrder)
        onDataChanged: Qt.callLater(deckTasks.keepPinnedOrder)
    }

    // TasksModel's own launch-in-place misses windows whose launcher is preferred:// (browser,
    // file manager) or that report only an app id (Electron), and those slid to the end. So a
    // window is put back in its pin's slot here, matched by .desktop name; unpinned ones follow.
    property bool dragActive: false
    property var preferred: ({})
    function appKey(u) {
        u = String(u || "");
        if (u.startsWith("preferred://"))
            u = preferred[u.slice(12)] || u;
        return u.split("?")[0].replace(/^applications:/, "").replace(/^.*\//, "")
            .replace(/\.desktop$/, "").toLowerCase();
    }
    function pinRank(row, pins) {
        const i = deckModel.makeModelIndex(row);
        for (const role of [TaskManager.AbstractTasksModel.LauncherUrlWithoutIcon, TaskManager.AbstractTasksModel.AppId]) {
            const k = appKey(deckModel.data(i, role));
            const at = k ? pins.indexOf(k) : -1;
            if (at !== -1)
                return at;
        }
        return 1e6;
    }
    function keepPinnedOrder() {
        if (dragActive)
            return;
        const pins = deckModel.launcherList.map(appKey);
        const ranks = [];
        for (let r = 0; r < deckModel.count; ++r)
            ranks.push(pinRank(r, pins));
        // Stable insertion sort, one model move per tile out of place
        for (let r = 1; r < ranks.length; ++r) {
            let to = r;
            while (to > 0 && ranks[to - 1] > ranks[r])
                --to;
            if (to !== r) {
                deckModel.move(r, to);
                ranks.splice(to, 0, ranks.splice(r, 1)[0]);
            }
        }
    }
    P5Support.DataSource {
        id: defaults
        engine: "executable"
        connectedSources: ["echo \"browser=$(xdg-settings get default-web-browser)\"; echo \"filemanager=$(xdg-mime query default inode/directory)\""]
        onNewData: (source, data) => {
            const map = {};
            for (const line of String(data.stdout || "").split("\n")) {
                const eq = line.indexOf("=");
                if (eq > 0 && line.slice(eq + 1).trim())
                    map[line.slice(0, eq)] = line.slice(eq + 1).trim();
            }
            deckTasks.preferred = map;
            disconnectSource(source);
            deckTasks.keepPinnedOrder();
        }
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
        PlasmaExtras.MenuItem {
            text: Plasmoid.configuration.onlyThisScreen ? "Show windows from all screens" : "Only this screen's windows"
            icon: "video-display"
            onClicked: Plasmoid.configuration.onlyThisScreen = !Plasmoid.configuration.onlyThisScreen
        }
    }
    // A searchable list of installed apps; click one to pin it (pinned ones are ticked, click again to unpin)
    function pickApp() {
        appSource.connectSource("python3 '" + Qt.resolvedUrl("../code/apps.py").toString().replace("file://", "") + "'");
        search.text = "";
        appDialog.visible = true;
        search.forceActiveFocus();
    }
    property var allApps: []
    P5Support.DataSource {
        id: appSource
        engine: "executable"
        onNewData: (source, data) => {
            try { deckTasks.allApps = JSON.parse(data.stdout); } catch (e) { deckTasks.allApps = []; }
            disconnectSource(source);
        }
    }
    PlasmaCore.Dialog {
        id: appDialog
        visualParent: addTile
        location: Plasmoid.location
        type: PlasmaCore.Dialog.PopupMenu
        hideOnWindowDeactivate: true
        flags: Qt.WindowStaysOnTopHint
        mainItem: ColumnLayout {
            width: Kirigami.Units.gridUnit * 18
            height: Kirigami.Units.gridUnit * 24
            PlasmaComponents.TextField {
                id: search
                Layout.fillWidth: true
                placeholderText: "Search apps to pin…"
                Keys.onEscapePressed: appDialog.visible = false
                Keys.onDownPressed: appList.forceActiveFocus()
                onAccepted: if (appList.count > 0) deckTasks.togglePin(appList.model[0].url)
            }
            ListView {
                id: appList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                keyNavigationEnabled: true
                model: {
                    const q = search.text.toLowerCase();
                    return deckTasks.allApps.filter(a => !q || a.name.toLowerCase().includes(q) || a.comment.toLowerCase().includes(q));
                }
                delegate: PlasmaComponents.ItemDelegate {
                    required property var modelData
                    width: ListView.view.width
                    readonly property bool isPinned: deckModel.launcherList.length >= 0 && deckTasks.pinned(modelData.url)
                    contentItem: RowLayout {
                        spacing: 8
                        Kirigami.Icon { source: modelData.icon; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            PlasmaComponents.Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                            PlasmaComponents.Label { text: modelData.comment; visible: text !== ""; opacity: 0.6; font.pointSize: 8; Layout.fillWidth: true; elide: Text.ElideRight }
                        }
                        Kirigami.Icon { source: "checkmark"; visible: isPinned; Layout.preferredWidth: 16; Layout.preferredHeight: 16 }
                    }
                    onClicked: deckTasks.togglePin(modelData.url)
                }
                PlasmaComponents.Label {
                    anchors.centerIn: parent
                    visible: appList.count === 0
                    text: deckTasks.allApps.length ? "No apps match" : "Loading apps…"
                    opacity: 0.6
                }
            }
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
