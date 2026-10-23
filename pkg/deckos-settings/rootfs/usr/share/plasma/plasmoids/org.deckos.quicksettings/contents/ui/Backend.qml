import QtQuick
import org.kde.plasma.plasma5support as P5Support

// What Quick Settings asks the deckos tool, since Plasma has no QML API for it: the update count,
// the display fix level, Gaming Mode. Commands run only on open, on a click, and for the update
// check every few hours; Wi-Fi, sound and the rest come from Plasma's own event-driven models.
Item {
    id: backend
    property bool expanded: false

    property int repoUpdates: -1  // -1: never checked
    property int aurUpdates: 0
    property double checkedAt: 0  // epoch seconds
    property string updateError: ""
    property bool checking: false
    property bool pacmanRanSinceCheck: false
    readonly property int updateCount: Math.max(0, repoUpdates) + aurUpdates

    property int displayLevel: -1
    property bool gamingAvailable: false
    property bool firewallInstalled: true

    readonly property int checkEvery: 3 * 3600  // seconds between background update checks

    readonly property string updatesText: {
        if (repoUpdates < 0)
            return checking ? "Checking for updates…" : "";
        if (updateCount === 0)
            return "Everything is up to date";
        return updateCount + (updateCount === 1 ? " update waiting" : " updates waiting");
    }

    P5Support.DataSource {
        id: exec
        engine: "executable"
        property var pending: ({})
        onNewData: (source, data) => {
            const callbacks = pending[source] || [];
            delete pending[source];
            disconnectSource(source);
            for (const done of callbacks)
                done(data["exit code"], data.stdout || "", data.stderr || "");
        }
    }

    // run(cmd, done(exitCode, stdout, stderr)); the same command asked twice runs once.
    function run(cmd: string, done): void {
        const callbacks = exec.pending[cmd] || [];
        callbacks.push(done || (() => {}));
        exec.pending[cmd] = callbacks;
        if (callbacks.length === 1)
            exec.connectSource(cmd);
    }

    // Starts an app and lets it outlive the popup.
    function launch(cmd: string): void {
        run(cmd + " >/dev/null 2>&1 &", null);
    }

    function openHub(page: string, update: bool): void {
        launch("deckos-hub --page " + page + (update ? " --update" : ""));
    }

    // `deckos quick-status` and `deckos updates` print key=value lines.
    function parse(out: string): void {
        const v = {};
        for (const line of out.split("\n")) {
            const i = line.indexOf("=");
            if (i > 0)
                v[line.slice(0, i)] = line.slice(i + 1);
        }
        if ("display" in v) displayLevel = parseInt(v.display);
        if ("gaming" in v) gamingAvailable = v.gaming === "1";
        if ("firewall" in v) firewallInstalled = v.firewall === "1";
        if ("checked" in v) {
            repoUpdates = parseInt(v.repo);
            aurUpdates = parseInt(v.aur) || 0;
            checkedAt = parseInt(v.checked);
            updateError = v.error || "";
        }
        pacmanRanSinceCheck = v.stale === "1";
    }

    // Re-checks if the last check is older than maxAge seconds (or pacman ran since).
    function check(maxAge: int): void {
        if (checking)
            return;
        checking = true;
        run("deckos updates --max-age " + maxAge, (code, out) => {
            checking = false;
            parse(out);
        });
    }

    function refresh(): void {
        run("deckos quick-status", (code, out) => {
            parse(out);
            if (pacmanRanSinceCheck || Date.now() / 1000 - checkedAt > 900)
                check(900);
        });
    }

    onExpandedChanged: if (expanded) refresh()
    Component.onCompleted: run("deckos quick-status", (code, out) => parse(out))  // cached counts, no network

    Timer {
        // First check a little after login, so it doesn't compete with startup.
        interval: 90 * 1000
        running: true
        repeat: true
        onTriggered: {
            interval = backend.checkEvery * 1000;
            backend.check(backend.checkEvery - 600);
        }
    }
}
