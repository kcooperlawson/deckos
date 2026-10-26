import QtQuick
QtObject {
    property string engine
    signal newData(string source, var data)
    function connectSource(s) {}
    function disconnectSource(s) {}
}
