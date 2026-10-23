import QtQuick
// Stand-in for the executable engine: canned output from the preview's demoCommands.
QtObject {
    property string engine
    signal newData(string source, var data)
    function connectSource(cmd) {
        console.log("run:", cmd);
        const key = Object.keys(demoCommands).find(k => cmd.startsWith(k));
        Qt.callLater(() => newData(cmd, { "exit code": 0, "stdout": key ? demoCommands[key] : "", "stderr": "" }));
    }
    function disconnectSource(cmd) {}
}
