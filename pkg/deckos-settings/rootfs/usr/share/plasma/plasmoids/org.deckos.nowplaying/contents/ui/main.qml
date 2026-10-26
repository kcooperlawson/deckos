// DecKoOS Now Playing: what's playing (any MPRIS player: Spotify, browsers, VLC...) on the desktop in the Vibe's
// look: the cover, the song and artist, a line for how far in, and play/skip when you point at it. Plasma's own
// MPRIS model (as its media controller uses); hidden when nothing plays, and the clock only runs while playing.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.mpris as Mpris
import org.kde.kirigami as Kirigami
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: np

    Vibes.Look {
        id: look
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    Mpris.Mpris2Model { id: mpris }
    readonly property var player: mpris.currentPlayer
    readonly property bool playing: player && player.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool hasTrack: !!player && (player.track || "") !== ""
    // Spotify reports old art links that no longer load; its images live on i.scdn.co
    readonly property string art: String(player?.artUrl ?? "").replace("https://open.spotify.com/image/", "https://i.scdn.co/image/")

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 300
    Layout.preferredWidth: 420
    Layout.minimumHeight: 120
    Layout.preferredHeight: 132
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    // Position: players only report it when asked; ask once a second while playing and on screen
    Timer {
        interval: 1000
        repeat: true
        running: np.playing && np.visible
        onTriggered: if (np.player && np.player.updatePosition) np.player.updatePosition()
    }

    Item {
        anchors.fill: parent
        opacity: np.hasTrack ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 400 } }

        Vibes.Plate { anchors.fill: parent; look: look }

        RowLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 16

            Rectangle {  // the cover
                Layout.preferredWidth: parent.height
                Layout.preferredHeight: parent.height
                radius: look.radius * 0.6
                clip: true
                color: Qt.rgba(1, 1, 1, 0.06)
                Image {
                    anchors.fill: parent
                    source: np.art
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize.width: 256
                }
                // gently breathing while the music plays
                scale: np.playing ? 1 : 0.96
                Behavior on scale { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Vibes.VibeText {
                    look: look
                    Layout.fillWidth: true
                    text: np.player?.track ?? ""
                    font.pixelSize: 22
                    elide: Text.ElideRight
                }
                Vibes.VibeText {
                    look: look
                    soft: true
                    Layout.fillWidth: true
                    text: np.player?.artist ?? ""
                    font.pixelSize: 15
                    elide: Text.ElideRight
                }
                Item { Layout.fillHeight: true }
                Rectangle {  // how far in
                    Layout.fillWidth: true
                    height: 3
                    radius: 1.5
                    color: Qt.rgba(1, 1, 1, 0.15)
                    Rectangle {
                        height: parent.height
                        radius: parent.radius
                        width: np.player && np.player.length > 0
                               ? parent.width * Math.min(1, np.player.position / np.player.length) : 0
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: look.colorA }
                            GradientStop { position: 1; color: look.colorB }
                        }
                    }
                }
                RowLayout {  // controls, when pointed at
                    spacing: 6
                    opacity: hover.hovered ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                    Repeater {
                        model: [["media-skip-backward", "Previous"], [np.playing ? "media-playback-pause" : "media-playback-start", "PlayPause"],
                                ["media-skip-forward", "Next"]]
                        Kirigami.Icon {
                            required property var modelData
                            Layout.preferredWidth: 22
                            Layout.preferredHeight: 22
                            source: modelData[0]
                            color: look.text
                            isMask: true
                            TapHandler { onTapped: if (np.player) np.player[modelData[1]]() }
                        }
                    }
                }
            }
        }
        HoverHandler { id: hover }
    }
}
