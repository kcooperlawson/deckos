// One folder's items as a flat, sorted table, fed by KDirLister.
//
// Why not KDirModel + a sort proxy: the proxy compares names with QCollator on every comparison
// and re-sorts on every batch, which is hundreds of milliseconds per batch at 50,000 files. Here
// each row keeps a precomputed collator sort key (memcmp-cheap), batches are merged into the
// sorted list, and views only ever see row insertions/removals/moves, never a reset.
#pragma once

#include <QAbstractTableModel>
#include <QCache>
#include <QCollatorSortKey>
#include <QHash>
#include <QPixmap>
#include <QSet>
#include <QTimer>
#include <QUrl>

#include <KFileItem>
#include <KIO/Global>

#include <optional>
#include <vector>

class KDirLister;
class QThreadPool;

class FolderModel : public QAbstractTableModel
{
    Q_OBJECT
public:
    enum Column { NameColumn, SizeColumn, ModifiedColumn, TypeColumn, ColumnCount };
    enum Role { FileItemRole = Qt::UserRole + 1, IsDirRole, ThumbnailRole, CutRole };

    explicit FolderModel(QObject *parent = nullptr);
    ~FolderModel() override;

    void openUrl(const QUrl &url);
    void reload();
    QUrl url() const { return m_url; }
    KDirLister *lister() const { return m_lister; }
    bool isLoading() const { return m_loading; }

    KFileItem itemAt(int row) const;
    KFileItem itemForIndex(const QModelIndex &index) const { return index.isValid() ? itemAt(index.row()) : KFileItem(); }
    KFileItem rootItem() const;
    QModelIndex indexForUrl(const QUrl &url) const;
    int folderCount() const { return m_folders; }
    int fileCount() const { return int(m_rows.size()) - m_folders; }
    KIO::filesize_t totalFileSize() const;

    void setShowHidden(bool show);
    bool showHidden() const;
    void setNameFilter(const QString &text);
    QString nameFilter() const { return m_filter; }
    void setFoldersFirst(bool first);

    void setThumbnail(const QUrl &url, const QPixmap &pixmap);
    bool hasThumbnail(const QUrl &url) const { return m_thumbs.contains(url); }
    void setCutUrls(const QList<QUrl> &urls);

    int sortColumn() const { return m_sortColumn; }
    Qt::SortOrder sortOrder() const { return m_sortOrder; }

    int rowCount(const QModelIndex &parent = {}) const override;
    int columnCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QVariant headerData(int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;
    bool setData(const QModelIndex &index, const QVariant &value, int role = Qt::EditRole) override;
    void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;
    QStringList mimeTypes() const override;
    QMimeData *mimeData(const QModelIndexList &indexes) const override;
    Qt::DropActions supportedDragActions() const override;
    Qt::DropActions supportedDropActions() const override;

Q_SIGNALS:
    void loadingStarted();
    void loadingFinished();
    void countsChanged();
    void errorOccurred(const QString &message);
    void redirected(const QUrl &url);
    void renameRequested(const KFileItem &item, const QString &newName);

private:
    struct Row {
        KFileItem item;
        std::optional<QCollatorSortKey> key;
        qint64 mtime = 0;
        KIO::filesize_t size = 0;
        int childCount = -1;
        bool dir = false;
        QString type;  // filled only when sorting by type
    };

    void onItemsAdded(const QUrl &dir, const KFileItemList &items);
    void onItemsDeleted(const KFileItemList &items);
    void onRefreshItems(const QList<QPair<KFileItem, KFileItem>> &items);
    void onClear();
    void onCompleted();
    void flushPending();

    std::vector<Row> makeRows(const KFileItemList &items) const;
    bool lessThan(const Row &a, const Row &b) const;
    void prepareTypes(std::vector<Row> &rows) const;
    void insertSorted(std::vector<Row> &&incoming);
    void resortAll();
    void removeRows(const QList<int> &rows);
    bool matchesFilter(const Row &row) const;
    void requestCount(int row) const;
    void setChildCount(const QUrl &url, int count, int generation);
    void recount();

    KDirLister *m_lister;
    QUrl m_url;
    std::vector<Row> m_rows;
    std::vector<Row> m_filteredOut;
    KFileItemList m_pending;
    QTimer m_flushTimer;
    bool m_loading = false;
    int m_folders = 0;
    int m_generation = 0;

    int m_sortColumn = NameColumn;
    Qt::SortOrder m_sortOrder = Qt::AscendingOrder;
    bool m_foldersFirst = true;
    QString m_filter;

    mutable QHash<QUrl, int> m_rowForUrl;
    mutable bool m_rowForUrlDirty = true;
    mutable QSet<QUrl> m_countRequested;
    QThreadPool *m_countPool;
    QCache<QUrl, QPixmap> m_thumbs;
    QSet<QUrl> m_cut;
};
