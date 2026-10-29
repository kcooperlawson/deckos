import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

// Workload modes from `deckos quick-status`: what deckos-modes.service freed for the game running now.
RowLayout {
    id: row
    property var backend
    readonly property bool gaming: backend.modeAuto && backend.mode === "gaming"
    spacing: 10

    Vibes.Notch {  // the DecKo icon chip, filled with the gradient when it's on
        implicitWidth: 38
        implicitHeight: 38
        look: Deck.look
        cut: 8
        lit: false
        edge: 0
        fill: Deck.raised
        gradientFill: row.gaming
        DeckIcon {
            anchors.centerIn: parent
            width: 18
            height: 18
            name: "gaming"
            color: row.gaming ? Deck.ink : Deck.subtext
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 1
        DeckText {
            Layout.fillWidth: true
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            text: !row.backend.modeAuto ? "Workload modes are off"
                  : row.gaming ? "Playing " + row.backend.modeGame : "Ready for games"
        }
        DeckText {
            Layout.fillWidth: true
            sub: true
            wrapMode: Text.Wrap
            maximumLineCount: 2
            text: {
                const b = row.backend;
                if (!b.modeAuto)
                    return "Games share the graphics card with Ollama and Docker";
                if (!row.gaming)
                    return "When a game starts, DecKoOS frees graphics memory and pauses background work";
                const parts = [];
                if (b.modeVram > 0)
                    parts.push((b.modeVram / 1e9).toFixed(1) + " GB of graphics memory freed");
                if (b.modeContainers > 0)
                    parts.push(b.modeContainers + (b.modeContainers === 1 ? " container" : " containers") + " paused");
                if (b.modeIndexing)
                    parts.push("indexing paused");
                return parts.length ? parts.join(" · ") : "Nothing in the background needed pausing";
            }
        }
    }
    DeckButton {
        visible: !row.backend.modeAuto
        text: "Turn on"
        onClicked: row.backend.setModes(true)
    }
    DeckButton {
        visible: row.backend.modeAuto && !row.gaming
        flat: true
        text: "Turn off"
        onClicked: row.backend.setModes(false)
    }
}
