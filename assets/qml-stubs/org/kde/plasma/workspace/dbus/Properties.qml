import QtQuick
QtObject {
    property int busType
    property string service
    property string path
    property string iface
    property var properties: ({ enabled: true, running: true, inhibited: false, daylight: false, currentTemperature: 4200 })
}
