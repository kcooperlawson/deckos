// What the menu opens on: pinned apps, then recently used apps and files side by side.
import QtQuick
import org.deckos.vibes as Vibes

Item {
    id: home

    signal leaveUp()
    signal allApps()

    readonly property int columns: 6
    readonly property int pinnedRows: Math.max(1, Math.min(3, Math.ceil(grid.count / columns)))
    readonly property int recentRows: 3

    function enter() {
        if (grid.count > 0) {
            grid.currentIndex = Math.max(0, grid.currentIndex);
            grid.forceActiveFocus();
        } else {
            recentAppsView.forceActiveFocus();
        }
    }

    SectionLabel {
        x: 4
        y: 6
        text: "Pinned"
    }

    Item {
        id: allButton
        anchors.right: parent.right
        y: 0
        width: allRow.width + 24
        height: 28
        Vibes.Notch {
            anchors.fill: parent
            look: deckMenu.look
            cut: 7
            lit: false
            fill: allMouse.containsMouse ? deckMenu.border : deckMenu.raised
        }

        Row {
            id: allRow
            anchors.centerIn: parent
            spacing: 4
            Text {
                text: "All apps"
                color: deckMenu.text
                font.family: deckMenu.hud
                font.pixelSize: 12
                font.weight: Font.Medium
                font.letterSpacing: 2
                font.capitalization: Font.AllUppercase
                anchors.verticalCenter: parent.verticalCenter
            }
            LineIcon {
                name: "chevron"
                width: 14
                height: 14
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            id: allMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: home.allApps()
        }
    }

    GridView {
        id: grid
        y: 32
        width: parent.width
        height: home.pinnedRows * cellHeight
        cellWidth: Math.floor(width / home.columns)
        cellHeight: 96
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: deckMenu.rootModel.favoritesModel
        delegate: AppTile {}
        currentIndex: -1
        activeFocusOnTab: true

        Keys.onUpPressed: event => {
            if (currentIndex < home.columns) {
                home.leaveUp();
            } else {
                event.accepted = false;
            }
        }
        Keys.onDownPressed: event => {
            if (currentIndex + home.columns >= count) {
                recentAppsView.currentIndex = 0;
                recentAppsView.forceActiveFocus();
            } else {
                event.accepted = false;
            }
        }
        Keys.onReturnPressed: deckMenu.activate(model, currentIndex)
        Keys.onEnterPressed: deckMenu.activate(model, currentIndex)
        Keys.onMenuPressed: if (currentItem) deckMenu.showActions(model, currentIndex, currentItem.model, currentItem, true)
    }

    Text {
        visible: grid.count === 0
        y: 44
        x: 4
        width: parent.width - 8
        text: "Nothing pinned yet. Right-click any app and pick Pin to menu."
        color: deckMenu.subtext
        font.pixelSize: 13
        wrapMode: Text.WordWrap
    }

    SectionLabel {
        id: recentLabel
        x: 4
        y: grid.y + Math.max(grid.height, 64) + 14
        text: "Recent"
    }

    Item {
        anchors.top: recentLabel.bottom
        anchors.topMargin: 8
        width: parent.width
        height: home.recentRows * 44

        RecentList {
            id: recentAppsView
            width: (parent.width - 16) / 2
            model: deckMenu.recentApps
            empty: "Apps you open show up here."
            rows: home.recentRows
            onLeaveUp: grid.count > 0 ? home.enter() : home.leaveUp()
            KeyNavigation.right: recentDocsView
        }

        RecentList {
            id: recentDocsView
            x: parent.width / 2 + 8
            width: (parent.width - 16) / 2
            model: deckMenu.recentDocs
            empty: "Files you open show up here."
            rows: home.recentRows
            onLeaveUp: grid.count > 0 ? home.enter() : home.leaveUp()
            KeyNavigation.left: recentAppsView
        }
    }
}
