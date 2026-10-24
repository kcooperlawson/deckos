#include "mainwindow.h"
#include "modewatch.h"
#include "style.h"
#include "tabpage.h"
#include "terminalpane.h"

#include <QAction>
#include <QApplication>
#include <QCloseEvent>
#include <QHBoxLayout>
#include <QMessageBox>
#include <QProcess>
#include <QStackedWidget>
#include <QTabBar>
#include <QTimer>
#include <QToolButton>
#include <QVBoxLayout>

#include <qtermwidget.h>

namespace {

QString tabQss()
{
    return QStringLiteral(R"(
QWidget#tabRow { background: #0B0D11; border-bottom: 1px solid #1D212A; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: #8C94A6; border: 1px solid transparent; border-radius: 8px;
    padding: 5px 6px 5px 12px; margin: 5px 2px; min-width: 60px; max-width: 280px; }
QTabBar::tab:hover { background: #171A21; color: #E8EAF0; }
QTabBar::tab:selected { background: #1D212A; border-color: #262B36; color: #E8EAF0; }
QToolButton#modeChip { color: white; font-weight: 600; border: none; border-radius: 9px; padding: 3px 10px;
    margin: 6px 4px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 %1, stop:1 %2); }
QSplitter::handle { background: #0B0D11; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #262B36; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #353B49; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; height: 0; }
)")
        .arg(Style::accent().name(), Style::accentPartner().name());
}

} // namespace

MainWindow::MainWindow(ModeWatch *modes, const QString &dir, const QStringList &command, bool hold)
    : m_modes(modes)
{
    setAttribute(Qt::WA_DeleteOnClose);
    setWindowIcon(QIcon::fromTheme(QStringLiteral("deckos-terminal"), QIcon::fromTheme(QStringLiteral("utilities-terminal"))));
    setStyleSheet(Style::chromeQss() + tabQss());

    auto *central = new QWidget(this);
    auto *layout = new QVBoxLayout(central);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    auto *row = new QWidget(central);
    row->setObjectName(QStringLiteral("tabRow"));
    row->setAttribute(Qt::WA_StyledBackground);
    auto *rowLayout = new QHBoxLayout(row);
    rowLayout->setContentsMargins(6, 0, 6, 0);
    rowLayout->setSpacing(2);

    m_tabs = new QTabBar(row);
    m_tabs->setDocumentMode(true);
    m_tabs->setExpanding(false);
    m_tabs->setMovable(true);
    m_tabs->setUsesScrollButtons(true);
    m_tabs->setElideMode(Qt::ElideMiddle);
    m_tabs->setDrawBase(false);
    rowLayout->addWidget(m_tabs);

    auto *plus = new QToolButton(row);
    plus->setIcon(Style::icon(QStringLiteral("plus")));
    plus->setToolTip(QStringLiteral("New tab (Ctrl+Shift+T)"));
    plus->setAutoRaise(true);
    connect(plus, &QToolButton::clicked, this, [this] { openTab(pane() ? pane()->currentDir() : QString()); });
    rowLayout->addWidget(plus);
    rowLayout->addStretch(1);

    // While a game runs: what workload modes freed for it. Click for the Hub's Gaming page.
    m_modeChip = new QToolButton(row);
    m_modeChip->setObjectName(QStringLiteral("modeChip"));
    m_modeChip->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
    m_modeChip->setIcon(QIcon(Style::pixmap(QStringLiteral("gaming"), Qt::white, 16, devicePixelRatioF())));
    m_modeChip->setCursor(Qt::PointingHandCursor);
    m_modeChip->setToolTip(QStringLiteral("Workload modes freed the graphics card for your game. Builds and tools here keep running."));
    connect(m_modeChip, &QToolButton::clicked, this, [] {
        QProcess::startDetached(QStringLiteral("deckos-hub"), {QStringLiteral("--page"), QStringLiteral("gaming")});
    });
    rowLayout->addWidget(m_modeChip);
    layout->addWidget(row);

    m_stack = new QStackedWidget(central);
    layout->addWidget(m_stack, 1);
    setCentralWidget(central);

    connect(m_tabs, &QTabBar::currentChanged, this, &MainWindow::pageChanged);
    connect(m_tabs, &QTabBar::tabMoved, this, [this](int from, int to) {
        QWidget *w = m_stack->widget(from);
        m_stack->removeWidget(w);
        m_stack->insertWidget(to, w);
        m_stack->setCurrentIndex(m_tabs->currentIndex());
    });
    connect(m_tabs, &QTabBar::tabBarClicked, this, [this](int i) {
        if (i >= 0 && QApplication::mouseButtons() & Qt::MiddleButton)
            closePage(qobject_cast<TabPage *>(m_stack->widget(i)));
    });
    connect(m_modes, &ModeWatch::changed, this, &MainWindow::updateMode);

    // The visible tab's folders and commands; hidden tabs catch up when shown.
    auto *timer = new QTimer(this);
    timer->setInterval(2000);
    connect(timer, &QTimer::timeout, this, [this] {
        if (isVisible() && !isMinimized() && currentPage())
            currentPage()->refresh();
    });
    timer->start();

    addShortcuts();
    updateMode();
    if (TabPage *page = openTab(dir, command); hold && page->activePane())
        page->activePane()->setHold(true);
    resize(1100, 700);
}

TabPage *MainWindow::currentPage() const
{
    return qobject_cast<TabPage *>(m_stack->currentWidget());
}

TerminalPane *MainWindow::pane() const
{
    TabPage *page = currentPage();
    return page ? page->activePane() : nullptr;
}

TabPage *MainWindow::openTab(const QString &dir, const QStringList &command)
{
    auto *page = new TabPage(dir, command);
    const int index = m_tabs->currentIndex() + 1;
    m_stack->insertWidget(index, page);
    m_tabs->insertTab(index, QString());

    auto *close = new QToolButton(m_tabs);
    close->setIcon(Style::icon(QStringLiteral("close")));
    close->setIconSize(QSize(14, 14));
    close->setAutoRaise(true);
    close->setToolTip(QStringLiteral("Close tab"));
    connect(close, &QToolButton::clicked, this, [this, page] { closePage(page); });
    m_tabs->setTabButton(index, QTabBar::RightSide, close);

    connect(page, &TabPage::infoChanged, this, [this, page] {
        updateTab(page);
        for (QAction *a : std::as_const(m_splitNav))
            a->setEnabled(currentPage() && currentPage()->panes().size() > 1);
    });
    connect(page, &TabPage::empty, this, [this, page] { closePage(page); });
    connect(page, &TabPage::bell, this, [this, page] {
        const int i = m_stack->indexOf(page);
        if (i != m_tabs->currentIndex())
            m_tabs->setTabTextColor(i, Style::accent());
        else
            QApplication::alert(this);
    });

    updateTab(page);
    m_tabs->setCurrentIndex(index);
    if (page->activePane())
        page->activePane()->focusTerminal();
    return page;
}

void MainWindow::updateTab(TabPage *page)
{
    const int i = m_stack->indexOf(page);
    TerminalPane *p = page->activePane();
    if (i < 0 || !p)
        return;
    m_tabs->setTabText(i, p->info().label());
    m_tabs->setTabToolTip(i, p->info().dir);
    if (i == m_tabs->currentIndex())
        setWindowTitle(p->info().label() + QStringLiteral(" — DeckOS Terminal"));
}

void MainWindow::pageChanged()
{
    const int i = m_tabs->currentIndex();
    if (i < 0)
        return;
    m_stack->setCurrentIndex(i);
    m_tabs->setTabTextColor(i, QColor());  // seen: clear the bell
    if (TabPage *page = currentPage()) {
        page->refresh();
        updateTab(page);
        for (QAction *a : std::as_const(m_splitNav))
            a->setEnabled(page->panes().size() > 1);
        if (page->activePane())
            page->activePane()->focusTerminal();
    }
}

void MainWindow::closePage(TabPage *page)
{
    const int i = m_stack->indexOf(page);
    if (i < 0)
        return;
    m_tabs->removeTab(i);
    m_stack->removeWidget(page);
    page->deleteLater();
    if (m_stack->count() == 0)
        close();
}

void MainWindow::updateMode()
{
    m_modeChip->setVisible(m_modes->gaming());
    m_modeChip->setText(m_modes->summary());
}

void MainWindow::addShortcut(const QKeySequence &keys, std::function<void()> fn, QAction **out)
{
    auto *a = new QAction(this);
    a->setShortcut(keys);
    a->setShortcutContext(Qt::WindowShortcut);
    connect(a, &QAction::triggered, this, fn);
    addAction(a);
    if (out)
        *out = a;
}

void MainWindow::addShortcuts()
{
    const auto ctrlShift = Qt::CTRL | Qt::SHIFT;
    addShortcut(ctrlShift | Qt::Key_T, [this] { openTab(pane() ? pane()->currentDir() : QString()); });
    addShortcut(ctrlShift | Qt::Key_N, [this] {
        (new MainWindow(m_modes, pane() ? pane()->currentDir() : QString()))->show();
    });
    addShortcut(ctrlShift | Qt::Key_W, [this] {
        if (TabPage *page = currentPage())
            page->closePane(page->activePane());
    });
    addShortcut(ctrlShift | Qt::Key_D, [this] { if (currentPage()) currentPage()->split(Qt::Horizontal); });
    addShortcut(ctrlShift | Qt::Key_E, [this] { if (currentPage()) currentPage()->split(Qt::Vertical); });
    addShortcut(ctrlShift | Qt::Key_C, [this] { if (pane()) pane()->term()->copyClipboard(); });
    addShortcut(ctrlShift | Qt::Key_V, [this] { if (pane()) pane()->term()->pasteClipboard(); });
    addShortcut(ctrlShift | Qt::Key_F, [this] { if (pane()) pane()->term()->toggleShowSearchBar(); });
    // DeckOS Assistant about the selection (an error, a command), or just the chat box
    addShortcut(ctrlShift | Qt::Key_A, [this] {
        QStringList args;
        if (TerminalPane *p = pane(); p && !p->term()->selectedText().trimmed().isEmpty())
            args << QStringLiteral("--ask")
                 << QStringLiteral("Explain this from my terminal (in %1), and fix it if something's wrong:\n%2")
                        .arg(p->currentDir(), p->term()->selectedText().trimmed().left(4000));
        QProcess::startDetached(QStringLiteral("deckos-assistant"), args);
    });
    addShortcut(Qt::CTRL | Qt::Key_Equal, [this] { if (pane()) pane()->zoom(1); });
    addShortcut(Qt::CTRL | Qt::Key_Plus, [this] { if (pane()) pane()->zoom(1); });
    addShortcut(Qt::CTRL | Qt::Key_Minus, [this] { if (pane()) pane()->zoom(-1); });
    addShortcut(Qt::CTRL | Qt::Key_0, [this] { if (pane()) pane()->zoom(0); });

    auto step = [this](int by) {
        const int n = m_tabs->count();
        if (n > 1)
            m_tabs->setCurrentIndex((m_tabs->currentIndex() + by + n) % n);
    };
    addShortcut(Qt::CTRL | Qt::Key_PageDown, [step] { step(1); });
    addShortcut(Qt::CTRL | Qt::Key_PageUp, [step] { step(-1); });
    addShortcut(Qt::CTRL | Qt::Key_Tab, [step] { step(1); });
    addShortcut(ctrlShift | Qt::Key_Backtab, [step] { step(-1); });
    for (int n = 1; n <= 9; ++n)
        addShortcut(QKeySequence(Qt::ALT | Qt::Key(Qt::Key_0 + n)), [this, n] {
            if (n <= m_tabs->count())
                m_tabs->setCurrentIndex(n - 1);
        });

    const QList<QPair<Qt::Key, Qt::ArrowType>> arrows = {
        {Qt::Key_Left, Qt::LeftArrow}, {Qt::Key_Right, Qt::RightArrow}, {Qt::Key_Up, Qt::UpArrow}, {Qt::Key_Down, Qt::DownArrow}};
    for (const auto &[key, arrow] : arrows) {
        QAction *a = nullptr;
        addShortcut(Qt::ALT | key, [this, arrow] { if (currentPage()) currentPage()->focusNeighbour(arrow); }, &a);
        a->setEnabled(false);
        m_splitNav << a;
    }
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    // A running program (a build, an editor, ssh) is worth a question; a shell at its prompt isn't.
    QStringList running;
    for (int i = 0; i < m_stack->count(); ++i) {
        for (TerminalPane *p : qobject_cast<TabPage *>(m_stack->widget(i))->panes()) {
            p->refresh();
            if (!p->info().command.isEmpty())
                running << p->info().command;
        }
    }
    if (!running.isEmpty() && isVisible()) {
        const auto answer = QMessageBox::question(
            this, QStringLiteral("Close DeckOS Terminal?"),
            QStringLiteral("Still running: %1. Closing the window stops %2.").arg(running.join(QStringLiteral(", ")),
                                                                                   running.size() == 1 ? QStringLiteral("it") : QStringLiteral("them")),
            QMessageBox::Close | QMessageBox::Cancel, QMessageBox::Cancel);
        if (answer != QMessageBox::Close) {
            event->ignore();
            return;
        }
    }
    event->accept();
}
