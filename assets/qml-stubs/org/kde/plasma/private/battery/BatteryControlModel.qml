import QtQuick
QtObject {
    enum ChargeStateEnum { NoCharge, Charging, Discharging, FullyCharged }
    property bool hasInternalBatteries: false
    property bool pluggedIn: true
    property int percent: 100
    property int state: 0
    property real smoothedRemainingMsec: 0
}
