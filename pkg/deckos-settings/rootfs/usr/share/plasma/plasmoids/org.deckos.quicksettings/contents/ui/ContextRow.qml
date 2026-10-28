import QtQuick
import QtQuick.Layouts

// DecKoOS Context (deckos-context.service): what DecKoOS thinks you're doing and why, and a quick way to correct it.
// A pick lasts an hour; Automatic hands it back. Gaming isn't offered: workload modes find games themselves.
ColumnLayout {
    id: ctx
    property var backend
    property bool picking: false
    readonly property var choices: [["developing", "Developing", "code"], ["listening", "Listening", "volume"],
        ["watching", "Watching", "play"], ["desktop", "Just the desktop", "appearance"]]
    spacing: 8

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Rectangle {
            implicitWidth: 34
            implicitHeight: 34
            radius: 9
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Deck.accent }
                GradientStop { position: 1; color: Deck.accentB }
            }
            DeckIcon {
                anchors.centerIn: parent
                width: 18
                height: 18
                name: ctx.backend.activityIcon || "appearance"
                color: "white"
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            DeckText {
                Layout.fillWidth: true
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                text: ctx.backend.activityLabel
            }
            DeckText {
                Layout.fillWidth: true
                sub: true
                wrapMode: Text.Wrap
                maximumLineCount: 2
                text: ctx.backend.activityWhy.charAt(0).toUpperCase() + ctx.backend.activityWhy.slice(1)
            }
        }
        DeckButton {
            flat: true
            text: ctx.picking ? "Close" : "Not right?"
            onClicked: ctx.picking = !ctx.picking
        }
    }
    Flow {
        visible: ctx.picking
        Layout.fillWidth: true
        spacing: 6
        Repeater {
            model: ctx.choices
            DeckButton {
                required property var modelData
                text: modelData[1]
                flat: ctx.backend.activity !== modelData[0]
                onClicked: { ctx.backend.setActivity(modelData[0]); ctx.picking = false; }
            }
        }
        DeckButton {
            visible: ctx.backend.activityPinned
            flat: true
            text: "Automatic"
            onClicked: { ctx.backend.setActivity("auto"); ctx.picking = false; }
        }
    }
}
