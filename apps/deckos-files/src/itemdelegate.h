// Paints file items for all three views with QPainter directly (no style sheets, no per-item
// widgets) and hosts the inline rename editor.
#pragma once

#include <QCache>
#include <QStyledItemDelegate>

class ItemDelegate : public QStyledItemDelegate
{
    Q_OBJECT
public:
    enum Mode { Grid, List, Details };

    explicit ItemDelegate(QObject *parent = nullptr);

    void setMode(Mode mode, int iconSize);
    Mode mode() const { return m_mode; }
    int iconSize() const { return m_iconSize; }
    QSize cellSize() const;
    QSize naturalCellSize() const;  // before the grid stretches cells to fill the row
    void setGridWidth(int width) { m_gridWidth = width; }

    void paint(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const override;
    QSize sizeHint(const QStyleOptionViewItem &option, const QModelIndex &index) const override;

    QWidget *createEditor(QWidget *parent, const QStyleOptionViewItem &option, const QModelIndex &index) const override;
    void setEditorData(QWidget *editor, const QModelIndex &index) const override;
    void setModelData(QWidget *editor, QAbstractItemModel *model, const QModelIndex &index) const override;
    void updateEditorGeometry(QWidget *editor, const QStyleOptionViewItem &option, const QModelIndex &index) const override;

private:
    void paintGrid(QPainter *p, const QStyleOptionViewItem &opt, const QModelIndex &index) const;
    void paintRow(QPainter *p, const QStyleOptionViewItem &opt, const QModelIndex &index) const;
    void paintIcon(QPainter *p, const QRect &box, const QModelIndex &index, bool selected) const;
    QStringList wrapped(const QString &text, const QFont &font, int width) const;

    Mode m_mode = Grid;
    int m_iconSize = 64;
    int m_gridWidth = 0;
    mutable QCache<QString, QStringList> m_wrapCache;
};
