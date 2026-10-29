import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

// The update count from `deckos updates` (cached; checked in the background every few hours).
RowLayout {
    id: row
    property var backend
    readonly property int count: backend.updateCount
    spacing: 10

    function ago(epoch: real): string {
        const m = Math.round((Date.now() / 1000 - epoch) / 60);
        return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago"
             : Math.round(m / 1440) + " d ago";
    }

    Vibes.Notch {  // the DecKo icon chip, filled with the gradient when it's on
        implicitWidth: 38
        implicitHeight: 38
        look: Deck.look
        cut: 8
        lit: false
        edge: 0
        fill: Deck.raised
        gradientFill: row.count > 0
        DeckIcon {
            anchors.centerIn: parent
            width: 18
            height: 18
            name: "update"
            color: row.count > 0 ? Deck.ink : Deck.subtext
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 1
        DeckText {
            Layout.fillWidth: true
            font.weight: Font.DemiBold
            text: row.backend.updateError ? "Couldn't check for updates"
                  : row.backend.updatesText || "Updates"
        }
        DeckText {
            Layout.fillWidth: true
            sub: true
            text: {
                const b = row.backend;
                if (b.checking)
                    return "Checking…";
                if (b.updateError)
                    return b.updateError;
                if (b.repoUpdates < 0)
                    return "Not checked yet";
                if (row.count > 0) {
                    const parts = [];
                    if (b.repoUpdates > 0)
                        parts.push(b.repoUpdates + " from Arch and CachyOS");
                    if (b.aurUpdates > 0)
                        parts.push(b.aurUpdates + " from the AUR");
                    return parts.join(", ");
                }
                return "Checked " + row.ago(b.checkedAt);
            }
        }
    }
    DeckButton {
        visible: row.count > 0
        primary: true
        text: "Update now"
        // Repo updates run in the Hub with its progress bar; AUR-only ones need its terminal button.
        onClicked: row.backend.openHub("system", row.backend.repoUpdates > 0)
    }
    DeckButton {
        visible: row.count === 0
        round: true
        flat: true
        icon: "refresh"
        tip: "Check now"
        enabled: !row.backend.checking
        onClicked: row.backend.check(0)
    }
}
