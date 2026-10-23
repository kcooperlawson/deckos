// File operations as KIO jobs: undo, progress (Plasma notifications) and conflict dialogs come
// from KIO itself.
#pragma once

#include <KFileItem>
#include <QUrl>

class KJob;
class QDropEvent;
class QWidget;

namespace Ops {
void open(const KFileItemList &items, QWidget *window);
void copy(const KFileItemList &items, bool cut);
void paste(const QUrl &dest, QWidget *window);
bool canPaste();
void trash(const QList<QUrl> &urls, QWidget *window);
void del(const QList<QUrl> &urls, QWidget *window);
void restore(const QList<QUrl> &urls, QWidget *window);
void emptyTrash(QWidget *window);
void rename(const KFileItem &item, const QString &newName, QWidget *window);
void batchRename(const KFileItemList &items, QWidget *window);
void drop(QDropEvent *event, const QUrl &dest, QWidget *window);
void openTerminal(const QUrl &dir, QWidget *window);
void properties(const KFileItemList &items, QWidget *window);
void undo(QWidget *window);
QList<QUrl> urls(const KFileItemList &items);
}
