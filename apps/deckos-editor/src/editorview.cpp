#include "editorview.h"

#include "style.h"

#include <QFileInfo>
#include <QFontDatabase>
#include <QPainter>
#include <QRegularExpression>
#include <QScrollBar>
#include <QTextBlock>

#include <KSyntaxHighlighting/Repository>
#include <KSyntaxHighlighting/SyntaxHighlighter>
#include <KSyntaxHighlighting/Theme>

namespace {

class Gutter : public QWidget
{
public:
    explicit Gutter(EditorView *view)
        : QWidget(view)
        , m_view(view)
    {
    }
    QSize sizeHint() const override { return {m_view->gutterWidth(), 0}; }

protected:
    void paintEvent(QPaintEvent *e) override { m_view->paintGutter(e); }

private:
    EditorView *m_view;
};

const QColor CurrentLine{0x15, 0x18, 0x20};
const QColor LineNumber{0x4A, 0x51, 0x62};
const QColor Search{0x4A, 0x3A, 0x12};
const QColor SearchCurrent{0x8A, 0x6A, 0x1A};
const QColor Bracket{0x2A, 0x35, 0x50};

} // namespace

EditorView::EditorView(KSyntaxHighlighting::Repository *repo, QWidget *parent)
    : QPlainTextEdit(parent)
    , m_repo(repo)
    , m_highlighter(new KSyntaxHighlighting::SyntaxHighlighter(document()))
    , m_gutter(new Gutter(this))
{
    QFont mono(QStringLiteral("JetBrainsMono Nerd Font"));
    mono.setStyleHint(QFont::Monospace);
    if (!QFontDatabase::families().contains(mono.family()))
        mono = QFontDatabase::systemFont(QFontDatabase::FixedFont);
    mono.setPointSize(m_baseFontSize);
    setFont(mono);
    setFrameShape(QFrame::NoFrame);
    setLineWrapMode(QPlainTextEdit::NoWrap);
    setCursorWidth(2);
    setTabStopDistance(fontMetrics().horizontalAdvance(QLatin1Char(' ')) * m_indent);

    QPalette pal = palette();
    pal.setColor(QPalette::Base, Style::Bg);
    pal.setColor(QPalette::Text, Style::Text);
    pal.setColor(QPalette::Highlight, QColor(0x26, 0x38, 0x5E));
    pal.setColor(QPalette::HighlightedText, Style::Text);
    setPalette(pal);

    const auto theme = m_repo->theme(QStringLiteral("DeckOS"));
    m_highlighter->setTheme(theme.isValid() ? theme : m_repo->defaultTheme(KSyntaxHighlighting::Repository::DarkTheme));

    connect(this, &QPlainTextEdit::blockCountChanged, this, [this] { setViewportMargins(gutterWidth(), 0, 0, 0); });
    connect(this, &QPlainTextEdit::updateRequest, this, &EditorView::updateGutter);
    connect(this, &QPlainTextEdit::cursorPositionChanged, this, [this] {
        updateExtraSelections();
        const QTextCursor c = textCursor();
        emit cursorMoved(c.blockNumber() + 1, c.positionInBlock() + 1);
    });
    setViewportMargins(gutterWidth(), 0, 0, 0);
    updateExtraSelections();
}

QString EditorView::title() const
{
    return m_doc.path().isEmpty() ? QStringLiteral("Untitled") : QFileInfo(m_doc.path()).fileName();
}

bool EditorView::isModified() const
{
    return document()->isModified();
}

void EditorView::setUnmodified()
{
    document()->setModified(false);
}

void EditorView::setDefinition(const KSyntaxHighlighting::Definition &def)
{
    m_def = def;
    m_highlighter->setDefinition(def);
}

void EditorView::pickDefinitionFor(const QString &path)
{
    auto def = m_repo->definitionForFileName(path);
    if (!def.isValid()) {
        // No extension match: a #! line names the language (scripts in ~/bin)
        const QString first = toPlainText().section(QLatin1Char('\n'), 0, 0);
        if (first.startsWith(QLatin1String("#!"))) {
            const QString interp = first.section(QLatin1Char('/'), -1).section(QLatin1Char(' '), -1);
            static const QHash<QString, QString> names = {{QStringLiteral("bash"), QStringLiteral("Bash")},
                                                          {QStringLiteral("sh"), QStringLiteral("Bash")},
                                                          {QStringLiteral("python3"), QStringLiteral("Python")},
                                                          {QStringLiteral("python"), QStringLiteral("Python")},
                                                          {QStringLiteral("node"), QStringLiteral("JavaScript")}};
            def = m_repo->definitionForName(names.value(interp.trimmed()));
        }
    }
    setDefinition(def);
    guessIndent();
}

// Indentation as the file already does it: tabs if lines start with tabs, else the most common step
void EditorView::guessIndent()
{
    int tabs = 0, spaces = 0;
    QHash<int, int> steps;
    int prev = 0;
    for (QTextBlock b = document()->begin(); b.isValid() && b.blockNumber() < 2000; b = b.next()) {
        const QString t = b.text();
        if (t.trimmed().isEmpty())
            continue;
        if (t.startsWith(QLatin1Char('\t'))) {
            ++tabs;
            continue;
        }
        int n = 0;
        while (n < t.size() && t[n] == QLatin1Char(' '))
            ++n;
        if (n > 0)
            ++spaces;
        if (n > prev && n - prev <= 8)
            ++steps[n - prev];
        prev = n;
    }
    if (tabs > spaces) {
        setIndent(4, true);
        return;
    }
    int best = 4, count = 0;
    for (auto it = steps.cbegin(); it != steps.cend(); ++it)
        if (it.value() > count && (it.key() == 2 || it.key() == 4 || it.key() == 8 || it.key() == 3))
            best = it.key(), count = it.value();
    setIndent(best, false);
}

void EditorView::setIndent(int spaces, bool tabs)
{
    m_indent = spaces;
    m_tabs = tabs;
    setTabStopDistance(fontMetrics().horizontalAdvance(QLatin1Char(' ')) * m_indent);
}

QString EditorView::indentUnit() const
{
    return m_tabs ? QStringLiteral("\t") : QString(m_indent, QLatin1Char(' '));
}

void EditorView::keyPressEvent(QKeyEvent *e)
{
    QTextCursor c = textCursor();
    if ((e->key() == Qt::Key_Return || e->key() == Qt::Key_Enter) && !(e->modifiers() & Qt::ShiftModifier)) {
        // Keep the line's indentation, and add a step after an opening bracket or a ':' (Python)
        const QString line = c.block().text().left(c.positionInBlock());
        const QString lead = line.left(line.size() - QString(line).remove(QRegularExpression(QStringLiteral("^\\s+"))).size());
        const QString trimmed = line.trimmed();
        QString indent = lead;
        if (trimmed.endsWith(QLatin1Char('{')) || trimmed.endsWith(QLatin1Char('(')) || trimmed.endsWith(QLatin1Char('['))
            || (trimmed.endsWith(QLatin1Char(':')) && m_def.name() == QLatin1String("Python")))
            indent += indentUnit();
        c.beginEditBlock();
        c.insertText(QStringLiteral("\n") + indent);
        // Between a pair: the closing bracket goes on its own line, back at the old indent
        const QString after = c.block().text().mid(c.positionInBlock(), 1);
        const QChar next = after.isEmpty() ? QChar() : after[0];
        if (indent != lead && (next == QLatin1Char('}') || next == QLatin1Char(')') || next == QLatin1Char(']'))) {
            const int keep = c.position();
            c.insertText(QStringLiteral("\n") + lead);
            c.setPosition(keep);
        }
        c.endEditBlock();
        setTextCursor(c);
        return;
    }
    if (e->key() == Qt::Key_Tab && c.hasSelection()) {  // indent the selected lines
        const int start = document()->findBlock(c.selectionStart()).blockNumber();
        const int end = document()->findBlock(c.selectionEnd()).blockNumber();
        c.beginEditBlock();
        for (int n = start; n <= end; ++n) {
            QTextCursor l(document()->findBlockByNumber(n));
            l.insertText(indentUnit());
        }
        c.endEditBlock();
        return;
    }
    if (e->key() == Qt::Key_Backtab) {  // unindent the line or the selected lines
        const int start = document()->findBlock(c.selectionStart()).blockNumber();
        const int end = document()->findBlock(c.selectionEnd()).blockNumber();
        c.beginEditBlock();
        for (int n = start; n <= end; ++n) {
            QTextBlock b = document()->findBlockByNumber(n);
            int remove = 0;
            const QString t = b.text();
            if (t.startsWith(QLatin1Char('\t')))
                remove = 1;
            else
                while (remove < m_indent && remove < t.size() && t[remove] == QLatin1Char(' '))
                    ++remove;
            QTextCursor l(b);
            l.movePosition(QTextCursor::Right, QTextCursor::KeepAnchor, remove);
            l.removeSelectedText();
        }
        c.endEditBlock();
        return;
    }
    if (e->key() == Qt::Key_Tab && !m_tabs) {
        c.insertText(QString(m_indent - c.positionInBlock() % m_indent, QLatin1Char(' ')));
        return;
    }
    if (e->key() == Qt::Key_Home && !(e->modifiers() & Qt::ControlModifier)) {
        // Home goes to the first character, then to the line's start
        const QString t = c.block().text();
        int first = 0;
        while (first < t.size() && t[first].isSpace())
            ++first;
        const auto mode = e->modifiers() & Qt::ShiftModifier ? QTextCursor::KeepAnchor : QTextCursor::MoveAnchor;
        c.setPosition(c.block().position() + (c.positionInBlock() == first ? 0 : first), mode);
        setTextCursor(c);
        return;
    }
    QPlainTextEdit::keyPressEvent(e);
}

void EditorView::toggleComment()
{
    const QString marker = m_def.singleLineCommentMarker();
    if (marker.isEmpty())
        return;
    QTextCursor c = textCursor();
    const int start = document()->findBlock(c.selectionStart()).blockNumber();
    int end = document()->findBlock(c.selectionEnd()).blockNumber();
    if (c.hasSelection() && document()->findBlock(c.selectionEnd()).position() == c.selectionEnd() && end > start)
        --end;  // a selection ending at a line's start doesn't include that line
    // Comment unless every non-empty line is already commented
    bool all = true;
    int col = INT_MAX;
    for (int n = start; n <= end; ++n) {
        const QString t = document()->findBlockByNumber(n).text();
        if (t.trimmed().isEmpty())
            continue;
        all = all && t.trimmed().startsWith(marker);
        col = std::min(col, int(t.indexOf(t.trimmed())));
    }
    if (col == INT_MAX)
        return;
    c.beginEditBlock();
    for (int n = start; n <= end; ++n) {
        QTextBlock b = document()->findBlockByNumber(n);
        const QString t = b.text();
        if (t.trimmed().isEmpty())
            continue;
        QTextCursor l(b);
        if (all) {
            const int at = t.indexOf(marker);
            l.setPosition(b.position() + at);
            l.setPosition(b.position() + at + marker.size() + (t.mid(at + marker.size(), 1) == QLatin1String(" ") ? 1 : 0),
                          QTextCursor::KeepAnchor);
            l.removeSelectedText();
        } else {
            l.setPosition(b.position() + col);
            l.insertText(marker + QLatin1Char(' '));
        }
    }
    c.endEditBlock();
}

void EditorView::goToLine(int line, int column)
{
    QTextBlock b = document()->findBlockByNumber(std::clamp(line, 1, blockCount()) - 1);
    QTextCursor c(b);
    c.movePosition(QTextCursor::Right, QTextCursor::MoveAnchor, std::clamp(column - 1, 0, b.length() - 1));
    setTextCursor(c);
    centerCursor();
}

void EditorView::duplicateLine()
{
    QTextCursor c = textCursor();
    c.beginEditBlock();
    const QString text = c.block().text();
    c.movePosition(QTextCursor::EndOfBlock);
    c.insertText(QStringLiteral("\n") + text);
    c.endEditBlock();
    setTextCursor(c);
}

void EditorView::moveLines(int direction)
{
    QTextCursor c = textCursor();
    const QTextBlock first = document()->findBlock(c.selectionStart());
    const QTextBlock last = document()->findBlock(c.selectionEnd());
    const QTextBlock other = direction < 0 ? first.previous() : last.next();
    if (!other.isValid())
        return;
    const int offset = c.position() - first.position();
    c.beginEditBlock();
    QTextCursor sel(first);
    sel.setPosition(last.position() + last.length() - 1, QTextCursor::KeepAnchor);
    const QString moving = sel.selectedText();
    const QString swapped = other.text();
    // Rewrite the span the two cover: the moving lines and their neighbour, in the new order
    QTextCursor span(direction < 0 ? other : first);
    span.setPosition((direction < 0 ? last : other).position() + (direction < 0 ? last : other).length() - 1,
                     QTextCursor::KeepAnchor);
    span.insertText(direction < 0 ? moving + QChar::ParagraphSeparator + swapped : swapped + QChar::ParagraphSeparator + moving);
    c.endEditBlock();
    QTextBlock moved = document()->findBlockByNumber(first.blockNumber() + direction);
    QTextCursor back(moved);
    back.setPosition(moved.position() + std::min(offset, moved.length() - 1));
    setTextCursor(back);
}

void EditorView::zoom(int steps)
{
    QFont f = font();
    f.setPointSize(steps == 0 ? m_baseFontSize : std::clamp(f.pointSize() + steps, 6, 48));
    setFont(f);
    setTabStopDistance(fontMetrics().horizontalAdvance(QLatin1Char(' ')) * m_indent);
    setViewportMargins(gutterWidth(), 0, 0, 0);
}

void EditorView::wheelEvent(QWheelEvent *e)
{
    if (e->modifiers() & Qt::ControlModifier) {
        zoom(e->angleDelta().y() > 0 ? 1 : -1);
        return;
    }
    QPlainTextEdit::wheelEvent(e);
}

void EditorView::setSearchMatches(const QList<QTextCursor> &all)
{
    m_matches = all;
    updateExtraSelections();
}

void EditorView::updateExtraSelections()
{
    QList<QTextEdit::ExtraSelection> sel;
    QTextEdit::ExtraSelection line;
    line.format.setBackground(CurrentLine);
    line.format.setProperty(QTextFormat::FullWidthSelection, true);
    line.cursor = textCursor();
    line.cursor.clearSelection();
    sel << line;
    for (const QTextCursor &m : std::as_const(m_matches)) {
        QTextEdit::ExtraSelection s;
        const bool current = m.selectionStart() == textCursor().selectionStart() && m.selectionEnd() == textCursor().selectionEnd();
        s.format.setBackground(current ? SearchCurrent : Search);
        s.cursor = m;
        sel << s;
    }
    const auto bracket = bracketMatch();
    if (!bracket.cursor.isNull())
        sel << bracket;
    setExtraSelections(sel);
}

// The partner of the bracket next to the cursor, lit
QTextEdit::ExtraSelection EditorView::bracketMatch() const
{
    QTextEdit::ExtraSelection none;
    const QString opens = QStringLiteral("([{"), closes = QStringLiteral(")]}");
    const QTextCursor c = textCursor();
    const QString text = toPlainText();
    for (int at : {c.position(), c.position() - 1}) {
        if (at < 0 || at >= text.size())
            continue;
        const QChar ch = text[at];
        int kind = opens.indexOf(ch), dir = 1;
        if (kind < 0) {
            kind = closes.indexOf(ch);
            dir = -1;
        }
        if (kind < 0)
            continue;
        const QChar open = opens[kind], close = closes[kind];
        int depth = 0;
        for (int i = at; i >= 0 && i < text.size() && std::abs(i - at) < 20000; i += dir) {
            if (text[i] == open)
                depth += dir;
            else if (text[i] == close)
                depth -= dir;
            if (depth == 0) {
                QTextEdit::ExtraSelection s;
                s.format.setBackground(Bracket);
                QTextCursor pair(document());  // the partner: the bracket at the cursor is in view already
                pair.setPosition(i);
                pair.setPosition(i + 1, QTextCursor::KeepAnchor);
                s.cursor = pair;
                return s;
            }
        }
        return none;
    }
    return none;
}

int EditorView::gutterWidth() const
{
    const int digits = QString::number(std::max(1, blockCount())).size();
    return 22 + fontMetrics().horizontalAdvance(QLatin1Char('9')) * std::max(3, digits);
}

void EditorView::updateGutter(const QRect &rect, int dy)
{
    if (dy)
        m_gutter->scroll(0, dy);
    else
        m_gutter->update(0, rect.y(), m_gutter->width(), rect.height());
}

void EditorView::resizeEvent(QResizeEvent *e)
{
    QPlainTextEdit::resizeEvent(e);
    const QRect cr = contentsRect();
    m_gutter->setGeometry(QRect(cr.left(), cr.top(), gutterWidth(), cr.height()));
}

void EditorView::paintGutter(QPaintEvent *event)
{
    QPainter p(m_gutter);
    p.fillRect(event->rect(), Style::Bg);
    p.setFont(font());
    const int current = textCursor().blockNumber();
    QTextBlock block = firstVisibleBlock();
    int top = qRound(blockBoundingGeometry(block).translated(contentOffset()).top());
    int bottom = top + qRound(blockBoundingRect(block).height());
    while (block.isValid() && top <= event->rect().bottom()) {
        if (block.isVisible() && bottom >= event->rect().top()) {
            p.setPen(block.blockNumber() == current ? Style::Text : LineNumber);
            p.drawText(0, top, m_gutter->width() - 12, fontMetrics().height(), Qt::AlignRight,
                       QString::number(block.blockNumber() + 1));
        }
        block = block.next();
        top = bottom;
        bottom = top + qRound(blockBoundingRect(block).height());
    }
}
