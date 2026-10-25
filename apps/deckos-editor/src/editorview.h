// One open file's editing area: line numbers, the current line, matching brackets and the language's
// colours (KSyntaxHighlighting, the definitions Kate uses, in the DeckOS theme).
#pragma once

#include <QPlainTextEdit>

#include <KSyntaxHighlighting/Definition>

#include "document.h"

namespace KSyntaxHighlighting {
class Repository;
class SyntaxHighlighter;
}

class EditorView : public QPlainTextEdit
{
    Q_OBJECT
public:
    explicit EditorView(KSyntaxHighlighting::Repository *repo, QWidget *parent = nullptr);

    Document &document_() { return m_doc; }
    const Document &document_() const { return m_doc; }

    // The tab's name: the file name, or "Untitled"
    QString title() const;
    bool isModified() const;
    void setUnmodified();

    void setDefinition(const KSyntaxHighlighting::Definition &def);
    KSyntaxHighlighting::Definition definition() const { return m_def; }
    void pickDefinitionFor(const QString &path);

    void setIndent(int spaces, bool tabs);
    int indentWidth() const { return m_indent; }
    bool indentWithTabs() const { return m_tabs; }

    void toggleComment();
    void goToLine(int line, int column = 1);
    void duplicateLine();
    void moveLines(int direction);  // -1 up, +1 down
    void zoom(int steps);           // 0 resets

    // Where find highlights all matches (with the current one marked)
    void setSearchMatches(const QList<QTextCursor> &all);

    // The gutter's paint and width (it's a child widget that calls back here)
    void paintGutter(QPaintEvent *event);
    int gutterWidth() const;

signals:
    void cursorMoved(int line, int column);

protected:
    void keyPressEvent(QKeyEvent *e) override;
    void resizeEvent(QResizeEvent *e) override;
    void wheelEvent(QWheelEvent *e) override;

private:
    void updateGutter(const QRect &rect, int dy);
    void updateExtraSelections();
    QTextEdit::ExtraSelection bracketMatch() const;
    void guessIndent();
    QString indentUnit() const;

    Document m_doc;
    KSyntaxHighlighting::Repository *m_repo;
    KSyntaxHighlighting::SyntaxHighlighter *m_highlighter;
    KSyntaxHighlighting::Definition m_def;
    QWidget *m_gutter;
    QList<QTextCursor> m_matches;
    int m_indent = 4;
    bool m_tabs = false;
    int m_baseFontSize = 11;
};
