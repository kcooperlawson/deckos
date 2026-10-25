pragma Singleton
import QtQuick
QtObject {
    enum ConstraintHints { NoHint, CanFillArea }
    property int formFactor: 2
    property int location: 4
    property int constraintHints
    property var containment: ({ screenGeometry: Qt.rect(0, 0, 1920, 1080) })
    property var configuration: ({ launchers: [], showLabels: previewLabels, onlyThisScreen: true })
}
