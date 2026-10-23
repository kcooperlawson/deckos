// Search results while typing: KRunner's matches grouped by kind (apps, settings, files,
// calculator, commands…), then apps from the DeckOS Store that aren't installed, then a row that
// opens the Store on the search. The search field keeps the keyboard: Up/Down move `cursor` over all
// of them, Enter runs the one it's on.
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: page

    readonly property int matches: results.count
    readonly property int total: matches + deckMenu.storeResults.length + 1
    property int cursor: 0

    function move(by) {
        cursor = Math.max(0, Math.min(total - 1, cursor + by));
        if (cursor < matches) {
            results.currentIndex = cursor;
            results.positionViewAtIndex(cursor, ListView.Contain);
        } else {
            results.currentIndex = -1;
            results.positionViewAtEnd();
        }
    }

    function accept() {
        if (cursor < matches) {
            deckMenu.activate(results.model, cursor);
        } else if (cursor < matches + deckMenu.storeResults.length) {
            deckMenu.openInStore(deckMenu.storeResults[cursor - matches].key);
        } else {
            deckMenu.searchStore(deckMenu.query.trim());
        }
    }

    function reset() {
        cursor = 0;
        results.currentIndex = 0;
        results.positionViewAtBeginning();
    }

    Connections {
        target: deckMenu
        function onQueryChanged() {
            page.reset();
        }
    }

    ListView {
        id: results
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        // Re-read on every count change, as Kickoff does: the merged model is replaced per query.
        model: deckMenu.runnerModel.count ? deckMenu.runnerModel.modelForRow(0) : null
        property bool keepCurrent: true
        delegate: ItemRow {}
        onCountChanged: if (page.cursor < count) currentIndex = page.cursor

        section.property: "group"
        section.delegate: SectionLabel {
            required property string section
            width: results.width
            height: 28
            leftPadding: 8
            verticalAlignment: Text.AlignBottom
            bottomPadding: 4
            text: section
        }

        footer: Column {
            width: results.width
            topPadding: 6

            Text {
                visible: results.count === 0 && !deckMenu.runnerModel.querying
                width: parent.width
                leftPadding: 8
                topPadding: 6
                bottomPadding: 10
                text: "Nothing on this PC matches “" + deckMenu.query.trim() + "”."
                color: deckMenu.subtext
                font.pixelSize: 13
                elide: Text.ElideRight
            }

            SectionLabel {
                visible: deckMenu.storeResults.length > 0
                width: parent.width
                height: 28
                leftPadding: 8
                verticalAlignment: Text.AlignBottom
                bottomPadding: 4
                text: "From the DeckOS Store"
            }

            Repeater {
                model: deckMenu.storeResults
                delegate: StoreRow {
                    required property var modelData
                    required property int index
                    width: results.width
                    app: modelData
                    cursor: page.cursor === page.matches + index
                    onChosen: deckMenu.openInStore(modelData.key)
                }
            }

            StoreRow {
                width: results.width
                app: ({ name: "Search the DeckOS Store for “" + deckMenu.query.trim() + "”", summary: "", icon: "" })
                line: "store"
                cursor: page.cursor === page.total - 1
                onChosen: deckMenu.searchStore(deckMenu.query.trim())
            }
        }
    }
}
