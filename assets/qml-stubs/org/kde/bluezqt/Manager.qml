pragma Singleton
import QtQuick
QtObject {
    property bool bluetoothOperational: true
    property bool bluetoothBlocked: false
    property var adapters: [{ powered: true }]
    property var connectedDevices: [{ name: "Xbox Wireless Controller" }]
}
