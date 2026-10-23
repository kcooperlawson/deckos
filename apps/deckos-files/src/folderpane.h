// One folder on screen: the path bar (KUrlNavigator, which also keeps the history), the views,
// thumbnails for what's visible, search and the instant filter.
#pragma once

#include <QPointer>
#include <QSet>
#include <QTimer>
#include <QWidget>

#include <KFileItem>

class FolderModel;
class FolderView;
class KFilePlacesModel;
class KUrlNavigator;
class QLabel;
class QLineEdit;
class QMenu;
class QVBoxLayout;
namespace KIO { class PreviewJob; }

class FolderPane : public QWidget
{
    Q_OBJECT
public:
    FolderPane(KFilePlacesModel *places, const QUrl &url, QWidget *parent = nullptr);

    QUrl url() const;
    void setUrl(const QUrl &url);
    FolderModel *model() const { return m_model; }
    FolderView *view() const { return m_view; }
    KUrlNavigator *navigator() const { return m_nav; }
    KFileItemList selectedItems() const;

    void search(const QString &text);
    bool isSearching() const { return !m_searchText.isEmpty(); }
    void showFilter();
    void setActive(bool active);
    void dockNavigator(bool inToolbar);

    void goBack();
    void goForward();
    void goUp();
    void reload();
    void newFolder();
    void openSelected();
    void showContextMenu(const QModelIndex &index, const QPoint &globalPos);
    QString statusText() const;
    QString title() const;

Q_SIGNALS:
    void urlChanged(const QUrl &url);
    void activated();
    void openInNewTab(const QUrl &url);
    void openInNewWindow(const QUrl &url);
    void statusChanged();
    void selectionChanged();
    void zoomRequested(int step);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    void loadPreviews();
    void onActivated(const QModelIndex &index);
    void showMessage(const QString &text);

    FolderModel *m_model;
    FolderView *m_view;
    KUrlNavigator *m_nav;
    QWidget *m_header;
    QVBoxLayout *m_headerLayout;
    QLineEdit *m_filter;
    QLabel *m_message;
    QPointer<KIO::PreviewJob> m_previewJob;
    QSet<QUrl> m_noPreview;
    QString m_searchText;
    QUrl m_searchBase;
    bool m_active = false;
    bool m_split = false;
    QList<QUrl> m_selectAfterLoad;
};
