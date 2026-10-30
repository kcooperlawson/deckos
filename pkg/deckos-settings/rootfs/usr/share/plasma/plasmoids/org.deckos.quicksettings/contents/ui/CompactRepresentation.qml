import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris
import org.deckos.vibes as Vibes

// The panel button: the sliders icon on a notched plate (when pointed at or open), a badge when updates are
// waiting, and while music plays a small live spectrum beside it (deckos-visualizer; it listens only then).
MouseArea {
    id: compact
    property var backend
    property bool expanded: false
    property bool vertical: false
    property bool wasExpanded: false
    signal activated(bool open)

    Layout.minimumWidth: vertical ? -1 : height + (playing ? bars.width + 6 : 0)
    Layout.preferredWidth: Layout.minimumWidth
    Layout.minimumHeight: vertical ? width : -1
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton
    onPressed: wasExpanded = expanded
    onClicked: activated(!wasExpanded)

    Accessible.role: Accessible.Button
    Accessible.name: "Quick settings"
    Accessible.description: backend.updatesText

    Mpris.Mpris2Model { id: mpris }
    readonly property bool playing: !vertical && !!mpris.currentPlayer
                                    && mpris.currentPlayer.playbackStatus === Mpris.PlaybackStatus.Playing
    Vibes.Levels { id: levels; active: compact.playing }

    // The tray island: one notched plate from here over everything after it in the panel (Plasma's tray and
    // clock), which Plasma draws on top. Found through our place in the panel's layout; on a vertical panel, or
    // anywhere else, it's just this button's own.
    property Item container: null
    function findContainer() {
        let it = compact;
        while (it && it.parent && !String(it.parent).startsWith("QQuickGridLayout"))
            it = it.parent;
        container = it && it.parent ? it : null;
    }
    Component.onCompleted: Qt.callLater(findContainer)
    readonly property real endPad: 10
    readonly property real islandWidth: {
        if (vertical || !container || !container.parent)
            return width;
        let right = 0;
        for (const c of container.parent.children)
            if (c.visible && c.width > 0 && String(c).startsWith("AppletContainer"))
                right = Math.max(right, c.x + c.width);
        // past the last one a little: the clock's digits run to its very edge, and the notch cuts in there
        return right > container.x + width ? right - container.x + endPad : width;
    }
    Vibes.Notch {
        x: 0
        y: 3
        width: compact.islandWidth
        height: compact.height - 6
        look: Deck.look
        cut: 12
        fill: Deck.look.glass
    }
    Vibes.Notch {  // pointed at or open: this button's own plate inside the island
        visible: compact.containsMouse || compact.expanded
        anchors.fill: parent
        anchors.margins: 7
        look: Deck.look
        cut: 7
        lit: false
        edge: 0
        fill: compact.expanded ? Deck.tint : Deck.hover
    }
    Row {  // the music, while it plays
        id: bars
        visible: compact.playing
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        height: 22
        spacing: 2
        Repeater {
            model: 7
            Rectangle {
                required property int index
                readonly property var l: levels.levels
                // seven bands from bass to treble, out of the service's bars
                readonly property real level: l.length ? l[Math.min(l.length - 1, Math.floor(Math.pow(index / 7, 1.6) * l.length))] : 0
                width: 3
                height: Math.max(3, bars.height * level)
                anchors.bottom: parent.bottom
                color: Deck.look.mix(index / 6)
                Behavior on height { NumberAnimation { duration: 90 } }
            }
        }
    }
    DeckIcon {
        id: icon
        // centred, or in the square at the right end while the music shows beside it
        x: compact.playing ? compact.width - (compact.height + width) / 2 : (compact.width - width) / 2
        anchors.verticalCenter: parent.verticalCenter
        readonly property int size: Math.min(compact.width, compact.height)
        width: size >= 32 ? 22 : 16  // icon sizes Plasma's own panel icons use
        height: width
        name: "sliders"
        color: compact.containsMouse || compact.expanded ? Deck.accent : Kirigami.Theme.textColor
    }
    Rectangle {
        visible: compact.backend.updateCount > 0
        anchors.left: icon.horizontalCenter
        anchors.bottom: icon.verticalCenter
        anchors.leftMargin: 2
        anchors.bottomMargin: 2
        height: 15
        width: Math.max(height, badgeText.implicitWidth + 8)
        color: Deck.accent
        border.width: 2
        border.color: Deck.bg
        Text {
            id: badgeText
            anchors.centerIn: parent
            text: compact.backend.updateCount > 99 ? "99+" : compact.backend.updateCount
            color: Deck.ink
            font.family: Deck.hud
            font.pixelSize: 10
            font.weight: Font.Bold
        }
    }
}
