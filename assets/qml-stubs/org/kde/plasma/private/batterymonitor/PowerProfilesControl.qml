import QtQuick
QtObject {
    property bool isSilent
    property var profiles: ["power-saver", "balanced", "performance"]
    property string activeProfile: "balanced"
    function setProfile(p) { activeProfile = p }
}
