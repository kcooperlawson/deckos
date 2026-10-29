// The music's levels for a widget: deckos-visualizer's bars (a local WebSocket, one byte per bar, 0..1 here),
// only while `active`, so nothing listens when no music plays. The service stops sending after a few seconds of
// silence; the bars then fall back to rest.
import QtQuick
import QtWebSockets

QtObject {
    id: feed
    property bool active: false
    property var levels: []

    property WebSocket socket: WebSocket {
        url: "ws://127.0.0.1:47823"
        active: feed.active
        onBinaryMessageReceived: message => {
            const bytes = new Uint8Array(message), next = [];
            for (let i = 0; i < bytes.length; i++)
                next.push(bytes[i] / 255);
            feed.levels = next;
        }
    }
    property Timer retry: Timer {  // the service may start after the desktop, or restart
        interval: 5000; repeat: true; running: feed.active
        onTriggered: if (feed.socket.status !== WebSocket.Open && feed.socket.status !== WebSocket.Connecting) {
            feed.socket.active = false;
            feed.socket.active = true;
        }
    }
    onActiveChanged: if (!active) levels = []
}
