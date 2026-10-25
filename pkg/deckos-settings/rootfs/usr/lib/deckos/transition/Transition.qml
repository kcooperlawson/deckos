// Covers the desktop while deckos session switches to Gaming Mode: the login splash (wordmark and
// its oO eyes glancing and blinking) fades in and keeps going until SDDM ends this session, so the switch
// reads as one animation (this, then Steam's startup movie of the same logo) instead of a flash
// of the closing desktop. qml6 Transition.qml -- --text=CAPTION [--splash=URL]
import QtQuick
import QtQuick.Window

Window {
    id: win
    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    Rectangle {
        id: cover
        anchors.fill: parent
        color: "#0f1115"
        opacity: 0
        NumberAnimation on opacity { to: 1; duration: 450; easing.type: Easing.OutCubic }

        Loader {
            anchors.fill: parent
            source: Qt.resolvedUrl(Qt.application.arguments.find(a => a.startsWith("--splash="))?.slice(9)
                                   || "file:///usr/share/plasma/look-and-feel/org.deckos.desktop/contents/splash/Splash.qml")
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: parent.height * 0.12
            text: Qt.application.arguments.find(a => a.startsWith("--text="))?.slice(7) || "Starting Gaming Mode"
            color: "#8C94A6"
            font.family: "Inter"
            font.pixelSize: Math.max(16, parent.height / 54)
        }
    }

    // Esc only hides the cover; the switch itself is already on its way
    Item {
        focus: true
        Keys.onEscapePressed: Qt.quit()
    }
}
