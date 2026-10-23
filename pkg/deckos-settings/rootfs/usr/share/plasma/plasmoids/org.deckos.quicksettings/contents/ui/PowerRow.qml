import QtQuick
import QtQuick.Layouts
import org.kde.plasma.private.battery
import org.kde.plasma.private.batterymonitor

// Power profile (power-profiles-daemon) and, on laptops, the battery. Hidden when there's neither.
RowLayout {
    id: row
    readonly property var profileList: profiles.profiles
    readonly property bool hasProfiles: profileList.length > 0
    readonly property bool hasBattery: battery.hasInternalBatteries
    readonly property bool available: hasProfiles || hasBattery
    readonly property var names: ({ "power-saver": "Saver", "balanced": "Balanced", "performance": "Performance" })

    function batteryText(): string {
        let s = battery.percent + "%";
        if (battery.state === BatteryControlModel.Charging)
            return s + " · charging";
        if (battery.pluggedIn)
            return s + " · plugged in";
        const mins = Math.round(battery.smoothedRemainingMsec / 60000);
        if (mins > 0)
            s += " · " + (mins >= 60 ? Math.floor(mins / 60) + " h " : "") + (mins % 60) + " min left";
        return s;
    }

    spacing: 8

    PowerProfilesControl {
        id: profiles
        isSilent: true
    }
    BatteryControlModel { id: battery }

    DeckIcon {
        name: row.hasBattery ? (battery.pluggedIn ? "battery-charging" : "battery") : "power"
        implicitWidth: 18
        implicitHeight: 18
        color: row.hasBattery && battery.percent <= 15 && !battery.pluggedIn ? Deck.danger : Deck.text
    }
    DeckText {
        Layout.fillWidth: true
        text: row.hasBattery ? row.batteryText() : "Power"
        sub: !row.hasBattery
    }

    Rectangle {  // segmented profile switch
        visible: row.hasProfiles
        implicitWidth: segments.implicitWidth + 4
        implicitHeight: 30
        radius: 8
        color: Deck.bg
        border.width: 1
        border.color: Deck.border
        Row {
            id: segments
            anchors.centerIn: parent
            spacing: 2
            Repeater {
                model: ["power-saver", "balanced", "performance"].filter(p => row.profileList.includes(p))
                delegate: Rectangle {
                    id: seg
                    required property string modelData
                    readonly property bool current: profiles.activeProfile === modelData
                    width: label.implicitWidth + 18
                    height: 26
                    radius: 6
                    color: segMouse.containsMouse && !current ? Deck.hover : "transparent"
                    gradient: current ? segGrad : null
                    Gradient {
                        id: segGrad
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: Deck.accent }
                        GradientStop { position: 1; color: Deck.accentB }
                    }
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: label.text
                    Accessible.checked: current
                    DeckText {
                        id: label
                        anchors.centerIn: parent
                        text: row.names[seg.modelData]
                        font.pixelSize: 12
                        font.weight: seg.current ? Font.DemiBold : Font.Normal
                        color: seg.current ? "white" : Deck.subtext
                    }
                    MouseArea {
                        id: segMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (!seg.current) profiles.setProfile(seg.modelData)
                    }
                }
            }
        }
    }
}
