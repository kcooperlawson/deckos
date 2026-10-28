// Vibe mode: one Stage window per monitor (each a view onto the same world), and the small player for when you
// leave the stage while your own music plays. `engine` (deckos_music.py) holds everything they share.
import QtQuick

QtObject {
    property Instantiator stages: Instantiator {
        model: engine.screens
        delegate: Stage {
            required property var modelData
            info: modelData
        }
    }
    property Mini mini: Mini {}
}
