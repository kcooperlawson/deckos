// DecKoOS Taskbar: pinned apps and open windows in the DecKo look (notched tiles, the gradient bar under the
// active app, dots for open windows). Windows, launchers, grouping and ordering
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
import org.kde.plasma.private.volume as PlasmaPa
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: deckTasks

    // Colours from the active colour scheme and accent, so themes and the Hub's accent reach this widget;
    // the surfaces are the scheme's background lifted towards its text, like the DecKoOS slate steps.
    readonly property color text: Kirigami.Theme.textColor
    readonly property color subtext: Kirigami.Theme.disabledTextColor
    // The desktop's accent, or the Vibe's colours, or the person's own (Hub > Appearance > Taskbar)
    readonly property string colorMode: Plasmoid.configuration.colorMode || "accent"
    readonly property color accent: colorMode === "accent" ? Kirigami.Theme.highlightColor : Plasmoid.configuration.colorA
    // The gradient partner: the accent shifted towards violet, like the brand tile (or the Vibe's/custom second colour)
    readonly property color accentB: colorMode === "accent"
        ? Qt.hsva((accent.hsvHue + 32 / 360) % 1, Math.min(1, accent.hsvSaturation + 0.04), accent.hsvValue, 1)
        : Plasmoid.configuration.colorB
    readonly property bool motion: Plasmoid.configuration.motion !== false
    // The DecKo look's app icons: apps DecKoOS knows get a line icon (DecKoOS's own set, by .desktop name or
    // window app id); the rest keep their own icon, in grey until active or pointed at
    readonly property bool lineIcons: Plasmoid.configuration.lineIcons !== false
    readonly property string iconDir: Qt.resolvedUrl("../../../../../deckos/icons/")
    readonly property var lineFor: ({
        "org.deckos.files": "folder", "org.kde.dolphin": "folder", "dolphin": "folder", "org.gnome.nautilus": "folder", "nemo": "folder",
        "thunar": "folder", "pcmanfm-qt": "folder",
        "org.deckos.terminal": "terminal", "org.kde.konsole": "terminal", "konsole": "terminal", "kitty": "terminal",
        "alacritty": "terminal", "org.wezfurlong.wezterm": "terminal", "com.mitchellh.ghostty": "terminal",
        "foot": "terminal",
        "deckos-hub": "system", "deckos-store": "store", "deckos-builder": "code", "deckos-bench": "gauge",
        "deckos-music": "music", "deckos-assistant": "ai",
        "firefox": "globe", "org.mozilla.firefox": "globe", "librewolf": "globe", "zen": "globe", "chromium": "globe",
        "google-chrome": "globe", "brave-browser": "globe", "vivaldi-stable": "globe", "microsoft-edge": "globe",
        "steam": "gaming", "com.valvesoftware.steam": "gaming", "net.lutris.lutris": "gaming",
        "com.heroicgameslauncher.hgl": "gaming", "heroic": "gaming",
        "discord": "chat", "com.discordapp.discord": "chat", "vesktop": "chat", "dev.vencord.vesktop": "chat",
        "org.telegram.desktop": "chat", "signal-desktop": "chat", "org.signal.signal": "chat",
        "com.anthropic.claude": "ai", "claude": "ai",
        "com.spotify.client": "headphones", "spotify": "headphones",
        "code": "code", "code-oss": "code", "codium": "code", "visual-studio-code": "code", "dev.zed.zed": "code",
        "org.kde.kate": "doc", "org.kde.kwrite": "doc", "org.kde.gwenview": "image", "org.kde.spectacle": "snapshot",
        "systemsettings": "sliders", "org.kde.systemsettings": "sliders", "vlc": "play", "mpv": "play",
        "org.kde.haruna": "play"
    })
    function lineIcon(url, appId) {
        if (!lineIcons)
            return "";
        for (const k of [appKey(url), appKey(appId)])
            if (k && lineFor[k])
                return lineFor[k];
        return "";
    }
    Vibes.Look { id: deckLook; colorA: deckTasks.accent; colorB: deckTasks.accentB }
    readonly property var look: deckLook

    // Apps playing sound right now (Plasma's audio streams, as the stock task manager reads them; events, not
    // polling). A tile pulses while its app plays: matched by process, or by name, since browsers and Spotify
    // play from a helper process rather than the window's own.
    PlasmaPa.PulseObjectFilterModel {
        id: audioStreams
        filters: [{ role: "VirtualStream", value: false }]
        sourceModel: PlasmaPa.SinkInputModel {}
    }
    property int audioEpoch: 0  // bumped when streams change, so the tiles look again
    Instantiator {
        id: playing
        model: audioStreams
        delegate: QtObject {
            required property var model
            readonly property int pid: Number(model.Client?.properties["application.process.id"] ?? 0)
            readonly property string name: String(model.Client?.properties["application.name"] ?? "")
            readonly property string binary: String(model.Client?.properties["application.process.binary"] ?? "")
            readonly property bool corked: model.Corked === true
            onCorkedChanged: deckTasks.audioEpoch++
        }
        onObjectAdded: deckTasks.audioEpoch++
        onObjectRemoved: deckTasks.audioEpoch++
    }
    // The system reacting to music (deckos vibe react on): the apps island pulses on the beat, only while something
    // plays sound (nothing listens otherwise)
    readonly property bool soundPlaying: {
        deckTasks.audioEpoch;
        for (let i = 0; i < playing.count; i++)
            if (playing.objectAt(i) && !playing.objectAt(i).corked)
                return true;
        return false;
    }
    Vibes.Levels { id: beat; active: Plasmoid.configuration.react && deckTasks.soundPlaying }

    function plain(s) {
        return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    }
    function isPlaying(pid, appName, appId) {
        const name = plain(appName), id = plain(String(appId || "").replace(/\.desktop$/, "").split(".").pop());
        for (let i = 0; i < playing.count; i++) {
            const s = playing.objectAt(i);
            if (!s || s.corked)
                continue;
            if (pid > 0 && s.pid === pid)
                return true;
            const sn = plain(s.name), sb = plain(s.binary);
            if (sn && (sn === name || sn === id) || sb && (sb === id || sb === name))
                return true;
        }
        return false;
    }
    readonly property color raised: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.08))
    readonly property color border: Qt.tint(Kirigami.Theme.backgroundColor, Qt.rgba(text.r, text.g, text.b, 0.13))
    readonly property color attention: "#F5A524"

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool labels: Plasmoid.configuration.showLabels && !vertical
    // A square tile per app, as tall as the panel is thick
    readonly property real tile: Math.max(24, (vertical ? width : height) - 12)  // inside the island
    // With titles, apps share the panel: up to 220 px each, never narrower than an icon and a few letters
    readonly property real labelWidth: Math.max(tile * 3, Math.min(220, (width - 4 * repeater.count) / Math.max(1, repeater.count)))

    preferredRepresentation: fullRepresentation
    Component.onCompleted: Plasmoid.constraintHints = Plasmoid.CanFillArea
    Layout.fillWidth: !vertical && labels
    Layout.fillHeight: vertical
    // The strip of apps, then the + tile
    Layout.preferredWidth: vertical ? -1 : strip.implicitWidth + Math.round(tile * 0.7) + 16
    Layout.preferredHeight: vertical ? strip.implicitHeight + Math.round(tile * 0.7) + 16 : -1
    Layout.minimumWidth: vertical ? -1 : Math.min(strip.implicitWidth, tile * 3) + Math.round(tile * 0.7)

    // `deckos accent` bumps iconEpoch after it recolours the icons: the tiles keep the icons they were
    // made with, so they're made again (no restart of Plasma needed)
    readonly property int iconEpoch: Plasmoid.configuration.iconEpoch
    readonly property bool lockedPins: Plasmoid.configuration.lockedPins  // Kid mode: a child can't add apps
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
        if (lockedPins)
            return;
        if (pinned(url))
            deckModel.requestRemoveLauncher(url);
        else
            deckModel.requestAddLauncher(url);
    }

    // Empty taskbar space: right-click to pin an app, or drop one here from the menu or a folder
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: if (!deckTasks.lockedPins) barMenu.openRelative()
    }
    // Any type filter here let the panel take the drop instead (it then failed to add an icon widget)
    DropArea {
        anchors.fill: parent
        onEntered: drag => drag.accepted = drag.hasUrls
        onDropped: drop => {
            // Locked (Kid mode): still taken here, so the panel doesn't add the app as a widget instead
            for (const u of (deckTasks.lockedPins ? [] : drop.urls)) {
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
        if (lockedPins)
            return;
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

    Vibes.Notch {  // the apps island
        x: 0
        y: deckTasks.vertical ? 0 : 3
        width: parent.width
        height: deckTasks.vertical ? parent.height : parent.height - 6
        look: deckTasks.look
        cut: 12
        fill: deckTasks.look.glass
        pulse: beat.pulse
    }
    Grid {
        id: strip
        anchors.left: deckTasks.vertical ? undefined : parent.left
        anchors.leftMargin: 8
        anchors.top: deckTasks.vertical ? parent.top : undefined
        anchors.topMargin: 8
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
        Item {
            anchors.centerIn: parent
            width: Math.round(deckTasks.tile * 0.5)
            height: width
            Vibes.Notch {
                anchors.fill: parent
                visible: addArea.containsMouse
                look: deckTasks.look
                cut: 6
                lit: false
                fill: deckTasks.raised
            }
            Text {
                anchors.centerIn: parent
                text: "+"
                color: addArea.containsMouse ? deckTasks.text : deckTasks.subtext
                opacity: addArea.containsMouse ? 1 : 0.6
                font.family: deckTasks.look.hud
                font.weight: Font.Medium
                font.pixelSize: Math.round(deckTasks.tile * 0.4)
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
