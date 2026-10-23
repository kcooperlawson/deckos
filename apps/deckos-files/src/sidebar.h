// Places, devices (usage bar, eject), network and trash, from KFilePlacesModel.
#pragma once

#include <QListView>
#include <QUrl>

class KCoreDirLister;
class KFilePlacesModel;

class Sidebar : public QListView
{
    Q_OBJECT
public:
    Sidebar(KFilePlacesModel *places, QWidget *parent = nullptr);
    void setCurrentUrl(const QUrl &url);
    int trashCount() const;

Q_SIGNALS:
    void placeActivated(const QUrl &url);
    void placeActivatedInNewTab(const QUrl &url);

protected:
    void mouseReleaseEvent(QMouseEvent *e) override;
    void contextMenuEvent(QContextMenuEvent *e) override;
    void dragEnterEvent(QDragEnterEvent *e) override;
    void dragMoveEvent(QDragMoveEvent *e) override;
    void dropEvent(QDropEvent *e) override;

private:
    void updateHidden();
    void open(const QModelIndex &index, bool newTab);

    KFilePlacesModel *m_places;
    KCoreDirLister *m_trash;
};
