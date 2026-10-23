#include "mainwindow.h"

#include "foldermodel.h"
#include "folderpane.h"
#include "operations.h"
#include "sidebar.h"
#include "style.h"

#include <memory>
#include <QAction>
#include <QApplication>
#include <QClipboard>
#include <QDir>
#include <QFutureWatcher>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QImageReader>
#include <QKeySequence>
#include <QLabel>
#include <QLineEdit>
#include <QMenu>
#include <QSlider>
#include <QSplitter>
#include <QStackedWidget>
#include <QStorageInfo>
#include <QTabBar>
#include <QToolButton>
#include <QVBoxLayout>
#include <QtConcurrent/QtConcurrentRun>

#include <KConfigGroup>
#include <KFilePlacesModel>
#include <KIO/FileUndoManager>
#include <KIO/Global>
#include <KIO/PreviewJob>
#include <KSharedConfig>
#include <KUrlNavigator>

namespace {
const int ZoomSteps[] = {16, 22, 32, 48, 64, 80, 96, 128, 160, 192, 256};
KConfigGroup settings()
{
    return KConfigGroup(KSharedConfig::openConfig(), QStringLiteral("General"));
}
} // namespace

struct MainWindow::Tab {
    QSplitter *splitter = nullptr;
    QList<FolderPane *> panes;
    FolderPane *active = nullptr;
};

KFilePlacesModel *MainWindow::places()
{
    static KFilePlacesModel *model = new KFilePlacesModel(qApp);
    return model;
}

MainWindow::MainWindow(const QList<QUrl> &urls, QWidget *parent)
    : QMainWindow(parent)
{
    setAttribute(Qt::WA_DeleteOnClose);
    setWindowTitle(QStringLiteral("DeckOS Files"));
    setWindowIcon(QIcon::fromTheme(QStringLiteral("deckos-files"), QIcon::fromTheme(QStringLiteral("system-file-manager"))));
    const KConfigGroup cfg = settings();
    m_mode = FolderView::Mode(qBound(0, cfg.readEntry("ViewMode", 0), 2));
    m_iconSizes[0] = cfg.readEntry("GridIconSize", 64);
    m_iconSizes[1] = cfg.readEntry("ListIconSize", 22);
    m_iconSizes[2] = cfg.readEntry("DetailsIconSize", 22);

    auto *central = new QWidget(this);
    auto *root = new QVBoxLayout(central);
    root->setContentsMargins(0, 0, 0, 0);
    root->setSpacing(0);

    // Toolbar: navigation, the active pane's path bar, search, view controls.
    auto *toolbar = new QWidget(central);
    toolbar->setObjectName(QStringLiteral("toolbar"));
    toolbar->setStyleSheet(Style::chromeQss());
    auto *tl = new QHBoxLayout(toolbar);
    tl->setContentsMargins(10, 8, 10, 8);
    tl->setSpacing(4);
    buildActions();
    tl->addWidget(toolButton(QStringLiteral("sidebar"), QStringLiteral("Sidebar (F9)"), m_sidebarAction));
    tl->addWidget(toolButton(QStringLiteral("chevron-left"), QStringLiteral("Back (Alt+Left)"), m_backAction));
    tl->addWidget(toolButton(QStringLiteral("chevron"), QStringLiteral("Forward (Alt+Right)"), m_forwardAction));
    tl->addWidget(toolButton(QStringLiteral("arrow-up"), QStringLiteral("Up (Alt+Up)"), m_upAction));
    tl->addSpacing(6);
    m_navSlot = new QHBoxLayout;
    m_navSlot->setContentsMargins(0, 0, 0, 0);
    tl->addLayout(m_navSlot, 1);
    tl->addSpacing(6);
    m_search = new QLineEdit(toolbar);
    m_search->setObjectName(QStringLiteral("search"));
    m_search->setPlaceholderText(QStringLiteral("Search"));
    m_search->setClearButtonEnabled(true);
    m_search->addAction(Style::icon(QStringLiteral("search")), QLineEdit::LeadingPosition);
    m_search->setFixedWidth(220);
    connect(m_search, &QLineEdit::returnPressed, this, [this] { search(m_search->text()); });
    connect(m_search, &QLineEdit::textChanged, this, [this](const QString &t) {
        if (t.isEmpty())
            search(QString());
    });
    tl->addWidget(m_search);
    tl->addSpacing(6);
    auto *segment = new QFrame(toolbar);
    segment->setObjectName(QStringLiteral("segment"));
    auto *sl = new QHBoxLayout(segment);
    sl->setContentsMargins(3, 3, 3, 3);
    sl->setSpacing(2);
    const char *viewIcons[] = {"grid", "list", "details"};
    const char *viewTips[] = {"Grid (Ctrl+1)", "List (Ctrl+2)", "Details (Ctrl+3)"};
    for (int i = 0; i < 3; ++i) {
        m_viewButtons[i] = toolButton(QString::fromLatin1(viewIcons[i]), QString::fromLatin1(viewTips[i]));
        m_viewButtons[i]->setCheckable(true);
        connect(m_viewButtons[i], &QToolButton::clicked, this, [this, i] { setViewMode(FolderView::Mode(i)); });
        sl->addWidget(m_viewButtons[i]);
    }
    tl->addWidget(segment);
    tl->addWidget(toolButton(QStringLiteral("split"), QStringLiteral("Split view (F3)"), m_splitAction));
    tl->addWidget(toolButton(QStringLiteral("panel-right"), QStringLiteral("Previews (F11)"), m_previewAction));
    QToolButton *menuButton = toolButton(QStringLiteral("menu"), QStringLiteral("Menu"));
    auto *menu = new QMenu(menuButton);
    menu->addAction(m_hiddenAction);
    menu->addAction(m_undoAction);
    menu->addSeparator();
    menu->addAction(QStringLiteral("New window"), QKeySequence(QStringLiteral("Ctrl+N")), this, [] { (new MainWindow)->show(); });
    menu->addAction(QStringLiteral("Open terminal here"), this, [this] { Ops::openTerminal(activePane()->url(), this); });
    menu->addAction(QStringLiteral("Network"), this, [this] { activePane()->setUrl(QUrl(QStringLiteral("remote:/"))); });
    menu->addAction(QStringLiteral("Trash"), this, [this] { activePane()->setUrl(QUrl(QStringLiteral("trash:/"))); });
    menuButton->setMenu(menu);
    menuButton->setPopupMode(QToolButton::InstantPopup);
    tl->addWidget(menuButton);
    root->addWidget(toolbar);

    m_tabBar = new QTabBar(central);
    m_tabBar->setDocumentMode(true);
    m_tabBar->setTabsClosable(true);
    m_tabBar->setMovable(true);
    m_tabBar->setExpanding(false);
    m_tabBar->setElideMode(Qt::ElideMiddle);
    m_tabBar->setStyleSheet(QStringLiteral(
        "QTabBar { background: #0F1115; } QTabBar::tab { background: transparent; color: #8C94A6; padding: 6px 14px;"
        " margin: 0 2px 4px 2px; border-radius: 8px; min-width: 120px; max-width: 240px; }"
        "QTabBar::tab:selected { background: #171A21; color: #E8EAF0; border: 1px solid #262B36; }"
        "QTabBar::tab:hover:!selected { background: #1D212A; }"));
    m_tabBar->hide();
    connect(m_tabBar, &QTabBar::currentChanged, this, [this](int i) {
        if (i < 0 || i >= m_tabs.size())
            return;
        m_stack->setCurrentWidget(m_tabs[i]->splitter);
        setActivePane(m_tabs[i]->active);
    });
    connect(m_tabBar, &QTabBar::tabCloseRequested, this, &MainWindow::closeTab);
    connect(m_tabBar, &QTabBar::tabMoved, this, [this](int from, int to) { m_tabs.move(from, to); });
    auto *tabRow = new QHBoxLayout;
    tabRow->setContentsMargins(10, 0, 10, 0);
    tabRow->addWidget(m_tabBar);
    tabRow->addStretch();
    root->addLayout(tabRow);

    auto *body = new QSplitter(central);
    body->setHandleWidth(1);
    body->setChildrenCollapsible(false);
    m_sidebar = new Sidebar(places(), body);
    m_sidebar->setMinimumWidth(170);
    connect(m_sidebar, &Sidebar::placeActivated, this, [this](const QUrl &u) { activePane()->setUrl(u); });
    connect(m_sidebar, &Sidebar::placeActivatedInNewTab, this, [this](const QUrl &u) { openTab(u); });
    m_stack = new QStackedWidget(body);

    m_previewPanel = new QWidget(body);
    m_previewPanel->setStyleSheet(Style::chromeQss());
    m_previewPanel->setMinimumWidth(240);
    auto *pl = new QVBoxLayout(m_previewPanel);
    pl->setContentsMargins(16, 16, 16, 16);
    m_previewImage = new QLabel(m_previewPanel);
    m_previewImage->setAlignment(Qt::AlignCenter);
    m_previewImage->setMinimumHeight(220);
    m_previewName = new QLabel(m_previewPanel);
    m_previewName->setObjectName(QStringLiteral("title"));
    m_previewName->setWordWrap(true);
    m_previewInfo = new QLabel(m_previewPanel);
    m_previewInfo->setObjectName(QStringLiteral("sub"));
    m_previewInfo->setWordWrap(true);
    m_previewInfo->setTextInteractionFlags(Qt::TextSelectableByMouse);
    pl->addWidget(m_previewImage);
    pl->addSpacing(8);
    pl->addWidget(m_previewName);
    pl->addWidget(m_previewInfo);
    pl->addStretch();
    m_previewPanel->setVisible(cfg.readEntry("PreviewsVisible", false));
    m_previewAction->setChecked(m_previewPanel->isVisible());
    m_sidebar->setVisible(cfg.readEntry("SidebarVisible", true));
    m_sidebarAction->setChecked(m_sidebar->isVisible());

    body->addWidget(m_sidebar);
    body->addWidget(m_stack);
    body->addWidget(m_previewPanel);
    body->setStretchFactor(1, 1);
    body->setSizes({220, 900, 280});
    root->addWidget(body, 1);

    auto *statusBar = new QWidget(central);
    statusBar->setStyleSheet(Style::chromeQss());
    auto *stl = new QHBoxLayout(statusBar);
    stl->setContentsMargins(14, 5, 14, 6);
    m_status = new QLabel(statusBar);
    m_status->setObjectName(QStringLiteral("sub"));
    m_free = new QLabel(statusBar);
    m_free->setObjectName(QStringLiteral("sub"));
    m_zoom = new QSlider(Qt::Horizontal, statusBar);
    m_zoom->setRange(0, int(std::size(ZoomSteps)) - 1);
    m_zoom->setFixedWidth(110);
    m_zoom->setToolTip(QStringLiteral("Zoom (Ctrl+= / Ctrl+-)"));
    connect(m_zoom, &QSlider::valueChanged, this, [this](int v) {
        m_iconSizes[m_mode] = ZoomSteps[v];
        for (Tab *t : std::as_const(m_tabs))
            for (FolderPane *p : std::as_const(t->panes))
                if (p->view()->mode() == m_mode)
                    p->view()->setIconSize(ZoomSteps[v]);
    });
    stl->addWidget(m_status, 1);
    stl->addWidget(m_free);
    stl->addSpacing(12);
    stl->addWidget(m_zoom);
    root->addWidget(statusBar);

    setCentralWidget(central);
    auto *undo = KIO::FileUndoManager::self();
    connect(undo, &KIO::FileUndoManager::undoAvailable, m_undoAction, &QAction::setEnabled);
    connect(undo, &KIO::FileUndoManager::undoTextChanged, m_undoAction, &QAction::setText);
    m_undoAction->setEnabled(undo->isUndoAvailable());

    const QList<QUrl> start = urls.isEmpty() ? QList<QUrl>{QUrl::fromLocalFile(QDir::homePath())} : urls;
    for (const QUrl &u : start)
        openTab(u, m_tabs.isEmpty());

    const QByteArray geometry = cfg.readEntry("Geometry", QByteArray());
    if (geometry.isEmpty() || !restoreGeometry(QByteArray::fromBase64(geometry)))
        resize(1280, 800);
}

MainWindow::~MainWindow()
{
    saveSettings();
    qDeleteAll(m_tabs);
}

void MainWindow::saveSettings()
{
    KConfigGroup cfg = settings();
    cfg.writeEntry("ViewMode", int(m_mode));
    cfg.writeEntry("GridIconSize", m_iconSizes[0]);
    cfg.writeEntry("ListIconSize", m_iconSizes[1]);
    cfg.writeEntry("DetailsIconSize", m_iconSizes[2]);
    cfg.writeEntry("PreviewsVisible", m_previewAction->isChecked());
    cfg.writeEntry("SidebarVisible", m_sidebarAction->isChecked());
    cfg.writeEntry("ShowHidden", m_hiddenAction->isChecked());
    cfg.writeEntry("Geometry", saveGeometry().toBase64());
    if (FolderPane *p = activePane()) {
        cfg.writeEntry("SortColumn", p->model()->sortColumn());
        cfg.writeEntry("SortOrder", int(p->model()->sortOrder()));
        cfg.writeEntry("DetailsHeader", p->view()->header()->saveState().toBase64());
    }
    cfg.sync();
}

QToolButton *MainWindow::toolButton(const QString &icon, const QString &tip, QAction *action)
{
    auto *b = new QToolButton(this);
    if (action) {
        b->setDefaultAction(action);
    }
    b->setIcon(Style::icon(icon));
    b->setToolTip(tip);
    b->setIconSize(QSize(18, 18));
    b->setAutoRaise(true);
    return b;
}

void MainWindow::buildActions()
{
    auto add = [this](const QString &text, const QList<QKeySequence> &keys, auto slot) {
        auto *a = new QAction(text, this);
        a->setShortcuts(keys);
        a->setShortcutContext(Qt::WindowShortcut);
        connect(a, &QAction::triggered, this, slot);
        addAction(a);
        return a;
    };
    using K = QKeySequence;
    m_backAction = add(QStringLiteral("Back"), {K(Qt::ALT | Qt::Key_Left), K(Qt::Key_Back)}, [this] { activePane()->goBack(); });
    m_forwardAction = add(QStringLiteral("Forward"), {K(Qt::ALT | Qt::Key_Right), K(Qt::Key_Forward)}, [this] { activePane()->goForward(); });
    m_upAction = add(QStringLiteral("Up"), {K(Qt::ALT | Qt::Key_Up)}, [this] { activePane()->goUp(); });
    add(QStringLiteral("Up"), {K(Qt::Key_Backspace)}, [this] {
        if (QApplication::focusWidget() && QApplication::focusWidget()->inherits("QLineEdit"))
            return;
        activePane()->goUp();
    });
    add(QStringLiteral("Home"), {K(Qt::ALT | Qt::Key_Home)}, [this] { activePane()->setUrl(QUrl::fromLocalFile(QDir::homePath())); });
    add(QStringLiteral("Reload"), {K(Qt::Key_F5), K(Qt::CTRL | Qt::Key_R)}, [this] { activePane()->reload(); });
    add(QStringLiteral("Edit location"), {K(Qt::Key_F6), K(Qt::CTRL | Qt::Key_L)}, [this] {
        KUrlNavigator *nav = activePane()->navigator();
        nav->setUrlEditable(true);
        nav->setFocus();
        if (nav->editor() && nav->editor()->lineEdit())
            nav->editor()->lineEdit()->selectAll();
    });
    add(QStringLiteral("New tab"), {K(Qt::CTRL | Qt::Key_T)}, [this] { openTab(activePane()->url()); });
    add(QStringLiteral("Close tab"), {K(Qt::CTRL | Qt::Key_W)}, [this] { closeTab(m_tabBar->currentIndex()); });
    add(QStringLiteral("Reopen closed tab"), {K(Qt::CTRL | Qt::SHIFT | Qt::Key_T)}, [this] {
        if (!m_closedTabs.isEmpty())
            openTab(m_closedTabs.takeLast());
    });
    add(QStringLiteral("Next tab"), {K(Qt::CTRL | Qt::Key_Tab), K(Qt::CTRL | Qt::Key_PageDown)}, [this] {
        m_tabBar->setCurrentIndex((m_tabBar->currentIndex() + 1) % m_tabBar->count());
    });
    add(QStringLiteral("Previous tab"), {K(Qt::CTRL | Qt::SHIFT | Qt::Key_Tab), K(Qt::CTRL | Qt::Key_PageUp)}, [this] {
        m_tabBar->setCurrentIndex((m_tabBar->currentIndex() + m_tabBar->count() - 1) % m_tabBar->count());
    });
    m_splitAction = add(QStringLiteral("Split view"), {K(Qt::Key_F3)}, [this] { toggleSplit(); });
    m_splitAction->setCheckable(true);
    m_previewAction = add(QStringLiteral("Previews"), {K(Qt::Key_F11)}, [this](bool on) { setPreviewsVisible(on); });
    m_previewAction->setCheckable(true);
    m_sidebarAction = add(QStringLiteral("Sidebar"), {K(Qt::Key_F9)}, [this](bool on) { m_sidebar->setVisible(on); });
    m_sidebarAction->setCheckable(true);
    m_hiddenAction = add(QStringLiteral("Show hidden files"), {K(Qt::CTRL | Qt::Key_H), K(Qt::ALT | Qt::Key_Period)}, [this](bool on) {
        for (Tab *t : std::as_const(m_tabs))
            for (FolderPane *p : std::as_const(t->panes))
                p->model()->setShowHidden(on);
    });
    m_hiddenAction->setCheckable(true);
    m_hiddenAction->setChecked(settings().readEntry("ShowHidden", false));
    add(QStringLiteral("Grid"), {K(Qt::CTRL | Qt::Key_1)}, [this] { setViewMode(FolderView::Grid); });
    add(QStringLiteral("List"), {K(Qt::CTRL | Qt::Key_2)}, [this] { setViewMode(FolderView::List); });
    add(QStringLiteral("Details"), {K(Qt::CTRL | Qt::Key_3)}, [this] { setViewMode(FolderView::Details); });
    add(QStringLiteral("Zoom in"), {K(Qt::CTRL | Qt::Key_Plus), K(Qt::CTRL | Qt::Key_Equal)}, [this] { zoom(1); });
    add(QStringLiteral("Zoom out"), {K(Qt::CTRL | Qt::Key_Minus)}, [this] { zoom(-1); });
    add(QStringLiteral("Search"), {K(Qt::CTRL | Qt::Key_F)}, [this] {
        m_search->setFocus();
        m_search->selectAll();
    });
    add(QStringLiteral("Filter"), {K(Qt::CTRL | Qt::Key_I)}, [this] { activePane()->showFilter(); });
    add(QStringLiteral("Copy"), {K(QKeySequence::Copy)}, [this] { Ops::copy(activePane()->selectedItems(), false); });
    add(QStringLiteral("Cut"), {K(QKeySequence::Cut)}, [this] {
        const KFileItemList items = activePane()->selectedItems();
        Ops::copy(items, true);
        activePane()->model()->setCutUrls(Ops::urls(items));
    });
    m_pasteAction = add(QStringLiteral("Paste"), {K(QKeySequence::Paste)}, [this] { Ops::paste(activePane()->url(), this); });
    m_undoAction = add(QStringLiteral("Undo"), {K(QKeySequence::Undo)}, [this] { Ops::undo(this); });
    add(QStringLiteral("Rename"), {K(Qt::Key_F2)}, [this] {
        const KFileItemList items = activePane()->selectedItems();
        if (items.size() > 1)
            Ops::batchRename(items, this);
        else
            activePane()->view()->editCurrent();
    });
    add(QStringLiteral("Move to trash"), {K(Qt::Key_Delete)}, [this] {
        const KFileItemList items = activePane()->selectedItems();
        if (items.isEmpty())
            return;
        if (activePane()->url().scheme() == QLatin1String("trash"))
            Ops::del(Ops::urls(items), this);
        else
            Ops::trash(Ops::urls(items), this);
    });
    add(QStringLiteral("Delete"), {K(Qt::SHIFT | Qt::Key_Delete)}, [this] {
        const KFileItemList items = activePane()->selectedItems();
        if (!items.isEmpty())
            Ops::del(Ops::urls(items), this);
    });
    add(QStringLiteral("New folder"), {K(Qt::Key_F10), K(Qt::CTRL | Qt::SHIFT | Qt::Key_N)}, [this] { activePane()->newFolder(); });
    add(QStringLiteral("Properties"), {K(Qt::ALT | Qt::Key_Return), K(Qt::ALT | Qt::Key_Enter)}, [this] {
        KFileItemList items = activePane()->selectedItems();
        if (items.isEmpty())
            items << activePane()->model()->rootItem();
        Ops::properties(items, this);
    });
    add(QStringLiteral("Open terminal"), {K(Qt::SHIFT | Qt::Key_F4)}, [this] { Ops::openTerminal(activePane()->url(), this); });
    add(QStringLiteral("Invert selection"), {K(Qt::CTRL | Qt::SHIFT | Qt::Key_A)}, [this] {
        FolderView *v = activePane()->view();
        QItemSelectionModel *sel = v->selectionModel();
        const QAbstractItemModel *m = v->model();
        if (m->rowCount() == 0)
            return;
        sel->select(QItemSelection(m->index(0, 0), m->index(m->rowCount() - 1, m->columnCount() - 1)), QItemSelectionModel::Toggle);
    });
    add(QStringLiteral("Add to Places"), {K(Qt::CTRL | Qt::Key_D)}, [this] {
        const QUrl u = activePane()->url();
        places()->addPlace(activePane()->title(), u, QStringLiteral("folder"), QString());
    });
    add(QStringLiteral("Escape"), {K(Qt::Key_Escape)}, [this] {
        if (!m_search->text().isEmpty()) {
            m_search->clear();
            activePane()->view()->setFocusToView();
        } else {
            activePane()->view()->selectionModel()->clearSelection();
        }
    });
    add(QStringLiteral("Quit"), {K(Qt::CTRL | Qt::Key_Q)}, [] { QApplication::closeAllWindows(); });
}

MainWindow::Tab *MainWindow::currentTab() const
{
    const int i = m_tabBar->currentIndex();
    return i >= 0 && i < m_tabs.size() ? m_tabs[i] : (m_tabs.isEmpty() ? nullptr : m_tabs.first());
}

MainWindow::Tab *MainWindow::tabOf(FolderPane *pane) const
{
    for (Tab *t : m_tabs)
        if (t->panes.contains(pane))
            return t;
    return nullptr;
}

FolderPane *MainWindow::activePane() const
{
    Tab *t = currentTab();
    return t ? t->active : nullptr;
}

FolderPane *MainWindow::createPane(const QUrl &url)
{
    auto *pane = new FolderPane(places(), url);
    const KConfigGroup cfg = settings();
    pane->model()->setShowHidden(m_hiddenAction->isChecked());
    pane->model()->sort(cfg.readEntry("SortColumn", 0), Qt::SortOrder(cfg.readEntry("SortOrder", 0)));
    pane->view()->header()->setSortIndicator(pane->model()->sortColumn(), pane->model()->sortOrder());
    const QByteArray header = QByteArray::fromBase64(cfg.readEntry("DetailsHeader", QByteArray()));
    if (!header.isEmpty())
        pane->view()->header()->restoreState(header);
    pane->view()->setMode(m_mode);
    pane->view()->setIconSize(m_iconSizes[m_mode]);
    connect(pane, &FolderPane::activated, this, [this, pane] { setActivePane(pane); });
    connect(pane, &FolderPane::urlChanged, this, [this, pane] {
        if (pane == activePane())
            syncChrome();
        Tab *t = tabOf(pane);
        if (t && t->active == pane)
            m_tabBar->setTabText(int(m_tabs.indexOf(t)), pane->title());
    });
    connect(pane, &FolderPane::statusChanged, this, [this, pane] {
        if (pane == activePane())
            updateStatus();
    });
    connect(pane, &FolderPane::selectionChanged, this, [this, pane] {
        if (pane == activePane())
            updatePreview();
    });
    connect(pane, &FolderPane::openInNewTab, this, [this](const QUrl &u) { openTab(u, false); });
    connect(pane, &FolderPane::openInNewWindow, this, [](const QUrl &u) { (new MainWindow({u}))->show(); });
    connect(pane, &FolderPane::zoomRequested, this, &MainWindow::zoom);
    return pane;
}

void MainWindow::openTab(const QUrl &url, bool activate)
{
    auto *tab = new Tab;
    tab->splitter = new QSplitter(m_stack);
    tab->splitter->setHandleWidth(8);
    tab->splitter->setChildrenCollapsible(false);
    FolderPane *pane = createPane(url);
    tab->splitter->addWidget(pane);
    tab->panes << pane;
    tab->active = pane;
    m_stack->addWidget(tab->splitter);
    const int at = m_tabBar->currentIndex() + 1;
    m_tabs.insert(at, tab);
    m_tabBar->insertTab(at, pane->title());
    m_tabBar->setVisible(m_tabs.size() > 1);
    if (activate || m_tabs.size() == 1) {
        m_tabBar->setCurrentIndex(at);
        m_stack->setCurrentWidget(tab->splitter);
        setActivePane(pane);
    }
}

void MainWindow::closeTab(int index)
{
    if (m_tabs.size() <= 1) {
        close();
        return;
    }
    Tab *t = m_tabs.takeAt(index);
    m_closedTabs << t->active->url();
    if (m_dockedPane && t->panes.contains(m_dockedPane))
        m_dockedPane = nullptr;
    m_tabBar->removeTab(index);
    t->splitter->deleteLater();
    delete t;
    m_tabBar->setVisible(m_tabs.size() > 1);
    setActivePane(currentTab()->active);
}

void MainWindow::setActivePane(FolderPane *pane)
{
    Tab *t = tabOf(pane);
    if (!t)
        return;
    t->active = pane;
    for (FolderPane *p : std::as_const(t->panes))
        p->setActive(p == pane);
    dockNavigator();
    syncChrome();
}

void MainWindow::dockNavigator()
{
    // One pane: its path bar sits in the toolbar. Split: each pane shows its own.
    Tab *t = currentTab();
    if (!t)
        return;
    FolderPane *want = t->panes.size() == 1 ? t->active : nullptr;
    if (m_dockedPane && m_dockedPane != want)
        m_dockedPane->dockNavigator(false);
    for (FolderPane *p : std::as_const(t->panes))
        if (p != want)
            p->dockNavigator(false);
    if (want && m_dockedPane != want) {
        want->dockNavigator(true);
        m_navSlot->addWidget(want->navigator());
        want->navigator()->show();
    }
    m_dockedPane = want;
}

void MainWindow::syncChrome()
{
    FolderPane *p = activePane();
    if (!p)
        return;
    setWindowTitle(p->title() + QStringLiteral(" — DeckOS Files"));
    Tab *t = currentTab();
    m_splitAction->setChecked(t && t->panes.size() > 1);
    const FolderView::Mode mode = p->view()->mode();
    for (int i = 0; i < 3; ++i)
        m_viewButtons[i]->setChecked(i == mode);
    const QSignalBlocker block(m_zoom);
    const int size = p->view()->iconSize();
    int step = 0;
    for (int i = 0; i < int(std::size(ZoomSteps)); ++i)
        if (ZoomSteps[i] <= size)
            step = i;
    m_zoom->setValue(step);
    m_sidebar->setCurrentUrl(p->url());
    if (!p->isSearching() && !m_search->hasFocus())
        m_search->clear();
    updateStatus();
    updatePreview();

    // Free space on the folder's drive, off the UI thread (statvfs can hang on a dead network mount).
    m_free->clear();
    const QUrl url = p->url();
    if (url.isLocalFile()) {
        auto *watcher = new QFutureWatcher<QString>(this);
        connect(watcher, &QFutureWatcher<QString>::finished, this, [this, watcher, url] {
            if (activePane() && activePane()->url() == url)
                m_free->setText(watcher->result());
            watcher->deleteLater();
        });
        watcher->setFuture(QtConcurrent::run([path = url.toLocalFile()] {
            const QStorageInfo info(path);
            return info.isValid() ? QStringLiteral("%1 free").arg(KIO::convertSize(KIO::filesize_t(info.bytesAvailable()))) : QString();
        }));
    }
}

void MainWindow::updateStatus()
{
    if (FolderPane *p = activePane())
        m_status->setText(p->statusText());
}

void MainWindow::updatePreview()
{
    if (!m_previewPanel->isVisible())
        return;
    FolderPane *p = activePane();
    if (!p)
        return;
    const KFileItemList sel = p->selectedItems();
    const KFileItem item = sel.size() == 1 ? sel.first() : p->model()->rootItem();
    if (m_previewJob)
        m_previewJob->kill();
    const qreal dpr = devicePixelRatioF();
    if (sel.size() > 1) {
        m_previewImage->setPixmap(Style::themeIcon(QStringLiteral("edit-copy")).pixmap(QSize(128, 128), dpr));
        m_previewName->setText(QStringLiteral("%1 items selected").arg(sel.size()));
        m_previewInfo->setText(p->statusText());
        return;
    }
    if (item.isNull()) {
        m_previewImage->clear();
        m_previewName->setText(p->title());
        m_previewInfo->setText(p->statusText());
        return;
    }
    m_previewImage->setPixmap(Style::themeIcon(item.iconName()).pixmap(QSize(128, 128), dpr));
    m_previewName->setText(item.text());
    QStringList info;
    info << (item.isDir() ? QStringLiteral("Folder") : item.mimeComment());
    if (!item.isDir())
        info << KIO::convertSize(item.size());
    else if (sel.isEmpty())
        info << p->statusText();
    const QDateTime mtime = item.time(KFileItem::ModificationTime);
    if (mtime.isValid())
        info << QStringLiteral("Modified %1").arg(QLocale().toString(mtime, QLocale::ShortFormat));
    if (item.isLocalFile() && item.mimetype().startsWith(QLatin1String("image/"))) {
        const QSize dims = QImageReader(item.localPath()).size();  // header only
        if (dims.isValid())
            info << QStringLiteral("%1 × %2").arg(dims.width()).arg(dims.height());
    }
    info << item.url().toDisplayString(QUrl::PreferLocalFile);
    m_previewInfo->setText(info.join(QLatin1Char('\n')));
    if (!item.isDir() && item.isLocalFile()) {
        static const QStringList plugins = KIO::PreviewJob::defaultPlugins();
        m_previewJob = KIO::filePreview({item}, QSize(256, 256), &plugins);
        m_previewJob->setDevicePixelRatio(dpr);
        connect(m_previewJob, &KIO::PreviewJob::gotPreview, this, [this](const KFileItem &, const QPixmap &pm) {
            m_previewImage->setPixmap(pm);
        });
    }
}

void MainWindow::setViewMode(FolderView::Mode mode)
{
    m_mode = mode;
    if (FolderPane *p = activePane()) {
        p->view()->setMode(mode);
        p->view()->setIconSize(m_iconSizes[mode]);
    }
    syncChrome();
}

void MainWindow::zoom(int step)
{
    m_zoom->setValue(qBound(0, m_zoom->value() + step, m_zoom->maximum()));
}

void MainWindow::toggleSplit()
{
    Tab *t = currentTab();
    if (!t)
        return;
    if (t->panes.size() > 1) {
        // Closing the split keeps the pane you're working in.
        FolderPane *other = t->panes[0] == t->active ? t->panes[1] : t->panes[0];
        if (m_dockedPane == other)
            m_dockedPane = nullptr;
        t->panes.removeOne(other);
        other->deleteLater();
    } else {
        FolderPane *pane = createPane(t->active->url());
        t->splitter->addWidget(pane);
        t->panes << pane;
        t->splitter->setSizes({1, 1});
    }
    setActivePane(t->active);
}

void MainWindow::setPreviewsVisible(bool visible)
{
    m_previewPanel->setVisible(visible);
    m_previewAction->setChecked(visible);
    updatePreview();
}

void MainWindow::search(const QString &text)
{
    if (FolderPane *p = activePane()) {
        if (text.isEmpty() && !p->isSearching())
            return;
        p->search(text);
        if (Tab *t = currentTab())
            m_tabBar->setTabText(int(m_tabs.indexOf(t)), p->title());
    }
}

void MainWindow::selectUrls(const QList<QUrl> &urls)
{
    if (FolderPane *p = activePane())
        p->view()->selectUrls(urls);
}

// ------------------------------------------------------------------ FileManager1

namespace {
QList<QUrl> toUrls(const QStringList &uris)
{
    QList<QUrl> urls;
    for (const QString &u : uris)
        urls << QUrl::fromUserInput(u, QDir::currentPath(), QUrl::AssumeLocalFile);
    return urls;
}
} // namespace

void FileManager1::ShowFolders(const QStringList &uris, const QString &)
{
    auto *w = new MainWindow(toUrls(uris));
    w->show();
    w->raise();
}

void FileManager1::ShowItems(const QStringList &uris, const QString &)
{
    const QList<QUrl> urls = toUrls(uris);
    if (urls.isEmpty())
        return;
    auto *w = new MainWindow({urls.first().adjusted(QUrl::RemoveFilename | QUrl::StripTrailingSlash)});
    w->show();
    w->raise();
    // Select once the folder has listed.
    auto *model = w->activePane()->model();
    auto conn = std::make_shared<QMetaObject::Connection>();
    *conn = QObject::connect(model, &FolderModel::loadingFinished, w, [w, urls, conn] {
        w->selectUrls(urls);
        QObject::disconnect(*conn);
    });
}

void FileManager1::ShowItemProperties(const QStringList &uris, const QString &)
{
    KFileItemList items;
    for (const QUrl &u : toUrls(uris))
        items << KFileItem(u);
    Ops::properties(items, nullptr);
}
