#include "folderpane.h"

#include "foldermodel.h"
#include "folderview.h"
#include "operations.h"
#include "style.h"

#include <QAbstractItemView>
#include <QApplication>
#include <QClipboard>
#include <QDir>
#include <QLabel>
#include <QLineEdit>
#include <QMenu>
#include <QPainter>
#include <QUrlQuery>
#include <QVBoxLayout>

#include <KFileItemActions>
#include <KFileItemListProperties>
#include <KFilePlacesModel>
#include <KIO/Global>
#include <KIO/PreviewJob>
#include <KNewFileMenu>
#include <KUrlNavigator>

#ifdef HAVE_BALOO
#include <Baloo/IndexerConfig>
#include <Baloo/Query>
#endif

FolderPane::FolderPane(KFilePlacesModel *places, const QUrl &url, QWidget *parent)
    : QWidget(parent)
    , m_model(new FolderModel(this))
{
    m_view = new FolderView(m_model, this);
    m_nav = new KUrlNavigator(places, url, this);
    m_nav->setPlacesSelectorVisible(false);
    m_nav->setHomeUrl(QUrl::fromLocalFile(QDir::homePath()));

    m_header = new QWidget(this);
    m_headerLayout = new QVBoxLayout(m_header);
    m_headerLayout->setContentsMargins(8, 6, 8, 4);
    m_headerLayout->addWidget(m_nav);

    m_filter = new QLineEdit(this);
    m_filter->setObjectName(QStringLiteral("search"));
    m_filter->setPlaceholderText(QStringLiteral("Filter this folder…"));
    m_filter->setClearButtonEnabled(true);
    m_filter->setStyleSheet(Style::chromeQss());
    m_filter->hide();

    m_message = new QLabel(m_view);
    m_message->setAlignment(Qt::AlignCenter);
    m_message->setStyleSheet(QStringLiteral("color: #8C94A6; font-size: 11pt; background: transparent;"));
    m_message->setAttribute(Qt::WA_TransparentForMouseEvents);
    m_message->hide();

    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(1, 1, 1, 1);
    lay->setSpacing(0);
    lay->addWidget(m_header);
    lay->addWidget(m_view, 1);
    lay->addWidget(m_filter);

    connect(m_nav, &KUrlNavigator::urlChanged, this, [this](const QUrl &u) {
        m_searchText.clear();
        m_filter->clear();
        m_model->openUrl(u);
        Q_EMIT urlChanged(u);
    });
    connect(m_nav, &KUrlNavigator::tabRequested, this, &FolderPane::openInNewTab);
    connect(m_nav, &KUrlNavigator::activated, this, &FolderPane::activated);
    connect(m_nav, &KUrlNavigator::urlsDropped, this, [this](const QUrl &dest, QDropEvent *e) { Ops::drop(e, dest, window()); });
    connect(m_model, &FolderModel::redirected, this, [this](const QUrl &u) {
        if (!isSearching())
            m_nav->setLocationUrl(u);
    });
    connect(m_model, &FolderModel::renameRequested, this, [this](const KFileItem &item, const QString &name) {
        Ops::rename(item, name, window());
        QUrl to = item.url().adjusted(QUrl::RemoveFilename);
        to.setPath(to.path() + name);
        m_selectAfterLoad = {to};
    });
    connect(m_model, &FolderModel::loadingStarted, this, [this] { m_message->hide(); });
    connect(m_model, &FolderModel::errorOccurred, this, &FolderPane::showMessage);
    connect(m_model, &FolderModel::countsChanged, this, [this] {
        if (!m_selectAfterLoad.isEmpty() && m_model->indexForUrl(m_selectAfterLoad.first()).isValid()) {
            m_view->selectUrls(m_selectAfterLoad);
            m_selectAfterLoad.clear();
        }
        if (!m_model->isLoading() && m_model->rowCount() == 0 && m_message->isHidden())
            showMessage(isSearching() ? QStringLiteral("Nothing found for “%1”").arg(m_searchText)
                        : !m_model->nameFilter().isEmpty() ? QStringLiteral("No names match “%1”").arg(m_model->nameFilter())
                        : m_model->url().scheme() == QLatin1String("trash") ? QStringLiteral("The trash is empty")
                                                                           : QStringLiteral("This folder is empty"));
        else if (m_model->rowCount() > 0)
            m_message->hide();
        Q_EMIT statusChanged();
    });
    connect(m_filter, &QLineEdit::textChanged, m_model, &FolderModel::setNameFilter);
    connect(m_filter, &QLineEdit::returnPressed, m_view, &FolderView::setFocusToView);

    connect(m_view, &FolderView::activated, this, &FolderPane::onActivated);
    connect(m_view, &FolderView::middleClicked, this, [this](const QModelIndex &idx) {
        const KFileItem item = m_model->itemForIndex(idx);
        if (item.isDir())
            Q_EMIT openInNewTab(item.url());
        else
            Ops::open({item}, window());
    });
    connect(m_view, &FolderView::contextMenuRequested, this, &FolderPane::showContextMenu);
    connect(m_view, &FolderView::backRequested, this, &FolderPane::goBack);
    connect(m_view, &FolderView::forwardRequested, this, &FolderPane::goForward);
    connect(m_view, &FolderView::zoomRequested, this, &FolderPane::zoomRequested);
    connect(m_view, &FolderView::focused, this, &FolderPane::activated);
    connect(m_view, &FolderView::dropped, this, [this](QDropEvent *e, const QUrl &dest) { Ops::drop(e, dest, window()); });
    connect(m_view, &FolderView::visibleRowsChanged, this, &FolderPane::loadPreviews);
    connect(m_view, &FolderView::selectionChanged, this, [this] {
        Q_EMIT selectionChanged();
        Q_EMIT statusChanged();
    });

    m_model->openUrl(url);
}

QUrl FolderPane::url() const
{
    return m_nav->locationUrl();
}

void FolderPane::setUrl(const QUrl &url)
{
    m_nav->setLocationUrl(url);
}

KFileItemList FolderPane::selectedItems() const
{
    return m_view->selectedItems();
}

QString FolderPane::title() const
{
    if (isSearching())
        return QStringLiteral("Search: %1").arg(m_searchText);
    const QUrl u = url();
    if (u.isLocalFile() && u.path() == QDir::homePath())
        return QStringLiteral("Home");
    const QString name = u.adjusted(QUrl::StripTrailingSlash).fileName();
    return name.isEmpty() ? (u.scheme() == QLatin1String("trash") ? QStringLiteral("Trash") : u.toDisplayString(QUrl::PreferLocalFile)) : name;
}

void FolderPane::setActive(bool active)
{
    m_active = active;
    m_nav->setActive(active);
    update();
}

void FolderPane::dockNavigator(bool inToolbar)
{
    m_split = !inToolbar;
    if (!inToolbar) {
        m_headerLayout->addWidget(m_nav);
        m_header->show();
    } else {
        m_header->hide();
    }
    update();
}

void FolderPane::paintEvent(QPaintEvent *)
{
    // In split view the active pane gets an accent outline.
    if (!m_split)
        return;
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(QPen(m_active ? Style::accent() : Style::Border, 1));
    p.setBrush(Qt::NoBrush);
    p.drawRoundedRect(QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5), Style::Radius, Style::Radius);
}

void FolderPane::goBack() { m_nav->goBack(); }
void FolderPane::goForward() { m_nav->goForward(); }
void FolderPane::goUp() { m_nav->goUp(); }

void FolderPane::reload()
{
    m_noPreview.clear();
    m_model->reload();
}

void FolderPane::showMessage(const QString &text)
{
    m_message->setText(text);
    m_message->setGeometry(m_view->rect());
    m_message->show();
    m_message->raise();
}

void FolderPane::onActivated(const QModelIndex &index)
{
    const KFileItem item = m_model->itemForIndex(index);
    if (item.isNull())
        return;
    if (item.isDir() && m_view->selectedItems().size() <= 1) {
        setUrl(item.targetUrl());
        return;
    }
    openSelected();
}

void FolderPane::openSelected()
{
    KFileItemList files;
    const KFileItemList items = selectedItems();
    for (const KFileItem &item : items) {
        if (item.isDir() && items.size() == 1) {
            setUrl(item.targetUrl());
            return;
        }
        if (item.isDir())
            Q_EMIT openInNewTab(item.targetUrl());
        else
            files << item;
    }
    Ops::open(files, window());
}

void FolderPane::newFolder()
{
    auto *menu = new KNewFileMenu(this);
    menu->setWorkingDirectory(isSearching() ? m_searchBase : url());
    menu->setParentWidget(window());
    connect(menu, &KNewFileMenu::directoryCreated, this, [this](const QUrl &u) { m_selectAfterLoad = {u}; });
    menu->createDirectory();
}

void FolderPane::showFilter()
{
    m_filter->show();
    m_filter->setFocus();
    m_filter->selectAll();
}

void FolderPane::search(const QString &text)
{
    if (text.isEmpty()) {
        if (isSearching()) {
            m_searchText.clear();
            m_model->openUrl(m_searchBase);
            Q_EMIT urlChanged(m_searchBase);
        }
        return;
    }
    if (!isSearching())
        m_searchBase = url();
    m_searchText = text;
    QUrl searchUrl;
#ifdef HAVE_BALOO
    // Indexed folders search names and contents through Baloo; anything else searches names.
    const Baloo::IndexerConfig config;
    if (m_searchBase.isLocalFile() && config.fileIndexingEnabled() && config.shouldBeIndexed(m_searchBase.toLocalFile())) {
        Baloo::Query q;
        q.setSearchString(text);
        q.setIncludeFolder(m_searchBase.toLocalFile());
        searchUrl = q.toSearchUrl(QStringLiteral("Search"));
    }
#endif
    if (searchUrl.isEmpty()) {
        searchUrl.setScheme(QStringLiteral("filenamesearch"));
        QUrlQuery query;
        query.addQueryItem(QStringLiteral("search"), text);
        query.addQueryItem(QStringLiteral("url"), m_searchBase.url());
        searchUrl.setQuery(query);
    }
    m_model->openUrl(searchUrl);
    Q_EMIT urlChanged(m_searchBase);
}

void FolderPane::loadPreviews()
{
    if (m_view->iconSize() < 32)
        return;
    KFileItemList wanted;
    for (int row : m_view->visibleRows()) {
        const KFileItem item = m_model->itemAt(row);
        // Remote files would be downloaded just to make a thumbnail.
        if (item.isDir() || !item.isLocalFile() || m_noPreview.contains(item.url()) || m_model->hasThumbnail(item.url()))
            continue;
        wanted << item;
    }
    if (m_previewJob)
        m_previewJob->kill();
    if (wanted.isEmpty())
        return;
    static const QStringList plugins = KIO::PreviewJob::defaultPlugins();
    const qreal dpr = devicePixelRatioF();
    const int size = m_view->iconSize();
    m_previewJob = KIO::filePreview(wanted, QSize(size, size), &plugins);
    m_previewJob->setDevicePixelRatio(dpr);
    connect(m_previewJob, &KIO::PreviewJob::gotPreview, this, [this](const KFileItem &item, const QPixmap &pm) {
        m_model->setThumbnail(item.url(), pm);
    });
    connect(m_previewJob, &KIO::PreviewJob::failed, this, [this](const KFileItem &item) { m_noPreview.insert(item.url()); });
}

QString FolderPane::statusText() const
{
    const KFileItemList sel = selectedItems();
    if (!sel.isEmpty()) {
        KIO::filesize_t size = 0;
        int dirs = 0;
        for (const KFileItem &i : sel) {
            if (i.isDir())
                ++dirs;
            else
                size += i.size();
        }
        QString text = sel.size() == 1 ? sel.first().text() : QStringLiteral("%1 selected").arg(sel.size());
        if (sel.size() > dirs)
            text += QStringLiteral(" (%1)").arg(KIO::convertSize(size));
        return text;
    }
    const int folders = m_model->folderCount(), files = m_model->fileCount();
    QStringList parts;
    if (folders)
        parts << (folders == 1 ? QStringLiteral("1 folder") : QStringLiteral("%1 folders").arg(QLocale().toString(folders)));
    if (files)
        parts << (files == 1 ? QStringLiteral("1 file") : QStringLiteral("%1 files").arg(QLocale().toString(files)))
                     + QStringLiteral(" (%1)").arg(KIO::convertSize(m_model->totalFileSize()));
    if (m_model->isLoading())
        parts << QStringLiteral("loading…");
    return parts.isEmpty() ? QString() : parts.join(QStringLiteral(", "));
}

void FolderPane::showContextMenu(const QModelIndex &index, const QPoint &pos)
{
    QWidget *win = window();
    auto *menu = new QMenu(this);
    menu->setAttribute(Qt::WA_DeleteOnClose);
    const QUrl here = isSearching() ? m_searchBase : url();
    const bool inTrash = here.scheme() == QLatin1String("trash");

    if (index.isValid() && !m_view->selectionModel()->isSelected(index.siblingAtColumn(0)))
        m_view->selectUrls({m_model->itemForIndex(index).url()}, false);
    const KFileItemList items = index.isValid() ? selectedItems() : KFileItemList();

    if (!items.isEmpty()) {
        const KFileItemListProperties props(items);
        if (inTrash) {
            menu->addAction(Style::icon(QStringLiteral("restore")), QStringLiteral("Restore"), this, [=] { Ops::restore(Ops::urls(items), win); });
            menu->addAction(Style::icon(QStringLiteral("trash")), QStringLiteral("Delete for good"), this, [=] { Ops::del(Ops::urls(items), win); });
            menu->addSeparator();
            menu->addAction(QStringLiteral("Properties"), this, [=] { Ops::properties(items, win); });
            menu->popup(pos);
            return;
        }
        menu->addAction(QStringLiteral("Open"), this, &FolderPane::openSelected);
        if (items.size() == 1 && items.first().isDir()) {
            const QUrl u = items.first().targetUrl();
            menu->addAction(QStringLiteral("Open in new tab"), this, [=] { Q_EMIT openInNewTab(u); });
            menu->addAction(QStringLiteral("Open in new window"), this, [=] { Q_EMIT openInNewWindow(u); });
        }
        auto *fileActions = new KFileItemActions(menu);
        fileActions->setParentWidget(win);
        fileActions->setItemListProperties(props);
        fileActions->insertOpenWithActionsTo(nullptr, menu, {});
        menu->addSeparator();
        QAction *cut = menu->addAction(Style::icon(QStringLiteral("cut")), QStringLiteral("Cut"), this, [=] { Ops::copy(items, true); });
        cut->setEnabled(props.supportsMoving());
        menu->addAction(Style::icon(QStringLiteral("copy")), QStringLiteral("Copy"), this, [=] { Ops::copy(items, false); });
        menu->addAction(QStringLiteral("Copy location"), this, [=] {
            QStringList paths;
            for (const KFileItem &i : items)
                paths << i.url().toDisplayString(QUrl::PreferLocalFile);
            QApplication::clipboard()->setText(paths.join(QLatin1Char('\n')));
        });
        QAction *rename = menu->addAction(Style::icon(QStringLiteral("rename")), QStringLiteral("Rename…"), this, [=, this] {
            if (items.size() > 1)
                Ops::batchRename(items, win);
            else
                m_view->editCurrent();
        });
        rename->setEnabled(props.supportsMoving());
        QAction *trash = menu->addAction(Style::icon(QStringLiteral("trash")), QStringLiteral("Move to trash"), this, [=] { Ops::trash(Ops::urls(items), win); });
        trash->setEnabled(props.supportsMoving() && props.isLocal());
        QAction *del = menu->addAction(QStringLiteral("Delete"), this, [=] { Ops::del(Ops::urls(items), win); });
        del->setEnabled(props.supportsDeleting());
        menu->addSeparator();
        fileActions->addActionsTo(menu);
        menu->addSeparator();
        menu->addAction(QStringLiteral("Properties"), this, [=] { Ops::properties(items, win); });
    } else {
        if (inTrash) {
            menu->addAction(Style::icon(QStringLiteral("trash")), QStringLiteral("Empty trash"), this, [=] { Ops::emptyTrash(win); });
        } else {
            auto *newMenu = new KNewFileMenu(menu);
            newMenu->setWorkingDirectory(here);
            newMenu->setParentWidget(win);
            newMenu->checkUpToDate();
            connect(newMenu, &KNewFileMenu::directoryCreated, this, [this](const QUrl &u) { m_selectAfterLoad = {u}; });
            connect(newMenu, &KNewFileMenu::fileCreated, this, [this](const QUrl &u) { m_selectAfterLoad = {u}; });
            menu->addAction(newMenu);
            QAction *paste = menu->addAction(Style::icon(QStringLiteral("paste")), QStringLiteral("Paste"), this, [=] { Ops::paste(here, win); });
            paste->setEnabled(Ops::canPaste());
            menu->addSeparator();
            menu->addAction(Style::icon(QStringLiteral("terminal")), QStringLiteral("Open terminal here"), this, [=] { Ops::openTerminal(here, win); });
        }
        menu->addAction(QStringLiteral("Select all"), m_view->view(), &QAbstractItemView::selectAll);
        menu->addSeparator();
        const KFileItem root = m_model->rootItem();
        if (!root.isNull())
            menu->addAction(QStringLiteral("Properties"), this, [=] { Ops::properties({root}, win); });
    }
    menu->popup(pos);
}
