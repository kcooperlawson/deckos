pragma Singleton
import QtQuick
QtObject {
    property int backgroundHints
    property var configuration: ({ gpu: "auto", showNetwork: true, seconds: 60 })
}
