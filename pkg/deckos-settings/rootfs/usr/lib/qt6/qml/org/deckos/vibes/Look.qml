// The DecKo look every DecKoOS desktop widget and the taskbar share: the shape is always the wordmark's notch, the
// numbers and labels always Chakra Petch (the wordmark's cut corners as type), and the colours the Vibe's two
// (`deckos vibe` writes style, colorA and colorB into each widget; with no Vibe, "deckos": the brand blue and violet).
import QtQuick

QtObject {
    property string style: "deckos"
    property color colorA: "#4C8DFF"
    property color colorB: "#7A5CFF"

    readonly property color text: "#F2F3F7"
    readonly property color subtext: Qt.rgba(0.86, 0.88, 0.94, 0.62)
    readonly property string family: "Inter"         // names, titles, sentences
    readonly property string hud: "Chakra Petch"     // numbers, labels, buttons
    readonly property int weight: Font.Normal
    readonly property bool italic: false
    readonly property bool glow: false
    readonly property bool plate: true
    readonly property real radius: 0
    readonly property real cut: 14                   // the notch, on cards
    // A card's ground: near-black, a breath of the Vibe's first colour in it
    readonly property color glass: Qt.rgba(0.04 + colorA.r * 0.03, 0.045 + colorA.g * 0.03, 0.07 + colorA.b * 0.04, 0.84)
    readonly property color line: Qt.rgba(1, 1, 1, 0.10)
    readonly property color off: Qt.rgba(1, 1, 1, 0.10)  // an unlit segment

    // Between the Vibe's two colours, t from 0 (colorA) to 1 (colorB)
    function mix(t) {
        return Qt.rgba(colorA.r + (colorB.r - colorA.r) * t, colorA.g + (colorB.g - colorA.g) * t,
                       colorA.b + (colorB.b - colorA.b) * t, 1);
    }
}
