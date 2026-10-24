// A DeckOS Terminal window: the tab row (tabs named after their project, the new-tab button, the
// workload mode strip) over the tabs' pages.
#pragma once

#include <functional>
#include <QMainWindow>
#include <QStringList>

class ModeWatch;
class QAction;
class QStackedWidget;
class QTabBar;
class QToolButton;
class TabPage;
class TerminalPane;

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    MainWindow(ModeWatch *modes, const QString &dir, const QStringList &command = {}, bool hold = false);

    TabPage *currentPage() const;
    TabPage *openTab(const QString &dir, const QStringList &command = {});

protected:
    void closeEvent(QCloseEvent *event) override;

private:
    void addShortcut(const QKeySequence &keys, std::function<void()> fn, QAction **out = nullptr);
    void addShortcuts();
    void closePage(TabPage *page);
    void updateTab(TabPage *page);
    void updateMode();
    void pageChanged();
    TerminalPane *pane() const;

    ModeWatch *m_modes;
    QTabBar *m_tabs;
    QStackedWidget *m_stack;
    QToolButton *m_modeChip;
    QList<QAction *> m_splitNav;  // Alt+arrows: only on while a tab is split, so programs keep them otherwise
};
