// Your library, sliding in from the left of the cover's screen (L, or the music button): albums from your Music
// folders; pick one and it plays here, and the stage takes its cover.
import QtQuick

Rectangle {
    id: drawer
    property bool open: false

    width: 460
    x: open ? 0 : -width - 20
    Behavior on x { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
    color: Qt.rgba(0.06, 0.07, 0.09, 0.82)
    border.color: Qt.rgba(1, 1, 1, 0.08)

    Text {
        id: heading
        x: 28
        y: 32
        text: "Your music"
        color: "white"
        font.family: "Inter Display"
        font.weight: Font.Bold
        font.pixelSize: 26
    }

    GridView {
        id: grid
        anchors.fill: parent
        anchors.topMargin: 84
        anchors.leftMargin: 20
        anchors.rightMargin: 12
        clip: true
        cellWidth: 210
        cellHeight: 262
        model: engine.albums
        delegate: Item {
            required property var modelData
            required property int index
            width: grid.cellWidth
            height: grid.cellHeight
            Column {
                x: 8
                spacing: 6
                Rectangle {
                    width: 190
                    height: 190
                    radius: 10
                    color: Qt.rgba(1, 1, 1, 0.06)
                    clip: true
                    scale: albumHover.hovered ? 1.04 : 1
                    Behavior on scale { NumberAnimation { duration: 140 } }
                    Image {
                        anchors.fill: parent
                        source: modelData.cover
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                    HoverHandler { id: albumHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: engine.playAlbum(index) }
                }
                Text {
                    width: 190
                    text: modelData.title
                    color: "white"
                    font.family: "Inter"
                    font.weight: Font.DemiBold
                    font.pixelSize: 14
                    elide: Text.ElideRight
                }
                Text {
                    width: 190
                    text: modelData.artist
                    color: Qt.rgba(1, 1, 1, 0.6)
                    font.family: "Inter"
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
            }
        }
    }

    Text {
        visible: grid.count === 0
        anchors.centerIn: parent
        width: parent.width - 60
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        text: "No music found yet. Put music in your Music folder (or a Music folder on any drive) and it shows up "
            + "here. Spotify and other players show on the stage by themselves."
        color: Qt.rgba(1, 1, 1, 0.6)
        font.family: "Inter"
        font.pixelSize: 15
    }
}
