import QtQuick

// Text and/or icon button. `primary` gets the accent gradient, like the Hub's primary buttons;
// `round` makes an icon-only circle (media controls, header buttons).
Rectangle {
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
    radius: round ? height / 2 : 8
    opacity: enabled ? 1 : 0.45
    border.width: primary || flat ? 0 : 1
    border.color: Deck.border
    color: mouse.pressed ? Deck.pressed : mouse.containsMouse ? Deck.hover : flat ? "transparent" : Deck.raised
    gradient: primary ? grad : null
    Gradient {
        id: grad
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: mouse.containsMouse ? Qt.lighter(Deck.accent, 1.15) : Deck.accent }
        GradientStop { position: 1; color: mouse.containsMouse ? Qt.lighter(Deck.accentB, 1.15) : Deck.accentB }
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
            color: button.primary ? "white" : Deck.text
        }
        DeckText {
            text: button.text
            visible: !!button.text
            anchors.verticalCenter: parent.verticalCenter
            color: button.primary ? "white" : Deck.text
            font.weight: Font.DemiBold
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
        radius: parent.radius + 2
        color: "transparent"
        border.color: Deck.accent
        border.width: 2
        visible: button.activeFocus
    }
}
