import QtQuick
import org.kde.kcmutils as KCMUtils
import org.kde.plasma.workspace.dbus as DBus

// Night light straight from KWin over D-Bus: pausing and resuming the schedule set in System
// Settings. Not set up yet: the tile opens the Night Light page.
Tile {
    readonly property var p: kwin.properties
    readonly property bool setUp: Boolean(p.enabled)
    // Plasma 6.9 adds deactivateManual(); before that, pausing is inhibit()/uninhibit(cookie).
    readonly property bool hasManual: p.deactivatedManual !== undefined
    readonly property bool paused: Boolean(p.inhibited) || Boolean(p.deactivatedManual) || Number(p.deactivatedUntil) > 0
    property int cookie: -1

    icon: "night"
    title: "Night light"
    checked: setUp && !paused
    subtitle: !setUp ? "Not set up"
              : paused ? "Paused"
              : p.daylight && !p.activatedManual && !Number(p.activatedUntil) ? "From sunset"
              : Number(p.currentTemperature) + " K"
    hasMore: true
    onMore: KCMUtils.KCMLauncher.openSystemSettings("kcm_nightlight")
    onToggled: {
        if (!setUp) {
            KCMUtils.KCMLauncher.openSystemSettings("kcm_nightlight");
        } else if (hasManual) {
            if (Number(p.deactivatedUntil) > 0)
                call("deactivateUntil", "(t)", [0]);
            else
                call("deactivateManual", "(b)", [!paused]);
        } else if (!paused) {
            call("inhibit", "", [], reply => cookie = Number(reply.value));
        } else if (cookie >= 0) {
            call("uninhibit", "(u)", [cookie]);
            cookie = -1;
        } else {
            KCMUtils.KCMLauncher.openSystemSettings("kcm_nightlight");  // paused by someone else
        }
    }

    function call(member: string, signature: string, args, done): void {
        const msg = {
            service: "org.kde.KWin.NightLight",
            path: "/org/kde/KWin/NightLight",
            iface: "org.kde.KWin.NightLight",
            member: member,
            arguments: args,
        };
        if (signature)
            msg.signature = signature;
        DBus.SessionBus.asyncCall(msg, done || (() => {}), error => console.warn("Night light:", member, "failed"));
    }

    DBus.Properties {
        id: kwin
        busType: DBus.BusType.Session
        service: "org.kde.KWin.NightLight"
        path: "/org/kde/KWin/NightLight"
        iface: "org.kde.KWin.NightLight"
    }
}
