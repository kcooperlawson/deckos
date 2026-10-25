import QtQuick
import QtQuick.Layouts

// A bolted plate: surface card with a screw head in each corner (the DecKoOS motif) and an
// optional kicker title.
Rectangle {
    id: plate
    property string kicker
    default property alias content: body.data

    Layout.fillWidth: true
    implicitHeight: body.implicitHeight + (kicker ? 38 : 24)
    radius: Deck.radius + 2
    color: Deck.surface
    border.width: 1
    border.color: Deck.border

    Repeater {
        model: 4
        delegate: Rectangle {
            required property int index
            x: index % 2 ? plate.width - 9 : 5
            y: index < 2 ? 5 : plate.height - 9
            width: 4
            height: 4
            radius: 2
            color: Deck.pressed
        }
    }
    DeckText {
        visible: !!plate.kicker
        x: 14
        y: 10
        text: plate.kicker
        sub: true
        font.pixelSize: 10
        font.weight: Font.Bold
        font.letterSpacing: 1.2
        color: Deck.muted
    }
    ColumnLayout {
        id: body
        x: 12
        y: plate.kicker ? 28 : 12
        width: plate.width - 24
        spacing: Deck.spacing
    }
}
