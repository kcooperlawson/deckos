#include "sidebar.h"

#include "operations.h"
#include "style.h"

#include <QHash>
#include <QMenu>
#include <QMimeData>
#include <QMouseEvent>
#include <QPainter>
#include <QStorageInfo>
#include <QStyledItemDelegate>
#include <QTimer>

#include <KCoreDirLister>
#include <KFilePlacesModel>
#include <KUrlMimeData>

namespace {

constexpr int RowH = 32;
constexpr int HeaderH = 30;
constexpr int BarH = 4;

QString groupName(KFilePlacesModel::GroupType g)
{
    switch (g) {
    case KFilePlacesModel::PlacesType:
        return QStringLiteral("PLACES");
    case KFilePlacesModel::RemoteType:
        return QStringLiteral("NETWORK");
    case KFilePlacesModel::DevicesType:
        return QStringLiteral("DRIVES");
    case KFilePlacesModel::RemovableDevicesType:
        return QStringLiteral("REMOVABLE");
    default:
        return QString();
    }
}

bool firstOfGroup(const QListView *view, const KFilePlacesModel *m, const QModelIndex &idx)
{
    for (int r = idx.row() - 1; r >= 0; --r) {
        if (view->isRowHidden(r))
            continue;
        return m->groupType(m->index(r, 0)) != m->groupType(idx);
    }
    return true;
}

class PlacesDelegate : public QStyledItemDelegate
{
public:
    PlacesDelegate(Sidebar *view, KFilePlacesModel *places)
        : QStyledItemDelegate(view), m_view(view), m_places(places)
    {
    }

    QSize sizeHint(const QStyleOptionViewItem &, const QModelIndex &idx) const override
    {
        int h = RowH;
        if (firstOfGroup(m_view, m_places, idx))
            h += HeaderH;
        if (usage(idx) >= 0)
            h += BarH + 4;
        return {200, h};
    }

    void paint(QPainter *p, const QStyleOptionViewItem &opt, const QModelIndex &idx) const override
    {
        p->save();
        p->setRenderHint(QPainter::Antialiasing);
        QRect r = opt.rect.adjusted(8, 0, -8, 0);
        if (firstOfGroup(m_view, m_places, idx)) {
            QFont f = opt.font;
            f.setPointSizeF(f.pointSizeF() * 0.8);
            f.setWeight(QFont::DemiBold);
            f.setLetterSpacing(QFont::AbsoluteSpacing, 0.8);
            p->setFont(f);
            p->setPen(Style::Muted);
            p->drawText(QRect(r.x() + 10, r.y() + 10, r.width(), HeaderH - 10), Qt::AlignLeft | Qt::AlignVCenter,
                        groupName(m_places->groupType(idx)));
            r.setTop(r.top() + HeaderH);
        }
        const bool selected = opt.state & QStyle::State_Selected;
        const bool hover = opt.state & QStyle::State_MouseOver;
        if (selected || hover) {
            p->setPen(Qt::NoPen);
            p->setBrush(selected ? Style::selectionFill() : Style::hoverFill());
            p->drawRoundedRect(QRectF(r).adjusted(0, 1, 0, -1), 8, 8);
        }
        const bool unmounted = m_places->setupNeeded(idx);
        const QRect iconRect(r.x() + 10, r.y() + (RowH - 18) / 2, 18, 18);
        m_places->icon(idx).paint(p, iconRect, Qt::AlignCenter, unmounted ? QIcon::Disabled : QIcon::Normal);
        const bool eject = m_places->data(idx, KFilePlacesModel::EjectAllowedRole).toBool()
            || m_places->data(idx, KFilePlacesModel::TeardownAllowedRole).toBool();
        QString text = m_places->text(idx);
        int right = r.right() - 8;
        if (eject && !unmounted) {
            p->drawPixmap(QRect(right - 16, r.y() + (RowH - 16) / 2, 16, 16), Style::pixmap(QStringLiteral("eject"), Style::Subtext, 16, p->device()->devicePixelRatioF()));
            right -= 22;
        }
        if (m_places->url(idx).scheme() == QLatin1String("trash")) {
            if (const int n = m_view->trashCount(); n > 0) {
                const QString c = QString::number(n);
                p->setPen(Style::Subtext);
                p->setFont(opt.font);
                p->drawText(QRect(right - 40, r.y(), 40, RowH), Qt::AlignRight | Qt::AlignVCenter, c);
                right -= 44;
            }
        }
        p->setFont(opt.font);
        p->setPen(unmounted ? Style::Subtext : Style::Text);
        const QRect textRect(iconRect.right() + 10, r.y(), right - iconRect.right() - 10, RowH);
        p->drawText(textRect, Qt::AlignLeft | Qt::AlignVCenter, opt.fontMetrics.elidedText(text, Qt::ElideRight, textRect.width()));
        const double used = usage(idx);
        if (used >= 0) {
            const QRectF bar(textRect.x(), r.y() + RowH - 3, textRect.width(), BarH);
            p->setPen(Qt::NoPen);
            p->setBrush(Style::Border);
            p->drawRoundedRect(bar, 2, 2);
            p->setBrush(used > 0.9 ? Style::Danger : Style::accent());
            p->drawRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * used, BarH), 2, 2);
        }
        p->restore();
    }

    bool ejectHit(const QModelIndex &idx, const QPoint &pos) const
    {
        const bool eject = m_places->data(idx, KFilePlacesModel::EjectAllowedRole).toBool()
            || m_places->data(idx, KFilePlacesModel::TeardownAllowedRole).toBool();
        if (!eject || m_places->setupNeeded(idx))
            return false;
        const QRect r = m_view->visualRect(idx);
        return pos.x() > r.right() - 40 && pos.y() > r.bottom() - RowH - BarH - 4;
    }

    // Share of a mounted drive in use, or -1 when there's no bar to draw. Cached; refreshed
    // by the sidebar's timer.
    double usage(const QModelIndex &idx) const
    {
        if (!m_places->data(idx, KFilePlacesModel::CapacityBarRecommendedRole).toBool() || m_places->setupNeeded(idx))
            return -1;
        const QUrl url = m_places->url(idx);
        if (!url.isLocalFile())
            return -1;
        auto it = m_usage.constFind(url);
        if (it != m_usage.constEnd())
            return *it;
        const QStorageInfo info(url.toLocalFile());
        const double used = info.isValid() && info.bytesTotal() > 0 ? 1.0 - double(info.bytesAvailable()) / double(info.bytesTotal()) : -1;
        m_usage.insert(url, used);
        return used;
    }

    void clearUsage() { m_usage.clear(); }

private:
    Sidebar *m_view;
    KFilePlacesModel *m_places;
    mutable QHash<QUrl, double> m_usage;
};

} // namespace

Sidebar::Sidebar(KFilePlacesModel *places, QWidget *parent)
    : QListView(parent)
    , m_places(places)
    , m_trash(new KCoreDirLister(this))
{
    setModel(places);
    auto *delegate = new PlacesDelegate(this, places);
    setItemDelegate(delegate);
    setFrameShape(QFrame::NoFrame);
    setMouseTracking(true);
    viewport()->setAttribute(Qt::WA_Hover);
    setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);
    setAcceptDrops(true);
    setDropIndicatorShown(false);
    setEditTriggers(NoEditTriggers);
    setAutoFillBackground(true);
    QPalette pal = palette();
    pal.setColor(QPalette::Base, Style::Sidebar);
    pal.setColor(QPalette::Window, Style::Sidebar);
    setPalette(pal);

    connect(places, &QAbstractItemModel::rowsInserted, this, &Sidebar::updateHidden);
    connect(places, &QAbstractItemModel::rowsRemoved, this, &Sidebar::updateHidden);
    connect(places, &QAbstractItemModel::modelReset, this, &Sidebar::updateHidden);
    connect(places, &QAbstractItemModel::dataChanged, this, [this, delegate] {
        delegate->clearUsage();
        updateHidden();
    });
    connect(places, &KFilePlacesModel::setupDone, this, [this](const QModelIndex &idx, bool ok) {
        if (ok)
            Q_EMIT placeActivated(m_places->url(idx));
    });
    auto *refresh = new QTimer(this);
    refresh->start(30000);
    connect(refresh, &QTimer::timeout, this, [this, delegate] {
        delegate->clearUsage();
        viewport()->update();
    });
    updateHidden();

    // The trash count comes from a live listing of trash:/ a moment after start.
    connect(m_trash, &KCoreDirLister::completed, viewport(), qOverload<>(&QWidget::update));
    connect(m_trash, &KCoreDirLister::itemsDeleted, viewport(), qOverload<>(&QWidget::update));
    connect(m_trash, &KCoreDirLister::itemsAdded, viewport(), qOverload<>(&QWidget::update));
    QTimer::singleShot(800, this, [this] { m_trash->openUrl(QUrl(QStringLiteral("trash:/"))); });
}

int Sidebar::trashCount() const
{
    return m_trash->items().size();
}

void Sidebar::updateHidden()
{
    // Recent files, search shortcuts and tags aren't part of DecKoOS Files' sidebar.
    for (int r = 0; r < m_places->rowCount(); ++r) {
        const QModelIndex idx = m_places->index(r, 0);
        const auto g = m_places->groupType(idx);
        const bool hide = m_places->isHidden(idx) || g == KFilePlacesModel::RecentlySavedType || g == KFilePlacesModel::SearchForType
            || g == KFilePlacesModel::TagsType || g == KFilePlacesModel::UnknownType;
        setRowHidden(r, hide);
    }
    doItemsLayout();
}

void Sidebar::setCurrentUrl(const QUrl &url)
{
    const QModelIndex idx = m_places->closestItem(url);
    if (idx.isValid() && m_places->url(idx).matches(url, QUrl::StripTrailingSlash))
        setCurrentIndex(idx);
    else
        clearSelection();
}

void Sidebar::open(const QModelIndex &idx, bool newTab)
{
    if (!idx.isValid())
        return;
    if (m_places->setupNeeded(idx)) {
        m_places->requestSetup(idx);  // mounts it; setupDone opens it
        return;
    }
    if (newTab)
        Q_EMIT placeActivatedInNewTab(m_places->url(idx));
    else
        Q_EMIT placeActivated(m_places->url(idx));
}

void Sidebar::mouseReleaseEvent(QMouseEvent *e)
{
    const QModelIndex idx = indexAt(e->position().toPoint());
    auto *d = static_cast<PlacesDelegate *>(itemDelegate());
    if (idx.isValid() && e->button() == Qt::LeftButton && d->ejectHit(idx, e->position().toPoint())) {
        if (m_places->data(idx, KFilePlacesModel::EjectAllowedRole).toBool())
            m_places->requestEject(idx);
        else
            m_places->requestTeardown(idx);
        return;
    }
    QListView::mouseReleaseEvent(e);
    if (e->button() == Qt::LeftButton || e->button() == Qt::MiddleButton)
        open(idx, e->button() == Qt::MiddleButton);
}

void Sidebar::contextMenuEvent(QContextMenuEvent *e)
{
    const QModelIndex idx = indexAt(e->pos());
    QMenu menu(this);
    if (idx.isValid()) {
        menu.addAction(QStringLiteral("Open in new tab"), this, [=, this] { open(idx, true); });
        if (m_places->url(idx).scheme() == QLatin1String("trash"))
            menu.addAction(Style::icon(QStringLiteral("trash")), QStringLiteral("Empty trash"), this, [this] { Ops::emptyTrash(window()); });
        if (m_places->data(idx, KFilePlacesModel::TeardownAllowedRole).toBool() && !m_places->setupNeeded(idx))
            menu.addAction(Style::icon(QStringLiteral("eject")), QStringLiteral("Safely remove"), this, [=, this] { m_places->requestTeardown(idx); });
        if (!m_places->isDevice(idx))
            menu.addAction(QStringLiteral("Remove from Places"), this, [=, this] { m_places->removePlace(idx); });
    }
    menu.addAction(Style::icon(QStringLiteral("network")), QStringLiteral("Add network folder…"), this, [this] {
        Q_EMIT placeActivated(QUrl(QStringLiteral("remote:/")));
    });
    menu.exec(e->globalPos());
}

void Sidebar::dragEnterEvent(QDragEnterEvent *e)
{
    if (e->mimeData()->hasUrls())
        e->acceptProposedAction();
}

void Sidebar::dragMoveEvent(QDragMoveEvent *e)
{
    e->acceptProposedAction();
}

void Sidebar::dropEvent(QDropEvent *e)
{
    const QModelIndex idx = indexAt(e->position().toPoint());
    if (idx.isValid() && !m_places->setupNeeded(idx)) {
        // Onto a place: copy/move there.
        Ops::drop(e, m_places->url(idx), window());
        return;
    }
    // Onto empty space: pin the dropped folders.
    for (const QUrl &u : KUrlMimeData::urlsFromMimeData(e->mimeData()))
        m_places->addPlace(u.fileName().isEmpty() ? u.toDisplayString() : u.fileName(), u, QStringLiteral("folder"), QString());
    e->acceptProposedAction();
}
