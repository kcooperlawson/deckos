import QtQuick
import org.deckos.vibes as Vibes
import QtQuick.Layouts

// The display fix ladder (`deckos display`), opened from the Display fix tile. A new level needs a
// restart; the Hub's Display page has the full explanations and the blackout watcher.
ColumnLayout {
    id: picker
    property var backend
    property int pending: -1  // level being saved
    property int saved: -1    // level saved this session, waiting for a restart
    property bool failed: false
    readonly property var levels: [
        ["Stock", "AMD defaults, no workarounds."],
        ["No FAMS", "No firmware memory-clock switching: the usual cause of 1–2 s blackouts."],
        ["Pinned VRAM clock", "Level 1, plus the VRAM clock locked to max. ~15–30 W more at idle."],
        ["No multi-monitor switching", "Level 2, plus no multi-monitor clock switching, PSR or Panel Replay."],
        ["Locked high", "Every GPU clock forced high. Last resort."],
    ]
    readonly property int shownLevel: pending >= 0 ? pending : backend.displayLevel

    spacing: 6

    function choose(n: int): void {
        if (n === backend.displayLevel || pending >= 0)
            return;
        pending = n;
        failed = false;
        backend.run("pkexec deckos display set " + n, code => {
            if (code === 0) {
                backend.displayLevel = n;
                saved = n;
            } else {
                failed = true;
            }
            pending = -1;
        });
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        Repeater {
            model: 5
            delegate: Item {
                id: chip
                required property int index
                readonly property bool current: picker.shownLevel === index
                Layout.fillWidth: true
                implicitHeight: 30
                Vibes.Notch {
                    anchors.fill: parent
                    look: Deck.look
                    cut: 7
                    lit: false
                    fill: chipMouse.containsMouse && !chip.current ? Deck.hover : Deck.raised
                    gradientFill: chip.current
                }
                opacity: picker.pending >= 0 && !current ? 0.5 : 1
                Accessible.role: Accessible.RadioButton
                Accessible.name: "Level " + index + ": " + picker.levels[index][0]
                Accessible.checked: current
                DeckText {
                    anchors.centerIn: parent
                    text: chip.index
                    font.weight: Font.DemiBold
                    font.family: Deck.hud
                    color: chip.current ? Deck.ink : Deck.text
                }
                MouseArea {
                    id: chipMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: picker.choose(chip.index)
                }
            }
        }
    }
    DeckText {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        maximumLineCount: 3
        sub: true
        text: {
            if (picker.failed)
                return "Not changed.";
            if (picker.pending >= 0)
                return "Saving level " + picker.pending + "…";
            const l = picker.levels[Math.max(0, picker.shownLevel)];
            return l[0] + ": " + l[1] + (picker.saved >= 0 ? " Restart to use it." : "");
        }
        color: picker.failed ? Deck.danger : picker.saved >= 0 && picker.pending < 0 ? Deck.warning : Deck.subtext
    }
    DeckButton {
        flat: true
        icon: "external"
        text: "More in DecKoOS Hub"
        Layout.alignment: Qt.AlignRight
        onClicked: picker.backend.openHub("display", false)
    }
}
