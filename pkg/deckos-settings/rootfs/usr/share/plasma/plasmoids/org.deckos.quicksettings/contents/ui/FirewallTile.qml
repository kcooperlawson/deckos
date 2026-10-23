import QtQuick
import org.kde.plasma.workspace.dbus as DBus

// firewalld is on exactly when its D-Bus name is up, so watching that costs nothing.
SmallTile {
    property var backend
    property bool working: false
    readonly property bool isOn: watcher.registered

    icon: isOn ? "shield" : "shield-off"
    title: "Firewall"
    subtitle: isOn ? "On" : "Off"
    tone: isOn ? "ok" : "bad"
    busy: working
    onClicked: {
        working = true;
        backend.run("pkexec systemctl " + (isOn ? "disable" : "enable") + " --now firewalld", () => working = false);
    }

    DBus.DBusServiceWatcher {
        id: watcher
        busType: DBus.BusType.System
        watchedService: "org.fedoraproject.FirewallD1"
    }
}
