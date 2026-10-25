// One app on the taskbar: a pinned launcher, a window, or a group of one app's windows.
// Click opens, focuses or minimizes; with several windows it cycles through them. Middle-click
// opens a new window, drag reorders, right-click lists the windows and pin/close actions.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.taskmanager as TaskManager

Item {
    id: task

    readonly property var tasksModel: deckModel
    readonly property bool launcherOnly: model.IsLauncher === true && !model.IsStartup
    readonly property bool active: model.IsActive === true
    readonly property int windows: model.IsGroupParent ? model.ChildCount : (launcherOnly ? 0 : 1)
    // Some apps (Electron ones like Claude) report no launcher: their app id names the .desktop file instead
    readonly property string url: model.LauncherUrlWithoutIcon ? String(model.LauncherUrlWithoutIcon)
        : model.AppId ? "applications:" + model.AppId + (String(model.AppId).endsWith(".desktop") ? "" : ".desktop") : ""
    readonly property int childCount: model.IsGroupParent ? model.ChildCount : 0
    readonly property int row: index
    readonly property bool dragging: mouse.drag.active || mouse.reordering

    width: deckTasks.labels ? deckTasks.labelWidth : deckTasks.tile
    height: deckTasks.vertical ? deckTasks.width : deckTasks.tile
    opacity: model.IsMinimized ? 0.7 : 1
    z: mouse.reordering ? 1 : 0

    function modelIndex() {
        return tasksModel.makeModelIndex(row);
    }
    // Where this tile is, so KWin's minimize animation flies to it
    function publish() {
        if (!launcherOnly)
            tasksModel.requestPublishDelegateGeometry(modelIndex(),
                Qt.rect(mapToGlobal(0, 0).x, mapToGlobal(0, 0).y, width, height), task);
    }
    onXChanged: publish()
    onYChanged: publish()
    onLauncherOnlyChanged: publish()

    function click() {
        if (launcherOnly || !model.IsGroupParent) {
            if (active && !launcherOnly)
                tasksModel.requestToggleMinimized(modelIndex());
            else
                tasksModel.requestActivate(modelIndex());
            return;
        }
        if (!active) {
            // Activating a group itself does nothing: bring up the window used last
            let last = 0, when = -1;
            for (let i = 0; i < childCount; ++i) {
                const t = tasksModel.data(tasksModel.makeModelIndex(row, i), TaskManager.AbstractTasksModel.LastActivated);
                const ms = t ? new Date(t).getTime() : 0;
                if (ms > when) { when = ms; last = i; }
            }
            tasksModel.requestActivate(tasksModel.makeModelIndex(row, last));
            return;
        }
        // Several windows and one of them in front: bring up the next one
        let current = -1;
        for (let i = 0; i < childCount; ++i) {
            if (tasksModel.data(tasksModel.makeModelIndex(row, i), TaskManager.AbstractTasksModel.IsActive))
                current = i;
        }
        tasksModel.requestActivate(tasksModel.makeModelIndex(row, (current + 1) % childCount));
    }

    // ---- the look

    Rectangle {
        id: plate
        anchors.fill: parent
        anchors.margins: 3
        radius: 10
        color: task.active ? Qt.rgba(0.30, 0.55, 1, 0.16)
            : mouse.containsMouse || task.dragging ? deckTasks.raised : "transparent"
        border.width: task.active || mouse.containsMouse ? 1 : 0
        border.color: task.active ? Qt.rgba(0.30, 0.55, 1, 0.45) : deckTasks.border
        Behavior on color { ColorAnimation { duration: 120 } }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: deckTasks.labels ? 8 : 0
            anchors.rightMargin: deckTasks.labels ? 8 : 0
            spacing: 8

            Kirigami.Icon {
                id: icon
                Layout.alignment: Qt.AlignCenter
                Layout.preferredWidth: Math.round(deckTasks.tile * 0.56)
                Layout.preferredHeight: Layout.preferredWidth
                source: model.decoration
                active: mouse.containsMouse
                scale: mouse.pressed ? 0.9 : 1
                Behavior on scale { NumberAnimation { duration: 90 } }
                // An app that's starting bounces gently until its window shows
                transform: Translate { id: bounce }
                SequentialAnimation {
                    running: model.IsStartup === true
                    loops: Animation.Infinite
                    alwaysRunToEnd: true
                    NumberAnimation { target: bounce; property: "y"; to: -4; duration: 260; easing.type: Easing.OutQuad }
                    NumberAnimation { target: bounce; property: "y"; to: 0; duration: 260; easing.type: Easing.InQuad }
                }
            }
            Text {
                visible: deckTasks.labels
                Layout.fillWidth: true
                text: model.display || model.AppName || ""
                color: task.active ? deckTasks.text : deckTasks.subtext
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 13
            }
        }
    }

    // The active app gets the accent gradient pill; other open apps a dot per window (up to 3)
    Rectangle {
        visible: !task.launcherOnly
        anchors.horizontalCenter: deckTasks.vertical ? undefined : parent.horizontalCenter
        anchors.verticalCenter: deckTasks.vertical ? parent.verticalCenter : undefined
        anchors.bottom: deckTasks.vertical ? undefined : parent.bottom
        anchors.left: deckTasks.vertical ? parent.left : undefined
        anchors.bottomMargin: 1
        anchors.leftMargin: 1
        width: deckTasks.vertical ? 3 : (task.active ? 18 : 4)
        height: deckTasks.vertical ? (task.active ? 18 : 4) : 3
        radius: 1.5
        Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        gradient: Gradient {
            orientation: deckTasks.vertical ? Gradient.Vertical : Gradient.Horizontal
            GradientStop { position: 0; color: model.IsDemandingAttention ? deckTasks.attention
                : task.active ? deckTasks.accent : deckTasks.subtext }
            GradientStop { position: 1; color: model.IsDemandingAttention ? deckTasks.attention
                : task.active ? deckTasks.accentB : deckTasks.subtext }
        }
        SequentialAnimation on opacity {
            running: model.IsDemandingAttention === true
            loops: Animation.Infinite
            alwaysRunToEnd: true
            NumberAnimation { to: 0.3; duration: 500 }
            NumberAnimation { to: 1; duration: 500 }
        }
    }
    Text {
        visible: task.windows > 1 && !deckTasks.labels
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 4
        text: task.windows
        color: deckTasks.subtext
        font.family: "Inter"
        font.pixelSize: 9
        font.bold: true
    }

    PlasmaCore.ToolTipArea {
        anchors.fill: parent
        active: !task.dragging && !menu.opened
        mainText: model.AppName || model.display || ""
        subText: task.launcherOnly ? (model.GenericName || "") : task.windows > 1
            ? task.windows + " windows" : (model.display !== model.AppName ? model.display || "" : "")
        icon: model.decoration
        location: Plasmoid.location
    }

    // ---- input

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        property point pressAt
        property bool reordering: false
        onReorderingChanged: deckTasks.dragActive = reordering

        onPressed: e => pressAt = Qt.point(e.x, e.y)
        onPositionChanged: e => {
            if (!(e.buttons & Qt.LeftButton))
                return;
            if (!reordering && Math.hypot(e.x - pressAt.x, e.y - pressAt.y) > 8)
                reordering = true;
            if (!reordering)
                return;
            const p = mapToItem(strip, e.x, e.y);
            const over = strip.childAt(p.x, p.y);
            if (over && over !== task && over.row !== undefined)
                tasksModel.move(row, over.row);
        }
        onReleased: e => {
            if (reordering) {
                reordering = false;
                tasksModel.syncLaunchers();
                return;
            }
            if (!containsMouse)
                return;
            if (e.button === Qt.LeftButton)
                task.click();
            else if (e.button === Qt.MiddleButton && model.CanLaunchNewInstance !== false)
                tasksModel.requestNewInstance(task.modelIndex());
            else if (e.button === Qt.RightButton)
                menu.openRelative();
        }
    }

    PlasmaExtras.Menu {
        id: menu
        visualParent: task
        placement: deckTasks.vertical ? PlasmaExtras.Menu.RightPosedTopAlignedPopup
            : PlasmaExtras.Menu.TopPosedLeftAlignedPopup
        property bool opened: status === PlasmaExtras.Menu.Open

        PlasmaExtras.MenuItem {
            text: "New window"
            icon: "window-new"
            visible: !task.launcherOnly && model.CanLaunchNewInstance !== false
            onClicked: tasksModel.requestNewInstance(task.modelIndex())
        }
        PlasmaExtras.MenuItem {
            text: deckTasks.pinned(task.url) ? "Unpin from taskbar" : "Pin to taskbar"
            icon: deckTasks.pinned(task.url) ? "window-unpin" : "window-pin"
            visible: task.url !== ""
            onClicked: deckTasks.togglePin(task.url)
        }
        PlasmaExtras.MenuItem {
            text: "Pin another app…"
            icon: "list-add"
            onClicked: deckTasks.pickApp()
        }
        PlasmaExtras.MenuItem { separator: true; visible: !task.launcherOnly }
        PlasmaExtras.MenuItem {
            text: task.windows > 1 ? "Close all " + task.windows + " windows" : "Close window"
            icon: "window-close"
            visible: !task.launcherOnly && model.IsClosable !== false
            onClicked: tasksModel.requestClose(task.modelIndex())
        }
    }

    // The group's windows by title, at the top of the menu, to jump straight to one
    Instantiator {
        // task.childCount, not model.ChildCount: in here "model" is the Instantiator's own
        model: task.childCount > 1 ? task.childCount : 0
        delegate: PlasmaExtras.MenuItem {
            required property int index
            text: task.tasksModel.data(task.tasksModel.makeModelIndex(task.row, index), Qt.DisplayRole) || ""
            onClicked: task.tasksModel.requestActivate(task.tasksModel.makeModelIndex(task.row, index))
        }
        onObjectAdded: (i, item) => menu.addMenuItem(item, menu.content[0] ?? null)
        onObjectRemoved: (i, item) => menu.removeMenuItem(item)
    }
}
