// A tab: one or more TerminalPanes in nested splitters. Splitting the active pane in the same
// direction as its splitter adds a sibling; the other direction nests a new splitter in its place.
#pragma once

#include <QList>
#include <QWidget>

class QSplitter;
class TerminalPane;

class TabPage : public QWidget
{
    Q_OBJECT
public:
    explicit TabPage(const QString &dir, const QStringList &command = {}, QWidget *parent = nullptr);

    TerminalPane *activePane() const { return m_active; }
    QList<TerminalPane *> panes() const;

    void split(Qt::Orientation orientation);
    void closePane(TerminalPane *pane);
    void focusNeighbour(Qt::ArrowType direction);
    void refresh();  // re-read every pane's project (the visible tab, on a timer)

Q_SIGNALS:
    void infoChanged();  // the active pane's project or command changed, or another pane became active
    void empty();        // the last pane closed
    void bell();

private:
    TerminalPane *addPane(const QString &dir, const QStringList &command = {});
    void setActive(TerminalPane *pane);
    void updateOutlines();

    QSplitter *m_root;
    TerminalPane *m_active = nullptr;
};
