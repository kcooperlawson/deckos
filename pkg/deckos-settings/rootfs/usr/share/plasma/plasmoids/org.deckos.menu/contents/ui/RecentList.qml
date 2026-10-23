// The first few recent apps or files (Plasma's activity stats), with a hint when there are none.
import QtQuick

ListView {
    id: list

    property string empty
    property int rows: 3
    signal leaveUp()

    height: rows * 44
    interactive: false
    clip: true
    currentIndex: -1
    activeFocusOnTab: true
    delegate: ItemRow {
        visible: index < list.rows
    }

    onActiveFocusChanged: if (activeFocus && currentIndex < 0 && count > 0) currentIndex = 0
    Keys.onUpPressed: event => {
        if (currentIndex <= 0) {
            list.leaveUp();
        } else {
            event.accepted = false;
        }
    }
    Keys.onDownPressed: event => event.accepted = currentIndex >= Math.min(count, rows) - 1
    Keys.onReturnPressed: deckMenu.activate(model, currentIndex)
    Keys.onEnterPressed: deckMenu.activate(model, currentIndex)
    Keys.onMenuPressed: if (currentItem) deckMenu.showActions(model, currentIndex, currentItem.model, currentItem, false)

    Text {
        visible: list.count === 0
        x: 8
        y: 12
        width: parent.width - 16
        text: list.empty
        color: deckMenu.subtext
        font.pixelSize: 13
        wrapMode: Text.WordWrap
    }
}
