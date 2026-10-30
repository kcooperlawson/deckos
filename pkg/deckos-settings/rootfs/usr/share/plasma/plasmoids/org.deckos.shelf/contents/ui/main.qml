// DecKoOS Shelf: the Desktop folder as live tiles on one notched plate, in place of Plasma's icon grid (which
// `deckos desktop shelf` hides; `deckos desktop icons` brings it back). /usr/lib/deckos/shelf/shelf.py says what each
// thing is, and adds downloads still arriving in Downloads on top. Newest first. Drop things on it to keep them on
// the Desktop (move, copy or link, like the desktop itself asks). Plasma's own job list (with a download's percent)
// isn't open to desktop widgets, so a download shows its size so far and a sweeping meter.
import QtQuick
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: shelf

    Vibes.Look {
        id: vibe
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    readonly property string helper: "/usr/lib/deckos/shelf/shelf.py"
    property var items: []
    property var seen: ({})  // paths whose tile has been dealt in already
    property string folder: ""     // the Desktop, as a path (from shelf.py)
    property string folderUrl: ""
    readonly property real pad: 18
    readonly property real gap: 10
    readonly property real half: (width - 2 * pad - gap) / 2
    // Newest first, but a half-width tile left alone before a wide one takes the next half-width one beside it
    readonly property var packed: {
        const wide = i => i.kind === "game" || i.kind === "partial";
        const rest = items.slice(), out = [];
        let open = false;  // a half-width tile waiting for its pair
        while (rest.length) {
            let next = rest.shift();
            if (open && wide(next)) {
                const k = rest.findIndex(i => !wide(i));
                if (k >= 0) {
                    rest.unshift(next);
                    next = rest.splice(k + 1, 1)[0];
                }
            }
            out.push(next);
            open = !wide(next) && !open;
        }
        return out;
    }
    readonly property bool arriving: items.some(i => i.kind === "partial")

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 300
    Layout.preferredWidth: 420
    Layout.preferredHeight: 640
    Component.onCompleted: {
        Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground;
        refresh();
    }

    // ------------------------------------------------------------------ what's there

    P5Support.DataSource {
        id: run
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source.indexOf(shelf.helper) === -1) {  // a move, copy or trash finished: look again
                shelf.refresh();
                return;
            }
            try {
                const out = JSON.parse(data.stdout);
                shelf.items = out.items;
                shelf.folder = out.folder;
                shelf.folderUrl = out.url;
            } catch (e) {
                console.warn("DecKoOS Shelf:", e, data.stderr);
            }
        }
    }
    function refresh() {
        run.connectSource("python3 " + helper + " # " + Date.now());  // the comment makes each run a new source
    }
    function sh(s) {  // one shell word
        return "'" + String(s).replace(/'/g, "'\\''") + "'";
    }
    function exec(cmd) {
        run.connectSource(cmd + " # " + Date.now());
    }

    FolderListModel {  // only to notice the Desktop changing
        folder: shelf.folderUrl
        showHidden: false
        showDirsFirst: false
        onCountChanged: refreshSoon.restart()
    }
    Timer { id: refreshSoon; interval: 300; onTriggered: shelf.refresh() }
    Timer {  // times ("2 h ago") and files still arriving move on by themselves
        interval: shelf.arriving ? 2000 : 60000
        repeat: true
        running: true
        onTriggered: shelf.refresh()
    }

    // ------------------------------------------------------------------ doing things

    function open(item) {
        Qt.openUrlExternally(item.kind === "game" ? item.launch : item.url);
    }
    function trash(item) {
        exec("kioclient move " + sh(item.url) + " trash:/");
    }
    property var menuItem: null
    function menu(item, from, x, y) {
        menuItem = item;
        const p = from.mapToItem(shelf, x, y);
        contextMenu.popup(shelf, p.x, p.y);
    }
    PlasmaComponents.Menu {
        id: contextMenu
        PlasmaComponents.MenuItem {
            text: shelf.menuItem && shelf.menuItem.kind === "game" ? "Play" : "Open"
            icon.name: "document-open"
            onTriggered: shelf.open(shelf.menuItem)
        }
        PlasmaComponents.MenuItem {
            text: "Open the Desktop folder"
            icon.name: "folder-open"
            onTriggered: Qt.openUrlExternally(shelf.folderUrl)
        }
        PlasmaComponents.MenuSeparator {}
        PlasmaComponents.MenuItem {
            text: "Move to Trash"
            icon.name: "user-trash"
            onTriggered: shelf.trash(shelf.menuItem)
        }
    }

    property var dropped: []
    PlasmaComponents.Menu {
        id: dropMenu
        PlasmaComponents.MenuItem {
            text: "Move here"
            icon.name: "go-jump"
            onTriggered: shelf.exec("kioclient move " + shelf.dropped.map(shelf.sh).join(" ") + " " + shelf.sh(shelf.folderUrl))
        }
        PlasmaComponents.MenuItem {
            text: "Copy here"
            icon.name: "edit-copy"
            onTriggered: shelf.exec("kioclient copy " + shelf.dropped.map(shelf.sh).join(" ") + " " + shelf.sh(shelf.folderUrl))
        }
        PlasmaComponents.MenuItem {
            text: "Link here"
            icon.name: "edit-link"
            enabled: shelf.dropped.every(u => String(u).startsWith("file://"))
            onTriggered: shelf.exec("ln -s " + shelf.dropped.map(u => shelf.sh(decodeURIComponent(String(u).slice(7)))).join(" ")
                                    + " " + shelf.sh(shelf.folder) + "/")
        }
    }

    // ------------------------------------------------------------------ the plate

    // The plate is as tall as what's on it (a few things don't get a tall empty card); past the widget's height, it
    // scrolls
    readonly property real plateHeight: Math.min(height, Math.max(200, scroller.y + tiles.height + pad))
    Vibes.Notch {
        width: parent.width
        height: shelf.plateHeight
        look: vibe
        cut: 18
        lit: true
    }

    Text {
        id: title
        x: shelf.pad
        y: 16
        text: "DESKTOP"
        color: vibe.text
        font.family: vibe.hud
        font.pixelSize: 12
        font.weight: Font.Bold
        font.letterSpacing: 2.4
    }
    Text {
        anchors.right: parent.right
        anchors.rightMargin: shelf.pad + 14
        anchors.verticalCenter: title.verticalCenter
        readonly property int n: shelf.items.filter(i => !i.arriving).length  // what's on the Desktop itself
        text: n + (n === 1 ? " ITEM" : " ITEMS")
        color: vibe.subtext
        font.family: vibe.hud
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.letterSpacing: 1.6
    }
    // Download a link: the one on the clipboard, through `deckos download` (resumes and retries until it's done, and
    // shows here while it arrives). A hidden TextEdit is how QML reads the clipboard.
    TextEdit { id: clip; visible: false }
    Text {
        id: linkButton
        anchors.right: parent.right
        anchors.rightMargin: shelf.pad + 110
        anchors.verticalCenter: title.verticalCenter
        text: "+ DOWNLOAD A LINK"
        color: linkMouse.containsMouse ? vibe.text : vibe.colorA
        font.family: vibe.hud
        font.pixelSize: 11
        font.weight: Font.Bold
        font.letterSpacing: 1.2
        MouseArea {
            id: linkMouse
            anchors.fill: parent
            anchors.margins: -6
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                clip.text = "";
                clip.paste();
                const url = clip.text.trim();
                if (/^(https?|ftp):\/\/\S+$/.test(url))
                    shelf.exec("deckos download " + shelf.sh(url));
                else
                    linkButton.text = "COPY A LINK FIRST";
            }
            onExited: linkButton.text = "+ DOWNLOAD A LINK"
        }
    }
    Text {
        id: where
        x: shelf.pad
        anchors.top: title.bottom
        anchors.topMargin: 3
        width: parent.width - 2 * shelf.pad
        text: (shelf.folder.replace(/^\/home\/[^\/]+/, "~") || "~/Desktop") + " · drop things here to keep them close"
        elide: Text.ElideRight
        color: vibe.subtext
        font.family: vibe.family
        font.pixelSize: 12
    }

    Flickable {
        id: scroller
        y: where.y + where.height + 14
        height: shelf.plateHeight - y - shelf.pad
        x: shelf.pad
        width: parent.width - 2 * shelf.pad
        contentHeight: tiles.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Flow {
            id: tiles
            width: scroller.width
            spacing: shelf.gap

            Repeater {
                model: shelf.packed
                Tile {
                    id: tileItem
                    required property var modelData
                    required property int index
                    item: modelData
                    look: vibe
                    owner: shelf
                    readonly property bool wide: modelData.kind === "game" || modelData.kind === "partial"
                    width: wide || shelf.half < 150 ? tiles.width : shelf.half
                    height: modelData.kind === "game" ? 176 : modelData.kind === "partial" ? 80 : 108
                    // Dealt in, one after another, the first time each thing shows (not on every refresh)
                    Vibes.Unfold { id: deal; target: tileItem; origin: Item.Top; delay: Math.min(8, tileItem.index) * 40 }
                    Component.onCompleted: if (!shelf.seen[modelData.path]) {
                        shelf.seen[modelData.path] = true;
                        deal.play();
                    }
                }
            }

            Item {  // an empty Desktop: what this is for
                visible: shelf.items.length === 0
                width: tiles.width
                height: 120
                Column {
                    anchors.centerIn: parent
                    width: parent.width - 40
                    spacing: 6
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: "NOTHING HERE YET"
                        color: vibe.text
                        font.family: vibe.hud
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        font.letterSpacing: 2
                    }
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: "Drop files, folders or a game's shortcut here. They're kept in your Desktop folder."
                        color: vibe.subtext
                        font.family: vibe.family
                        font.pixelSize: 12
                    }
                }
            }
        }
    }

    DropArea {
        width: parent.width
        height: shelf.plateHeight
        keys: ["text/uri-list"]
        onEntered: drag => drag.accept(Qt.LinkAction)
        onDropped: drop => {
            const urls = drop.urls.filter(u => !String(u).startsWith(shelf.folderUrl + "/"));
            if (!urls.length)
                return;
            shelf.dropped = urls;
            dropMenu.popup(shelf, drop.x, drop.y);
        }
        Vibes.Notch {  // shown while something's held over the shelf
            anchors.fill: parent
            visible: parent.containsDrag
            look: vibe
            cut: 18
            lit: true
            edge: 2
            fill: Qt.rgba(vibe.colorA.r, vibe.colorA.g, vibe.colorA.b, 0.12)
        }
    }
}
