import QtQuick
import org.deckos.vibes as Vibes

// Text and/or icon button, notched like the DecKo cards. `primary` is filled with the accent gradient and its
// text in spaced Chakra Petch capitals; `round` makes an icon-only square button (media controls, header buttons).
Item {
    id: button
    property string text
    property string icon
    property bool primary: false
    property bool round: false
    property bool flat: false
    property int iconSize: 16
    property string tip
    signal clicked()

    implicitHeight: 30
    implicitWidth: round ? implicitHeight : row.implicitWidth + 24
    opacity: enabled ? 1 : 0.45
    Vibes.Notch {
        anchors.fill: parent
        look: Deck.look
        cut: Math.min(8, height / 3)
        lit: false
        edge: button.primary || button.flat ? 0 : 1
        fill: mouse.pressed ? Deck.pressed : mouse.containsMouse ? Deck.hover : button.flat ? "transparent" : Deck.raised
        gradientFill: button.primary
        opacity: button.primary && mouse.containsMouse ? 0.88 : 1
    }

    Accessible.role: Accessible.Button
    Accessible.name: text || tip
    Accessible.onPressAction: clicked()
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6
        DeckIcon {
            name: button.icon
            visible: !!button.icon
            width: button.iconSize
            height: button.iconSize
            anchors.verticalCenter: parent.verticalCenter
            color: button.primary ? Deck.ink : Deck.text
        }
        DeckText {
            text: button.text
            visible: !!button.text
            anchors.verticalCenter: parent.verticalCenter
            color: button.primary ? Deck.ink : Deck.text
            font.family: button.primary ? Deck.hud : Deck.font
            font.weight: Font.DemiBold
            font.letterSpacing: button.primary ? 1.6 : 0
            font.capitalization: button.primary ? Font.AllUppercase : Font.MixedCase
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: button.clicked()
    }
    Rectangle {  // keyboard focus ring
        anchors.fill: parent
        anchors.margins: -2
        color: "transparent"
        border.color: Deck.accent
        border.width: 2
        visible: button.activeFocus
    }
}
