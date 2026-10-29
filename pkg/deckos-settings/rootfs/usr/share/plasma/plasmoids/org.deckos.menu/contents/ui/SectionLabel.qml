// "PINNED", "RECENT"…: the DecKo label (spaced Chakra Petch capitals) over every group.
import QtQuick

Text {
    color: deckMenu.subtext
    font.family: deckMenu.hud
    font.pixelSize: 12
    font.weight: Font.Medium
    font.letterSpacing: 2.8
    font.capitalization: Font.AllUppercase
    elide: Text.ElideRight
}
