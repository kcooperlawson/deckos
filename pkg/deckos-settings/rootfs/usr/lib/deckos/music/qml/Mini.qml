// The small player: your own music keeps playing after you leave the stage. Vibe mode goes back in; closing it
// stops the music.
import QtQuick
import QtQuick.Window

Window {
    id: mini
    visible: engine.mode === "mini"
    width: 460
    height: 132
    minimumWidth: 400
    minimumHeight: 132
    title: "DecKoOS Music"
    color: "#0F1115"
    onClosing: engine.quit()

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.darker(engine.base, 1.2) }
            GradientStop { position: 1; color: "#0F1115" }
        }
    }
    Row {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 14
        Rectangle {
            width: 100
            height: 100
            radius: 10
            clip: true
            color: Qt.rgba(1, 1, 1, 0.06)
            Image { anchors.fill: parent; source: engine.art; fillMode: Image.PreserveAspectCrop }
        }
        Column {
            width: parent.width - 114
            spacing: 4
            Text {
                width: parent.width
                text: engine.title || "Nothing playing"
                color: "white"
                font.family: "Inter"
                font.weight: Font.Bold
                font.pixelSize: 16
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                text: engine.artist
                color: Qt.rgba(1, 1, 1, 0.6)
                font.family: "Inter"
                font.pixelSize: 13
                elide: Text.ElideRight
            }
            Row {
                spacing: 10
                topPadding: 8
                IconButton { icon: "previous"; size: 40; onClicked: engine.previous() }
                IconButton { icon: engine.playing ? "pause" : "play"; size: 40; filled: true; onClicked: engine.playPause() }
                IconButton { icon: "next"; size: 40; onClicked: engine.next() }
                Rectangle {
                    width: vibeLabel.implicitWidth + 28
                    height: 40
                    radius: 20
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: engine.accent }
                        GradientStop { position: 1; color: engine.second }
                    }
                    Text {
                        id: vibeLabel
                        anchors.centerIn: parent
                        text: "Vibe mode"
                        color: "white"
                        font.family: "Inter"
                        font.weight: Font.DemiBold
                        font.pixelSize: 13
                    }
                    TapHandler { onTapped: engine.enter() }
                }
            }
        }
    }
}
