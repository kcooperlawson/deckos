// The item views for one folder: a QListView in list mode for Grid and List (its uniform-size
// fast path, which stays smooth at 50,000+ items) and a QTreeView for Details. Both share one
// selection model, so switching views keeps the selection.
#pragma once

#include <QAbstractItemModel>
#include <QStackedWidget>
#include <QTimer>
#include <QUrl>

#include <KFileItem>

class FolderModel;
class ItemDelegate;
class QAbstractItemView;
class QDropEvent;
class QHeaderView;
class QItemSelectionModel;
class QListView;
class QTreeView;

class FolderView : public QStackedWidget
{
    Q_OBJECT
public:
    enum Mode { Grid, List, Details };

    FolderView(FolderModel *model, QWidget *parent = nullptr);

    void setMode(Mode mode);
    Mode mode() const { return m_mode; }
    void setIconSize(int size);
    int iconSize() const;

    FolderModel *model() const { return m_model; }
    QAbstractItemView *view() const;
    QItemSelectionModel *selectionModel() const { return m_selection; }
    QHeaderView *header() const;

    KFileItemList selectedItems() const;
    QModelIndexList selectedRows() const;
    QList<int> visibleRows() const;
    void selectUrls(const QList<QUrl> &urls, bool scroll = true);
    void editCurrent();
    void setFocusToView();

    // Called by the views (they're template classes, so they can't have signals of their own).
    void emitActivated(const QModelIndex &index) { Q_EMIT activated(index); }
    void emitMiddleClicked(const QModelIndex &index) { Q_EMIT middleClicked(index); }
    void emitContextMenu(const QModelIndex &index, const QPoint &globalPos) { Q_EMIT contextMenuRequested(index, globalPos); }
    void emitBack() { Q_EMIT backRequested(); }
    void emitForward() { Q_EMIT forwardRequested(); }
    void emitZoom(int step) { Q_EMIT zoomRequested(step); }
    void emitFocusIn() { Q_EMIT focused(); }
    void emitDrop(QDropEvent *event, const QUrl &dest) { Q_EMIT dropped(event, dest); }
    void scheduleVisibleCheck();
    void relayoutGrid();
    ItemDelegate *delegate() const { return m_delegate; }

Q_SIGNALS:
    void activated(const QModelIndex &index);
    void middleClicked(const QModelIndex &index);
    void contextMenuRequested(const QModelIndex &index, const QPoint &globalPos);
    void backRequested();
    void forwardRequested();
    void zoomRequested(int step);
    void focused();
    void dropped(QDropEvent *event, const QUrl &dest);
    void selectionChanged();
    void visibleRowsChanged();

private:
    FolderModel *m_model;
    ItemDelegate *m_delegate;
    QListView *m_list;
    QTreeView *m_tree;
    QItemSelectionModel *m_selection;
    Mode m_mode = Grid;
    QTimer m_visibleTimer;
};
