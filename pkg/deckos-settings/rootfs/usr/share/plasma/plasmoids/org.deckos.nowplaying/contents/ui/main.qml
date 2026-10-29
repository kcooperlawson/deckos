// DecKoOS Now Playing: what's playing (any MPRIS player: Spotify, browsers, VLC...) on a DecKo card: the cover
// notched like the card, the song and artist, the music's own spectrum (deckos-visualizer, while it plays), and how
// far in as a lit line; play/skip when you point at it. Plasma's own MPRIS model (as its media controller uses);
// hidden when nothing plays, and the clock and the spectrum only run while playing.
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
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

    Vibes.Levels { id: levels; active: np.playing && np.visible }

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 340
    Layout.preferredWidth: 404
    Layout.minimumHeight: 200
    Layout.preferredHeight: 216
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    // Position: players only report it when asked; ask once a second while playing and on screen
    Timer {
        interval: 1000
        repeat: true
        running: np.playing && np.visible
        onTriggered: if (np.player && np.player.updatePosition) np.player.updatePosition()
    }
    function clock(us) {
        const s = Math.max(0, Math.floor((us || 0) / 1e6));
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    Item {
        anchors.fill: parent
        opacity: np.hasTrack ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 400 } }

        Vibes.Notch { anchors.fill: parent; look: look }

        GridLayout {
            anchors.fill: parent
            anchors.margins: 18
            columns: 2
            columnSpacing: 16
            rowSpacing: 12

            Item {  // the cover, notched like the card
                Layout.preferredWidth: 96
                Layout.preferredHeight: 96
                Rectangle { anchors.fill: parent; color: Qt.rgba(1, 1, 1, 0.06); visible: cover.status !== Image.Ready }
                Image {
                    id: cover
                    anchors.fill: parent
                    source: np.art
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize.width: 256
                    visible: false
                }
                Shape {
                    id: coverMask
                    anchors.fill: parent
                    visible: false
                    layer.enabled: true
                    layer.samples: 4
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: "white"
                        PathPolyline { path: [Qt.point(0, 0), Qt.point(86, 0), Qt.point(96, 10), Qt.point(96, 96),
                                              Qt.point(10, 96), Qt.point(0, 86)] }
                    }
                }
                MultiEffect {
                    anchors.fill: parent
                    source: cover
                    maskEnabled: true
                    maskThresholdMin: 0.5  // without a threshold every pixel passes and nothing is masked
                    maskSpreadAtMin: 1.0
                    maskSource: coverMask
                    visible: cover.status === Image.Ready
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 3
                Vibes.Hud { look: look; text: np.playing ? "Now playing" : "Paused"; color: look.colorA }
                Text {
                    Layout.fillWidth: true
                    text: np.player?.track ?? ""
                    color: look.text
                    font.family: look.family
                    font.weight: Font.DemiBold
                    font.pixelSize: 19
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: [np.player?.artist ?? "", np.player?.album ?? ""].filter(s => s).join(" · ")
                    color: look.subtext
                    font.family: look.family
                    font.pixelSize: 14
                    elide: Text.ElideRight
                }
                RowLayout {  // controls, when pointed at
                    Layout.topMargin: 4
                    spacing: 10
                    opacity: hover.hovered ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                    Repeater {
                        model: [["media-skip-backward", "Previous"], [np.playing ? "media-playback-pause" : "media-playback-start", "PlayPause"],
                                ["media-skip-forward", "Next"]]
                        Kirigami.Icon {
                            required property var modelData
                            Layout.preferredWidth: 20
                            Layout.preferredHeight: 20
                            source: modelData[0]
                            color: look.text
                            isMask: true
                            TapHandler { onTapped: if (np.player) np.player[modelData[1]]() }
                        }
                    }
                }
            }

            Row {  // the spectrum: the music's own bars, resting low when there's nothing to show
                id: spectrum
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                spacing: 3
                readonly property int bars: 40
                Repeater {
                    model: spectrum.bars
                    Rectangle {
                        required property int index
                        readonly property real level: levels.levels.length
                            ? levels.levels[Math.floor(index * levels.levels.length / spectrum.bars)] : 0
                        width: (spectrum.width - spectrum.spacing * (spectrum.bars - 1)) / spectrum.bars
                        height: Math.max(3, spectrum.height * level)
                        anchors.bottom: parent.bottom
                        gradient: Gradient {
                            GradientStop { position: 0; color: look.colorA }
                            GradientStop { position: 1; color: look.colorB }
                        }
                        Behavior on height { NumberAnimation { duration: 90 } }
                    }
                }
            }

            RowLayout {  // how far in
                Layout.columnSpan: 2
                Layout.fillWidth: true
                spacing: 12
                Vibes.Hud { look: look; text: np.clock(np.player?.position); font.letterSpacing: 1; font.pixelSize: 12 }
                Item {
                    Layout.fillWidth: true
                    height: 11
                    readonly property real done: np.player && np.player.length > 0 ? Math.min(1, np.player.position / np.player.length) : 0
                    Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 3; color: look.off }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width * parent.done
                        height: 3
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: look.colorA }
                            GradientStop { position: 1; color: look.colorB }
                        }
                    }
                    Rectangle { x: parent.width * parent.done - 1; width: 3; height: 11; color: look.text }
                }
                Vibes.Hud { look: look; text: np.clock(np.player?.length); font.letterSpacing: 1; font.pixelSize: 12 }
            }
        }
        HoverHandler { id: hover }
    }
}
