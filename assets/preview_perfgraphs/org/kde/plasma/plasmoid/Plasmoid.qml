pragma Singleton
import QtQuick
QtObject {
    property int backgroundHints
    property var configuration: ({ gpu: "auto", showNetwork: true, seconds: 60, style: "cozy", colorA: "#F2C46D", colorB: "#6FBF8E" })
}
