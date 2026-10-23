// Stand-in for the "executable" engine: commands go to the preview's Python shell.
import QtQuick
Item {
    property string engine
    property var connectedSources: []
    signal newData(string source, var data)
    function connectSource(cmd) {
        const r = previewShell.run(cmd);
        Qt.callLater(() => newData(cmd, { "exit code": r[0], stdout: r[1] }));
    }
    function disconnectSource(cmd) {}
}
