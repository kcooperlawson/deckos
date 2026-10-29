// Text readable over any wallpaper (a soft shadow): what floats on the scene, like the clock
import QtQuick
import QtQuick.Effects

Text {
    property var look
    property bool soft: false  // secondary text
    color: soft ? look.subtext : look.text
    font.family: look.family
    font.weight: soft ? Font.Normal : look.weight
    font.italic: look.italic && !soft
    renderType: Text.QtRendering
    layer.enabled: true
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: look.glow ? look.colorA : "#000000"
        shadowOpacity: look.glow ? 0.9 : 0.75  // stronger now there's no plate behind the text
        shadowBlur: look.glow ? 0.8 : 0.6
        shadowHorizontalOffset: 0
        shadowVerticalOffset: look.glow ? 0 : 1
    }
}
