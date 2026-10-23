/* DeckOS install slideshow: drawn in QML (no images) so it stays sharp at any resolution.
   One card per slide, Steady Downloader style, with a gradient accent and a thin progress strip. */

import QtQuick
import calamares.slideshow 1.0

Presentation {
    id: presentation

    readonly property color bg: "#0F1115"
    readonly property color surface: "#171A21"
    readonly property color border: "#262B36"
    readonly property color text: "#E8EAF0"
    readonly property color subtext: "#8C94A6"
    readonly property color accentA: "#4C8DFF"
    readonly property color accentB: "#7A5CFF"

    Timer {
        interval: 12000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    component DeckSlide: Slide {
        id: s
        property string kicker
        property string title
        property string body
        property var points: []

        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: presentation.bg }

        // The DeckOS wallpaper (neon thumbstick, streaks), dimmed behind the card.
        Image {
            anchors.fill: parent
            source: "file:///usr/share/deckos/branding/wallpaper-1920.png"
            fillMode: Image.PreserveAspectCrop
            opacity: 0.55
            asynchronous: true
        }

        Rectangle {
            id: card
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, 760)
            height: col.implicitHeight + 64
            radius: 12
            color: presentation.surface
            border.color: presentation.border

            Rectangle {  // gradient accent bar
                x: 32; y: 0; width: 56; height: 3; radius: 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: presentation.accentA }
                    GradientStop { position: 1; color: presentation.accentB }
                }
            }

            Column {
                id: col
                x: 32; y: 32
                width: card.width - 64
                spacing: 10

                Text { text: s.kicker.toUpperCase(); color: presentation.subtext; font.pixelSize: 12; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                Text { text: s.title; color: presentation.text; font.family: "Inter Display"; font.pixelSize: 30; font.weight: Font.DemiBold; wrapMode: Text.WordWrap; width: parent.width }
                Text { text: s.body; color: presentation.subtext; font.pixelSize: 15; lineHeight: 1.35; wrapMode: Text.WordWrap; width: parent.width }
                Item { width: 1; height: 6 }
                Repeater {
                    model: s.points
                    delegate: Row {
                        spacing: 10
                        Rectangle { width: 6; height: 6; radius: 3; color: presentation.accentA; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: modelData; color: presentation.text; font.pixelSize: 14 }
                    }
                }
            }
        }
    }

    DeckSlide {
        kicker: "Installing DeckOS"
        title: "Built for your 7800X3D and RX 9070 XT"
        body: "DeckOS runs the CachyOS kernel and, once online, packages compiled specifically for Zen 4 — so the same games and models run faster than on a generic build."
        points: ["Zen 4-optimised packages and kernel", "Mesa RADV for the RX 9070 XT", "Compressed RAM swap, tuned scheduler"]
    }
    DeckSlide {
        kicker: "Gaming"
        title: "Steam Gaming Mode, built in"
        body: "Switch from the desktop to a console-style Steam Big Picture on the Samsung at 4K 144 Hz with one click — and back from Steam's Power menu."
        points: ["Proton-CachyOS and GE-Proton", "MangoHud overlay, GameMode", "Xbox Wireless Adapter driver"]
    }
    DeckSlide {
        kicker: "Your drives"
        title: "Your Windows drives, untouched"
        body: "Your Windows, SSD and BIG drives stay NTFS and open read/write in Dolphin and Steam. Nothing was reformatted. Your Steam library on D: works too."
        points: ["/mnt/Windows, /mnt/SSD, /mnt/BIG", "deckos steam-ntfs for Proton games on NTFS"]
    }
    DeckSlide {
        kicker: "Display"
        title: "A fix for the Samsung blackouts"
        body: "The flicker fix you chose is applied before the first boot. If the Odyssey still blinks, step up a level in DeckOS Hub › Display and reboot."
        points: ["Watch mode logs exactly what happened", "Levels 0–4, changeable any time"]
    }
    DeckSlide {
        kicker: "Safety net"
        title: "Every update is a snapshot"
        body: "Before and after each update, DeckOS takes a btrfs snapshot. If something breaks, pick “DeckOS snapshots” in the boot menu and start yesterday's system."
        points: ["Boot menu with DeckOS, Windows and snapshots", "Btrfs Assistant to browse and restore"]
    }
    DeckSlide {
        kicker: "AI and modding"
        title: "Claude Code, local models, your tools"
        body: "Claude Code is ready in the terminal. Ollama runs models on the GPU through ROCm. VS Code, JetBrains Toolbox, Docker and .NET are a tick away."
        points: ["claude — in any project folder", "ollama run qwen3", "DeckOS Hub for everything else"]
    }

    function onActivate() { presentation.currentSlide = 0 }
    function onLeave() { }
}
