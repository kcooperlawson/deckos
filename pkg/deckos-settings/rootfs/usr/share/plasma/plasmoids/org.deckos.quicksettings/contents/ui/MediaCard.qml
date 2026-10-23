import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import org.kde.plasma.private.mpris as Mpris

// Now playing, like the Hub's card: art, title, artist, seek and controls for whichever player
// Plasma considers current (Spotify, Firefox, VLC…).
Section {
    id: card
    property bool expanded: true

    readonly property var player: mpris.currentPlayer
    readonly property bool available: !!player && !!player.track
    readonly property bool playing: !!player && player.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property real length: player ? player.length / 1e6 : 0  // seconds
    // Our own clock: Spotify reports position 0, and players only signal position on seeks.
    property real pos: 0
    readonly property string trackKey: player ? player.identity + player.track + player.artist : ""

    function sync(): void {
        if (!player)
            return;
        player.updatePosition();
        if (player.position > 0)
            pos = player.position / 1e6;
    }
    function time(s: real): string {
        s = Math.max(0, Math.floor(s));
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    onTrackKeyChanged: {
        pos = 0;
        sync();
    }
    onExpandedChanged: if (expanded) sync()

    Mpris.Mpris2Model { id: mpris }
    Connections {
        target: card.player
        ignoreUnknownSignals: true
        function onPositionChanged() {
            if (card.player.position > 0)
                card.pos = card.player.position / 1e6;
        }
    }
    Timer {
        interval: 1000
        repeat: true
        running: card.expanded && card.playing && card.available
        onTriggered: card.pos = card.length > 0 ? Math.min(card.length, card.pos + 1) : card.pos + 1
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12

        Item {
            id: art
            implicitWidth: 64
            implicitHeight: 64
            // Spotify still hands out art links on a host that no longer serves them.
            readonly property string url: card.player ? String(card.player.artUrl)
                .replace("https://open.spotify.com/image/", "https://i.scdn.co/image/") : ""
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: Deck.raised
                visible: artImage.status !== Image.Ready
                DeckIcon {
                    anchors.centerIn: parent
                    name: "music"
                    color: Deck.muted
                    width: 24
                    height: 24
                }
            }
            Image {
                id: artImage
                anchors.fill: parent
                source: art.url
                sourceSize: Qt.size(128, 128)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: false
            }
            Rectangle {
                id: artMask
                anchors.fill: parent
                radius: 8
                visible: false
                layer.enabled: true
            }
            MultiEffect {
                anchors.fill: parent
                source: artImage
                maskEnabled: true
                maskSource: artMask
                visible: artImage.status === Image.Ready
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            DeckText {
                Layout.fillWidth: true
                text: ("Now playing" + (card.player && card.player.identity ? " · " + card.player.identity : "")).toUpperCase()
                font.pixelSize: 10
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Deck.muted
            }
            DeckText {
                Layout.fillWidth: true
                text: card.player ? card.player.track : ""
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            DeckText {
                Layout.fillWidth: true
                sub: true
                text: card.player ? card.player.artist : ""
            }
        }

        RowLayout {
            spacing: 4
            DeckButton {
                round: true
                flat: true
                icon: "previous"
                tip: "Previous"
                enabled: !!card.player && card.player.canGoPrevious
                onClicked: card.player.Previous()
            }
            DeckButton {
                round: true
                primary: true
                implicitHeight: 38
                iconSize: 18
                icon: card.playing ? "pause" : "play"
                tip: card.playing ? "Pause" : "Play"
                enabled: !!card.player && card.player.canControl
                onClicked: card.playing ? card.player.Pause() : card.player.Play()
            }
            DeckButton {
                round: true
                flat: true
                icon: "next"
                tip: "Next"
                enabled: !!card.player && card.player.canGoNext
                onClicked: card.player.Next()
            }
        }
    }

    RowLayout {
        visible: card.length > 0
        Layout.fillWidth: true
        spacing: 8
        DeckText {
            sub: true
            font.pixelSize: 11
            text: card.time(card.pos)
        }
        DeckSlider {
            Layout.fillWidth: true
            implicitHeight: 16
            to: card.length
            stepSize: 1
            value: card.pos
            Accessible.name: "Seek"
            // Seek once at the end of a drag; keys and the wheel seek right away.
            onMoved: v => {
                card.pos = v;
                if (!pressed)
                    card.player.position = v * 1e6;
            }
            onReleased: v => card.player.position = v * 1e6
        }
        DeckText {
            sub: true
            font.pixelSize: 11
            text: card.time(card.length)
        }
    }
}
