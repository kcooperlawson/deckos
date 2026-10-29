import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

// A section card: a DecKo notch (faint edge) with an optional kicker title in spaced Chakra Petch capitals.
Item {
    id: plate
    property string kicker
    default property alias content: body.data

    Layout.fillWidth: true
    implicitHeight: body.implicitHeight + (kicker ? 38 : 24)
    Vibes.Notch {
        anchors.fill: parent
        look: Deck.look
        cut: 12
        lit: false
        fill: Deck.surface
    }
    DeckText {
        visible: !!plate.kicker
        x: 14
        y: 10
        text: plate.kicker
        sub: true
        font.family: Deck.hud
        font.pixelSize: 11
        font.weight: Font.Medium
        font.letterSpacing: 2.6
        font.capitalization: Font.AllUppercase
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
