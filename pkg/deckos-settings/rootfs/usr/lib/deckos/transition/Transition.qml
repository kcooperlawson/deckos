// Covers the desktop while deckos session switches to Gaming Mode: the login splash (wordmark and
// its oO eyes glancing and blinking) fades in and keeps going until SDDM ends this session, so the switch
// reads as one animation (this, then Steam's startup movie of the same logo) instead of a flash
// of the closing desktop. The cover rises from the dock as a plate with a lit edge (the dock taking the desktop
// with it), then the splash appears on it. Coming back, KSplash and the dock unfolding in are the same move reversed.
// qml6 Transition.qml -- --text=CAPTION [--splash=URL]
import QtQuick
import QtQuick.Window

Window {
    id: win
    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    // The rise: from the bottom edge, where the dock is, up over the whole screen
    property real rise: 0
    NumberAnimation on rise { from: 0; to: 1; duration: 520; easing.type: Easing.InOutCubic }

    Rectangle {
        id: cover
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height * win.rise
        color: "#0f1115"
        clip: true

        Rectangle {  // the leading edge, lit in DecKoOS's blue to violet while it moves
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 2
            opacity: 1 - win.rise * win.rise
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#4C8DFF" }
                GradientStop { position: 1; color: "#7A5CFF" }
            }
        }

        Loader {
            // the splash sits on the whole screen, so it stays put while the plate rises over it
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: win.height
            opacity: Math.max(0, (win.rise - 0.6) / 0.4)
            source: Qt.resolvedUrl(Qt.application.arguments.find(a => a.startsWith("--splash="))?.slice(9)
                                   || "file:///usr/share/plasma/look-and-feel/org.deckos.desktop/contents/splash/Splash.qml")
        }

        Text {
            opacity: Math.max(0, (win.rise - 0.6) / 0.4)
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
