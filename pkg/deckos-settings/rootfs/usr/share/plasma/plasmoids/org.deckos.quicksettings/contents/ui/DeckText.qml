import QtQuick

Text {
    property bool sub: false
    color: sub ? Deck.subtext : Deck.text
    font.family: Deck.font
    font.pixelSize: sub ? 12 : 13
    elide: Text.ElideRight
    maximumLineCount: 1
    textFormat: Text.PlainText
}
