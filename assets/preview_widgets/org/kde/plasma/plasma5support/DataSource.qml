import QtQuick
// The command runner: silent, except the Desktop shelf's helper, which answers with the preview script's demo Desktop
QtObject {
    id: source
    property string engine
    signal newData(string source, var data)
    function connectSource(s) {
        if (s.indexOf("shelf.py") !== -1 && typeof previewShelf !== "undefined")
            Qt.callLater(() => source.newData(s, { stdout: previewShelf, stderr: "", "exit code": 0 }));
    }
    function disconnectSource(s) {}
}
