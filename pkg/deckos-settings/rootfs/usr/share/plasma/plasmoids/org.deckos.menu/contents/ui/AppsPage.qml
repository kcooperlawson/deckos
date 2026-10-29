// Every app: Plasma's menu categories on the left, the chosen category's apps on the right
// (A–Z headings under "All Applications").
import QtQuick
import org.deckos.vibes as Vibes
import org.kde.kirigami as Kirigami

Item {
    id: page

    signal leaveUp()
    signal back()

    property int refreshes: 0  // re-reads modelForRow() after the root model rebuilds

    // DecKoOS line icons for the standard menu categories; anything else keeps its theme icon.
    readonly property var lineIcons: ({
        "All Applications": "grid", "Development": "code", "Education": "flask", "Games": "gaming",
        "Graphics": "image", "Internet": "globe", "Multimedia": "music", "Office": "doc",
        "Science & Math": "flask", "Settings": "sliders", "System": "system", "Utilities": "package",
        "Lost & Found": "package"
    })

    function enter() {
        categories.currentIndex = Math.max(0, categories.currentIndex);
        categories.forceActiveFocus();
    }

    Connections {
        target: deckMenu.rootModel
        function onRefreshed() {
            page.refreshes++;
        }
    }

    Item {
        id: backButton
        width: backRow.width + 20
        height: 28
        Vibes.Notch {
            anchors.fill: parent
            look: deckMenu.look
            cut: 7
            lit: false
            fill: backMouse.containsMouse ? deckMenu.border : deckMenu.raised
        }

        Row {
            id: backRow
            anchors.centerIn: parent
            spacing: 4
            LineIcon {
                name: "chevron-left"
                width: 14
                height: 14
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: "Pinned"
                color: deckMenu.text
                font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            id: backMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: page.back()
        }
    }

    SectionLabel {
        anchors.left: backButton.right
        anchors.leftMargin: 12
        anchors.verticalCenter: backButton.verticalCenter
        text: "All apps"
    }

    ListView {
        id: categories
        y: 38
        width: 190
        height: parent.height - y
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: deckMenu.rootModel
        currentIndex: 0
        activeFocusOnTab: true
        delegate: Item {
            id: cat
            required property var model
            required property int index
            readonly property bool group: model.hasChildren === true || model.isParent === true
            readonly property bool current: ListView.isCurrentItem

            width: categories.width
            height: group ? 36 : 0
            visible: group

            Vibes.Notch {
                anchors.fill: parent
                anchors.topMargin: 1
                anchors.bottomMargin: 1
                visible: cat.current || catMouse.containsMouse
                look: deckMenu.look
                cut: 8
                lit: cat.current && categories.activeFocus
                fill: cat.current ? deckMenu.raised : deckMenu.hot
            }
            LineIcon {
                visible: !!page.lineIcons[cat.model.display]
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                name: page.lineIcons[cat.model.display] || ""
                tint: cat.current ? deckMenu.accent : deckMenu.subtext
            }
            Kirigami.Icon {
                visible: !page.lineIcons[cat.model.display]
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 18
                height: 18
                source: cat.model.decoration
            }
            Text {
                x: 38
                width: parent.width - 46
                anchors.verticalCenter: parent.verticalCenter
                text: cat.index === 0 ? "All apps" : cat.model.display ?? ""  // undefined while the app list reloads
                color: cat.current ? deckMenu.text : Qt.tint(deckMenu.text, Qt.rgba(deckMenu.subtext.r, deckMenu.subtext.g, deckMenu.subtext.b, 0.4))
                font.pixelSize: 13
                elide: Text.ElideRight
            }
            MouseArea {
                id: catMouse
                anchors.fill: parent
                hoverEnabled: true
                onClicked: categories.currentIndex = cat.index
            }
        }

        Keys.onUpPressed: event => {
            if (currentIndex <= 0) {
                page.leaveUp();
            } else {
                event.accepted = false;
            }
        }
        Keys.onRightPressed: page.enterApps()
        Keys.onReturnPressed: page.enterApps()
        Keys.onEnterPressed: page.enterApps()
    }

    function enterApps() {
        if (apps.count > 0) {
            apps.currentIndex = 0;
            apps.forceActiveFocus();
        }
    }

    Rectangle {
        x: categories.width + 10
        y: categories.y
        width: 1
        height: categories.height
        color: deckMenu.border
    }

    ListView {
        id: apps
        x: categories.width + 20
        y: categories.y
        width: parent.width - x
        height: categories.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: {
            page.refreshes;  // dependency
            return deckMenu.rootModel.count > 0 ? deckMenu.rootModel.modelForRow(categories.currentIndex) : null;
        }
        delegate: ItemRow {}
        currentIndex: -1
        activeFocusOnTab: true
        section.property: categories.currentIndex === 0 ? "group" : ""
        section.delegate: SectionLabel {
            required property string section
            width: apps.width
            height: 26
            leftPadding: 8
            verticalAlignment: Text.AlignBottom
            text: section
        }
        onModelChanged: currentIndex = -1

        Keys.onLeftPressed: categories.forceActiveFocus()
        Keys.onUpPressed: event => {
            if (currentIndex <= 0) {
                categories.forceActiveFocus();
            } else {
                event.accepted = false;
            }
        }
        Keys.onReturnPressed: deckMenu.activate(model, currentIndex)
        Keys.onEnterPressed: deckMenu.activate(model, currentIndex)
        Keys.onMenuPressed: if (currentItem) deckMenu.showActions(model, currentIndex, currentItem.model, currentItem, false)
    }
}
