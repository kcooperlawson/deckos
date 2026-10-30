// One thing on the Desktop as a tile (shelf.py says what it is): a game with its art and Play, a folder with what's
// in it, a picture as itself, a text file's first lines, an app with its icon, anything else with its size. Click
// opens it, right click for more, drag it out to anywhere a file can go.
import QtQuick
import QtQuick.Effects
import org.kde.kirigami as Kirigami
import org.deckos.vibes as Vibes

Item {
    id: tile
    property var item
    property var look
    property var owner  // the shelf (main.qml): open(), menu()
    readonly property string kind: item ? item.kind : ""
    readonly property bool picture: kind === "image" || (kind === "game" && item.art !== "")
    readonly property bool hovered: mouse.containsMouse

    Drag.active: drag.active
    Drag.dragType: Drag.Automatic
    Drag.supportedActions: Qt.CopyAction | Qt.MoveAction | Qt.LinkAction
    Drag.mimeData: ({ "text/uri-list": tile.item ? tile.item.url : "" })

    Vibes.Notch {
        anchors.fill: parent
        look: tile.look
        cut: tile.kind === "game" ? 14 : 10
        lit: tile.hovered
        fill: tile.hovered ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(0.09, 0.08, 0.13, 0.86)
    }

    // ---- the picture: a game's art or the image itself, cut to the notch, darkened at the bottom for the words
    Item {
        id: art
        anchors.fill: parent
        anchors.margins: 1
        visible: tile.picture
        layer.enabled: visible
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: artMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }
        Image {
            anchors.fill: parent
            source: !tile.item ? "" : tile.kind === "game" ? tile.item.art : tile.kind === "image" ? tile.item.url : ""
            sourceSize.width: 640
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.2; color: "transparent" }
                GradientStop { position: 1; color: Qt.rgba(0.03, 0.02, 0.06, 0.95) }
            }
        }
    }
    Item {
        id: artMask
        anchors.fill: art
        visible: false
        layer.enabled: true
        Vibes.Notch { anchors.fill: parent; cut: tile.kind === "game" ? 13 : 9; lit: false; edge: 0; fill: "white" }
    }

    // ---- the top line: an icon (or a kicker over art) and the name
    Row {
        id: head
        x: 14
        y: 12
        width: parent.width - 28
        spacing: 9
        visible: !tile.picture
        Kirigami.Icon {
            width: tile.kind === "app" ? 34 : 18
            height: width
            source: !tile.item ? "" : tile.kind === "app" ? tile.item.icon  // the app's own; the rest DecKoOS's line icons
                  : "/usr/share/deckos/icons/" + ({ folder: "folder", text: "doc", partial: "download" }[tile.kind] || "doc")
                    + ".svg"
            color: tile.look ? tile.look.colorA : "white"
            isMask: tile.kind !== "app"
        }
        Column {
            width: head.width - (tile.kind === "app" ? 43 : 27)
            spacing: 1
            Text {
                width: parent.width
                text: tile.item ? tile.item.title : ""
                textFormat: Text.PlainText
                elide: Text.ElideMiddle
                color: tile.look ? tile.look.text : "white"
                font.family: "Inter"
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                visible: tile.kind === "app" && text !== ""
                text: tile.item && tile.kind === "app" ? tile.item.detail : ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: tile.look ? tile.look.subtext : "#aaa"
                font.family: "Inter"
                font.pixelSize: 11
            }
        }
    }
    Text {  // over art: what it is
        visible: tile.kind === "game"
        x: 14
        y: 12
        text: "STEAM · GAME"
        color: "#FFF1C4"
        font.family: "Chakra Petch"
        font.pixelSize: 10
        font.weight: Font.DemiBold
        font.letterSpacing: 1.6
        style: Text.Raised
        styleColor: Qt.rgba(0, 0, 0, 0.5)
    }

    // ---- the middle: a folder's pictures, a text file's first lines
    Row {
        visible: tile.kind === "folder" && tile.item.pictures.length > 0
        x: 14
        y: 40
        spacing: 6
        Repeater {
            model: tile.kind === "folder" ? tile.item.pictures : []
            Image {
                required property string modelData
                width: 34
                height: 26
                source: modelData
                sourceSize.width: 96
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                clip: true
            }
        }
    }
    Column {
        visible: tile.kind === "text"
        x: 14
        y: 38
        width: parent.width - 28
        spacing: 2
        Repeater {
            model: tile.kind === "text" ? tile.item.lines.slice(0, tile.height > 120 ? 3 : 2) : []
            Text {
                required property string modelData
                width: parent.width
                text: modelData
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: tile.look ? tile.look.subtext : "#aaa"
                font.family: "JetBrains Mono"
                font.pixelSize: 11
            }
        }
    }

    // ---- a download still arriving: its size is all there is to know, so the segments sweep while it grows
    Vibes.Segments {
        id: sweep
        visible: tile.kind === "partial"
        x: 14
        y: 38
        width: parent.width - 28
        look: tile.look
        count: 40
        segmentHeight: 6
        spacing: 2
        SequentialAnimation on value {
            running: tile.kind === "partial" && tile.visible
            loops: Animation.Infinite
            NumberAnimation { from: 0; to: 1; duration: 1600; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1; to: 0; duration: 1600; easing.type: Easing.InOutSine }
        }
    }

    // ---- the bottom: the name over art, the facts in Chakra Petch
    Column {
        x: 14
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: parent.width - (tile.kind === "game" ? 130 : 28)
        spacing: 2
        Text {
            visible: tile.picture
            width: parent.width
            text: tile.item ? tile.item.title : ""
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: "white"
            style: Text.Raised
            styleColor: Qt.rgba(0, 0, 0, 0.55)
            font.family: tile.kind === "game" ? "Inter Display" : "Inter"
            font.pixelSize: tile.kind === "game" ? 20 : 13
            font.weight: Font.DemiBold
        }
        Text {
            visible: tile.kind !== "app" && text !== ""
            width: parent.width
            text: !tile.item ? "" : tile.kind === "game" ? tile.item.detail : tile.item.detail.toUpperCase()
            elide: Text.ElideRight
            color: tile.picture ? Qt.rgba(1, 1, 1, 0.82) : (tile.look ? tile.look.subtext : "#aaa")
            font.family: tile.kind === "game" ? "Inter" : "Chakra Petch"
            font.pixelSize: tile.kind === "game" ? 12 : 11
            font.weight: tile.kind === "game" ? Font.Normal : Font.DemiBold
            font.letterSpacing: tile.kind === "game" ? 0 : 1.1
        }
    }

    // ---- a game's Play
    Item {
        visible: tile.kind === "game"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 14
        width: 92
        height: 34
        Vibes.Notch { anchors.fill: parent; look: tile.look; cut: 8; gradientFill: true; lit: false; edge: 0 }
        Row {
            anchors.centerIn: parent
            spacing: 6
            Kirigami.Icon {
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 14
                source: "media-playback-start"
                color: "#0B0D16"
                isMask: true
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "PLAY"
                color: "#0B0D16"
                font.family: "Chakra Petch"
                font.pixelSize: 13
                font.weight: Font.Bold
                font.letterSpacing: 0.8
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: event => event.button === Qt.RightButton ? tile.owner.menu(tile.item, tile, event.x, event.y)
                                                             : tile.owner.open(tile.item)
        DragHandler {
            id: drag
            target: null
            onActiveChanged: if (active) tile.grabToImage(r => { tile.Drag.imageSource = r.url; })
        }
    }
}
