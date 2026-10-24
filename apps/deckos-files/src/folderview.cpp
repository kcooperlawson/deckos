#include "folderview.h"

#include "foldermodel.h"
#include "itemdelegate.h"
#include "style.h"

#include <QApplication>
#include <QDrag>
#include <QHeaderView>
#include <QListView>
#include <QMimeData>
#include <QMouseEvent>
#include <QPainter>
#include <QProxyStyle>
#include <QScrollBar>
#include <QTreeView>

namespace {

// Keeps the base style for everything except item backgrounds and focus frames, which the
// delegate and views paint themselves.
class ViewStyle : public QProxyStyle
{
public:
    void drawPrimitive(PrimitiveElement pe, const QStyleOption *opt, QPainter *p, const QWidget *w) const override
    {
        if (pe == PE_FrameFocusRect || pe == PE_PanelItemViewRow || pe == PE_PanelItemViewItem)
            return;
        QProxyStyle::drawPrimitive(pe, opt, p, w);
    }
};

// Behaviour both views share: drops through KIO, middle-click, mouse back/forward, Ctrl+wheel
// zoom, a light drag pixmap.
template<class Base>
class ItemView : public Base
{
public:
    explicit ItemView(FolderView *owner)
        : Base(owner)
        , m_owner(owner)
    {
        this->setSelectionMode(QAbstractItemView::ExtendedSelection);
        this->setSelectionBehavior(QAbstractItemView::SelectRows);
        this->setEditTriggers(QAbstractItemView::NoEditTriggers);
        this->setDragDropMode(QAbstractItemView::DragDrop);
        this->setDropIndicatorShown(false);
        this->setDefaultDropAction(Qt::MoveAction);
        this->setContextMenuPolicy(Qt::CustomContextMenu);
        this->setFrameShape(QFrame::NoFrame);
        this->setMouseTracking(true);
        this->viewport()->setAttribute(Qt::WA_Hover);
        this->setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);
        this->setHorizontalScrollMode(QAbstractItemView::ScrollPerPixel);
        auto *style = new ViewStyle;
        style->setParent(this);
        this->setStyle(style);
        QObject::connect(this, &QAbstractItemView::activated, owner, &FolderView::emitActivated);
        QObject::connect(this, &QWidget::customContextMenuRequested, owner, [this](const QPoint &pos) {
            m_owner->emitContextMenu(this->indexAt(pos), this->viewport()->mapToGlobal(pos));
        });
        QObject::connect(this->verticalScrollBar(), &QScrollBar::valueChanged, owner, &FolderView::scheduleVisibleCheck);
        QObject::connect(this->horizontalScrollBar(), &QScrollBar::valueChanged, owner, &FolderView::scheduleVisibleCheck);
    }

protected:
    void mousePressEvent(QMouseEvent *e) override
    {
        if (e->button() == Qt::BackButton) {
            m_owner->emitBack();
            return;
        }
        if (e->button() == Qt::ForwardButton) {
            m_owner->emitForward();
            return;
        }
        Base::mousePressEvent(e);
    }

    void mouseReleaseEvent(QMouseEvent *e) override
    {
        if (e->button() == Qt::MiddleButton) {
            const QModelIndex idx = this->indexAt(e->position().toPoint());
            if (idx.isValid())
                m_owner->emitMiddleClicked(idx);
            return;
        }
        Base::mouseReleaseEvent(e);
    }

    void wheelEvent(QWheelEvent *e) override
    {
        if (e->modifiers() & Qt::ControlModifier) {
            m_zoomAccum += e->angleDelta().y();
            if (qAbs(m_zoomAccum) >= 120) {
                m_owner->emitZoom(m_zoomAccum > 0 ? 1 : -1);
                m_zoomAccum = 0;
            }
            e->accept();
            return;
        }
        Base::wheelEvent(e);
    }

    void focusInEvent(QFocusEvent *e) override
    {
        Base::focusInEvent(e);
        m_owner->emitFocusIn();
    }

    void resizeEvent(QResizeEvent *e) override
    {
        Base::resizeEvent(e);
        m_owner->scheduleVisibleCheck();
    }

    void dragEnterEvent(QDragEnterEvent *e) override
    {
        if (e->mimeData()->hasUrls())
            e->acceptProposedAction();
        else
            e->ignore();
    }

    void dragMoveEvent(QDragMoveEvent *e) override
    {
        Base::dragMoveEvent(e);  // autoscroll
        if (!e->mimeData()->hasUrls()) {
            e->ignore();
            return;
        }
        const QModelIndex idx = this->indexAt(e->position().toPoint());
        const QModelIndex target = idx.isValid() && idx.data(FolderModel::IsDirRole).toBool() ? idx.siblingAtColumn(0) : QModelIndex();
        if (target != m_dropTarget) {
            m_dropTarget = target;
            this->viewport()->update();
        }
        e->acceptProposedAction();
    }

    void dragLeaveEvent(QDragLeaveEvent *e) override
    {
        Base::dragLeaveEvent(e);
        m_dropTarget = QModelIndex();
        this->viewport()->update();
    }

    void dropEvent(QDropEvent *e) override
    {
        const QModelIndex idx = this->indexAt(e->position().toPoint());
        QUrl dest = m_owner->model()->url();
        if (idx.isValid() && idx.data(FolderModel::IsDirRole).toBool())
            dest = m_owner->model()->itemForIndex(idx).url();
        m_dropTarget = QModelIndex();
        this->viewport()->update();
        // Dropping items back onto the folder they came from does nothing.
        if (e->source() == this && dest == m_owner->model()->url()) {
            e->ignore();
            return;
        }
        m_owner->emitDrop(e, dest);
        e->acceptProposedAction();
    }

    void startDrag(Qt::DropActions actions) override
    {
        const QModelIndexList rows = m_owner->selectedRows();
        if (rows.isEmpty())
            return;
        auto *drag = new QDrag(this);
        drag->setMimeData(m_owner->model()->mimeData(rows));
        // One icon and a count, rather than a picture of every selected item.
        const qreal dpr = this->devicePixelRatioF();
        QPixmap pm(QSize(64, 64) * dpr);
        pm.setDevicePixelRatio(dpr);
        pm.fill(Qt::transparent);
        QPainter p(&pm);
        p.setRenderHint(QPainter::Antialiasing);
        const QPixmap thumb = rows.first().data(FolderModel::ThumbnailRole).value<QPixmap>();
        if (!thumb.isNull())
            p.drawPixmap(QRect(4, 4, 48, 48), thumb.scaled(QSize(48, 48) * dpr, Qt::KeepAspectRatio, Qt::SmoothTransformation));
        else
            rows.first().data(Qt::DecorationRole).value<QIcon>().paint(&p, QRect(4, 4, 48, 48));
        if (rows.size() > 1) {
            p.setPen(Qt::NoPen);
            p.setBrush(Style::accent());
            p.drawRoundedRect(QRectF(34, 36, 28, 20), 10, 10);
            p.setPen(Qt::white);
            QFont f = this->font();
            f.setBold(true);
            f.setPointSizeF(f.pointSizeF() * 0.85);
            p.setFont(f);
            p.drawText(QRectF(34, 36, 28, 20), Qt::AlignCenter, rows.size() > 99 ? QStringLiteral("99+") : QString::number(rows.size()));
        }
        p.end();
        drag->setPixmap(pm);
        drag->setHotSpot(QPoint(24, 24));
        drag->exec(actions, Qt::IgnoreAction);
    }

    void paintEvent(QPaintEvent *e) override
    {
        Base::paintEvent(e);
        if (m_dropTarget.isValid()) {
            QPainter p(this->viewport());
            p.setRenderHint(QPainter::Antialiasing);
            QRect r = this->visualRect(m_dropTarget);
            if (QTreeView *tree = qobject_cast<QTreeView *>(this))
                r = QRect(0, r.y(), tree->viewport()->width(), r.height());
            p.setPen(QPen(Style::accent(), 2));
            p.setBrush(Qt::NoBrush);
            p.drawRoundedRect(QRectF(r).adjusted(3, 3, -3, -3), 8, 8);
        }
    }

    FolderView *m_owner;
    QPersistentModelIndex m_dropTarget;
    int m_zoomAccum = 0;
};

class GridView : public ItemView<QListView>
{
public:
    explicit GridView(FolderView *owner)
        : ItemView<QListView>(owner)
    {
        setViewMode(QListView::ListMode);  // list mode's uniform-size layout is far cheaper than icon mode
        setMovement(QListView::Static);
        // Static movement means "icons can't be rearranged", and QListView takes it as "no drag and
        // drop" too: it switches dragging off and the viewport's drops off. Files are still dragged.
        setDragEnabled(true);
        viewport()->setAcceptDrops(true);
        setDragDropMode(QAbstractItemView::DragDrop);
        setResizeMode(QListView::Adjust);
        setUniformItemSizes(true);
        setWrapping(true);
        setLayoutMode(QListView::Batched);
        setBatchSize(4000);
        setSpacing(0);
        setWordWrap(false);
        setTextElideMode(Qt::ElideMiddle);
    }

protected:
    void resizeEvent(QResizeEvent *e) override
    {
        ItemView<QListView>::resizeEvent(e);
        m_owner->relayoutGrid();
    }
};

class DetailsView : public ItemView<QTreeView>
{
public:
    explicit DetailsView(FolderView *owner)
        : ItemView<QTreeView>(owner)
    {
        setRootIsDecorated(false);
        setItemsExpandable(false);
        setUniformRowHeights(true);
        setAllColumnsShowFocus(true);
        setIndentation(0);
        setExpandsOnDoubleClick(false);
        header()->setStretchLastSection(false);
        header()->setSectionsMovable(true);
        header()->setHighlightSections(false);
        header()->setDefaultAlignment(Qt::AlignLeft | Qt::AlignVCenter);
        header()->setStyleSheet(QStringLiteral(
            "QHeaderView { background: #0F1115; border: none; border-bottom: 1px solid #262B36; }"
            "QHeaderView::section { background: #0F1115; color: #8C94A6; border: none; padding: 6px 10px;"
            " font-weight: 600; }"
            "QHeaderView::section:hover { color: #E8EAF0; }"
            "QHeaderView::up-arrow, QHeaderView::down-arrow { width: 10px; height: 10px; subcontrol-position: center right; }"));
        QPalette pal = palette();
        pal.setColor(QPalette::Highlight, Qt::transparent);
        setPalette(pal);
    }

protected:
    void drawRow(QPainter *p, const QStyleOptionViewItem &opt, const QModelIndex &index) const override
    {
        const bool selected = selectionModel() && selectionModel()->isSelected(index.siblingAtColumn(0));
        const bool hover = index.row() == m_hoverRow;
        if (selected || hover) {
            p->save();
            p->setRenderHint(QPainter::Antialiasing);
            p->setPen(selected ? QPen(Style::accent(), 1) : Qt::NoPen);
            p->setBrush(selected ? Style::selectionFill() : Style::hoverFill());
            const QRect r(4, opt.rect.y(), viewport()->width() - 8, opt.rect.height());
            p->drawRoundedRect(QRectF(r).adjusted(0.5, 1.5, -0.5, -1.5), 7, 7);
            p->restore();
        }
        QStyleOptionViewItem o = opt;
        if (hover)
            o.state |= QStyle::State_MouseOver;
        ItemView<QTreeView>::drawRow(p, o, index);
    }

    void mouseMoveEvent(QMouseEvent *e) override
    {
        ItemView<QTreeView>::mouseMoveEvent(e);
        const int row = indexAt(e->position().toPoint()).row();
        if (row != m_hoverRow) {
            m_hoverRow = row;
            viewport()->update();
        }
    }

    void leaveEvent(QEvent *e) override
    {
        ItemView<QTreeView>::leaveEvent(e);
        m_hoverRow = -1;
        viewport()->update();
    }

private:
    int m_hoverRow = -1;
};

} // namespace

FolderView::FolderView(FolderModel *model, QWidget *parent)
    : QStackedWidget(parent)
    , m_model(model)
    , m_delegate(new ItemDelegate(this))
{
    m_list = new GridView(this);
    m_tree = new DetailsView(this);
    for (QAbstractItemView *v : {static_cast<QAbstractItemView *>(m_list), static_cast<QAbstractItemView *>(m_tree)}) {
        v->setModel(model);
        v->setItemDelegate(m_delegate);
    }
    // One selection for both views.
    QItemSelectionModel *own = m_tree->selectionModel();
    m_selection = m_list->selectionModel();
    m_tree->setSelectionModel(m_selection);
    delete own;
    connect(m_selection, &QItemSelectionModel::selectionChanged, this, &FolderView::selectionChanged);

    QHeaderView *h = m_tree->header();
    h->resizeSection(FolderModel::NameColumn, 440);
    h->resizeSection(FolderModel::SizeColumn, 110);
    h->resizeSection(FolderModel::ModifiedColumn, 170);
    h->resizeSection(FolderModel::TypeColumn, 190);
    h->setSortIndicator(model->sortColumn(), model->sortOrder());
    m_tree->setSortingEnabled(true);  // after the indicator, or it sorts by the header's default first

    addWidget(m_list);
    addWidget(m_tree);

    m_visibleTimer.setSingleShot(true);
    m_visibleTimer.setInterval(60);
    connect(&m_visibleTimer, &QTimer::timeout, this, &FolderView::visibleRowsChanged);
    for (auto sig : {&QAbstractItemModel::rowsInserted, &QAbstractItemModel::rowsRemoved})
        connect(model, sig, this, &FolderView::scheduleVisibleCheck);
    connect(model, &QAbstractItemModel::layoutChanged, this, &FolderView::scheduleVisibleCheck);
    connect(model, &QAbstractItemModel::modelReset, this, &FolderView::scheduleVisibleCheck);

    setMode(Grid);
}

QAbstractItemView *FolderView::view() const
{
    return m_mode == Details ? static_cast<QAbstractItemView *>(m_tree) : static_cast<QAbstractItemView *>(m_list);
}

QHeaderView *FolderView::header() const
{
    return m_tree->header();
}

void FolderView::setMode(Mode mode)
{
    const bool hadFocus = view()->hasFocus();
    m_mode = mode;
    const int size = mode == Grid ? 64 : 22;
    m_delegate->setMode(mode == Grid ? ItemDelegate::Grid : mode == List ? ItemDelegate::List : ItemDelegate::Details, size);
    if (mode == Details) {
        setCurrentWidget(m_tree);
    } else {
        m_list->setFlow(mode == Grid ? QListView::LeftToRight : QListView::TopToBottom);
        // The grid always fits the width; only the compact list scrolls sideways.
        m_list->setHorizontalScrollBarPolicy(mode == Grid ? Qt::ScrollBarAlwaysOff : Qt::ScrollBarAsNeeded);
        relayoutGrid();
        setCurrentWidget(m_list);
    }
    const QModelIndex current = m_selection->currentIndex();
    if (current.isValid())
        view()->scrollTo(current);
    if (hadFocus)
        view()->setFocus();
    scheduleVisibleCheck();
}

void FolderView::setIconSize(int size)
{
    m_delegate->setMode(m_delegate->mode(), size);
    if (m_mode == Details) {
        m_tree->doItemsLayout();
        m_tree->viewport()->update();
    } else {
        relayoutGrid();
    }
    scheduleVisibleCheck();
}

int FolderView::iconSize() const
{
    return m_delegate->iconSize();
}

void FolderView::relayoutGrid()
{
    QSize cell = m_delegate->naturalCellSize();
    if (m_mode == Grid) {
        // Spread the leftover width over the columns so the grid fills the view edge to edge.
        const int avail = qMax(1, m_list->viewport()->width() - 8);
        const int cols = qMax(1, avail / cell.width());
        cell.setWidth(avail / cols);
    }
    m_delegate->setGridWidth(m_mode == Grid ? cell.width() : 0);
    if (m_list->gridSize() != cell)
        m_list->setGridSize(cell);
}

void FolderView::scheduleVisibleCheck()
{
    m_visibleTimer.start();
}

KFileItemList FolderView::selectedItems() const
{
    KFileItemList items;
    for (const QModelIndex &idx : selectedRows())
        items << m_model->itemForIndex(idx);
    return items;
}

QModelIndexList FolderView::selectedRows() const
{
    QModelIndexList rows = m_selection->selectedRows(0);
    std::sort(rows.begin(), rows.end(), [](const QModelIndex &a, const QModelIndex &b) { return a.row() < b.row(); });
    return rows;
}

QList<int> FolderView::visibleRows() const
{
    QList<int> rows;
    QAbstractItemView *v = view();
    const QRect area = v->viewport()->rect();
    QModelIndex first = v->indexAt(QPoint(4, 4));
    if (!first.isValid())
        first = v->indexAt(QPoint(m_delegate->cellSize().width() / 2, m_delegate->cellSize().height() / 2));
    if (!first.isValid())
        first = m_model->index(0, 0);
    const int count = m_model->rowCount();
    for (int row = qMax(0, first.row()); row < count && rows.size() < 2000; ++row) {
        const QRect r = v->visualRect(m_model->index(row, 0));
        if (r.top() > area.bottom() || r.left() > area.right())
            break;
        if (r.intersects(area))
            rows << row;
    }
    return rows;
}

void FolderView::selectUrls(const QList<QUrl> &urls, bool scroll)
{
    QItemSelection sel;
    QModelIndex last;
    for (const QUrl &u : urls) {
        const QModelIndex idx = m_model->indexForUrl(u);
        if (idx.isValid()) {
            sel.select(idx, idx.siblingAtColumn(FolderModel::ColumnCount - 1));
            last = idx;
        }
    }
    if (!last.isValid())
        return;
    m_selection->select(sel, QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Rows);
    m_selection->setCurrentIndex(last, QItemSelectionModel::NoUpdate);
    if (scroll)
        view()->scrollTo(last);
}

void FolderView::editCurrent()
{
    QModelIndex idx = m_selection->currentIndex();
    if (!idx.isValid() || !m_selection->isSelected(idx.siblingAtColumn(0))) {
        const QModelIndexList rows = selectedRows();
        if (rows.isEmpty())
            return;
        idx = rows.first();
    }
    idx = idx.siblingAtColumn(0);
    view()->scrollTo(idx);
    view()->edit(idx);
}

void FolderView::setFocusToView()
{
    view()->setFocus();
}
