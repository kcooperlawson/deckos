// DecKoOS Menu: DecKoOS's app launcher, in the DecKo look (notched tiles and buttons, Chakra Petch labels, the
// accent gradient, DecKoOS line icons). Apps, favourites, recent items and power actions come from Plasma's
// own kicker backend and search from KRunner, exactly as Kickoff gets them; the DecKoOS Store is
// asked (lazily, off the first frame) for apps a search matches that aren't installed.
// Plain QtQuick, no Controls: fewer objects to build, so the popup is ready the moment it opens.
// The other files reach the models and palette through the `deckMenu` id, like Kickoff's `kickoff`.
import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.private.kicker as Kicker
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: deckMenu

    // Colours from the active colour scheme and accent, so themes and the Hub's accent reach this widget;
    // the surfaces are the scheme's background lifted towards its text, like the DecKoOS slate steps.
    readonly property color text: Kirigami.Theme.textColor
    readonly property color subtext: Kirigami.Theme.disabledTextColor
    readonly property color accent: Kirigami.Theme.highlightColor
    // The gradient partner: the accent shifted towards violet, like the brand tile
    readonly property color accentB: Qt.hsva((accent.hsvHue + 32 / 360) % 1, Math.min(1, accent.hsvSaturation + 0.04),
                                             accent.hsvValue, 1)
    readonly property color base: Kirigami.Theme.backgroundColor
    readonly property color surface: Qt.tint(base, Qt.rgba(text.r, text.g, text.b, 0.035))
    readonly property color raised: Qt.tint(base, Qt.rgba(text.r, text.g, text.b, 0.07))
    readonly property color border: Qt.tint(base, Qt.rgba(text.r, text.g, text.b, 0.12))
    readonly property color hot: Qt.rgba(accent.r, accent.g, accent.b, 0.16)
    readonly property color hotBorder: Qt.rgba(accent.r, accent.g, accent.b, 0.45)
    readonly property string hud: "Chakra Petch"  // labels, numbers, buttons
    readonly property color ink: "#0B0D16"        // text and icons on the gradient
    Vibes.Look { id: menuLook; colorA: deckMenu.accent; colorB: deckMenu.accentB }
    readonly property var look: menuLook
    // DecKoOS line icons (/usr/share/deckos/icons), relative to contents/ui so the Windows preview
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

    // ---- DecKoOS Store suggestions: looked up 350 ms after typing stops, never on the first frame

    property var storeResults: []
    property var actionResults: []  // DecKoOS actions (usr/share/deckos/actions.toml) the search matches

    Timer {
        id: storeTimer
        interval: 350
        onTriggered: {
            const q = deckMenu.query.trim();
            deckMenu.exec("python3 /usr/lib/deckos/actions/actions.py find --limit 3 -- " + deckMenu.quote(q), (code, out) => {
                if (q !== deckMenu.query.trim()) {
                    return;
                }
                try {
                    deckMenu.actionResults = code === 0 ? JSON.parse(out) : [];
                } catch (e) {
                    deckMenu.actionResults = [];
                }
            });
            if (!Plasmoid.configuration.storeResults || q.length < 3) {
                return;
            }
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
        actionResults = [];
        if (query.trim().length >= 2) {
            storeTimer.restart();
        } else {
            storeTimer.stop();
        }
    }

    function runAction(id) {
        launch("python3 /usr/lib/deckos/actions/actions.py run " + quote(id));
    }

    function openInStore(appKey) {
        launch("deckos-store --app " + quote(appKey));
    }

    function searchStore(term) {
        launch("deckos-store --search " + quote(term));
    }

    // DecKoOS Assistant's chat box, asked the search as a question ("install obs", "why is my wifi slow")
    function askAssistant(text) {
        launch("deckos-assistant --ask " + quote(text));
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
        Accessible.name: "DecKoOS Menu"
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
