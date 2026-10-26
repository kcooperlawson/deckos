pragma Singleton
import QtQuick
// The widget's settings come from the preview script (previewConfig: a context property)
QtObject {
    property int backgroundHints
    property var configuration: previewConfig
}
