// What the scenes react to: the music's levels from deckos-visualizer (a local WebSocket, one byte per bar), boiled
// down to bass, mids, highs, energy and a beat counter. Scenes use these inside their own world (lights, rain,
// stars) instead of drawing bars on top. With no music it settles to zero and the service stops sending.
import QtQuick
import QtWebSockets

QtObject {
    id: feed

    property bool active: false
    property var levels: []
    property real bass: 0
    property real mid: 0
    property real high: 0
    property real energy: 0
    property int beats: 0  // goes up by one on each beat: scenes watch it (onBeatsChanged)
    property real beatStrength: 0

    property real _avg: 0
    property double _last: 0

    function take(next) {
        const n = next.length;
        if (!n)
            return;
        const part = (a, b) => {
            let s = 0;
            for (let i = Math.floor(a * n); i < Math.floor(b * n); i++)
                s += next[i];
            return s / Math.max(1, Math.floor(b * n) - Math.floor(a * n));
        };
        const b = part(0, 0.15), m = part(0.15, 0.6), h = part(0.6, 1);
        // Up at once, down gently: lights that flicker with every sample look like a fault, not music
        bass = Math.max(b, bass * 0.82);
        mid = Math.max(m, mid * 0.85);
        high = Math.max(h, high * 0.8);
        energy += ((b + m + h) / 3 - energy) * 0.1;
        // A beat: the low end jumping well above where it's been lately
        const now = Date.now();
        if (b > _avg * 1.35 + 0.06 && now - _last > 220) {
            _last = now;
            beatStrength = Math.min(1, (b - _avg) * 2.5);
            beats++;
        }
        _avg += (b - _avg) * 0.08;
        levels = next;
    }

    property WebSocket socket: WebSocket {
        url: "ws://127.0.0.1:47823"
        active: feed.active
        onBinaryMessageReceived: message => {
            const bytes = new Uint8Array(message);
            const next = [];
            for (let i = 0; i < bytes.length; i++)
                next.push(bytes[i] / 255);
            feed.take(next);
        }
    }
    // The service starts with the session; if the wallpaper was first (or the service restarted), connect again.
    // Checked on a timer rather than on statusChanged's argument, which newer Qt no longer passes in.
    property Timer retry: Timer {
        interval: 5000; repeat: true; running: feed.active
        onTriggered: if (feed.socket.status !== WebSocket.Open && feed.socket.status !== WebSocket.Connecting) {
            feed.socket.active = false;
            feed.socket.active = true;
        }
    }
    onActiveChanged: if (!active) { bass = mid = high = energy = 0; levels = []; }
}
