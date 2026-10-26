// Stand-in for PlasmaCore.Dialog (a popup window): never shown in the preview
import QtQuick

Item {
    property Item mainItem
    property Item visualParent
    property int location: 0
    property int type: 0
    property int flags: 0
    property bool hideOnWindowDeactivate: false
    visible: false
}
