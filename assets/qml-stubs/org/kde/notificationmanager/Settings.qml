import QtQuick
QtObject {
    property date notificationsInhibitedUntil: new Date(NaN)
    property bool notificationsInhibitedByApplication: false
    function revokeApplicationInhibitions() {}
    function save() {}
}
