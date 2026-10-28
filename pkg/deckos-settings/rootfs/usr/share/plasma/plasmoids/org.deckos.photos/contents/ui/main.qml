// DecKoOS Photos: your pictures on the desktop, fading to the next one every few minutes (Pictures, unless you've
// picked a folder). Only reads the folder; click for the next one, double-click opens it.
import QtQuick
import QtQuick.Layouts
import QtCore
import Qt.labs.folderlistmodel
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: photos

    Vibes.Look {
        id: vibe
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    readonly property string folder: Plasmoid.configuration.folder
                                     || StandardPaths.writableLocation(StandardPaths.PicturesLocation)
    property int at: -1
    property bool front: true  // which of the two images is showing; the other loads the next picture

    function next() {
        const n = files.count;
        if (!n)
            return;
        let i = Math.floor(Math.random() * n);
        if (n > 1 && i === at)
            i = (i + 1) % n;
        at = i;
        (front ? b : a).source = files.get(i, "fileUrl");
        front = !front;
    }

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 200
    Layout.preferredWidth: 360
    Layout.preferredHeight: 240
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    FolderListModel {
        id: files
        folder: "file://" + String(photos.folder).replace(/^file:\/\//, "")
        nameFilters: ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.JPEG", "*.PNG", "*.WEBP"]
        showDirs: false
        onStatusChanged: if (status === FolderListModel.Ready && photos.at < 0) photos.next()
    }
    Timer {
        interval: Math.max(1, Plasmoid.configuration.minutes) * 60000; repeat: true
        running: files.count > 1
        onTriggered: photos.next()
    }

    Image {
        id: a
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 1024
        opacity: photos.front ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 1500 } }
    }
    Image {
        id: b
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 1024
        opacity: photos.front ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 1500 } }
    }

    Vibes.VibeText {
        anchors.centerIn: parent
        visible: files.status === FolderListModel.Ready && files.count === 0
        look: vibe
        soft: true
        width: parent.width - 32
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
        text: "Put some pictures in your Pictures folder and they'll show here"
        font.pixelSize: 14
    }
    MouseArea {
        anchors.fill: parent
        onDoubleClicked: if (photos.at >= 0) Qt.openUrlExternally(files.get(photos.at, "fileUrl"))
        onClicked: photos.next()
    }
}
