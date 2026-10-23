import QtQuick
import org.kde.bluezqt as BluezQt
import org.kde.kcmutils as KCMUtils

// Bluetooth on/off the way Plasma's own applet does it: unblock rfkill, then power the adapters.
Tile {
    readonly property var manager: BluezQt.Manager
    readonly property bool isOn: manager.bluetoothOperational
    readonly property var connected: manager.connectedDevices

    readonly property bool available: manager.bluetoothBlocked || manager.adapters.length > 0
    icon: "bluetooth"
    title: "Bluetooth"
    checked: isOn
    subtitle: !isOn ? "Off"
              : connected.length === 1 ? connected[0].name
              : connected.length > 1 ? connected.length + " devices"
              : "On"
    hasMore: true
    onToggled: {
        const enable = !isOn;
        manager.bluetoothBlocked = !enable;
        for (const adapter of manager.adapters)
            adapter.powered = enable;
    }
    onMore: KCMUtils.KCMLauncher.openSystemSettings("kcm_bluetooth")
}
