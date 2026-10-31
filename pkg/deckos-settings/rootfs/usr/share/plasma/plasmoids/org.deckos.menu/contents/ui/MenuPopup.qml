// The popup: search field on top, then the home page (pinned + recent), all apps, or search
// results, and the footer. Keyboard first: it opens with the search field focused, typing anywhere
// lands there, arrows move, Enter opens, Escape clears / goes back / closes.
import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

Item {
    id: popup
    Vibes.Unfold { target: popup; open: deckMenu.expanded }  // DecKoOS's one motion: it unfolds from the panel

    property int page: 0  // 0 home, 1 all apps
    readonly property bool searching: deckMenu.query.length > 0

    Layout.minimumWidth: 640
    Layout.preferredWidth: 640
    Layout.maximumWidth: 640
    Layout.minimumHeight: 596
    Layout.preferredHeight: 596
    Layout.maximumHeight: 596
    implicitWidth: 640
    implicitHeight: 596

    Component.onCompleted: {
        deckMenu.actionMenu = actionMenu;
        deckMenu.rootModel.refresh();
        deckMenu.exec("command -v gamescope-session-plus", code => deckMenu.gamingAvailable = code === 0);
    }

    Connections {
        target: deckMenu
        function onExpandedChanged() {
            if (deckMenu.expanded) {
                search.forceActiveFocus();
            } else {  // reset while hidden, so opening again is just showing it
                actionMenu.close();
                search.text = "";
                popup.page = 0;
            }
        }
    }

    function focusSearch() {
        search.forceActiveFocus();
    }

    function down() {
        if (searching) {
            results.move(1);
        } else if (page === 0) {
            home.enter();
        } else {
            apps.enter();
        }
    }

    function cancel() {
        if (search.text !== "") {
            search.text = "";
        } else if (page !== 0) {
            page = 0;
            search.forceActiveFocus();
        } else {
            deckMenu.expanded = false;
        }
    }

    // Typing while a grid or list has the keyboard goes to the search field.
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Escape) {
            popup.cancel();
            event.accepted = true;
        } else if (event.text !== "" && event.text.charCodeAt(0) >= 32 && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
            search.text += event.text;
            search.forceActiveFocus();
            event.accepted = true;
        } else if (event.key === Qt.Key_Backspace && search.text !== "") {
            search.text = search.text.slice(0, -1);
            search.forceActiveFocus();
            event.accepted = true;
        }
    }

    Item {
        id: searchBox
        x: 6
        y: 6
        width: parent.width - 12
        height: 46
        Vibes.Notch {  // notched, its edge lit while you type
            pulse: deckMenu.pulse  // the music's beat (deckos vibe react on)
            anchors.fill: parent
            look: deckMenu.look
            cut: 11
            lit: search.activeFocus
            fill: deckMenu.base
        }

        LineIcon {
            x: 13
            anchors.verticalCenter: parent.verticalCenter
            name: "search"
            tint: search.activeFocus ? deckMenu.accent : deckMenu.subtext
        }

        TextInput {
            id: search
            objectName: "search"  // the preview types into it
            x: 42
            width: parent.width - x - 14
            anchors.verticalCenter: parent.verticalCenter
            focus: true
            color: deckMenu.text
            selectionColor: deckMenu.accent
            selectedTextColor: "white"
            font.pixelSize: 14
            clip: true
            selectByMouse: true
            Accessible.role: Accessible.EditableText
            Accessible.name: "Search"
            onTextChanged: deckMenu.query = text

            Text {
                visible: search.text === ""
                anchors.verticalCenter: parent.verticalCenter
                text: "Search apps, files and settings"
                color: deckMenu.subtext
                font: search.font
            }

            Keys.onDownPressed: popup.down()
            Keys.onUpPressed: if (popup.searching) results.move(-1)
            Keys.onReturnPressed: if (popup.searching) results.accept()
            Keys.onEnterPressed: if (popup.searching) results.accept()
            Keys.onEscapePressed: popup.cancel()
            Keys.onTabPressed: popup.down()
        }
    }

    Item {
        id: body
        x: 12
        y: searchBox.y + searchBox.height + 14
        width: parent.width - 24
        height: footer.y - y - 6

        HomePage {
            id: home
            anchors.fill: parent
            visible: !popup.searching && popup.page === 0
            onLeaveUp: popup.focusSearch()
            onAllApps: {
                popup.page = 1;
                apps.enter();
            }
        }

        AppsPage {
            id: apps
            anchors.fill: parent
            visible: !popup.searching && popup.page === 1
            onLeaveUp: popup.focusSearch()
            onBack: {
                popup.page = 0;
                popup.focusSearch();
            }
        }

        SearchPage {
            id: results
            anchors.fill: parent
            anchors.leftMargin: -6
            anchors.rightMargin: -6
            visible: popup.searching
        }
    }

    Footer {
        id: footer
        anchors.bottom: parent.bottom
        width: parent.width
    }

    ActionMenu {
        id: actionMenu
        anchors.fill: parent
        z: 10
    }
}
