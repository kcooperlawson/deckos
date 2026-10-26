#include "findbar.h"

#include "editorview.h"
#include "style.h"

#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QRegularExpression>
#include <QTextBlock>
#include <QToolButton>
#include <QVBoxLayout>

namespace {

QToolButton *toggle(const QString &text, const QString &tip, QWidget *parent)
{
    auto *b = new QToolButton(parent);
    b->setText(text);
    b->setToolTip(tip);
    b->setCheckable(true);
    b->setAutoRaise(true);
    b->setCursor(Qt::PointingHandCursor);
    return b;
}

constexpr int MaxMatches = 10000;  // lighting more than this is slower than it is useful

} // namespace

FindBar::FindBar(QWidget *parent)
    : QFrame(parent)
{
    setObjectName(QStringLiteral("findBar"));
    auto *v = new QVBoxLayout(this);
    v->setContentsMargins(12, 8, 12, 8);
    v->setSpacing(6);

    auto *row = new QHBoxLayout;
    m_find = new QLineEdit(this);
    m_find->setPlaceholderText(QStringLiteral("Find"));
    m_find->setClearButtonEnabled(true);
    row->addWidget(m_find, 1);
    m_case = toggle(QStringLiteral("Aa"), QStringLiteral("Match case"), this);
    m_words = toggle(QStringLiteral("W"), QStringLiteral("Whole words"), this);
    m_regex = toggle(QStringLiteral(".*"), QStringLiteral("Regular expression"), this);
    row->addWidget(m_case);
    row->addWidget(m_words);
    row->addWidget(m_regex);
    m_count = new QLabel(this);
    m_count->setMinimumWidth(90);
    m_count->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    row->addWidget(m_count);
    auto *prev = new QToolButton(this);
    prev->setIcon(Style::icon(QStringLiteral("chevron-left")));
    prev->setToolTip(QStringLiteral("Previous (Shift+Enter)"));
    prev->setAutoRaise(true);
    auto *nextB = new QToolButton(this);
    nextB->setIcon(Style::icon(QStringLiteral("chevron")));
    nextB->setToolTip(QStringLiteral("Next (Enter)"));
    nextB->setAutoRaise(true);
    auto *closeB = new QToolButton(this);
    closeB->setIcon(Style::icon(QStringLiteral("close")));
    closeB->setToolTip(QStringLiteral("Close (Esc)"));
    closeB->setAutoRaise(true);
    row->addWidget(prev);
    row->addWidget(nextB);
    row->addWidget(closeB);
    v->addLayout(row);

    m_replaceRow = new QWidget(this);
    auto *r = new QHBoxLayout(m_replaceRow);
    r->setContentsMargins(0, 0, 0, 0);
    m_replace = new QLineEdit(m_replaceRow);
    m_replace->setPlaceholderText(QStringLiteral("Replace with"));
    r->addWidget(m_replace, 1);
    auto *one = new QPushButton(QStringLiteral("Replace"), m_replaceRow);
    auto *all = new QPushButton(QStringLiteral("Replace all"), m_replaceRow);
    r->addWidget(one);
    r->addWidget(all);
    v->addWidget(m_replaceRow);

    connect(m_find, &QLineEdit::textChanged, this, &FindBar::refresh);
    for (QToolButton *t : {m_case, m_words, m_regex})
        connect(t, &QToolButton::toggled, this, &FindBar::refresh);
    connect(m_find, &QLineEdit::returnPressed, this, [this] { next(QGuiApplication::keyboardModifiers() & Qt::ShiftModifier); });
    connect(m_replace, &QLineEdit::returnPressed, this, &FindBar::replaceOne);
    connect(prev, &QToolButton::clicked, this, [this] { next(true); });
    connect(nextB, &QToolButton::clicked, this, [this] { next(false); });
    connect(closeB, &QToolButton::clicked, this, &FindBar::close_);
    connect(one, &QPushButton::clicked, this, &FindBar::replaceOne);
    connect(all, &QPushButton::clicked, this, &FindBar::replaceAll);
    hide();
}

void FindBar::setView(EditorView *view)
{
    if (m_view)
        m_view->setSearchMatches({});
    m_view = view;
    if (isVisible())
        refresh();
}

void FindBar::open(bool replace)
{
    m_replaceRow->setVisible(replace);
    // A one-line selection is what to look for
    if (m_view && m_view->textCursor().hasSelection() && !m_view->textCursor().selectedText().contains(QChar::ParagraphSeparator))
        m_find->setText(m_view->textCursor().selectedText());
    show();
    m_find->setFocus();
    m_find->selectAll();
    refresh();
}

void FindBar::close_()
{
    hide();
    if (m_view) {
        m_view->setSearchMatches({});
        m_view->setFocus();
    }
}

QList<QPair<int, int>> FindBar::matches(const QString &text, const QString &query, bool caseSensitive, bool regex,
                                        bool wholeWords, QString *error)
{
    QList<QPair<int, int>> out;
    if (query.isEmpty())
        return out;
    QString pattern = regex ? query : QRegularExpression::escape(query);
    if (wholeWords)
        pattern = QStringLiteral("\\b(?:") + pattern + QStringLiteral(")\\b");
    QRegularExpression re(pattern, caseSensitive ? QRegularExpression::NoPatternOption
                                                 : QRegularExpression::CaseInsensitiveOption);
    re.setPatternOptions(re.patternOptions() | QRegularExpression::MultilineOption | QRegularExpression::UseUnicodePropertiesOption);
    if (!re.isValid()) {
        if (error)
            *error = re.errorString();
        return out;
    }
    auto it = re.globalMatch(text);
    while (it.hasNext() && out.size() < MaxMatches) {
        const auto m = it.next();
        if (m.capturedLength() > 0)
            out.append({int(m.capturedStart()), int(m.capturedLength())});
    }
    return out;
}

QList<QTextCursor> FindBar::cursors() const
{
    QList<QTextCursor> out;
    if (!m_view)
        return out;
    QString error;
    for (const auto &[start, len] : matches(m_view->toPlainText(), m_find->text(), m_case->isChecked(),
                                            m_regex->isChecked(), m_words->isChecked(), &error)) {
        QTextCursor c(m_view->document());
        c.setPosition(start);
        c.setPosition(start + len, QTextCursor::KeepAnchor);
        out.append(c);
    }
    return out;
}

void FindBar::refresh()
{
    if (!m_view || !isVisible())
        return;
    QString error;
    matches({}, m_find->text(), false, m_regex->isChecked(), false, &error);
    const auto all = cursors();
    m_view->setSearchMatches(all);
    if (!error.isEmpty())
        m_count->setText(QStringLiteral("Not a valid pattern"));
    else if (m_find->text().isEmpty())
        m_count->clear();
    else if (all.isEmpty())
        m_count->setText(QStringLiteral("No matches"));
    else
        m_count->setText(all.size() >= MaxMatches ? QStringLiteral("10,000+ matches")
                         : all.size() == 1        ? QStringLiteral("1 match")
                                                  : QStringLiteral("%1 matches").arg(all.size()));
    m_count->setStyleSheet(all.isEmpty() && !m_find->text().isEmpty() ? QStringLiteral("color: #FF6B6B;") : QString());
}

void FindBar::next(bool backwards)
{
    const auto all = cursors();
    if (!m_view || all.isEmpty())
        return;
    const int at = backwards ? m_view->textCursor().selectionStart() : m_view->textCursor().selectionEnd();
    QTextCursor pick = backwards ? all.last() : all.first();  // wraps around
    if (backwards) {
        for (auto it = all.crbegin(); it != all.crend(); ++it)
            if (it->selectionEnd() <= at && it->selectionStart() < at) {
                pick = *it;
                break;
            }
    } else {
        for (const QTextCursor &c : all)
            if (c.selectionStart() >= at) {
                pick = c;
                break;
            }
    }
    m_view->setTextCursor(pick);
    m_view->centerCursor();
    m_view->setSearchMatches(all);
}

void FindBar::replaceOne()
{
    if (!m_view)
        return;
    const QTextCursor sel = m_view->textCursor();
    // Replace the current match if one is selected, then move to the next
    for (const QTextCursor &c : cursors()) {
        if (c.selectionStart() == sel.selectionStart() && c.selectionEnd() == sel.selectionEnd()) {
            QTextCursor edit = sel;
            if (m_regex->isChecked()) {
                QRegularExpression re(m_find->text(), m_case->isChecked() ? QRegularExpression::NoPatternOption
                                                                         : QRegularExpression::CaseInsensitiveOption);
                edit.insertText(sel.selectedText().replace(re, m_replace->text()));
            } else {
                edit.insertText(m_replace->text());
            }
            m_view->setTextCursor(edit);
            break;
        }
    }
    next(false);
    refresh();
}

void FindBar::replaceAll()
{
    if (!m_view)
        return;
    const auto all = cursors();
    QTextCursor edit(m_view->document());
    edit.beginEditBlock();  // one undo step for the lot
    // From the end, so earlier positions stay valid
    for (auto it = all.crbegin(); it != all.crend(); ++it) {
        QTextCursor c = *it;
        if (m_regex->isChecked()) {
            QRegularExpression re(m_find->text(), m_case->isChecked() ? QRegularExpression::NoPatternOption
                                                                     : QRegularExpression::CaseInsensitiveOption);
            c.insertText(c.selectedText().replace(re, m_replace->text()));
        } else {
            c.insertText(m_replace->text());
        }
    }
    edit.endEditBlock();
    m_count->setText(all.size() == 1 ? QStringLiteral("Replaced 1") : QStringLiteral("Replaced %1").arg(all.size()));
    m_view->setSearchMatches({});
}
