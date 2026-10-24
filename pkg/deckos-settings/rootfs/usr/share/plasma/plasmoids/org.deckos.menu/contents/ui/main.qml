// DeckOS Menu: DeckOS's app launcher, in the DeckOS look (slate surfaces, 1px borders, accent
// gradient, DeckOS line icons). Apps, favourites, recent items and power actions come from Plasma's
// own kicker backend and search from KRunner, exactly as Kickoff gets them; the DeckOS Store is
// asked (lazily, off the first frame) for apps a search matches that aren't installed.
// Plain QtQuick, no Controls: fewer objects to build, so the popup is ready the moment it opens.
// The other files reach the models and palette through the `deckMenu` id, like Kickoff's `kickoff`.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.private.kicker as Kicker
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: deckMenu

    readonly property color base: "#0F1115"
    readonly property color surface: "#171A21"
    readonly property color raised: "#1E222B"
    readonly property color border: "#262B36"
    readonly property color text: "#E8EAF0"
    readonly property color subtext: "#8C94A6"
    readonly property color accent: "#4C8DFF"
    readonly property color accentB: "#7A5CFF"
    readonly property color hot: Qt.rgba(0.30, 0.55, 1, 0.16)
    readonly property color hotBorder: Qt.rgba(0.30, 0.55, 1, 0.45)
    // DeckOS line icons (/usr/share/deckos/icons), relative to contents/ui so the Windows preview
    // finds them in the repo the same way.
    readonly property string iconDir: Qt.resolvedUrl("../../../../../deckos/icons/")

    property string query: ""
    property bool gamingAvailable: false

    // ---- Plasma's data, created with the applet so the first open has nothing left to load

    readonly property Kicker.RootModel rootModel: Kicker.RootModel {
        autoPopulate: false  // refreshed once the popup is built (preloaded at login)
        appletInterface: deckMenu
        appNameFormat: 0  // name only; the generic name goes in the description line
        flat: true
        sorted: true
        showSeparators: false
        showTopLevelItems: true
        showAllApps: true
        showAllAppsCategorized: false
        showRecentApps: false
        showRecentDocs: false
        showPowerSession: false
        showFavoritesPlaceholder: false
        showRootSeparator: false
        highlightNewlyInstalledApps: true

        Component.onCompleted: {
            favoritesModel.initForClient("org.deckos.menu.favorites.instance-" + Plasmoid.id);
            if (!Plasmoid.configuration.favoritesPortedToKAstats) {
                if (favoritesModel.count < 1) {
                    favoritesModel.portOldFavorites(Plasmoid.configuration.favorites);
                }
                Plasmoid.configuration.favoritesPortedToKAstats = true;
            }
        }
    }

    readonly property Kicker.RunnerModel runnerModel: Kicker.RunnerModel {
        query: deckMenu.query
        appletInterface: deckMenu
        mergeResults: true
        favoritesModel: deckMenu.rootModel.favoritesModel
    }

    readonly property Kicker.RecentUsageModel recentApps: Kicker.RecentUsageModel {
        shownItems: Kicker.RecentUsageModel.OnlyApps  // a C++ enum: Qt 6 QML needs the name, not 1
        favoritesModel: deckMenu.rootModel.favoritesModel
    }

    readonly property Kicker.RecentUsageModel recentDocs: Kicker.RecentUsageModel {
        shownItems: Kicker.RecentUsageModel.OnlyDocs
        favoritesModel: deckMenu.rootModel.favoritesModel
    }

    // ---- shared by the delegates

    property Item actionMenu: null  // MenuPopup's right-click menu

    function activate(model, row) {
        if (model && model.trigger(row, "", null)) {
            expanded = false;
        }
    }

    // roles: the delegate's model roles (favoriteId, actionList…); pinned: it's in the pinned grid
    function showActions(model, row, roles, item, pinned) {
        if (actionMenu) {
            actionMenu.show(model, row, roles, item, pinned);
        }
    }

    // ---- running commands (Store lookups, Gaming Mode, the Store window)

    P5Support.DataSource {
        id: shell
        engine: "executable"
        connectedSources: []
        property var callbacks: ({})
        onNewData: (source, data) => {
            disconnectSource(source);
            const done = callbacks[source];
            delete callbacks[source];
            if (done) {
                done(data["exit code"], data.stdout || "");
            }
        }
    }

    function quote(s) {
        return "'" + String(s).replace(/'/g, "'\\''") + "'";
    }

    function exec(cmd, done) {
        if (done) {
            shell.callbacks[cmd] = done;
        }
        shell.connectSource(cmd);
    }

    // Detached, so the data source isn't held open while the app runs.
    function launch(cmd) {
        exec("setsid -f " + cmd + " >/dev/null 2>&1");
        expanded = false;
    }

    // ---- DeckOS Store suggestions: looked up 350 ms after typing stops, never on the first frame

    property var storeResults: []

    Timer {
        id: storeTimer
        interval: 350
        onTriggered: {
            const q = deckMenu.query.trim();
            deckMenu.exec("python3 /usr/lib/deckos/store/store_find.py --limit 4 -- " + deckMenu.quote(q), (code, out) => {
                if (q !== deckMenu.query.trim()) {
                    return;  // typed on since
                }
                try {
                    deckMenu.storeResults = code === 0 ? JSON.parse(out) : [];
                } catch (e) {
                    deckMenu.storeResults = [];
                }
            });
        }
    }

    onQueryChanged: {
        storeResults = [];
        if (Plasmoid.configuration.storeResults && query.trim().length >= 3) {
            storeTimer.restart();
        } else {
            storeTimer.stop();
        }
    }

    function openInStore(appKey) {
        launch("deckos-store --app " + quote(appKey));
    }

    function searchStore(term) {
        launch("deckos-store --search " + quote(term));
    }

    function startGamingMode() {
        launch("deckos session gaming --ask");
    }

    // ---- the applet

    activationTogglesExpanded: true  // Meta (Plasma's launcher shortcut) opens and closes it
    hideOnWindowDeactivate: true
    preferredRepresentation: compactRepresentation
    fullRepresentation: MenuPopup {
        focus: true
    }

    compactRepresentation: MouseArea {
        id: button
        property bool wasExpanded: false
        Layout.minimumWidth: height
        Layout.preferredWidth: height
        hoverEnabled: true
        Accessible.name: "DeckOS Menu"
        Accessible.role: Accessible.Button
        onPressed: wasExpanded = deckMenu.expanded
        onClicked: deckMenu.expanded = !wasExpanded

        Kirigami.Icon {
            anchors.fill: parent
            source: Plasmoid.configuration.icon
            active: button.containsMouse
        }
    }
}
