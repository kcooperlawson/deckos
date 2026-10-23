// Right-click menu for an app or file, drawn inside the popup in the DeckOS look: pin/unpin and
// move for pinned apps, then whatever the kicker model offers (jump-list actions, add to panel or
// desktop, edit, open folder…). Clicking outside, Escape or picking an entry closes it.
import QtQuick
import org.kde.kirigami as Kirigami

MouseArea {
    id: menu

    property var model: null
    property int row: -1
    property var entries: []
    property int cursor: 0

    visible: false
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: close()

    function show(model, row, roles, item, pinned) {
        const favorites = deckMenu.rootModel.favoritesModel;
        const id = roles.favoriteId || "";
        const list = [];
        if (pinned) {
            list.push({ text: "Unpin from menu", line: "close", actionId: "_deckos_unpin", favoriteId: id });
            if (row > 0) {
                list.push({ text: "Move left", line: "chevron-left", actionId: "_deckos_move", to: row - 1 });
            }
            if (row < favorites.count - 1) {
                list.push({ text: "Move right", line: "chevron", actionId: "_deckos_move", to: row + 1 });
            }
        } else if (id !== "" && favorites.enabled !== false) {
            const isPinned = favorites.isFavorite(id);
            list.push({ text: isPinned ? "Unpin from menu" : "Pin to menu", line: isPinned ? "close" : "star",
                        actionId: isPinned ? "_deckos_unpin" : "_deckos_pin", favoriteId: id });
        }
        const extra = roles.hasActionList ? roles.actionList : [];
        for (let i = 0; i < (extra ? extra.length : 0); i++) {
            const a = extra[i];
            if (a.type === "separator" && (list.length === 0 || list[list.length - 1].type === "separator")) {
                continue;
            }
            list.push(a);
        }
        while (list.length && list[list.length - 1].type === "separator") {
            list.pop();
        }
        if (list.length === 0) {
            return;
        }
        menu.model = model;
        menu.row = row;
        menu.entries = list;
        menu.cursor = list[0].type === "title" ? 1 : 0;
        const p = item.mapToItem(menu, item.width / 2, item.height / 2);
        box.x = Math.max(6, Math.min(p.x, menu.width - box.width - 6));
        box.y = Math.max(6, Math.min(p.y, menu.height - box.height - 6));
        visible = true;
        box.forceActiveFocus();
    }

    function close() {
        visible = false;
        entries = [];
    }

    function run(entry) {
        const favorites = deckMenu.rootModel.favoritesModel;
        close();
        if (entry.actionId === "_deckos_pin") {
            favorites.addFavorite(entry.favoriteId);
        } else if (entry.actionId === "_deckos_unpin") {
            favorites.removeFavorite(entry.favoriteId);
        } else if (entry.actionId === "_deckos_move") {
            favorites.moveRow(row, entry.to);
        } else if (model && model.trigger(row, entry.actionId, entry.actionArgument)) {
            deckMenu.expanded = false;
        }
    }

    function step(by) {
        for (let i = cursor + by; i >= 0 && i < entries.length; i += by) {
            if (entries[i].type !== "separator" && entries[i].type !== "title") {
                cursor = i;
                return;
            }
        }
    }

    Rectangle {
        id: box
        width: 240
        height: column.height + 12
        radius: 10
        color: deckMenu.surface
        border.color: deckMenu.border

        Keys.onUpPressed: menu.step(-1)
        Keys.onDownPressed: menu.step(1)
        Keys.onReturnPressed: menu.run(menu.entries[menu.cursor])
        Keys.onEnterPressed: menu.run(menu.entries[menu.cursor])
        Keys.onEscapePressed: menu.close()
        Keys.onPressed: event => event.accepted = true  // keep keys from leaking into the search

        MouseArea {  // clicks on the box itself shouldn't close it
            anchors.fill: parent
        }

        Column {
            id: column
            x: 6
            y: 6
            width: parent.width - 12

            Repeater {
                model: menu.entries
                delegate: Item {
                    id: entry
                    required property var modelData
                    required property int index
                    readonly property bool line: modelData.type === "separator"
                    readonly property bool title: modelData.type === "title"
                    readonly property bool lit: !line && !title && (menu.cursor === index || mouse.containsMouse)

                    width: column.width
                    height: line ? 9 : 32

                    Rectangle {
                        visible: entry.line
                        anchors.centerIn: parent
                        width: parent.width - 12
                        height: 1
                        color: deckMenu.border
                    }
                    Rectangle {
                        visible: entry.lit
                        anchors.fill: parent
                        radius: 7
                        color: deckMenu.hot
                    }
                    LineIcon {
                        visible: !!entry.modelData.line
                        x: 9
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16
                        height: 16
                        name: entry.modelData.line || ""
                        tint: entry.lit ? deckMenu.text : deckMenu.subtext
                    }
                    Kirigami.Icon {
                        visible: !entry.line && !entry.modelData.line && !!entry.modelData.icon
                        x: 9
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16
                        height: 16
                        source: entry.modelData.icon || ""
                    }
                    Text {
                        visible: !entry.line
                        x: 34
                        width: parent.width - 40
                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.modelData.text || ""
                        color: entry.title ? deckMenu.subtext : deckMenu.text
                        font.pixelSize: entry.title ? 11 : 13
                        font.weight: entry.title ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }
                    MouseArea {
                        id: mouse
                        anchors.fill: parent
                        enabled: !entry.line && !entry.title && entry.modelData.enabled !== false
                        hoverEnabled: true
                        onEntered: menu.cursor = entry.index
                        onClicked: menu.run(entry.modelData)
                    }
                }
            }
        }
    }
}
