// A DeckOS Editor window: the tab row with New/Open/Save, the open files, find and replace, and a
// status line (position, language, indentation, line endings) whose parts are menus.
#pragma once

#include <functional>
#include <QMainWindow>
#include <QStringList>

class EditorView;
class FindBar;
class QFileSystemWatcher;
class QLabel;
class QStackedWidget;
class QTabBar;
class QToolButton;

namespace KSyntaxHighlighting {
class Repository;
}

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(KSyntaxHighlighting::Repository *repo, bool restore = true);

    // Opens `path` in a tab (or switches to it), at `line` if given. Returns the tab's view.
    EditorView *openFile(const QString &path, int line = 0);
    EditorView *newTab();
    EditorView *current() const;
    int count() const;
    bool save(EditorView *view, bool askPath = false);
    // For the demo: the window as it would look with a message showing
    void showMessage(const QString &text, bool warn = false);

protected:
    void closeEvent(QCloseEvent *event) override;
    void changeEvent(QEvent *event) override;
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dropEvent(QDropEvent *event) override;

private:
    void addShortcut(const QKeySequence &keys, std::function<void()> fn);
    void buildHeader();
    void buildStatus();
    bool closeTab(int index);
    bool confirmClose(EditorView *view);
    void tabChanged();
    void updateTab(EditorView *view);
    void updateStatus();
    void checkDisk(EditorView *view);
    void openDialog();
    void goToLineDialog();
    void languageMenu();
    void indentMenu();
    void endingsMenu();
    void saveSession() const;
    void restoreSession();
    EditorView *viewAt(int index) const;
    int indexOf(EditorView *view) const;

    KSyntaxHighlighting::Repository *m_repo;
    QTabBar *m_tabs;
    QStackedWidget *m_stack;
    FindBar *m_find;
    QWidget *m_banner;
    QLabel *m_bannerText;
    QFileSystemWatcher *m_watcher;
    QToolButton *m_position;
    QToolButton *m_language;
    QToolButton *m_indent;
    QToolButton *m_endings;
    QLabel *m_message;
    QStringList m_closed;  // for Ctrl+Shift+T
    bool m_wrap = false;
};
