#include "itemdelegate.h"

#include "foldermodel.h"
#include "style.h"

#include <QAbstractItemView>
#include <QLineEdit>
#include <QMimeDatabase>
#include <QPainter>
#include <QPainterPath>
#include <QTextLayout>

namespace {

constexpr int GridPad = 6;
constexpr int GridTextLines = 2;

QFontMetrics metrics(const QStyleOptionViewItem &opt)
{
    return opt.fontMetrics;
}

} // namespace

ItemDelegate::ItemDelegate(QObject *parent)
    : QStyledItemDelegate(parent)
{
    m_wrapCache.setMaxCost(8000);
}

void ItemDelegate::setMode(Mode mode, int iconSize)
{
    m_mode = mode;
    m_iconSize = iconSize;
    m_wrapCache.clear();
}

QSize ItemDelegate::cellSize() const
{
    QSize s = naturalCellSize();
    if (m_mode == Grid && m_gridWidth > 0)
        s.setWidth(m_gridWidth);
    return s;
}

QSize ItemDelegate::naturalCellSize() const
{
    const QFontMetrics fm(QFont{});
    switch (m_mode) {
    case Grid: {
        const int w = qMax(m_iconSize + 2 * GridPad + 24, 96);
        return {w, GridPad + m_iconSize + 6 + GridTextLines * fm.height() + GridPad + 2};
    }
    case List:
        return {qMax(220, m_iconSize * 10), qMax(m_iconSize, fm.height()) + 8};
    case Details:
        return {0, qMax(m_iconSize, fm.height()) + 10};
    }
    return {};
}

QSize ItemDelegate::sizeHint(const QStyleOptionViewItem &, const QModelIndex &) const
{
    return cellSize();
}

void ItemDelegate::paint(QPainter *p, const QStyleOptionViewItem &option, const QModelIndex &index) const
{
    p->save();
    p->setRenderHint(QPainter::Antialiasing);
    p->setRenderHint(QPainter::SmoothPixmapTransform);
    const KFileItem item = index.data(FolderModel::FileItemRole).value<KFileItem>();
    // Cut items and hidden files are drawn faded, like Dolphin.
    if (index.data(FolderModel::CutRole).toBool())
        p->setOpacity(0.45);
    else if (index.column() == FolderModel::NameColumn && item.isHidden())
        p->setOpacity(0.6);
    if (m_mode == Grid)
        paintGrid(p, option, index);
    else
        paintRow(p, option, index);
    p->restore();
}

void ItemDelegate::paintIcon(QPainter *p, const QRect &box, const QModelIndex &index, bool selected) const
{
    const QPixmap thumb = index.data(FolderModel::ThumbnailRole).value<QPixmap>();
    if (!thumb.isNull()) {
        QSizeF s = thumb.deviceIndependentSize();
        s.scale(box.size(), Qt::KeepAspectRatio);
        const QRectF r(box.x() + (box.width() - s.width()) / 2.0, box.y() + (box.height() - s.height()) / 2.0, s.width(), s.height());
        p->drawPixmap(r, thumb, QRectF(thumb.rect()));
        if (box.width() >= 48) {
            p->setPen(QPen(selected ? Style::accent() : Style::Border, 1));
            p->setBrush(Qt::NoBrush);
            p->drawRect(r.adjusted(-0.5, -0.5, 0.5, 0.5));
        }
        return;
    }
    const QIcon icon = index.data(Qt::DecorationRole).value<QIcon>();
    icon.paint(p, box, Qt::AlignCenter, QIcon::Normal);
}

void ItemDelegate::paintGrid(QPainter *p, const QStyleOptionViewItem &opt, const QModelIndex &index) const
{
    const QRect cell = opt.rect.adjusted(2, 2, -2, -2);
    const bool selected = opt.state & QStyle::State_Selected;
    const bool hover = opt.state & QStyle::State_MouseOver;
    if (selected || hover) {
        p->setPen(selected ? QPen(Style::accent(), 1) : Qt::NoPen);
        p->setBrush(selected ? Style::selectionFill() : Style::hoverFill());
        p->drawRoundedRect(QRectF(cell).adjusted(0.5, 0.5, -0.5, -0.5), Style::Radius, Style::Radius);
    }
    if (opt.state & QStyle::State_HasFocus && !selected) {
        p->setPen(QPen(Style::Border, 1));
        p->setBrush(Qt::NoBrush);
        p->drawRoundedRect(QRectF(cell).adjusted(0.5, 0.5, -0.5, -0.5), Style::Radius, Style::Radius);
    }

    const QRect iconBox(cell.x() + (cell.width() - m_iconSize) / 2, cell.y() + GridPad, m_iconSize, m_iconSize);
    paintIcon(p, iconBox, index, selected);

    const QFontMetrics fm = metrics(opt);
    const QRect textRect(cell.x() + 4, iconBox.bottom() + 6, cell.width() - 8, GridTextLines * fm.height());
    const QStringList lines = wrapped(index.data(Qt::DisplayRole).toString(), opt.font, textRect.width());
    p->setPen(Style::Text);
    p->setFont(opt.font);
    int y = textRect.y();
    for (const QString &line : lines) {
        p->drawText(QRect(textRect.x(), y, textRect.width(), fm.height()), Qt::AlignHCenter | Qt::AlignVCenter, line);
        y += fm.height();
    }
}

void ItemDelegate::paintRow(QPainter *p, const QStyleOptionViewItem &opt, const QModelIndex &index) const
{
    const bool selected = opt.state & QStyle::State_Selected;
    const QFontMetrics fm = metrics(opt);
    QRect r = opt.rect;

    if (m_mode == List) {
        // Compact mode paints its own row background; details rows are painted by the view.
        const bool hover = opt.state & QStyle::State_MouseOver;
        if (selected || hover) {
            p->setPen(selected ? QPen(Style::accent(), 1) : Qt::NoPen);
            p->setBrush(selected ? Style::selectionFill() : Style::hoverFill());
            p->drawRoundedRect(QRectF(r).adjusted(2.5, 1.5, -2.5, -1.5), 6, 6);
        }
    }

    p->setFont(opt.font);
    if (index.column() == FolderModel::NameColumn) {
        const int pad = m_mode == Details ? 10 : 8;
        const QRect iconBox(r.x() + pad, r.y() + (r.height() - m_iconSize) / 2, m_iconSize, m_iconSize);
        paintIcon(p, iconBox, index, selected);
        const QRect textRect(iconBox.right() + 9, r.y(), r.right() - iconBox.right() - 15, r.height());
        p->setPen(Style::Text);
        p->drawText(textRect, Qt::AlignLeft | Qt::AlignVCenter, fm.elidedText(index.data().toString(), Qt::ElideMiddle, textRect.width()));
        return;
    }
    const QString text = index.data().toString();
    if (text.isEmpty())
        return;
    const auto align = Qt::Alignment(index.data(Qt::TextAlignmentRole).toInt());
    const QRect textRect = r.adjusted(10, 0, -12, 0);
    p->setPen(selected ? Style::Text : Style::Subtext);
    p->drawText(textRect, align, fm.elidedText(text, Qt::ElideRight, textRect.width()));
}

QStringList ItemDelegate::wrapped(const QString &text, const QFont &font, int width) const
{
    const QFontMetrics fm(font);
    const QString key = QString::number(width) + QLatin1Char('|') + text;
    if (const QStringList *hit = m_wrapCache.object(key))
        return *hit;
    QStringList lines;
    if (fm.horizontalAdvance(text) <= width) {
        lines << text;
    } else {
        QTextLayout layout(text, font);
        QTextOption option;
        option.setWrapMode(QTextOption::WrapAtWordBoundaryOrAnywhere);
        layout.setTextOption(option);
        layout.beginLayout();
        QTextLine line = layout.createLine();
        line.setLineWidth(width);
        int firstLen = qMax(1, line.textLength());
        layout.endLayout();
        // A break mid-word (IMG_2026052 / 0.jpg) moves back to a _ - . or space in the line's second half.
        if (firstLen < text.size() && !text.at(firstLen - 1).isSpace() && !text.at(firstLen).isSpace()) {
            for (int i = firstLen - 1; i > firstLen / 2; --i) {
                if (QStringLiteral("_-. ").contains(text.at(i))) {
                    firstLen = text.at(i) == QLatin1Char('.') ? i : i + 1;
                    break;
                }
            }
        }
        lines << text.left(firstLen).trimmed();
        // The second line keeps the end of the name (usually the extension) visible.
        lines << fm.elidedText(text.mid(firstLen), Qt::ElideMiddle, width);
    }
    m_wrapCache.insert(key, new QStringList(lines));
    return lines;
}

QWidget *ItemDelegate::createEditor(QWidget *parent, const QStyleOptionViewItem &, const QModelIndex &) const
{
    auto *edit = new QLineEdit(parent);
    edit->setFrame(false);
    edit->setStyleSheet(QStringLiteral("QLineEdit { background: #171A21; color: #E8EAF0; border: 1px solid %1; border-radius: 6px; padding: 2px 5px; }")
                            .arg(Style::accent().name()));
    if (m_mode == Grid)
        edit->setAlignment(Qt::AlignHCenter);
    return edit;
}

void ItemDelegate::setEditorData(QWidget *editor, const QModelIndex &index) const
{
    auto *edit = static_cast<QLineEdit *>(editor);
    const QString name = index.data(Qt::EditRole).toString();
    edit->setText(name);
    // Select the name without its extension (".tar.gz" counts as one), like Dolphin.
    const bool dir = index.data(FolderModel::IsDirRole).toBool();
    const QString suffix = dir ? QString() : QMimeDatabase().suffixForFileName(name);
    int len = name.size();
    if (!suffix.isEmpty())
        len -= suffix.size() + 1;
    else if (!dir && name.lastIndexOf(QLatin1Char('.')) > 0)
        len = name.lastIndexOf(QLatin1Char('.'));
    edit->setSelection(0, len);
}

void ItemDelegate::setModelData(QWidget *editor, QAbstractItemModel *model, const QModelIndex &index) const
{
    model->setData(index, static_cast<QLineEdit *>(editor)->text(), Qt::EditRole);
}

void ItemDelegate::updateEditorGeometry(QWidget *editor, const QStyleOptionViewItem &opt, const QModelIndex &) const
{
    const QRect r = opt.rect;
    const int h = editor->sizeHint().height();
    if (m_mode == Grid) {
        const int top = r.y() + 2 + GridPad + m_iconSize + 4;
        editor->setGeometry(r.x() + 4, top, r.width() - 8, h);
    } else {
        const int pad = m_mode == Details ? 10 : 8;
        const int left = r.x() + pad + m_iconSize + 5;
        editor->setGeometry(left, r.y() + (r.height() - h) / 2, r.right() - left - 4, h);
    }
}
