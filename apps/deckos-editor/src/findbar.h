// Find and replace, under the text: every match lit, a count, Enter for the next one.
#pragma once

#include <QFrame>
#include <QTextCursor>

class EditorView;
class QLabel;
class QLineEdit;
class QToolButton;

class FindBar : public QFrame
{
    Q_OBJECT
public:
    explicit FindBar(QWidget *parent = nullptr);

    void setView(EditorView *view);
    void open(bool replace);
    void close_();
    void next(bool backwards = false);
    void replaceOne();
    void replaceAll();

    // All matches of `query` in `text` as (start, length); exposed for the tests
    static QList<QPair<int, int>> matches(const QString &text, const QString &query, bool caseSensitive, bool regex,
                                          bool wholeWords, QString *error = nullptr);

private:
    void refresh();
    QList<QTextCursor> cursors() const;

    EditorView *m_view = nullptr;
    QLineEdit *m_find;
    QLineEdit *m_replace;
    QLabel *m_count;
    QToolButton *m_case;
    QToolButton *m_regex;
    QToolButton *m_words;
    QWidget *m_replaceRow;
};
