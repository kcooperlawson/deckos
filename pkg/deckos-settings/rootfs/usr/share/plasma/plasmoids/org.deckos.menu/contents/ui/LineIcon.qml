// A DeckOS line icon (drawn in black, recoloured here).
import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.Icon {
    property string name
    property color tint: deckMenu.subtext

    implicitWidth: 18
    implicitHeight: 18
    source: deckMenu.iconDir + name + ".svg"
    isMask: true
    color: tint
    roundToIconSize: false
}
