import QtQuick
import org.kde.kcmutils as KCMUtils
import org.kde.plasma.networkmanagement as PlasmaNM

// Wi-Fi on/off through plasma-nm. Without a Wi-Fi card it's a status tile for the wired network.
Tile {
    id: tile
    readonly property bool hasWifi: devices.wirelessDeviceAvailable && nm.wirelessHwEnabled
    // NetworkStatus lists "Wi-Fi: Connected to Home" lines, one per active connection.
    readonly property var connections: status.activeConnections.split("\n").filter(l => l.includes(": "))
    readonly property string wifiLine: connections.find(l => /^(Wi-?Fi|Wireless)/i.test(l)) || ""

    function networkName(line: string): string {
        const s = line.slice(line.indexOf(": ") + 2);
        const m = s.match(/^(?:Connected to|Connecting to) (.*?)(?: \((?:no|limited|log in).*\))?$/);
        return m ? m[1] : s;
    }

    icon: hasWifi && !nm.wirelessEnabled ? "wifi-off" : hasWifi ? "wifi" : "globe"
    title: hasWifi ? "Wi-Fi" : "Network"
    checked: hasWifi ? nm.wirelessEnabled : connections.length > 0
    subtitle: {
        if (hasWifi && !nm.wirelessEnabled)
            return "Off";
        const line = hasWifi ? wifiLine : connections[0] || "";
        if (line)
            return (line.includes("Connecting to") ? "Connecting to " : "") + networkName(line);
        return "Not connected";
    }
    hasMore: true
    onToggled: {
        if (hasWifi)
            handler.enableWireless(!nm.wirelessEnabled);
        else
            KCMUtils.KCMLauncher.openSystemSettings("kcm_networkmanagement");
    }
    onMore: KCMUtils.KCMLauncher.openSystemSettings("kcm_networkmanagement")

    PlasmaNM.EnabledConnections { id: nm }
    PlasmaNM.AvailableDevices { id: devices }
    PlasmaNM.NetworkStatus { id: status }
    PlasmaNM.Handler { id: handler }
}
