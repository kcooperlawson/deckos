// DecKoOS login screen (SDDM, Qt 6 greeter).
// A clock over the DecKoOS wallpaper, one login card, and a bottom bar for the session, keyboard
// layout and power. Plain QtQuick (no Controls styling), so it looks the same whatever style the
// greeter runs with. Colours match DecKoOS Hub: slate surfaces, 1px borders, accent gradient.
import QtQuick
import QtQuick.Effects

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#0F1115"

    readonly property color surface: "#E6171A21"
    readonly property color border: "#262B36"
    readonly property color text: "#E8EAF0"
    readonly property color subtext: "#8C94A6"
    readonly property color accent: config.accent || "#4C8DFF"
    readonly property color accentB: config.accentB || "#7A5CFF"
    readonly property color danger: "#FF6B6B"
    readonly property real s: Math.max(0.75, Math.min(width / 1920, height / 1080))  // UI scale
    // Picked once the session list is in (pickSession): never Gaming Mode by default, since SDDM
    // lists it first and a Gaming Mode that fails to start would bounce you straight back here.
    property int sessionIndex: 0
    property bool sessionPicked: false
    property int userIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
    readonly property var user: users.count > 0 ? users.itemAt(Math.min(userIndex, users.count - 1)) : null
    readonly property string kidTag: " (Kid mode)"  // deckos kids add puts it in a child's full name
    property int plasmaIndex: -1

    // Readable copies of the models' rows (SDDM's models can't be indexed directly from QML).
    Item {
        visible: false
        Repeater {
            id: users
            model: userModel
            delegate: Item {
                required property string name
                required property string realName
                required property string icon
                required property bool needsPassword
            }
            onCountChanged: Qt.callLater(root.pickUser)
        }
        Repeater {
            id: sessions
            model: sessionModel
            delegate: Item {
                required property string name
                required property string file
            }
            onCountChanged: Qt.callLater(root.pickSession)
        }
    }

    Image {
        anchors.fill: parent
        source: config.background || ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }
    Rectangle {  // darken the side the text sits on
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#F00B0D11" }
            GradientStop { position: 0.5; color: "#A60B0D11" }
            GradientStop { position: 1.0; color: "#260B0D11" }
        }
    }

    // ---- clock

    Column {
        id: clock
        x: 96 * root.s
        y: 84 * root.s
        spacing: 2 * root.s
        property date now: new Date()
        Timer { interval: 1000; running: true; repeat: true; onTriggered: clock.now = new Date() }
        Text {
            text: Qt.formatTime(clock.now, Qt.locale().timeFormat(Locale.ShortFormat))
            color: root.text
            font.family: "Inter Display"
            font.weight: Font.DemiBold
            font.pixelSize: 96 * root.s
        }
        Text {
            text: Qt.formatDate(clock.now, "dddd, MMMM d")
            color: root.subtext
            font.family: "Inter"
            font.pixelSize: 22 * root.s
        }
    }

    // ---- login card

    Rectangle {
        id: card
        x: 96 * root.s
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: 40 * root.s
        width: 420 * root.s
        height: content.implicitHeight + 64 * root.s
        radius: 14 * root.s
        color: root.surface
        border.color: root.border
        border.width: 1

        SequentialAnimation {  // shake on a wrong password
            id: shake
            loops: 2
            NumberAnimation { target: card; property: "x"; to: 96 * root.s - 10; duration: 45 }
            NumberAnimation { target: card; property: "x"; to: 96 * root.s + 10; duration: 90 }
            NumberAnimation { target: card; property: "x"; to: 96 * root.s; duration: 45 }
        }

        Column {
            id: content
            x: 32 * root.s
            y: 32 * root.s
            width: card.width - 64 * root.s
            spacing: 18 * root.s

            Image {
                source: config.wordmark || "/usr/share/deckos/branding/wordmark.svg"
                height: 30 * root.s
                fillMode: Image.PreserveAspectFit
                sourceSize.height: height * 2
            }

            Row {  // who: avatar, name, and arrows when there's more than one user
                spacing: 14 * root.s
                width: parent.width
                Item {
                    id: avatar
                    width: 56 * root.s
                    height: width
                    Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: root.accent }
                            GradientStop { position: 1; color: root.accentB }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: root.user ? (root.user.realName || root.user.name).charAt(0).toUpperCase() : "?"
                            color: "white"
                            font.family: "Inter Display"
                            font.weight: Font.DemiBold
                            font.pixelSize: 24 * root.s
                        }
                    }
                    Image {
                        id: face
                        anchors.fill: parent
                        source: root.user && root.user.icon ? "file://" + root.user.icon : ""
                        sourceSize.width: width * 2
                        fillMode: Image.PreserveAspectCrop
                        visible: false
                    }
                    Item {
                        id: faceMask
                        anchors.fill: parent
                        visible: false
                        layer.enabled: true
                        Rectangle { anchors.fill: parent; radius: width / 2; color: "black" }
                    }
                    MultiEffect {
                        anchors.fill: parent
                        source: face
                        visible: face.status === Image.Ready
                        maskEnabled: true
                        maskSource: faceMask
                    }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - avatar.width - (users.count > 1 ? 76 : 14) * root.s
                    Text {
                        width: parent.width
                        text: root.user ? root.shown(root.user) : ""
                        color: root.text
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.weight: Font.DemiBold
                        font.pixelSize: 19 * root.s
                    }
                    Text {
                        text: (root.user ? root.user.name : "") + "  ·  " + sddm.hostName
                        color: root.subtext
                        font.family: "Inter"
                        font.pixelSize: 13 * root.s
                    }
                }
                Row {
                    visible: users.count > 1
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4 * root.s
                    IconButton { icon: "chevron-left"; onClicked: root.userIndex = (root.userIndex + users.count - 1) % users.count }
                    IconButton { icon: "chevron"; onClicked: root.userIndex = (root.userIndex + 1) % users.count }
                }
            }

            Rectangle {  // password
                id: field
                visible: !root.user || root.user.needsPassword
                width: parent.width
                height: 46 * root.s
                radius: 9 * root.s
                color: "#0F1115"
                border.width: 1
                border.color: password.activeFocus ? root.accent : root.border
                TextInput {
                    id: password
                    anchors.fill: parent
                    anchors.leftMargin: 14 * root.s
                    anchors.rightMargin: 14 * root.s
                    verticalAlignment: TextInput.AlignVCenter
                    echoMode: TextInput.Password
                    passwordCharacter: "●"
                    color: root.text
                    selectionColor: root.accent
                    font.family: "Inter"
                    font.pixelSize: 15 * root.s
                    focus: true
                    onAccepted: root.login()
                    onTextEdited: error.text = ""
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: password.text.length === 0
                        text: "Password"
                        color: "#5A6172"
                        font: password.font
                    }
                }
            }

            Text {
                id: error
                width: parent.width
                visible: text.length > 0 || capsHint.visible
                text: ""
                color: root.danger
                wrapMode: Text.WordWrap
                font.family: "Inter"
                font.pixelSize: 13 * root.s
                Text {
                    id: capsHint
                    visible: error.text.length === 0 && typeof keyboard !== "undefined" && keyboard.capsLock
                    text: "Caps Lock is on"
                    color: "#F5B84B"
                    font: error.font
                }
            }

            Rectangle {  // log in
                width: parent.width
                height: 46 * root.s
                radius: 9 * root.s
                opacity: loginArea.pressed ? 0.85 : 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: loginArea.containsMouse ? Qt.lighter(root.accent, 1.15) : root.accent }
                    GradientStop { position: 1; color: loginArea.containsMouse ? Qt.lighter(root.accentB, 1.15) : root.accentB }
                }
                Row {
                    anchors.centerIn: parent
                    spacing: 8 * root.s
                    Text {
                        text: "Log in"
                        color: "white"
                        font.family: "Inter"
                        font.weight: Font.DemiBold
                        font.pixelSize: 15 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Image {
                        source: "icons/arrow-right.svg"
                        width: 18 * root.s
                        height: width
                        sourceSize.width: width * 2
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: loginArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.login()
                }
            }
        }
    }

    // ---- Kid mode: each child as a big picture under the card; one tap (no password) and they're in

    Column {
        id: kidsRow
        visible: kidRepeater.kids > 0
        x: 96 * root.s
        anchors.top: card.bottom
        anchors.topMargin: 28 * root.s
        spacing: 12 * root.s
        Text {
            text: "Kids"
            color: root.subtext
            font.family: "Inter"
            font.weight: Font.DemiBold
            font.pixelSize: 14 * root.s
        }
        Row {
            spacing: 18 * root.s
            Repeater {
                id: kidRepeater
                property int kids: 0
                model: userModel
                delegate: Item {
                    id: kid
                    required property string name
                    required property string realName
                    required property string icon
                    required property int index
                    readonly property bool isKid: realName.endsWith(root.kidTag)
                    visible: isKid
                    width: isKid ? 104 * root.s : 0
                    height: isKid ? 128 * root.s : 0
                    Component.onCompleted: if (isKid) kidRepeater.kids++
                    Rectangle {
                        id: kidFace
                        width: 96 * root.s
                        height: width
                        radius: width / 2
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: root.kidColour(kid.name)
                        border.width: kidArea.containsMouse ? 3 : 0
                        border.color: "white"
                        Text {
                            anchors.centerIn: parent
                            visible: kidPic.status !== Image.Ready
                            text: kid.realName.charAt(0).toUpperCase()
                            color: "white"
                            font.family: "Inter Display"
                            font.weight: Font.Bold
                            font.pixelSize: 44 * root.s
                        }
                        Image {
                            id: kidPic
                            anchors.fill: parent
                            source: kid.icon ? "file://" + kid.icon : ""
                            sourceSize.width: width * 2
                            fillMode: Image.PreserveAspectCrop
                            visible: false
                        }
                        MultiEffect {
                            anchors.fill: parent
                            source: kidPic
                            visible: kidPic.status === Image.Ready
                            maskEnabled: true
                            maskSource: faceMask
                        }
                    }
                    Text {
                        anchors.top: kidFace.bottom
                        anchors.topMargin: 8 * root.s
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: kid.realName.slice(0, -root.kidTag.length)
                        color: root.text
                        font.family: "Inter"
                        font.weight: Font.DemiBold
                        font.pixelSize: 16 * root.s
                    }
                    MouseArea {
                        id: kidArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            error.text = ""
                            root.userIndex = kid.index
                            // Always the desktop for a child, never Gaming Mode
                            sddm.login(kid.name, "", root.plasmaIndex >= 0 ? root.plasmaIndex : root.sessionIndex)
                        }
                    }
                }
            }
        }
    }

    // ---- bottom bar: session, keyboard layout, power

    Row {
        x: 96 * root.s
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40 * root.s
        spacing: 10 * root.s
        Pill {
            icon: "display"
            label: sessions.count > 0 && sessions.itemAt(root.sessionIndex) ? sessions.itemAt(root.sessionIndex).name : "Session"
            tip: "Session"
            onClicked: root.sessionIndex = (root.sessionIndex + 1) % Math.max(1, sessions.count)
        }
        Pill {
            visible: typeof keyboard !== "undefined" && keyboard.layouts.length > 1
            icon: "keyboard"
            label: visible ? keyboard.layouts[keyboard.currentLayout].shortName.toUpperCase() : ""
            onClicked: keyboard.currentLayout = (keyboard.currentLayout + 1) % keyboard.layouts.length
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 96 * root.s
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40 * root.s
        spacing: 10 * root.s
        Pill { visible: sddm.canSuspend; icon: "sleep"; label: "Sleep"; onClicked: sddm.suspend() }
        Pill { visible: sddm.canReboot; icon: "refresh"; label: "Restart"; onClicked: sddm.reboot() }
        Pill { visible: sddm.canPowerOff; icon: "power-off"; label: "Shut down"; onClicked: sddm.powerOff() }
    }

    // The card is for grown-ups: when the last login was a child's (after "I'm done"), show the last grown-up
    // instead; the children stay in their row under the card.
    function pickUser() {
        var last = userModel.lastIndex
        var lastItem = last >= 0 ? users.itemAt(last) : null
        if (!lastItem || !lastItem.realName.endsWith(kidTag))
            return
        for (var i = 0; i < users.count; i++) {
            var u = users.itemAt(i)
            if (u && !u.realName.endsWith(kidTag)) {
                userIndex = i
                return
            }
        }
    }
    function shown(u) {
        var n = u.realName || u.name
        return n.endsWith(kidTag) ? n.slice(0, -kidTag.length) : n
    }
    function kidColour(name) {  // the same bright colour for a child every time
        var colours = ["#FF7A59", "#4C8DFF", "#3DD68C", "#F5B84B", "#B36BFF", "#FF5C9A", "#22C7B8"]
        var h = 0
        for (var i = 0; i < name.length; i++)
            h = (h * 31 + name.charCodeAt(i)) % 997
        return colours[h % colours.length]
    }

    // The last session used, unless that was Gaming Mode; then Plasma (Wayland).
    function pickSession() {
        if (sessionPicked || sessions.count === 0)
            return
        var plasma = -1, last = sessionModel.lastIndex
        for (var i = 0; i < sessions.count; i++) {
            var f = sessions.itemAt(i) ? String(sessions.itemAt(i).file) : ""
            if (plasma < 0 && (f === "plasma.desktop" || f.endsWith("/plasma.desktop")))
                plasma = i
        }
        plasmaIndex = plasma
        var lastItem = last >= 0 ? sessions.itemAt(last) : null
        var lastIsGaming = lastItem && String(lastItem.file).indexOf("deckos-gaming") >= 0
        sessionIndex = lastItem && !lastIsGaming ? last : (plasma >= 0 ? plasma : Math.max(0, last))
        sessionPicked = true
    }

    function login() {
        if (!root.user)
            return
        error.text = ""
        sddm.login(root.user.name, password.text, root.sessionIndex)
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            error.text = "That password didn't work. Try again."
            password.selectAll()
            password.forceActiveFocus()
            shake.start()
        }
    }

    Component.onCompleted: password.forceActiveFocus()

    // ---- small parts

    component IconButton: Rectangle {
        id: ib
        property string icon
        signal clicked
        width: 30 * root.s
        height: width
        radius: 8 * root.s
        color: ibArea.containsMouse ? "#2A2F3B" : "transparent"
        Image {
            anchors.centerIn: parent
            source: "icons/" + ib.icon + ".svg"
            width: 16 * root.s
            height: width
            sourceSize.width: width * 2
        }
        MouseArea { id: ibArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ib.clicked() }
    }

    component Pill: Rectangle {
        id: pill
        property string icon
        property string label
        property string tip
        signal clicked
        width: pillRow.implicitWidth + 28 * root.s
        height: 38 * root.s
        radius: 9 * root.s
        color: pillArea.containsMouse ? "#F2202530" : "#CC171A21"
        border.color: root.border
        border.width: 1
        Row {
            id: pillRow
            anchors.centerIn: parent
            spacing: 8 * root.s
            Image {
                source: "icons/" + pill.icon + ".svg"
                width: 16 * root.s
                height: width
                sourceSize.width: width * 2
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: pill.label
                color: root.text
                font.family: "Inter"
                font.pixelSize: 13 * root.s
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea { id: pillArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pill.clicked() }
    }
}
