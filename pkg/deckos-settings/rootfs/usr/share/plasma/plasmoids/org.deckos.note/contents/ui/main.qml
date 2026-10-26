// DecKoOS Note: a note on the desktop in the Vibe's type, saved as you type. Empty, it shows a thought for the day
// (old, public-domain words; one per day, the same all day).
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: note

    Vibes.Look {
        id: look
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    readonly property var thoughts: [
        ["Well begun is half done.", "Aristotle"],
        ["Nothing will come of nothing.", "Shakespeare"],
        ["The journey of a thousand miles begins with one step.", "Lao Tzu"],
        ["Simplicity is the ultimate sophistication.", "proverb"],
        ["Nature does not hurry, yet everything is accomplished.", "Lao Tzu"],
        ["What we think, we become.", "the Dhammapada"],
        ["Knowing yourself is the beginning of all wisdom.", "Aristotle"],
        ["It does not matter how slowly you go, so long as you do not stop.", "after Confucius"],
        ["Be kind, for everyone you meet is fighting a hard battle.", "proverb"],
        ["The best time to plant a tree was twenty years ago. The second best time is now.", "proverb"],
        ["Rest is not idleness.", "John Lubbock"],
        ["Where there is love there is life.", "proverb"],
        ["Fortune favours the bold.", "Virgil"],
        ["Little by little, one travels far.", "proverb"]
    ]
    readonly property var today: thoughts[Math.floor(Date.now() / 86400000) % thoughts.length]

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 220
    Layout.preferredWidth: 300
    Layout.preferredHeight: 180
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    Vibes.Plate { anchors.fill: parent; look: look }

    TextEdit {
        id: edit
        anchors.fill: parent
        anchors.margins: 18
        text: Plasmoid.configuration.text
        wrapMode: TextEdit.Wrap
        color: look.text
        font.family: look.family
        font.italic: look.italic
        font.pixelSize: 18
        selectByMouse: true
        onTextChanged: if (text !== Plasmoid.configuration.text) save.restart()
        Timer {  // saved a moment after the last key, not on every key
            id: save
            interval: 800
            onTriggered: Plasmoid.configuration.text = edit.text
        }
    }
    ColumnLayout {  // the thought for the day, while the note is empty
        visible: edit.text === "" && !edit.activeFocus
        anchors.fill: parent
        anchors.margins: 18
        Vibes.VibeText {
            look: look
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: "“" + note.today[0] + "”"
            font.pixelSize: 19
        }
        Vibes.VibeText {
            look: look
            soft: true
            text: "— " + note.today[1]
            font.pixelSize: 13
        }
        Item { Layout.fillHeight: true }
        Vibes.VibeText {
            look: look
            soft: true
            text: "Click to write a note"
            font.pixelSize: 11
        }
    }
}
