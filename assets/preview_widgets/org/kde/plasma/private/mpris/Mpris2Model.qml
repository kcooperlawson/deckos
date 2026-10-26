import QtQuick
// The preview script's player (a Python object: QML can't name methods PlayPause like the real one)
QtObject {
    property var currentPlayer: previewPlayer
}
