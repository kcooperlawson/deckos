import QtQuick
import org.kde.notificationmanager as NotificationManager

// Do Not Disturb, sharing Plasma's notification settings (the notifications applet sees the change).
Tile {
    readonly property date until: settings.notificationsInhibitedUntil
    readonly property bool timed: !isNaN(until.getTime()) && until.getTime() > Date.now()
    readonly property bool isOn: timed || settings.notificationsInhibitedByApplication

    icon: isOn ? "bell-off" : "bell"
    title: "Do not disturb"
    checked: isOn
    subtitle: !isOn ? "Off"
              : settings.notificationsInhibitedByApplication && !timed ? "On while an app asks"
              : until.getTime() - Date.now() < 24 * 3600 * 1000 ? "Until " + until.toLocaleTimeString(Qt.locale(), Locale.ShortFormat)
              : "On"
    onToggled: {
        if (isOn) {
            settings.notificationsInhibitedUntil = undefined;
            settings.revokeApplicationInhibitions();
        } else {
            // Plasma's own "until turned off" is a year from now.
            const d = new Date();
            d.setFullYear(d.getFullYear() + 1);
            settings.notificationsInhibitedUntil = d;
        }
        settings.save();
    }

    NotificationManager.Settings { id: settings }
}
