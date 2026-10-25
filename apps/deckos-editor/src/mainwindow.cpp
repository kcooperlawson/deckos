#include "mainwindow.h"

#include "editorview.h"
#include "findbar.h"
#include "style.h"

#include <QAction>
#include <QApplication>
#include <QCloseEvent>
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QHBoxLayout>
#include <QInputDialog>
#include <QLabel>
#include <QMenu>
#include <QMessageBox>
#include <QMimeData>
#include <QProcess>
#include <QPushButton>
#include <QShortcut>
#include <QStackedWidget>
#include <QStatusBar>
#include <QTabBar>
#include <QTimer>
#include <QToolButton>
#include <QVBoxLayout>

#include <KConfigGroup>
#include <KSharedConfig>
#include <KSyntaxHighlighting/Definition>
#include <KSyntaxHighlighting/Repository>

namespace {

QToolButton *headerButton(const QString &icon, const QString &tip, QWidget *parent)
{
    auto *b = new QToolButton(parent);
    b->setIcon(Style::icon(icon));
    b->setToolTip(tip);
    b->setAutoRaise(true);
    b->setIconSize({18, 18});
    b->setCursor(Qt::PointingHandCursor);
    return b;
}

QToolButton *statusButton(QWidget *parent)
{
    auto *b = new QToolButton(parent);
    b->setAutoRaise(true);
    b->setCursor(Qt::PointingHandCursor);
    b->setObjectName(QStringLiteral("statusPart"));
    return b;
}

KConfigGroup sessionGroup()
{
    return KConfigGroup(KSharedConfig::openConfig(QStringLiteral("deckos-editorrc")), QStringLiteral("Session"));
}

const char *Qss = R"(
QMainWindow, QStackedWidget { background: #0F1115; }
QTabBar { background: #0B0D11; }
QTabBar::tab { background: transparent; color: #8C94A6; padding: 9px 14px; border: none; border-right: 1px solid #171A21;
    min-width: 90px; max-width: 220px; }
QTabBar::tab:selected { background: #0F1115; color: #E8EAF0; border-top: 2px solid %ACCENT%; }
QTabBar::tab:hover:!selected { color: #E8EAF0; background: #11141A; }
QFrame#findBar, QWidget#banner { background: #171A21; border-top: 1px solid #262B36; }
QStatusBar { background: #0B0D11; border-top: 1px solid #171A21; color: #8C94A6; }
QStatusBar::item { border: none; }
QToolButton#statusPart { color: #8C94A6; padding: 2px 8px; border-radius: 6px; }
QToolButton#statusPart:hover { background: #1D212A; color: #E8EAF0; }
QPlainTextEdit { selection-background-color: #26385E; }
)";

} // namespace

MainWindow::MainWindow(KSyntaxHighlighting::Repository *repo, bool restore)
    : m_repo(repo)
{
    setWindowTitle(QStringLiteral("DeckOS Editor"));
    setWindowIcon(QIcon::fromTheme(QStringLiteral("deckos-editor")));
    setAcceptDrops(true);
    resize(1100, 740);
    setStyleSheet(Style::chromeQss() + QString::fromLatin1(Qss).replace(QStringLiteral("%ACCENT%"), Style::accent().name()));

    auto *central = new QWidget(this);
    auto *v = new QVBoxLayout(central);
    v->setContentsMargins(0, 0, 0, 0);
    v->setSpacing(0);
    m_tabs = new QTabBar(central);
    m_stack = new QStackedWidget(central);
    m_find = new FindBar(central);
    m_banner = new QWidget(central);
    m_banner->setObjectName(QStringLiteral("banner"));
    m_banner->setAttribute(Qt::WA_StyledBackground, true);
    auto *bl = new QHBoxLayout(m_banner);
    bl->setContentsMargins(14, 8, 14, 8);
    m_bannerText = new QLabel(m_banner);
    bl->addWidget(m_bannerText, 1);
    auto *reload = new QPushButton(QStringLiteral("Reload"), m_banner);
    auto *keep = new QPushButton(QStringLiteral("Keep mine"), m_banner);
    bl->addWidget(reload);
    bl->addWidget(keep);
    m_banner->hide();

    v->addWidget(m_stack, 1);
    v->addWidget(m_banner);
    v->addWidget(m_find);
    setCentralWidget(central);
    buildHeader();
    buildStatus();

    m_watcher = new QFileSystemWatcher(this);
    connect(m_watcher, &QFileSystemWatcher::fileChanged, this, [this](const QString &path) {
        // Editors save by replacing the file: watch the new one, and look a moment later
        QTimer::singleShot(150, this, [this, path] {
            if (QFileInfo::exists(path) && !m_watcher->files().contains(path))
                m_watcher->addPath(path);
            for (int i = 0; i < count(); ++i)
                if (viewAt(i)->document_().path() == path)
                    checkDisk(viewAt(i));
        });
    });
    connect(reload, &QPushButton::clicked, this, [this] {
        EditorView *v = current();
        if (!v)
            return;
        const int line = v->textCursor().blockNumber() + 1;
        if (v->document_().load(v->document_().path()) == Document::Load::Ok) {
            v->setPlainText(v->document_().text());
            v->setUnmodified();
            v->goToLine(line);
        }
        m_banner->hide();
    });
    connect(keep, &QPushButton::clicked, this, [this] {
        if (EditorView *v = current())
            v->document_().forgetDiskState();
        m_banner->hide();
    });

    addShortcut(QKeySequence::New, [this] { newTab(); });
    addShortcut(QKeySequence::Open, [this] { openDialog(); });
    addShortcut(QKeySequence::Save, [this] { if (current()) save(current()); });
    addShortcut(QKeySequence::SaveAs, [this] { if (current()) save(current(), true); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+W")), [this] { closeTab(m_tabs->currentIndex()); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+T")), [this] {
        if (!m_closed.isEmpty())
            openFile(m_closed.takeLast());
    });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+Tab")), [this] { m_tabs->setCurrentIndex((m_tabs->currentIndex() + 1) % std::max(1, count())); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+Tab")), [this] {
        m_tabs->setCurrentIndex((m_tabs->currentIndex() + count() - 1) % std::max(1, count()));
    });
    addShortcut(QKeySequence::Find, [this] { m_find->open(false); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+H")), [this] { m_find->open(true); });
    addShortcut(QKeySequence::FindNext, [this] { m_find->next(false); });
    addShortcut(QKeySequence::FindPrevious, [this] { m_find->next(true); });
    addShortcut(QKeySequence(QStringLiteral("Esc")), [this] {
        if (m_find->isVisible())
            m_find->close_();
    });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+G")), [this] { goToLineDialog(); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+/")), [this] { if (current()) current()->toggleComment(); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+D")), [this] { if (current()) current()->duplicateLine(); });
    addShortcut(QKeySequence(QStringLiteral("Alt+Up")), [this] { if (current()) current()->moveLines(-1); });
    addShortcut(QKeySequence(QStringLiteral("Alt+Down")), [this] { if (current()) current()->moveLines(1); });
    addShortcut(QKeySequence::ZoomIn, [this] { if (current()) current()->zoom(1); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+=")), [this] { if (current()) current()->zoom(1); });
    addShortcut(QKeySequence::ZoomOut, [this] { if (current()) current()->zoom(-1); });
    addShortcut(QKeySequence(QStringLiteral("Ctrl+0")), [this] { if (current()) current()->zoom(0); });
    addShortcut(QKeySequence(QStringLiteral("Alt+Z")), [this] {
        m_wrap = !m_wrap;
        for (int i = 0; i < count(); ++i)
            viewAt(i)->setLineWrapMode(m_wrap ? QPlainTextEdit::WidgetWidth : QPlainTextEdit::NoWrap);
        showMessage(m_wrap ? QStringLiteral("Long lines wrap") : QStringLiteral("Long lines scroll"));
    });

    connect(m_tabs, &QTabBar::currentChanged, this, &MainWindow::tabChanged);
    connect(m_tabs, &QTabBar::tabCloseRequested, this, [this](int i) { closeTab(i); });
    connect(m_tabs, &QTabBar::tabMoved, this, [this](int from, int to) {
        QWidget *w = m_stack->widget(from);
        m_stack->removeWidget(w);
        m_stack->insertWidget(to, w);
    });

    if (restore)
        restoreSession();
    if (count() == 0)
        newTab();
}

void MainWindow::addShortcut(const QKeySequence &keys, std::function<void()> fn)
{
    auto *s = new QShortcut(keys, this);
    connect(s, &QShortcut::activated, this, std::move(fn));
}

void MainWindow::buildHeader()
{
    auto *header = new QWidget(centralWidget());
    header->setObjectName(QStringLiteral("header"));
    header->setStyleSheet(QStringLiteral("QWidget#header { background: #0B0D11; border-bottom: 1px solid #171A21; }"));
    header->setAttribute(Qt::WA_StyledBackground, true);
    auto *h = new QHBoxLayout(header);
    h->setContentsMargins(6, 0, 8, 0);
    h->setSpacing(2);
    m_tabs->setParent(header);
    m_tabs->setTabsClosable(true);
    m_tabs->setMovable(true);
    m_tabs->setExpanding(false);
    m_tabs->setDocumentMode(true);
    m_tabs->setElideMode(Qt::ElideMiddle);
    m_tabs->setUsesScrollButtons(true);
    h->addWidget(m_tabs, 1);
    auto *add = headerButton(QStringLiteral("plus"), QStringLiteral("New file (Ctrl+N)"), header);
    auto *open = headerButton(QStringLiteral("folder"), QStringLiteral("Open (Ctrl+O)"), header);
    auto *saveB = headerButton(QStringLiteral("download"), QStringLiteral("Save (Ctrl+S)"), header);
    auto *find = headerButton(QStringLiteral("search"), QStringLiteral("Find and replace (Ctrl+F, Ctrl+H)"), header);
    auto *more = headerButton(QStringLiteral("menu"), QStringLiteral("More"), header);
    for (QToolButton *b : {add, open, saveB, find, more})
        h->addWidget(b);
    connect(add, &QToolButton::clicked, this, [this] { newTab(); });
    connect(open, &QToolButton::clicked, this, &MainWindow::openDialog);
    connect(saveB, &QToolButton::clicked, this, [this] { if (current()) save(current()); });
    connect(find, &QToolButton::clicked, this, [this] { m_find->open(true); });
    auto *menu = new QMenu(more);
    menu->addAction(QStringLiteral("Save as…"), QKeySequence::SaveAs, this, [this] { if (current()) save(current(), true); });
    menu->addAction(QStringLiteral("Reopen closed tab"), QKeySequence(QStringLiteral("Ctrl+Shift+T")), this, [this] {
        if (!m_closed.isEmpty())
            openFile(m_closed.takeLast());
    });
    menu->addSeparator();
    menu->addAction(QStringLiteral("Go to line…"), QKeySequence(QStringLiteral("Ctrl+G")), this, &MainWindow::goToLineDialog);
    menu->addAction(QStringLiteral("Comment or uncomment"), QKeySequence(QStringLiteral("Ctrl+/")), this,
                    [this] { if (current()) current()->toggleComment(); });
    menu->addAction(QStringLiteral("Wrap long lines"), QKeySequence(QStringLiteral("Alt+Z")), this, [this] {
        m_wrap = !m_wrap;
        for (int i = 0; i < count(); ++i)
            viewAt(i)->setLineWrapMode(m_wrap ? QPlainTextEdit::WidgetWidth : QPlainTextEdit::NoWrap);
    });
    menu->addSeparator();
    menu->addAction(QStringLiteral("Open containing folder"), this, [this] {
        if (current() && !current()->document_().path().isEmpty())
            QProcess::startDetached(QStringLiteral("xdg-open"), {QFileInfo(current()->document_().path()).absolutePath()});
    });
    more->setMenu(menu);
    more->setPopupMode(QToolButton::InstantPopup);
    static_cast<QVBoxLayout *>(centralWidget()->layout())->insertWidget(0, header);
}

void MainWindow::buildStatus()
{
    auto *bar = statusBar();
    bar->setSizeGripEnabled(false);
    m_message = new QLabel(bar);
    bar->addWidget(m_message, 1);
    m_position = statusButton(bar);
    m_language = statusButton(bar);
    m_indent = statusButton(bar);
    m_endings = statusButton(bar);
    auto *utf8 = new QLabel(QStringLiteral("UTF-8"), bar);
    utf8->setContentsMargins(8, 0, 10, 0);
    for (QToolButton *b : {m_position, m_language, m_indent, m_endings})
        bar->addPermanentWidget(b);
    bar->addPermanentWidget(utf8);
    connect(m_position, &QToolButton::clicked, this, &MainWindow::goToLineDialog);
    connect(m_language, &QToolButton::clicked, this, &MainWindow::languageMenu);
    connect(m_indent, &QToolButton::clicked, this, &MainWindow::indentMenu);
    connect(m_endings, &QToolButton::clicked, this, &MainWindow::endingsMenu);
}

EditorView *MainWindow::viewAt(int index) const
{
    return qobject_cast<EditorView *>(m_stack->widget(index));
}

int MainWindow::indexOf(EditorView *view) const
{
    return m_stack->indexOf(view);
}

EditorView *MainWindow::current() const
{
    return viewAt(m_tabs->currentIndex());
}

int MainWindow::count() const
{
    return m_stack->count();
}

EditorView *MainWindow::newTab()
{
    auto *view = new EditorView(m_repo, m_stack);
    view->setLineWrapMode(m_wrap ? QPlainTextEdit::WidgetWidth : QPlainTextEdit::NoWrap);
    connect(view->document(), &QTextDocument::modificationChanged, this, [this, view] { updateTab(view); });
    connect(view, &EditorView::cursorMoved, this, &MainWindow::updateStatus);
    const int i = m_stack->addWidget(view);
    m_tabs->insertTab(i, view->title());
    m_tabs->setCurrentIndex(i);
    view->setFocus();
    return view;
}

EditorView *MainWindow::openFile(const QString &path, int line)
{
    const QString abs = QFileInfo(path).absoluteFilePath();
    for (int i = 0; i < count(); ++i) {
        if (viewAt(i)->document_().path() == abs) {
            m_tabs->setCurrentIndex(i);
            if (line > 0)
                viewAt(i)->goToLine(line);
            return viewAt(i);
        }
    }
    Document doc;
    switch (doc.load(abs)) {
    case Document::Load::Ok:
        break;
    case Document::Load::Missing: {
        // A path that doesn't exist yet: a new file that saves there
        EditorView *v = current() && current()->document_().path().isEmpty() && !current()->isModified() ? current() : newTab();
        v->document_() = Document();
        v->setProperty("newPath", abs);
        m_tabs->setTabText(indexOf(v), QFileInfo(abs).fileName());
        v->pickDefinitionFor(abs);
        showMessage(QStringLiteral("%1 is a new file: it's created when you save.").arg(QFileInfo(abs).fileName()));
        return v;
    }
    case Document::Load::TooBig:
        showMessage(QStringLiteral("%1 is over 64 MB, too big to open here.").arg(QFileInfo(abs).fileName()), true);
        return nullptr;
    case Document::Load::Binary:
        showMessage(QStringLiteral("%1 isn't a text file.").arg(QFileInfo(abs).fileName()), true);
        return nullptr;
    case Document::Load::NotUtf8:
        showMessage(QStringLiteral("%1 isn't UTF-8 text, so it can't be opened safely.").arg(QFileInfo(abs).fileName()), true);
        return nullptr;
    case Document::Load::Unreadable:
        showMessage(QStringLiteral("Couldn't open %1: %2").arg(QFileInfo(abs).fileName(), doc.lastError()), true);
        return nullptr;
    }
    // The empty first tab is replaced rather than kept beside the file
    EditorView *v = current() && current()->document_().path().isEmpty() && !current()->isModified()
                            && current()->property("newPath").toString().isEmpty()
                        ? current()
                        : newTab();
    v->document_() = doc;
    v->setPlainText(doc.text());
    v->setUnmodified();
    v->pickDefinitionFor(abs);
    m_tabs->setTabText(indexOf(v), v->title());
    m_tabs->setTabToolTip(indexOf(v), abs);
    m_watcher->addPath(abs);
    if (line > 0)
        v->goToLine(line);
    m_closed.removeAll(abs);
    if (!QFileInfo(abs).isWritable())
        showMessage(QStringLiteral("You can read this file; saving it asks for your password."));
    updateStatus();
    saveSession();
    return v;
}

bool MainWindow::save(EditorView *view, bool askPath)
{
    Document &doc = view->document_();
    QString path = doc.path().isEmpty() ? view->property("newPath").toString() : doc.path();
    if (path.isEmpty() || askPath) {
        path = QFileDialog::getSaveFileName(this, QStringLiteral("Save as"), path.isEmpty() ? QDir::homePath() : path);
        if (path.isEmpty())
            return false;
    }
    m_watcher->removePath(doc.path());  // our own save isn't a change on disk
    const auto result = doc.save(view->toPlainText(), path);
    if (result == Document::Save::NeedsAdmin) {
        if (doc.path().isEmpty() || QFileInfo(path).absoluteFilePath() != doc.path()) {
            showMessage(QStringLiteral("You can't save in that folder. Pick another one."), true);
            return false;
        }
        if (QMessageBox::question(this, QStringLiteral("Save as administrator?"),
                                  QStringLiteral("%1 belongs to the system. Save it with your password?")
                                      .arg(QFileInfo(path).fileName()))
            != QMessageBox::Yes)
            return false;
        QString error;
        if (!doc.saveAsAdmin(view->toPlainText(), &error)) {
            showMessage(QStringLiteral("Not saved: %1").arg(error), true);
            m_watcher->addPath(doc.path());
            return false;
        }
    } else if (result == Document::Save::Failed) {
        showMessage(QStringLiteral("Couldn't save: %1").arg(doc.lastError()), true);
        m_watcher->addPath(doc.path());
        return false;
    }
    view->setProperty("newPath", QVariant());
    view->setUnmodified();
    if (!view->definition().isValid())
        view->pickDefinitionFor(doc.path());
    m_watcher->addPath(doc.path());
    m_tabs->setTabText(indexOf(view), view->title());
    m_tabs->setTabToolTip(indexOf(view), doc.path());
    showMessage(QStringLiteral("Saved %1").arg(view->title()));
    updateStatus();
    saveSession();
    return true;
}

bool MainWindow::confirmClose(EditorView *view)
{
    if (!view->isModified())
        return true;
    m_tabs->setCurrentIndex(indexOf(view));
    QMessageBox box(QMessageBox::Question, QStringLiteral("Save changes?"),
                    QStringLiteral("%1 has changes you haven't saved.").arg(view->title()), QMessageBox::NoButton, this);
    auto *saveB = box.addButton(QStringLiteral("Save"), QMessageBox::AcceptRole);
    auto *discard = box.addButton(QStringLiteral("Don't save"), QMessageBox::DestructiveRole);
    box.addButton(QMessageBox::Cancel);
    box.setDefaultButton(saveB);
    box.exec();
    if (box.clickedButton() == saveB)
        return save(view);
    return box.clickedButton() == discard;
}

bool MainWindow::closeTab(int index)
{
    EditorView *view = viewAt(index);
    if (!view || !confirmClose(view))
        return false;
    if (!view->document_().path().isEmpty()) {
        m_closed.append(view->document_().path());
        m_watcher->removePath(view->document_().path());
    }
    m_tabs->removeTab(index);
    m_stack->removeWidget(view);
    view->deleteLater();
    if (count() == 0)
        newTab();
    saveSession();
    return true;
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    for (int i = 0; i < count(); ++i) {
        if (!confirmClose(viewAt(i))) {
            event->ignore();
            return;
        }
    }
    saveSession();
    event->accept();
}

void MainWindow::changeEvent(QEvent *event)
{
    QMainWindow::changeEvent(event);
    // Back to the window: a file changed while we were away shows its banner now
    if (event->type() == QEvent::ActivationChange && isActiveWindow() && current())
        checkDisk(current());
}

void MainWindow::checkDisk(EditorView *view)
{
    if (!view->document_().changedOnDisk() || view != current())
        return;
    if (!QFileInfo::exists(view->document_().path())) {
        m_bannerText->setText(QStringLiteral("%1 was deleted or moved. Save to put it back.").arg(view->title()));
        m_banner->show();
        return;
    }
    if (!view->isModified()) {  // nothing of ours to lose: just follow the file
        const int line = view->textCursor().blockNumber() + 1;
        if (view->document_().load(view->document_().path()) == Document::Load::Ok) {
            view->setPlainText(view->document_().text());
            view->setUnmodified();
            view->goToLine(line);
            showMessage(QStringLiteral("%1 changed on disk and was reloaded.").arg(view->title()));
        }
        return;
    }
    m_bannerText->setText(QStringLiteral("%1 changed on disk, and you have changes here too.").arg(view->title()));
    m_banner->show();
}

void MainWindow::tabChanged()
{
    m_stack->setCurrentIndex(m_tabs->currentIndex());
    m_find->setView(current());
    m_banner->hide();
    if (current()) {
        current()->setFocus();
        setWindowTitle(current()->title() + QStringLiteral(" — DeckOS Editor"));
        checkDisk(current());
    }
    updateStatus();
}

void MainWindow::updateTab(EditorView *view)
{
    const int i = indexOf(view);
    if (i < 0)
        return;
    // A dot before the name for unsaved changes (the close button stays where it is)
    m_tabs->setTabText(i, (view->isModified() ? QStringLiteral("● ") : QString()) + view->title());
    if (view == current())
        setWindowTitle((view->isModified() ? QStringLiteral("● ") : QString()) + view->title() + QStringLiteral(" — DeckOS Editor"));
}

void MainWindow::updateStatus()
{
    EditorView *v = current();
    if (!v)
        return;
    const QTextCursor c = v->textCursor();
    const int selected = c.selectedText().size();
    m_position->setText(QStringLiteral("Line %1, column %2").arg(c.blockNumber() + 1).arg(c.positionInBlock() + 1)
                        + (selected ? QStringLiteral(" · %1 selected").arg(selected) : QString()));
    m_language->setText(v->definition().isValid() && v->definition().name() != QLatin1String("None")
                            ? v->definition().translatedName()
                            : QStringLiteral("Plain text"));
    m_indent->setText(v->indentWithTabs() ? QStringLiteral("Tabs") : QStringLiteral("Spaces: %1").arg(v->indentWidth()));
    m_endings->setText(v->document_().crlf() ? QStringLiteral("CRLF (Windows)") : QStringLiteral("LF"));
}

void MainWindow::showMessage(const QString &text, bool warn)
{
    m_message->setText(text);
    m_message->setStyleSheet(warn ? QStringLiteral("color: #FF6B6B; padding-left: 10px;") : QStringLiteral("padding-left: 10px;"));
    QTimer::singleShot(warn ? 8000 : 4000, m_message, [label = m_message, text] {
        if (label->text() == text)
            label->clear();
    });
}

void MainWindow::openDialog()
{
    const QString dir = current() && !current()->document_().path().isEmpty()
                            ? QFileInfo(current()->document_().path()).absolutePath()
                            : QDir::homePath();
    for (const QString &f : QFileDialog::getOpenFileNames(this, QStringLiteral("Open"), dir))
        openFile(f);
}

void MainWindow::goToLineDialog()
{
    EditorView *v = current();
    if (!v)
        return;
    bool ok = false;
    const int line = QInputDialog::getInt(this, QStringLiteral("Go to line"),
                                          QStringLiteral("Line (1–%1)").arg(v->blockCount()),
                                          v->textCursor().blockNumber() + 1, 1, v->blockCount(), 1, &ok);
    if (ok)
        v->goToLine(line);
}

void MainWindow::languageMenu()
{
    EditorView *v = current();
    if (!v)
        return;
    QMenu menu(this);
    menu.addAction(QStringLiteral("Plain text"), this, [this, v] {
        v->setDefinition({});
        updateStatus();
    });
    // The everyday ones first, then every language by section
    static const QStringList common = {QStringLiteral("Bash"), QStringLiteral("C++"), QStringLiteral("CMake"),
                                       QStringLiteral("CSS"), QStringLiteral("HTML"), QStringLiteral("INI Files"),
                                       QStringLiteral("JavaScript"), QStringLiteral("JSON"), QStringLiteral("Markdown"),
                                       QStringLiteral("Python"), QStringLiteral("QML"), QStringLiteral("Rust"),
                                       QStringLiteral("TOML"), QStringLiteral("YAML")};
    for (const QString &name : common) {
        const auto def = m_repo->definitionForName(name);
        if (def.isValid())
            menu.addAction(def.translatedName(), this, [this, v, def] {
                v->setDefinition(def);
                updateStatus();
            });
    }
    menu.addSeparator();
    QHash<QString, QMenu *> sections;
    for (const auto &def : m_repo->definitions()) {
        if (def.isHidden())
            continue;
        QMenu *&sub = sections[def.translatedSection()];
        if (!sub)
            sub = menu.addMenu(def.translatedSection());
        sub->addAction(def.translatedName(), this, [this, v, def] {
            v->setDefinition(def);
            updateStatus();
        });
    }
    menu.exec(m_language->mapToGlobal(QPoint(0, -menu.sizeHint().height())));
}

void MainWindow::indentMenu()
{
    EditorView *v = current();
    if (!v)
        return;
    QMenu menu(this);
    for (int n : {2, 4, 8})
        menu.addAction(QStringLiteral("Spaces: %1").arg(n), this, [this, v, n] {
            v->setIndent(n, false);
            updateStatus();
        });
    menu.addAction(QStringLiteral("Tabs"), this, [this, v] {
        v->setIndent(v->indentWidth(), true);
        updateStatus();
    });
    menu.exec(m_indent->mapToGlobal(QPoint(0, -menu.sizeHint().height())));
}

void MainWindow::endingsMenu()
{
    EditorView *v = current();
    if (!v)
        return;
    QMenu menu(this);
    menu.addAction(QStringLiteral("LF (Linux and macOS)"), this, [this, v] {
        if (v->document_().crlf()) {
            v->document_().setCrlf(false);
            v->document()->setModified(true);
        }
        updateStatus();
    });
    menu.addAction(QStringLiteral("CRLF (Windows)"), this, [this, v] {
        if (!v->document_().crlf()) {
            v->document_().setCrlf(true);
            v->document()->setModified(true);
        }
        updateStatus();
    });
    menu.exec(m_endings->mapToGlobal(QPoint(0, -menu.sizeHint().height())));
}

void MainWindow::saveSession() const
{
    QStringList files;
    for (int i = 0; i < count(); ++i)
        if (!viewAt(i)->document_().path().isEmpty())
            files << viewAt(i)->document_().path();
    KConfigGroup g = sessionGroup();
    g.writeEntry("Files", files);
    g.writeEntry("Current", current() ? current()->document_().path() : QString());
    g.sync();
}

void MainWindow::restoreSession()
{
    const KConfigGroup g = sessionGroup();
    for (const QString &f : g.readEntry("Files", QStringList()))
        if (QFileInfo::exists(f))
            openFile(f);
    const QString cur = g.readEntry("Current", QString());
    for (int i = 0; i < count(); ++i)
        if (viewAt(i)->document_().path() == cur)
            m_tabs->setCurrentIndex(i);
}

void MainWindow::dragEnterEvent(QDragEnterEvent *event)
{
    if (event->mimeData()->hasUrls())
        event->acceptProposedAction();
}

void MainWindow::dropEvent(QDropEvent *event)
{
    for (const QUrl &u : event->mimeData()->urls())
        if (u.isLocalFile())
            openFile(u.toLocalFile());
}
