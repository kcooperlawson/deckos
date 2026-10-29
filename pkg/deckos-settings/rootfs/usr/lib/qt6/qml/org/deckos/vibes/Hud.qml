// A DecKo label: Chakra Petch, spaced capitals, quiet (NOW PLAYING, CPU, WEDNESDAY), or `strong` for numbers.
import QtQuick

Text {
    property var look
    property bool strong: false
    color: !look ? "transparent" : strong ? look.text : look.subtext
    font.family: look ? look.hud : "Chakra Petch"
    font.weight: strong ? Font.DemiBold : Font.Medium
    font.letterSpacing: strong ? 0.5 : 2.6
    font.capitalization: strong ? Font.MixedCase : Font.AllUppercase
    font.pixelSize: strong ? 28 : 11
    renderType: Text.QtRendering
}
