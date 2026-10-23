import QtQuick
Item {
    property bool expanded: false
    property bool activationTogglesExpanded: false
    property bool hideOnWindowDeactivate: true
    property Component preferredRepresentation
    property Component fullRepresentation
    property Component compactRepresentation
    property Item fullRepresentationItem
}
