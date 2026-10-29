// Bottom bar: you (opens user settings), Gaming Mode, and lock / log out / sleep / restart / shut
// down from Plasma's session model (actions this PC can't do are left out). Hovering a button names
// it under your name.
import QtQuick
import org.deckos.vibes as Vibes
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

        Vibes.Notch {
            anchors.fill: parent
            visible: userArea.containsMouse
            look: deckMenu.look
            cut: 8
            lit: false
            fill: deckMenu.raised
        }

        Row {
            id: userRow
            x: 6
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            Vibes.Notch {  // your initial on a notched gradient chip (or your picture)
                width: 36
                height: 36
                anchors.verticalCenter: parent.verticalCenter
                look: deckMenu.look
                cut: 8
                lit: false
                edge: 0
                gradientFill: true
                Text {
                    anchors.centerIn: parent
                    text: (user.fullName || user.loginName || "?").charAt(0).toUpperCase()
                    color: deckMenu.ink
                    font.family: deckMenu.hud
                    font.pixelSize: 17
                    font.weight: Font.Bold
                }
                Kirigami.ShadowedImage {
                    anchors.fill: parent
                    radius: 0
                    source: user.faceIconUrl
                    visible: status === Image.Ready
                    asynchronous: true
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

        Item {
            id: gaming
            visible: deckMenu.gamingAvailable
            width: gamingRow.width + 32
            height: 38
            activeFocusOnTab: visible
            opacity: gamingMouse.pressed ? 0.85 : gamingMouse.containsMouse ? 0.92 : 1
            Vibes.Notch {  // the one filled button: notched, the accent gradient
                anchors.fill: parent
                look: deckMenu.look
                cut: 9
                lit: false
                edge: gaming.activeFocus ? 2 : 0
                fill: "white"
                gradientFill: true
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
                    tint: deckMenu.ink
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "Gaming Mode"
                    color: deckMenu.ink
                    font.family: deckMenu.hud
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    font.letterSpacing: 2
                    font.capitalization: Font.AllUppercase
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
