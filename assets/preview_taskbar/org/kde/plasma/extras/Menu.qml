import QtQuick
QtObject {
    enum Status { Closed, Loading, Open }
    enum Placement { TopPosedLeftAlignedPopup, RightPosedTopAlignedPopup }
    default property list<QtObject> content
    property var visualParent
    property int placement
    property int status
    function openRelative() {}
    function addMenuItem(item, before) {}
    function removeMenuItem(item) {}
}
