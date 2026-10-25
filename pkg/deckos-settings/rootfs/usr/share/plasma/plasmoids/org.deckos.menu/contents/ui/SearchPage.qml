// Search results while typing: DecKoOS actions ("Link my Windows drives") at the top, then KRunner's
// matches grouped by kind (apps, settings, files, calculator, commands…), then apps from the DecKoOS
// Store that aren't installed, then rows that ask DecKoOS Assistant the search and open the Store on it.
// The search field keeps the keyboard: Up/Down move `cursor` over all of them, Enter runs the one it's on.
// The cursor starts on the first match, not an action, so Enter still opens the app typed ("steam"
// opens Steam, though "Switch to Gaming Mode" sits above it); Up reaches the actions.
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: page

    // cursor runs over: actions, then matches, then Store apps, then the two link rows
    readonly property int actions: deckMenu.actionResults.length
    readonly property int matches: results.count
    readonly property int total: actions + matches + deckMenu.storeResults.length + 2
    property int cursor: 0
    property bool moved: false  // until the keyboard moves, the cursor stays on the first match

    onActionsChanged: if (!moved) {
        cursor = actions;
        Qt.callLater(results.positionViewAtBeginning);  // the actions header, not just the first match
    }

    function move(by) {
        moved = true;
        cursor = Math.max(0, Math.min(total - 1, cursor + by));
        const m = cursor - actions;
        if (cursor < actions) {
            results.currentIndex = -1;
            results.positionViewAtBeginning();
        } else if (m < matches) {
            results.currentIndex = m;
            results.positionViewAtIndex(m, ListView.Contain);
        } else {
            results.currentIndex = -1;
            results.positionViewAtEnd();
        }
    }

    function accept() {
        const m = cursor - actions;
        if (cursor < actions) {
            deckMenu.runAction(deckMenu.actionResults[cursor].id);
        } else if (m < matches) {
            deckMenu.activate(results.model, m);
        } else if (m < matches + deckMenu.storeResults.length) {
            deckMenu.openInStore(deckMenu.storeResults[m - matches].key);
        } else if (cursor === total - 2) {
            deckMenu.askAssistant(deckMenu.query.trim());
        } else {
            deckMenu.searchStore(deckMenu.query.trim());
        }
    }

    function reset() {
        moved = false;
        cursor = actions;
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
        // move() scrolls for the keyboard; following the current item by itself hid the actions header
        highlightFollowsCurrentItem: false
        delegate: ItemRow {}
        onCountChanged: {
            if (page.cursor >= page.actions && page.cursor - page.actions < count)
                currentIndex = page.cursor - page.actions;
            // Following the current item scrolls the header out of sight: show it while nothing's moved
            if (!page.moved)
                Qt.callLater(positionViewAtBeginning);
        }

        header: Column {
            width: results.width
            visible: page.actions > 0
            height: visible ? implicitHeight : 0
            // Its rows arrive after the matches: keep it in view as it grows, until the keyboard moves
            onHeightChanged: if (!page.moved) results.positionViewAtBeginning()

            SectionLabel {
                width: parent.width
                height: 28
                leftPadding: 8
                verticalAlignment: Text.AlignBottom
                bottomPadding: 4
                text: "In DecKoOS"
            }

            Repeater {
                model: deckMenu.actionResults
                delegate: StoreRow {
                    required property var modelData
                    required property int index
                    width: results.width
                    app: ({ name: modelData.title, summary: modelData.summary || "", icon: "" })
                    line: modelData.icon || "arrow-right"
                    cursor: page.cursor === index
                    onChosen: deckMenu.runAction(modelData.id)
                }
            }
        }

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
                text: "From the DecKoOS Store"
            }

            Repeater {
                model: deckMenu.storeResults
                delegate: StoreRow {
                    required property var modelData
                    required property int index
                    width: results.width
                    app: modelData
                    cursor: page.cursor === page.actions + page.matches + index
                    onChosen: deckMenu.openInStore(modelData.key)
                }
            }

            // First of the two, so a question that matches nothing goes to the assistant on Enter
            StoreRow {
                width: results.width
                app: ({ name: "Ask DecKoOS Assistant: “" + deckMenu.query.trim() + "”",
                        summary: "Install, set up or find out anything, on this PC", icon: "" })
                line: "ai"
                cursor: page.cursor === page.total - 2
                onChosen: deckMenu.askAssistant(deckMenu.query.trim())
            }

            StoreRow {
                width: results.width
                app: ({ name: "Search the DecKoOS Store for “" + deckMenu.query.trim() + "”", summary: "", icon: "" })
                line: "store"
                cursor: page.cursor === page.total - 1
                onChosen: deckMenu.searchStore(deckMenu.query.trim())
            }
        }
    }
}
