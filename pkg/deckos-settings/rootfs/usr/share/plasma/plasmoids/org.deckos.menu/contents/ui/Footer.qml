// Bottom bar: you (opens user settings), Gaming Mode, and lock / log out / sleep / restart / shut
// down from Plasma's session model (actions this PC can't do are left out). Hovering a button names
// it under your name.
import QtQuick
import org.kde.plasma.private.kicker as Kicker
import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami

Item {
    id: footer

    property string hint: ""
    readonly property var actions: [
        { id: "lock-screen", icon: "lock", tip: "Lock" },
        { id: "logout", icon: "log-out", tip: "Log out" },
        { id: "suspend", icon: "sleep", tip: "Sleep" },
        { id: "reboot", icon: "refresh", tip: "Restart" },
        { id: "shutdown", icon: "power-off", tip: "Shut down" }
    ]

    height: 56

    KCoreAddons.KUser {
        id: user
    }

    // Readable copy of the session actions (row per favoriteId), so buttons can find theirs.
    Repeater {
        id: system
        model: Kicker.SystemModel {
            id: systemModel
            favoritesModel: deckMenu.rootModel.systemFavoritesModel
        }
        delegate: Item {
            required property var model
            readonly property string action: model.favoriteId || ""
            readonly property bool usable: model.disabled !== true
        }
    }

    function systemRow(id) {
        for (let i = 0; i < system.count; i++) {
            const it = system.itemAt(i);
            if (it && it.action === id && it.usable) {
                return i;
            }
        }
        return -1;
    }

    Rectangle {
        width: parent.width
        height: 1
        color: deckMenu.border
    }

    MouseArea {
        id: userArea
        x: 6
        anchors.verticalCenter: parent.verticalCenter
        width: userRow.width + 12
        height: 44
        hoverEnabled: true
        onClicked: deckMenu.launch("systemsettings kcm_users")

        Rectangle {
            anchors.fill: parent
            radius: 9
            color: userArea.containsMouse ? deckMenu.raised : "transparent"
        }

        Row {
            id: userRow
            x: 6
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            Rectangle {
                width: 32
                height: 32
                radius: 16
                anchors.verticalCenter: parent.verticalCenter
                gradient: Gradient {
                    GradientStop { position: 0; color: deckMenu.accent }
                    GradientStop { position: 1; color: deckMenu.accentB }
                }
                Text {
                    anchors.centerIn: parent
                    text: (user.fullName || user.loginName || "?").charAt(0).toUpperCase()
                    color: "white"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }
                Kirigami.ShadowedImage {
                    anchors.fill: parent
                    radius: 16
                    source: user.faceIconUrl
                    visible: status === Image.Ready
                    asynchronous: true
                    cache: false
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    text: user.fullName || user.loginName
                    color: deckMenu.text
                    font.pixelSize: 13
                }
                Text {
                    text: footer.hint !== "" ? footer.hint : userArea.containsMouse ? "Account settings" : user.loginName
                    color: deckMenu.subtext
                    font.pixelSize: 11
                }
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6

        Rectangle {
            id: gaming
            visible: deckMenu.gamingAvailable
            width: gamingRow.width + 32
            height: 36
            radius: 9
            activeFocusOnTab: visible
            border.color: activeFocus ? "white" : "transparent"
            opacity: gamingMouse.pressed ? 0.85 : 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: gamingMouse.containsMouse ? Qt.lighter(deckMenu.accent, 1.12) : deckMenu.accent }
                GradientStop { position: 1; color: gamingMouse.containsMouse ? Qt.lighter(deckMenu.accentB, 1.12) : deckMenu.accentB }
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Switch to Gaming Mode"
            Keys.onReturnPressed: deckMenu.startGamingMode()
            Keys.onEnterPressed: deckMenu.startGamingMode()

            Row {
                id: gamingRow
                anchors.centerIn: parent
                spacing: 8
                LineIcon {
                    name: "gaming"
                    tint: "white"
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "Gaming Mode"
                    color: "white"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea {
                id: gamingMouse
                anchors.fill: parent
                hoverEnabled: true
                onClicked: deckMenu.startGamingMode()
                onContainsMouseChanged: footer.hint = containsMouse ? "Switch to Gaming Mode" : ""
            }
        }

        Item {
            visible: gaming.visible
            width: 6
            height: 1
        }

        Repeater {
            model: footer.actions
            delegate: IconButton {
                required property var modelData
                readonly property int row: system.count >= 0 ? footer.systemRow(modelData.id) : -1
                visible: row >= 0
                icon: modelData.icon
                tip: modelData.tip
                onHoveredChanged: footer.hint = hovered ? tip : ""
                onClicked: {
                    deckMenu.expanded = false;
                    systemModel.trigger(row, "", null);
                }
            }
        }
    }
}
