pragma Singleton
import QtQuick

// The DecKoOS palette (same as hub_style.py). The accent follows Plasma's; FullRepresentation sets it.
QtObject {
    readonly property color bg: "#0F1115"
    readonly property color surface: "#171A21"
    readonly property color raised: "#1D212A"
    readonly property color border: "#262B36"
    readonly property color hover: "#2A2F3B"
    readonly property color pressed: "#353B49"
    readonly property color text: "#E8EAF0"
    readonly property color subtext: "#8C94A6"
    readonly property color muted: "#5A6172"
    readonly property color success: "#3DD68C"
    readonly property color warning: "#F5B84B"
    readonly property color danger: "#FF6B6B"

    property color accent: "#4C8DFF"
    // The gradient partner: the accent shifted towards violet, like the brand tile.
    readonly property color accentB: Qt.hsva((accent.hsvHue + 32 / 360) % 1, Math.min(1, accent.hsvSaturation + 0.04),
                                             accent.hsvValue, 1)
    readonly property color tint: Qt.rgba(accent.r, accent.g, accent.b, 0.15)

    readonly property int radius: 10
    readonly property int spacing: 8
    readonly property string font: "Inter"

    // The DecKoOS line icons and logo, installed by deckos-settings (assets/icons.py draws them).
    readonly property string share: "file:///usr/share/deckos/"
    function icon(name: string): string {
        return share + "icons/" + name + ".svg";
    }
}
