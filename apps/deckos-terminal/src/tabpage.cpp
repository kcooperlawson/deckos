#include "tabpage.h"
#include "terminalpane.h"

#include <QPointer>
#include <QSplitter>
#include <QTimer>
#include <QVBoxLayout>

namespace {

QSplitter *makeSplitter(Qt::Orientation orientation)
{
    auto *s = new QSplitter(orientation);
    s->setChildrenCollapsible(false);
    s->setHandleWidth(3);
    return s;
}

} // namespace

TabPage::TabPage(const QString &dir, const QStringList &command, QWidget *parent)
    : QWidget(parent)
    , m_root(makeSplitter(Qt::Horizontal))
{
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(m_root);
    TerminalPane *first = addPane(dir, command);
    m_root->addWidget(first);
    setActive(first);
}

QList<TerminalPane *> TabPage::panes() const
{
    return m_root->findChildren<TerminalPane *>();
}

TerminalPane *TabPage::addPane(const QString &dir, const QStringList &command)
{
    auto *pane = new TerminalPane(dir, command);
    connect(pane, &TerminalPane::focused, this, &TabPage::setActive);
    connect(pane, &TerminalPane::finished, this, &TabPage::closePane);
    connect(pane, &TerminalPane::bell, this, &TabPage::bell);
    connect(pane, &TerminalPane::infoChanged, this, [this, pane] {
        if (pane == m_active)
            Q_EMIT infoChanged();
    });
    return pane;
}

void TabPage::setActive(TerminalPane *pane)
{
    if (m_active == pane)
        return;
    m_active = pane;
    updateOutlines();
    Q_EMIT infoChanged();
}

void TabPage::updateOutlines()
{
    const QList<TerminalPane *> all = panes();
    for (TerminalPane *p : all)
        p->setActive(all.size() > 1 && p == m_active);  // one pane needs no outline
}

void TabPage::split(Qt::Orientation orientation)
{
    TerminalPane *current = m_active;
    if (!current)
        return;
    auto *parent = qobject_cast<QSplitter *>(current->parentWidget());
    TerminalPane *pane = addPane(current->currentDir());
    if (parent->orientation() == orientation || parent->count() == 1) {
        parent->setOrientation(orientation);
        const int at = parent->indexOf(current);
        QList<int> sizes = parent->sizes();
        const int half = sizes.value(at) / 2;
        parent->insertWidget(at + 1, pane);
        sizes[at] = half;
        sizes.insert(at + 1, half);
        parent->setSizes(sizes);
    } else {
        const int at = parent->indexOf(current);
        const QList<int> sizes = parent->sizes();
        QSplitter *nested = makeSplitter(orientation);
        parent->replaceWidget(at, nested);
        nested->addWidget(current);
        nested->addWidget(pane);
        nested->setSizes({1, 1});
        parent->setSizes(sizes);
    }
    pane->focusTerminal();
    setActive(pane);
}

void TabPage::closePane(TerminalPane *pane)
{
    auto *parent = qobject_cast<QSplitter *>(pane->parentWidget());
    // The pane next to the closed one gets the focus, as in Konsole: picked before the tree changes.
    QPointer<TerminalPane> neighbour;
    if (parent && parent->count() > 1) {
        const int at = parent->indexOf(pane);
        QWidget *w = parent->widget(at > 0 ? at - 1 : at + 1);
        neighbour = qobject_cast<TerminalPane *>(w);
        if (!neighbour)
            neighbour = w->findChild<TerminalPane *>();
    }
    pane->hide();
    pane->setParent(nullptr);
    pane->deleteLater();
    if (pane == m_active)
        m_active = nullptr;

    // A splitter left with one child hands it to its own parent; an empty one goes away.
    while (parent && parent != m_root && parent->count() <= 1) {
        auto *grand = qobject_cast<QSplitter *>(parent->parentWidget());
        const int pos = grand->indexOf(parent);
        if (parent->count() == 1)
            grand->replaceWidget(pos, parent->widget(0));
        else
            parent->setParent(nullptr);
        parent->deleteLater();
        parent = grand;
    }

    const QList<TerminalPane *> rest = panes();
    if (rest.isEmpty()) {
        Q_EMIT empty();
        return;
    }
    if (!m_active) {
        setActive(neighbour ? neighbour.data() : rest.first());
        QPointer<TerminalPane> target = m_active;
        QTimer::singleShot(0, this, [target] {
            if (target)
                target->focusTerminal();
        });
    }
    updateOutlines();
}

void TabPage::focusNeighbour(Qt::ArrowType direction)
{
    if (!m_active)
        return;
    const QRect from(m_active->mapTo(this, QPoint(0, 0)), m_active->size());
    TerminalPane *best = nullptr;
    int bestDistance = INT_MAX;
    for (TerminalPane *p : panes()) {
        if (p == m_active)
            continue;
        const QRect r(p->mapTo(this, QPoint(0, 0)), p->size());
        int gap = -1;
        bool overlaps = false;
        switch (direction) {
        case Qt::LeftArrow: gap = from.left() - r.right(); overlaps = r.bottom() >= from.top() && r.top() <= from.bottom(); break;
        case Qt::RightArrow: gap = r.left() - from.right(); overlaps = r.bottom() >= from.top() && r.top() <= from.bottom(); break;
        case Qt::UpArrow: gap = from.top() - r.bottom(); overlaps = r.right() >= from.left() && r.left() <= from.right(); break;
        case Qt::DownArrow: gap = r.top() - from.bottom(); overlaps = r.right() >= from.left() && r.left() <= from.right(); break;
        default: break;
        }
        if (gap < 0 || !overlaps)
            continue;
        if (gap < bestDistance) {
            bestDistance = gap;
            best = p;
        }
    }
    if (best) {
        best->focusTerminal();
        setActive(best);
    }
}

void TabPage::refresh()
{
    for (TerminalPane *p : panes())
        p->refresh();
}
