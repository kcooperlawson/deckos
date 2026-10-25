import QtQuick
// Stand-in for KSysGuard Sensor: deterministic waves from previewClock.t (preview_perfgraphs.py steps it).
QtObject {
    enum Status { Unknown, Loading, Ready, Error, Removing }
    property string sensorId
    property int updateRateLimit
    property bool enabled: true
    property int status: Sensor.Ready
    readonly property real t: previewClock.t
    readonly property real value: {
        const w = (base, amp, per) => base + amp * Math.sin(t / per) + amp * 0.35 * Math.sin(t / 2.1);
        const id = sensorId.replace(/^gpu\/gpu\d+/, "gpu");
        switch (id) {
        case "cpu/all/usage": return Math.max(2, w(24, 14, 6));
        case "cpu/all/averageTemperature": return w(61, 5, 9);
        case "gpu/usage": return t > 22 ? Math.min(99, w(88, 8, 3)) : w(6, 3, 4);
        case "gpu/temperature": return t > 22 ? w(71, 2, 7) : 48;
        case "gpu/usedVram": return t > 22 ? 9.1e9 + 2e8 * Math.sin(t / 5) : 2.7e9;
        case "gpu/totalVram": return sensorId === "gpu/gpu0/totalVram" ? 17095983104 : 2147483648;
        case "memory/physical/used": return 9.4e9 + 1.2e9 * Math.min(1, Math.max(0, (t - 20) / 8));
        case "memory/physical/total": return 33.4e9;
        case "network/all/download": return t % 17 < 6 ? 38e6 + 9e6 * Math.sin(t) : 120e3;
        case "network/all/upload": return t % 17 < 6 ? 2.1e6 : 40e3;
        }
        return 0;
    }
}
