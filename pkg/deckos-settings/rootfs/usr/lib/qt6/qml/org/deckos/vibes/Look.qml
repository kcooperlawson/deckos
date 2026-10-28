// The look DecKoOS's desktop widgets share, per Vibe: type, glow, the plate behind them. `deckos vibe` writes each
// widget's style and colours; with no Vibe ("deckos") they follow the desktop accent like the rest of DecKoOS.
import QtQuick

QtObject {
    property string style: "deckos"
    property color colorA: "#4C8DFF"
    property color colorB: "#7A5CFF"

    readonly property color text: "#F2F3F7"
    readonly property color subtext: Qt.rgba(0.95, 0.95, 0.97, 0.68)
    readonly property string family: style === "neon" ? "JetBrains Mono" : "Inter Display"
    readonly property int weight: ({ lofi: Font.Light, neon: Font.Medium, midnight: Font.Thin, cozy: Font.Normal })[style]
                                  ?? Font.Light
    readonly property bool italic: style === "lofi"
    readonly property bool glow: style === "neon"  // text lit in the Vibe's colour
    // No plate behind the cards: every Vibe floats its widgets on the scene with only a shadow, so they sit in the
    // picture instead of on top of it (plates read as bubbles, and got in the way of desktop icons)
    readonly property bool plate: false
    readonly property real radius: ({ midnight: 6, neon: 4, cozy: 22, lofi: 18 })[style] ?? 14
}
