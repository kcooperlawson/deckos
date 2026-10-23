#include "foldermodel.h"

#include "style.h"

#include <QCollator>
#include <QDirIterator>
#include <QLocale>
#include <QMimeData>
#include <QThreadPool>
#include <QtConcurrent/QtConcurrentMap>

#include <KDirLister>
#include <KIO/Global>
#include <KIO/Job>
#include <KUrlMimeData>

#include <algorithm>
#include <numeric>

namespace {

const QCollator &collator()
{
    // QCollator isn't safe to share between threads; each worker gets its own.
    thread_local const QCollator c = [] {
        QCollator c;
        c.setNumericMode(true);
        c.setCaseSensitivity(Qt::CaseInsensitive);
        return c;
    }();
    return c;
}

// Batches arriving while a folder lists are merged on this interval; the first one goes out fast
// so something is on screen right away.
constexpr int FirstFlushMs = 15;
constexpr int FlushMs = 250;
constexpr int ParallelKeysAbove = 1500;

} // namespace

FolderModel::FolderModel(QObject *parent)
    : QAbstractTableModel(parent)
    , m_lister(new KDirLister(this))
    , m_countPool(new QThreadPool(this))
{
    m_lister->setAutoErrorHandlingEnabled(false);
    m_lister->setDelayedMimeTypes(true);
    m_countPool->setMaxThreadCount(2);
    m_thumbs.setMaxCost(256 * 1024 * 1024);
    m_flushTimer.setSingleShot(true);
    connect(&m_flushTimer, &QTimer::timeout, this, &FolderModel::flushPending);

    connect(m_lister, &KCoreDirLister::started, this, [this] {
        m_loading = true;
        Q_EMIT loadingStarted();
    });
    connect(m_lister, &KCoreDirLister::itemsAdded, this, &FolderModel::onItemsAdded);
    connect(m_lister, &KCoreDirLister::itemsDeleted, this, &FolderModel::onItemsDeleted);
    connect(m_lister, &KCoreDirLister::refreshItems, this, &FolderModel::onRefreshItems);
    connect(m_lister, &KCoreDirLister::clear, this, &FolderModel::onClear);
    connect(m_lister, &KCoreDirLister::completed, this, &FolderModel::onCompleted);
    connect(m_lister, &KCoreDirLister::canceled, this, &FolderModel::onCompleted);
    connect(m_lister, &KCoreDirLister::redirection, this, [this](const QUrl &, const QUrl &to) {
        m_url = to;
        Q_EMIT redirected(to);
    });
    connect(m_lister, &KCoreDirLister::jobError, this, [this](KIO::Job *job) {
        Q_EMIT errorOccurred(job->errorString());
    });
}

FolderModel::~FolderModel()
{
    m_countPool->clear();
    m_countPool->waitForDone();
}

void FolderModel::openUrl(const QUrl &url)
{
    m_url = url;
    ++m_generation;
    m_countRequested.clear();
    m_thumbs.clear();
    m_lister->openUrl(url);
}

void FolderModel::reload()
{
    ++m_generation;
    m_countRequested.clear();
    m_thumbs.clear();
    m_lister->openUrl(m_url, KCoreDirLister::Reload);
}

KFileItem FolderModel::itemAt(int row) const
{
    return row >= 0 && row < int(m_rows.size()) ? m_rows[size_t(row)].item : KFileItem();
}

KFileItem FolderModel::rootItem() const
{
    return m_lister->rootItem();
}

QModelIndex FolderModel::indexForUrl(const QUrl &url) const
{
    if (m_rowForUrlDirty) {
        m_rowForUrl.clear();
        m_rowForUrl.reserve(qsizetype(m_rows.size()));
        for (size_t i = 0; i < m_rows.size(); ++i)
            m_rowForUrl.insert(m_rows[i].item.url().adjusted(QUrl::StripTrailingSlash), int(i));
        m_rowForUrlDirty = false;
    }
    const int row = m_rowForUrl.value(url.adjusted(QUrl::StripTrailingSlash), -1);
    return row >= 0 ? index(row, 0) : QModelIndex();
}

KIO::filesize_t FolderModel::totalFileSize() const
{
    KIO::filesize_t total = 0;
    for (const Row &r : m_rows)
        if (!r.dir)
            total += r.size;
    return total;
}

void FolderModel::setShowHidden(bool show)
{
    if (m_lister->showHiddenFiles() == show)
        return;
    m_lister->setShowHiddenFiles(show);
    m_lister->emitChanges();
}

bool FolderModel::showHidden() const
{
    return m_lister->showHiddenFiles();
}

void FolderModel::setNameFilter(const QString &text)
{
    if (text == m_filter)
        return;
    flushPending();
    m_filter = text;
    // Rare and user-paced, so a reset is fine here.
    beginResetModel();
    std::vector<Row> all = std::move(m_rows);
    all.insert(all.end(), std::make_move_iterator(m_filteredOut.begin()), std::make_move_iterator(m_filteredOut.end()));
    m_rows.clear();
    m_filteredOut.clear();
    for (Row &r : all)
        (matchesFilter(r) ? m_rows : m_filteredOut).push_back(std::move(r));
    prepareTypes(m_rows);
    std::stable_sort(m_rows.begin(), m_rows.end(), [this](const Row &a, const Row &b) { return lessThan(a, b); });
    m_rowForUrlDirty = true;
    recount();
    endResetModel();
    Q_EMIT countsChanged();
}

void FolderModel::setFoldersFirst(bool first)
{
    if (first == m_foldersFirst)
        return;
    m_foldersFirst = first;
    resortAll();
}

void FolderModel::setThumbnail(const QUrl &url, const QPixmap &pixmap)
{
    const QModelIndex idx = indexForUrl(url);
    if (!idx.isValid())
        return;
    m_thumbs.insert(url, new QPixmap(pixmap), int(qint64(pixmap.width()) * pixmap.height() * 4));
    Q_EMIT dataChanged(idx, idx, {ThumbnailRole});
}

void FolderModel::setCutUrls(const QList<QUrl> &urls)
{
    QSet<QUrl> next(urls.cbegin(), urls.cend());
    const QSet<QUrl> changed = (next - m_cut) + (m_cut - next);
    m_cut = std::move(next);
    for (const QUrl &u : changed) {
        const QModelIndex idx = indexForUrl(u);
        if (idx.isValid())
            Q_EMIT dataChanged(idx, idx, {CutRole});
    }
}

int FolderModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : int(m_rows.size());
}

int FolderModel::columnCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : ColumnCount;
}

QVariant FolderModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || size_t(index.row()) >= m_rows.size())
        return {};
    const Row &r = m_rows[size_t(index.row())];
    switch (role) {
    case Qt::DisplayRole:
        switch (index.column()) {
        case NameColumn:
            return r.item.text();
        case SizeColumn:
            if (r.dir) {
                if (r.childCount < 0) {
                    requestCount(index.row());
                    return QString();
                }
                return r.childCount == 1 ? QStringLiteral("1 item") : QStringLiteral("%1 items").arg(QLocale().toString(r.childCount));
            }
            return KIO::convertSize(r.size);
        case ModifiedColumn:
            return r.mtime ? QLocale().toString(QDateTime::fromMSecsSinceEpoch(r.mtime), QLocale::ShortFormat) : QString();
        case TypeColumn:
            return r.dir ? QStringLiteral("Folder") : r.item.mimeComment();
        }
        break;
    case Qt::EditRole:
        return r.item.name();
    case Qt::DecorationRole:
        if (index.column() == NameColumn)
            return Style::themeIcon(r.item.iconName());
        break;
    case Qt::ToolTipRole:
        if (index.column() == NameColumn)
            return r.dir ? r.item.text() : QStringLiteral("%1\n%2 · %3").arg(r.item.text(), r.item.mimeComment(), KIO::convertSize(r.size));
        break;
    case Qt::TextAlignmentRole:
        if (index.column() == SizeColumn)
            return QVariant::fromValue(Qt::AlignRight | Qt::AlignVCenter);
        return QVariant::fromValue(Qt::AlignLeft | Qt::AlignVCenter);
    case FileItemRole:
        return QVariant::fromValue(r.item);
    case IsDirRole:
        return r.dir;
    case ThumbnailRole:
        if (const QPixmap *pm = m_thumbs.object(r.item.url()))
            return *pm;
        break;
    case CutRole:
        return m_cut.contains(r.item.url());
    }
    return {};
}

QVariant FolderModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (orientation != Qt::Horizontal)
        return {};
    if (role == Qt::DisplayRole) {
        switch (section) {
        case NameColumn:
            return QStringLiteral("Name");
        case SizeColumn:
            return QStringLiteral("Size");
        case ModifiedColumn:
            return QStringLiteral("Modified");
        case TypeColumn:
            return QStringLiteral("Type");
        }
    } else if (role == Qt::TextAlignmentRole) {
        return QVariant::fromValue((section == SizeColumn ? Qt::AlignRight : Qt::AlignLeft) | Qt::AlignVCenter);
    }
    return {};
}

Qt::ItemFlags FolderModel::flags(const QModelIndex &index) const
{
    if (!index.isValid())
        return Qt::ItemIsDropEnabled;
    Qt::ItemFlags f = Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
    const Row &r = m_rows[size_t(index.row())];
    if (r.dir)
        f |= Qt::ItemIsDropEnabled;
    if (index.column() == NameColumn && r.item.isWritable())
        f |= Qt::ItemIsEditable;
    return f;
}

bool FolderModel::setData(const QModelIndex &index, const QVariant &value, int role)
{
    if (role != Qt::EditRole || !index.isValid())
        return false;
    const KFileItem item = itemAt(index.row());
    const QString name = value.toString().trimmed();
    if (name.isEmpty() || name == item.name())
        return false;
    // The rename runs as a KIO job; the lister reports the result as a refresh.
    Q_EMIT renameRequested(item, name);
    return false;
}

void FolderModel::sort(int column, Qt::SortOrder order)
{
    if (column < 0 || column >= ColumnCount)
        return;
    if (column == m_sortColumn && order == m_sortOrder)
        return;
    m_sortColumn = column;
    m_sortOrder = order;
    resortAll();
}

QStringList FolderModel::mimeTypes() const
{
    return KUrlMimeData::mimeDataTypes();
}

QMimeData *FolderModel::mimeData(const QModelIndexList &indexes) const
{
    QList<QUrl> urls, local;
    QSet<int> seen;
    for (const QModelIndex &idx : indexes) {
        if (seen.contains(idx.row()))
            continue;
        seen.insert(idx.row());
        const KFileItem item = itemAt(idx.row());
        urls << item.url();
        local << item.mostLocalUrl();
    }
    auto *mime = new QMimeData;
    KUrlMimeData::setUrls(urls, local, mime);
    return mime;
}

Qt::DropActions FolderModel::supportedDragActions() const
{
    return Qt::CopyAction | Qt::MoveAction | Qt::LinkAction;
}

Qt::DropActions FolderModel::supportedDropActions() const
{
    return Qt::CopyAction | Qt::MoveAction | Qt::LinkAction;
}

// ------------------------------------------------------------------ lister events

void FolderModel::onItemsAdded(const QUrl &, const KFileItemList &items)
{
    m_pending += items;
    if (!m_flushTimer.isActive())
        m_flushTimer.start(!m_loading ? 0 : (m_rows.empty() ? FirstFlushMs : FlushMs));
}

void FolderModel::onCompleted()
{
    m_flushTimer.stop();
    flushPending();
    m_loading = false;
    Q_EMIT loadingFinished();
    Q_EMIT countsChanged();
}

void FolderModel::onClear()
{
    m_flushTimer.stop();
    m_pending.clear();
    beginResetModel();
    m_rows.clear();
    m_filteredOut.clear();
    m_folders = 0;
    m_rowForUrlDirty = true;
    m_cut.clear();
    endResetModel();
    Q_EMIT countsChanged();
}

void FolderModel::onItemsDeleted(const KFileItemList &items)
{
    flushPending();
    QSet<QUrl> gone;
    for (const KFileItem &item : items)
        gone.insert(item.url());
    std::erase_if(m_filteredOut, [&](const Row &r) { return gone.contains(r.item.url()); });
    QList<int> rows;
    for (const QUrl &u : std::as_const(gone)) {
        const QModelIndex idx = indexForUrl(u);
        if (idx.isValid())
            rows << idx.row();
    }
    removeRows(rows);
    Q_EMIT countsChanged();
}

void FolderModel::onRefreshItems(const QList<QPair<KFileItem, KFileItem>> &items)
{
    flushPending();
    KFileItemList moved;
    QList<int> movedRows;
    for (const auto &[oldItem, newItem] : items) {
        const QModelIndex idx = indexForUrl(oldItem.url());
        if (!idx.isValid()) {
            // A refreshed item can start or stop matching the filter.
            auto it = std::find_if(m_filteredOut.begin(), m_filteredOut.end(), [&](const Row &r) { return r.item.url() == oldItem.url(); });
            if (it != m_filteredOut.end()) {
                m_filteredOut.erase(it);
                moved << newItem;
            }
            continue;
        }
        const int row = idx.row();
        std::vector<Row> fresh = makeRows({newItem});
        Row &r = m_rows[size_t(row)];
        const bool renamed = oldItem.url() != newItem.url() || oldItem.text() != newItem.text();
        if (!renamed)
            fresh[0].childCount = r.dir && oldItem.time(KFileItem::ModificationTime) == newItem.time(KFileItem::ModificationTime) ? r.childCount : -1;
        if (fresh[0].childCount < 0)
            m_countRequested.remove(newItem.url());
        m_thumbs.remove(oldItem.url());
        r = std::move(fresh[0]);
        if (m_sortColumn == TypeColumn && !r.dir)
            r.type = r.item.mimeComment();
        const bool inOrder = (row == 0 || !lessThan(m_rows[size_t(row)], m_rows[size_t(row - 1)]))
            && (row + 1 >= int(m_rows.size()) || !lessThan(m_rows[size_t(row + 1)], m_rows[size_t(row)]));
        if (renamed || !inOrder || !matchesFilter(r)) {
            moved << newItem;
            movedRows << row;
        } else {
            Q_EMIT dataChanged(index(row, 0), index(row, ColumnCount - 1));
        }
    }
    m_rowForUrlDirty = true;
    recount();
    if (!movedRows.isEmpty()) {
        removeRows(movedRows);
        m_pending += moved;
        flushPending();
    } else if (!moved.isEmpty()) {
        m_pending += moved;
        flushPending();
    }
}

void FolderModel::flushPending()
{
    if (m_pending.isEmpty())
        return;
    std::vector<Row> incoming = makeRows(m_pending);
    m_pending.clear();
    std::vector<Row> visible;
    visible.reserve(incoming.size());
    for (Row &r : incoming)
        (matchesFilter(r) ? visible : m_filteredOut).push_back(std::move(r));
    if (!visible.empty())
        insertSorted(std::move(visible));
    Q_EMIT countsChanged();
}

// ------------------------------------------------------------------ sorting

std::vector<FolderModel::Row> FolderModel::makeRows(const KFileItemList &items) const
{
    std::vector<Row> rows;
    rows.reserve(size_t(items.size()));
    for (const KFileItem &item : items) {
        Row r;
        r.item = item;
        r.dir = item.isDir();
        r.size = r.dir ? 0 : item.size();
        const QDateTime t = item.time(KFileItem::ModificationTime);
        r.mtime = t.isValid() ? t.toMSecsSinceEpoch() : 0;
        rows.push_back(std::move(r));
    }
    auto computeKey = [](Row &r) { r.key = collator().sortKey(r.item.text()); };
    if (rows.size() > ParallelKeysAbove)
        QtConcurrent::blockingMap(rows, computeKey);
    else
        std::for_each(rows.begin(), rows.end(), computeKey);
    return rows;
}

void FolderModel::prepareTypes(std::vector<Row> &rows) const
{
    if (m_sortColumn != TypeColumn)
        return;
    for (Row &r : rows)
        if (r.type.isEmpty() && !r.dir)
            r.type = r.item.mimeComment();
}

bool FolderModel::lessThan(const Row &a, const Row &b) const
{
    // Folders stay on top whichever way the list is sorted.
    if (m_foldersFirst && a.dir != b.dir)
        return a.dir;
    int c = 0;
    switch (m_sortColumn) {
    case SizeColumn:
        if (a.dir && b.dir)
            c = (a.childCount > b.childCount) - (a.childCount < b.childCount);
        else
            c = (a.size > b.size) - (a.size < b.size);
        break;
    case ModifiedColumn:
        c = (a.mtime > b.mtime) - (a.mtime < b.mtime);
        break;
    case TypeColumn:
        c = QString::compare(a.type, b.type, Qt::CaseInsensitive);
        break;
    default:
        break;
    }
    if (c == 0)
        c = a.key->compare(*b.key);
    if (c == 0)
        c = QString::compare(a.item.name(), b.item.name());
    return m_sortOrder == Qt::AscendingOrder ? c < 0 : c > 0;
}

void FolderModel::insertSorted(std::vector<Row> &&incoming)
{
    prepareTypes(incoming);
    auto less = [this](const Row &a, const Row &b) { return lessThan(a, b); };
    std::stable_sort(incoming.begin(), incoming.end(), less);
    for (const Row &r : incoming)
        m_folders += r.dir;
    m_rowForUrlDirty = true;

    if (m_rows.empty()) {
        beginInsertRows({}, 0, int(incoming.size()) - 1);
        m_rows = std::move(incoming);
        endInsertRows();
        return;
    }

    // Where each run of new rows lands in the current list.
    std::vector<std::pair<size_t, size_t>> runs;  // (position in m_rows, first index in incoming)
    for (size_t i = 0; i < incoming.size(); ++i) {
        const size_t pos = size_t(std::upper_bound(m_rows.begin(), m_rows.end(), incoming[i], less) - m_rows.begin());
        if (runs.empty() || runs.back().first != pos)
            runs.emplace_back(pos, i);
    }

    if (runs.size() <= 64) {
        // Few runs (a new file, a paste): insert them from the end so earlier positions stay valid.
        for (size_t k = runs.size(); k-- > 0;) {
            const auto [pos, first] = runs[k];
            const size_t last = k + 1 < runs.size() ? runs[k + 1].second : incoming.size();
            beginInsertRows({}, int(pos), int(pos + (last - first)) - 1);
            m_rows.insert(m_rows.begin() + qptrdiff(pos), std::make_move_iterator(incoming.begin() + qptrdiff(first)),
                          std::make_move_iterator(incoming.begin() + qptrdiff(last)));
            endInsertRows();
        }
        return;
    }

    // Many scattered runs (a big folder still listing): append, then one re-sort as a layout
    // change, which keeps the selection and scroll position.
    const int oldCount = int(m_rows.size());
    beginInsertRows({}, oldCount, oldCount + int(incoming.size()) - 1);
    m_rows.insert(m_rows.end(), std::make_move_iterator(incoming.begin()), std::make_move_iterator(incoming.end()));
    endInsertRows();
    resortAll();
}

void FolderModel::resortAll()
{
    if (m_rows.empty())
        return;
    Q_EMIT layoutAboutToBeChanged({}, QAbstractItemModel::VerticalSortHint);
    prepareTypes(m_rows);
    std::vector<int> order(m_rows.size());
    std::iota(order.begin(), order.end(), 0);
    std::stable_sort(order.begin(), order.end(), [this](int a, int b) { return lessThan(m_rows[size_t(a)], m_rows[size_t(b)]); });
    std::vector<int> newRowOf(m_rows.size());
    std::vector<Row> sorted;
    sorted.reserve(m_rows.size());
    for (size_t i = 0; i < order.size(); ++i) {
        newRowOf[size_t(order[i])] = int(i);
        sorted.push_back(std::move(m_rows[size_t(order[i])]));
    }
    m_rows = std::move(sorted);
    m_rowForUrlDirty = true;

    const QModelIndexList from = persistentIndexList();
    QModelIndexList to;
    to.reserve(from.size());
    for (const QModelIndex &idx : from)
        to << index(newRowOf[size_t(idx.row())], idx.column());
    changePersistentIndexList(from, to);
    Q_EMIT layoutChanged({}, QAbstractItemModel::VerticalSortHint);
}

void FolderModel::removeRows(const QList<int> &rows)
{
    if (rows.isEmpty())
        return;
    QList<int> sorted = rows;
    std::sort(sorted.begin(), sorted.end(), std::greater<int>());
    // Contiguous ranges, from the bottom up.
    qsizetype i = 0;
    while (i < sorted.size()) {
        int last = sorted[i], first = last;
        while (i + 1 < sorted.size() && sorted[i + 1] == first - 1)
            first = sorted[++i];
        ++i;
        beginRemoveRows({}, first, last);
        for (int r = first; r <= last; ++r)
            m_folders -= m_rows[size_t(r)].dir;
        m_rows.erase(m_rows.begin() + first, m_rows.begin() + last + 1);
        endRemoveRows();
    }
    m_rowForUrlDirty = true;
}

bool FolderModel::matchesFilter(const Row &row) const
{
    return m_filter.isEmpty() || row.item.text().contains(m_filter, Qt::CaseInsensitive);
}

void FolderModel::recount()
{
    m_folders = 0;
    for (const Row &r : m_rows)
        m_folders += r.dir;
}

// ------------------------------------------------------------------ folder item counts

void FolderModel::requestCount(int row) const
{
    const Row &r = m_rows[size_t(row)];
    const QUrl url = r.item.url();
    if (m_countRequested.contains(url))
        return;
    m_countRequested.insert(url);
    const QString path = r.item.localPath();
    if (path.isEmpty())
        return;  // remote folders: counting means listing them, which isn't free
    const bool hidden = showHidden();
    const int generation = m_generation;
    // Safe without a guard: the destructor waits for the pool, and Qt drops queued calls to a
    // deleted object.
    auto *self = const_cast<FolderModel *>(this);
    m_countPool->start([self, url, path, hidden, generation] {
        QDir::Filters filters = QDir::AllEntries | QDir::NoDotAndDotDot | QDir::System;
        if (hidden)
            filters |= QDir::Hidden;
        int n = 0;
        QDirIterator it(path, filters);
        while (it.hasNext()) {
            it.next();
            ++n;
        }
        QMetaObject::invokeMethod(self, [self, url, n, generation] { self->setChildCount(url, n, generation); }, Qt::QueuedConnection);
    });
}

void FolderModel::setChildCount(const QUrl &url, int count, int generation)
{
    if (generation != m_generation)
        return;
    const QModelIndex idx = indexForUrl(url);
    if (!idx.isValid())
        return;
    m_rows[size_t(idx.row())].childCount = count;
    Q_EMIT dataChanged(index(idx.row(), SizeColumn), index(idx.row(), SizeColumn), {Qt::DisplayRole});
}
