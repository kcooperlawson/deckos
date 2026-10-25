// "PINNED", "RECENT"…: the small spaced capitals DecKoOS uses over every group.
import QtQuick

Text {
    color: deckMenu.subtext
    font.pixelSize: 11
    font.weight: Font.DemiBold
    font.letterSpacing: 1.2
    font.capitalization: Font.AllUppercase
    elide: Text.ElideRight
}
