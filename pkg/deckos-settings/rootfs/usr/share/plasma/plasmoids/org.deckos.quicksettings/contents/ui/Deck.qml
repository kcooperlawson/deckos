pragma Singleton
import QtQuick
import org.kde.kirigami as Kirigami
import org.deckos.vibes as Vibes

// The DecKoOS palette, from the active colour scheme and accent so themes and the Hub's accent reach
// Quick Settings; the surfaces are the scheme's background lifted towards its text. Shapes and type are the DecKo
// look (org.deckos.vibes): notched tiles, Chakra Petch labels, segmented sliders.
QtObject {
    id: deck
    readonly property color bg: Kirigami.Theme.backgroundColor
    readonly property color text: Kirigami.Theme.textColor
    readonly property color subtext: Kirigami.Theme.disabledTextColor
    readonly property color surface: Qt.tint(bg, Qt.rgba(text.r, text.g, text.b, 0.035))
    readonly property color raised: Qt.tint(bg, Qt.rgba(text.r, text.g, text.b, 0.06))
    readonly property color border: Qt.tint(bg, Qt.rgba(text.r, text.g, text.b, 0.12))
    readonly property color hover: Qt.tint(bg, Qt.rgba(text.r, text.g, text.b, 0.10))
    readonly property color pressed: Qt.tint(bg, Qt.rgba(text.r, text.g, text.b, 0.15))
    readonly property color muted: Qt.tint(subtext, Qt.rgba(bg.r, bg.g, bg.b, 0.35))
    readonly property color success: "#3DD68C"
    readonly property color warning: "#F5B84B"
    readonly property color danger: "#FF6B6B"

    readonly property color accent: Kirigami.Theme.highlightColor
    // The gradient partner: the accent shifted towards violet, like the brand tile.
    readonly property color accentB: Qt.hsva((accent.hsvHue + 32 / 360) % 1, Math.min(1, accent.hsvSaturation + 0.04),
                                             accent.hsvValue, 1)
    readonly property color tint: Qt.rgba(accent.r, accent.g, accent.b, 0.15)

    readonly property int radius: 0
    readonly property int spacing: 8
    readonly property string font: "Inter"
    readonly property string hud: "Chakra Petch"  // labels, numbers, buttons
    readonly property color ink: "#0B0D16"   // text and icons on the gradient
    readonly property QtObject look: Vibes.Look { colorA: deck.accent; colorB: deck.accentB }

    // The DecKoOS line icons and logo, installed by deckos-settings (assets/icons.py draws them).
    readonly property string share: "file:///usr/share/deckos/"
    function icon(name: string): string {
        return share + "icons/" + name + ".svg";
    }
}
