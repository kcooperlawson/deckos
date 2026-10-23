import QtQuick
QtObject {
    property bool isSilent
    property bool isBrightnessAvailable: true
    property ListModel displays: ListModel {
        ListElement { displayName: "DP-1"; label: "Samsung Odyssey G70B"; brightness: 70; maxBrightness: 100 }
        ListElement { displayName: "DP-2"; label: "LG UltraGear"; brightness: 45; maxBrightness: 100 }
    }
    function setBrightness(name, value) {
        for (let i = 0; i < displays.count; i++)
            if (displays.get(i).displayName === name)
                displays.setProperty(i, "brightness", value);
    }
}
