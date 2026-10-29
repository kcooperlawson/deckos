// The song's lyrics, live (lyrics.py, followed by the engine 30 times a second). Big on a screen of their own when
// there are two or more monitors; a band of three lines under the cover on one. The line being sung fills with the
// Vibe's colours as it goes and pulses on the beat; when the song moves on the lines glide up, the old one fading
// above, the next one waiting below. A gap in the singing shows three dots; a song without timed lyrics scrolls
// them with the song; one without any shows its title instead.
import QtQuick
import QtQuick.Effects

Item {
    id: view
    property bool big: true        // a whole screen, or the band under the cover
    property real kick: 0          // the stage's beat, 1 on the beat and fading
    property real reveal: 1
    readonly property var lines: engine.lyricLines
    readonly property int index: engine.lyricIndex
    readonly property string state_: engine.lyricsState
    readonly property real lineHeight: height * (big ? 0.16 : 0.3)
    readonly property real mainSize: Math.min(height * (big ? 0.085 : 0.16), width * 0.06)
    opacity: reveal
    visible: state_ !== "off"

    // The glide: when the line changes, everything starts a line lower and slides up into place
    property real shift: 0
    onIndexChanged: { shift = lineHeight; glide.restart(); }
    NumberAnimation { id: glide; target: view; property: "shift"; to: 0; duration: 420; easing.type: Easing.OutCubic }

    function lineAt(k) {
        return k >= 0 && k < lines.length ? lines[k].text : "";
    }

    // Behind the words, so they read over any look (the busy ones too): the whole lyrics screen a little darker,
    // and a darker band where the lines are
    Rectangle {
        anchors.fill: parent
        visible: view.big && (view.state_ === "synced" || view.state_ === "plain")
        color: Qt.rgba(0, 0, 0, 0.3)
    }
    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        height: view.lineHeight * (view.big ? 5.6 : 3.0)  // every line shown sits on the dark part
        visible: view.state_ === "synced" || view.state_ === "plain"
        gradient: Gradient {
            GradientStop { position: 0; color: "transparent" }
            GradientStop { position: 0.12; color: Qt.rgba(0, 0, 0, 0.66) }
            GradientStop { position: 0.88; color: Qt.rgba(0, 0, 0, 0.66) }
            GradientStop { position: 1; color: "transparent" }
        }
    }

    // Every word gets a soft dark shadow round it (one effect over all the lines), its own contrast on any colour
    Item {
        id: words_
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "black"
            shadowOpacity: 0.95
            shadowBlur: 0.55
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 2
        }

    // ---- synced: the lines around the one being sung
    Repeater {
        model: view.state_ === "synced" ? (view.big ? [-2, -1, 0, 1, 2] : [-1, 0, 1]) : []
        Item {
            id: row
            required property int modelData
            readonly property int k: view.index + modelData
            readonly property bool now: modelData === 0
            readonly property string text: view.lineAt(k)
            width: view.width * 0.86
            height: view.lineHeight
            x: (view.width - width) / 2
            y: view.height / 2 - height / 2 + modelData * view.lineHeight + view.shift
            opacity: now ? 1 : Math.max(0, 0.62 - 0.2 * (Math.abs(modelData) - 1)) * (k >= 0 && k < view.lines.length ? 1 : 0)
            scale: now ? 1 + 0.035 * view.kick : 0.82
            Behavior on scale { NumberAnimation { duration: 90 } }

            // the words, dim, and over them the same words filling with colour as they're sung (written out twice:
            // an inline component couldn't see row and view)
            Text {
                id: words
                anchors.fill: parent
                text: row.text
                color: row.now ? Qt.rgba(1, 1, 1, 0.75) : "white"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: 12
                font.pixelSize: row.now ? view.mainSize : view.mainSize * 0.7
                font.family: "Inter Display"
                font.weight: row.now ? Font.Bold : Font.DemiBold
            }
            Item {  // the sung part: the line's width so far, in the Vibe's colours
                visible: row.now && row.text !== ""
                x: (row.width - words.contentWidth) / 2
                width: words.contentWidth * engine.lyricThrough
                height: parent.height
                clip: true
                Text {
                    x: -parent.x
                    width: row.width
                    height: row.height
                    text: row.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: 12
                    font: words.font
                    layer.enabled: true
                    layer.effect: ShaderEffect {
                        // lighter than the look's own colours, so the sung words never match what's behind them
                        property color a: Qt.lighter(engine.accent, 1.35)
                        property color b: Qt.lighter(engine.second, 1.45)
                        fragmentShader: "fill.frag.qsb"
                    }
                }
            }
            // a gap in the singing: three dots, bouncing on the beat
            Row {
                visible: row.now && row.text === "" && view.index >= 0
                anchors.centerIn: parent
                spacing: view.mainSize * 0.4
                Repeater {
                    model: 3
                    Rectangle {
                        required property int index
                        width: view.mainSize * 0.28
                        height: width
                        radius: width / 2
                        color: index === 1 ? engine.second : engine.accent
                        y: -view.mainSize * 0.25 * view.kick * (1 - Math.abs(index - 1) * 0.4)
                    }
                }
            }
        }
    }
    // before the first line: what's coming
    Text {
        visible: view.state_ === "synced" && view.index < 0
        anchors.centerIn: parent
        text: view.lineAt(0)
        color: Qt.rgba(1, 1, 1, 0.5)
        font.family: "Inter Display"
        font.weight: Font.DemiBold
        font.pixelSize: view.mainSize * 0.7
        width: parent.width * 0.86
        horizontalAlignment: Text.AlignHCenter
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: 12
    }

    }

    // ---- lyrics without times: shown whole, scrolling along with the song
    Item {
        visible: view.state_ === "plain"
        anchors.fill: parent
        clip: true
        Text {
            id: plain
            width: parent.width * 0.8
            x: parent.width * 0.1
            property real through: 0  // how far into the song (the engine's position is read, not bound)
            y: parent.height * 0.45 - (height - parent.height * 0.2) * through
            text: engine.lyricsPlain
            color: Qt.rgba(1, 1, 1, 0.85)
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            lineHeight: 1.25
            font.family: "Inter Display"
            font.weight: Font.DemiBold
            font.pixelSize: view.mainSize * 0.55
            Timer {
                interval: 1000; repeat: true; running: plain.visible; triggeredOnStart: true
                onTriggered: plain.through = engine.length > 0 ? Math.min(1, engine.position() / engine.length) : 0
            }
            Behavior on y { NumberAnimation { duration: 1000 } }
        }
    }

    // ---- nothing to sing along to (big screen only: the band just stays empty)
    Column {
        visible: view.big && (view.state_ === "none" || view.state_ === "loading")
        anchors.centerIn: parent
        width: parent.width * 0.8
        spacing: view.mainSize * 0.25
        Text {
            width: parent.width
            text: engine.title
            color: "white"
            horizontalAlignment: Text.AlignHCenter
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 14
            font.family: "Chakra Petch"
            font.weight: Font.DemiBold
            font.pixelSize: view.mainSize * 1.3
        }
        Text {
            width: parent.width
            text: engine.artist
            color: Qt.rgba(1, 1, 1, 0.7)
            horizontalAlignment: Text.AlignHCenter
            font.family: "Inter Display"
            font.pixelSize: view.mainSize * 0.55
        }
        Text {
            width: parent.width
            text: view.state_ === "loading" ? "Finding the lyrics…" : "No lyrics for this song"
            color: Qt.rgba(1, 1, 1, 0.45)
            horizontalAlignment: Text.AlignHCenter
            font.family: "Chakra Petch"
            font.letterSpacing: 3
            font.capitalization: Font.AllUppercase
            font.pixelSize: view.mainSize * 0.28
        }
    }
}
