// The window: toolbar, tabs (each one or two panes in a splitter), sidebar, previews panel and
// status bar, plus every action and its Dolphin-style shortcut. No KXmlGui: it costs start time.
#pragma once

#include <QMainWindow>
#include <QPointer>
#include <QUrl>

#include "folderview.h"

class FolderPane;
class KFilePlacesModel;
class QHBoxLayout;
class QLabel;
class QLineEdit;
class QSlider;
class QSplitter;
class QStackedWidget;
class QTabBar;
class QToolButton;
class Sidebar;
namespace KIO { class PreviewJob; }

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(const QList<QUrl> &urls = {}, QWidget *parent = nullptr);
    ~MainWindow() override;

    static KFilePlacesModel *places();

    FolderPane *activePane() const;
    void openTab(const QUrl &url, bool activate = true);
    void setViewMode(FolderView::Mode mode);
    void toggleSplit();
    void setPreviewsVisible(bool visible);
    void search(const QString &text);
    void selectUrls(const QList<QUrl> &urls);

private:
    struct Tab;
    Tab *currentTab() const;
    Tab *tabOf(FolderPane *pane) const;
    FolderPane *createPane(const QUrl &url);
    void setActivePane(FolderPane *pane);
    void closeTab(int index);
    void syncChrome();
    void dockNavigator();
    void updateStatus();
    void updatePreview();
    void zoom(int step);
    void buildActions();
    void saveSettings();
    QToolButton *toolButton(const QString &icon, const QString &tip, QAction *action = nullptr);

    QTabBar *m_tabBar;
    QStackedWidget *m_stack;
    Sidebar *m_sidebar;
    QWidget *m_previewPanel;
    QLabel *m_previewImage;
    QLabel *m_previewName;
    QLabel *m_previewInfo;
    QPointer<KIO::PreviewJob> m_previewJob;
    QHBoxLayout *m_navSlot;
    QPointer<FolderPane> m_dockedPane;
    QLineEdit *m_search;
    QLabel *m_status;
    QLabel *m_free;
    QSlider *m_zoom;
    QToolButton *m_viewButtons[3];
    QAction *m_backAction, *m_forwardAction, *m_upAction, *m_splitAction, *m_previewAction, *m_sidebarAction,
        *m_hiddenAction, *m_undoAction, *m_pasteAction;
    QList<Tab *> m_tabs;
    QList<QUrl> m_closedTabs;
    FolderView::Mode m_mode = FolderView::Grid;
    int m_iconSizes[3] = {64, 22, 22};
};

// org.freedesktop.FileManager1: "Show in folder" from Firefox, Plasma and other apps.
class FileManager1 : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.freedesktop.FileManager1")
public:
    using QObject::QObject;
public Q_SLOTS:
    Q_SCRIPTABLE void ShowFolders(const QStringList &uris, const QString &startupId);
    Q_SCRIPTABLE void ShowItems(const QStringList &uris, const QString &startupId);
    Q_SCRIPTABLE void ShowItemProperties(const QStringList &uris, const QString &startupId);
};
