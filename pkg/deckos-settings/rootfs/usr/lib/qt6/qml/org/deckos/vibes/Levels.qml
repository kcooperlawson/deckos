// The music's levels for a widget: deckos-visualizer's bars (a local WebSocket, one byte per bar, 0..1 here),
// only while `active`, so nothing listens when no music plays. The service stops sending after a few seconds of
// silence; the bars then fall back to rest. Boiled down too, for things that move with the music rather than draw
// it: bass, mid, high, a beat counter (watch onBeatsChanged) and `pulse`, a kick on each beat that fades out (what
// DecKoOS's islands and plates breathe with when the system reacts to music: `deckos vibe react on`).
import QtQuick
import QtWebSockets

QtObject {
    id: feed
    property bool active: false
    property var levels: []
    property real bass: 0
    property real mid: 0
    property real high: 0
    property int beats: 0
    property real pulse: 0  // 0..1: up on a beat, fading in about half a second

    property real _avg: 0
    property double _last: 0

    function take(next) {
        const n = next.length;
        if (!n)
            return;
        const part = (a, b) => {
            let s = 0;
            const i0 = Math.floor(a * n), i1 = Math.max(i0 + 1, Math.floor(b * n));
            for (let i = i0; i < i1; i++)
                s += next[i];
            return s / (i1 - i0);
        };
        const b = part(0, 0.15), m = part(0.15, 0.6), h = part(0.6, 1);
        // Up at once, down gently: light that flickers with every sample looks like a fault, not music
        bass = Math.max(b, bass * 0.82);
        mid = Math.max(m, mid * 0.85);
        high = Math.max(h, high * 0.8);
        const now = Date.now();
        if (b > _avg * 1.35 + 0.06 && now - _last > 220) {  // the low end jumping well above where it's been
            _last = now;
            pulse = Math.min(1, 0.45 + (b - _avg) * 2.5);
            beats++;
        } else {
            pulse *= 0.86;  // ~30 frames a second: half gone in about 150 ms, gone in half a second
        }
        _avg += (b - _avg) * 0.08;
        levels = next;
    }

    property WebSocket socket: WebSocket {
        url: "ws://127.0.0.1:47823"
        active: feed.active
        onBinaryMessageReceived: message => {
            const bytes = new Uint8Array(message), next = [];
            for (let i = 0; i < bytes.length; i++)
                next.push(bytes[i] / 255);
            feed.take(next);
        }
    }
    property Timer retry: Timer {  // the service may start after the desktop, or restart
        interval: 5000; repeat: true; running: feed.active
        onTriggered: if (feed.socket.status !== WebSocket.Open && feed.socket.status !== WebSocket.Connecting) {
            feed.socket.active = false;
            feed.socket.active = true;
        }
    }
    onActiveChanged: if (!active) { levels = []; bass = mid = high = pulse = 0; }
}
