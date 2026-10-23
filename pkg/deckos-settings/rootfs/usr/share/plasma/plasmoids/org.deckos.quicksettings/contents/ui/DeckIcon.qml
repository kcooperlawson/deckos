import QtQuick
import org.kde.kirigami as Kirigami

// A DeckOS line icon (drawn in #000), recoloured on the GPU.
Kirigami.Icon {
    property string name
    source: name ? Deck.icon(name) : ""
    isMask: true
    color: Deck.text
    implicitWidth: 20
    implicitHeight: 20
}
