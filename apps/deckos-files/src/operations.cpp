#include "operations.h"

#include "style.h"

#include <QDir>
#include <QApplication>
#include <QClipboard>
#include <QDialog>
#include <QDialogButtonBox>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMimeData>
#include <QMimeDatabase>
#include <QPushButton>
#include <QRadioButton>
#include <QSpinBox>
#include <QVBoxLayout>

#include <KIO/AskUserActionInterface>
#include <KIO/BatchRenameJob>
#include <KIO/CopyJob>
#include <KIO/DeleteOrTrashJob>
#include <KIO/DropJob>
#include <KIO/FileUndoManager>
#include <KIO/JobUiDelegate>
#include <KIO/OpenUrlJob>
#include <KIO/Paste>
#include <KIO/PasteJob>
#include <KIO/RestoreJob>
#include <KJobUiDelegate>
#include <KJobWidgets>
#include <KPropertiesDialog>
#include <KTerminalLauncherJob>
#include <KUrlMimeData>

namespace Ops {

using Iface = KIO::AskUserActionInterface;

void autoErrors(KJob *job)
{
    if (job->uiDelegate())
        job->uiDelegate()->setAutoErrorHandlingEnabled(true);
}

QList<QUrl> urls(const KFileItemList &items)
{
    QList<QUrl> list;
    for (const KFileItem &i : items)
        list << i.url();
    return list;
}

void open(const KFileItemList &items, QWidget *window)
{
    for (const KFileItem &item : items) {
        auto *job = new KIO::OpenUrlJob(item.targetUrl(), item.mimetype());
        job->setUiDelegate(new KIO::JobUiDelegate(KJobUiDelegate::AutoHandlingEnabled, window));
        job->setShowOpenOrExecuteDialog(true);
        job->start();
    }
}

void copy(const KFileItemList &items, bool cut)
{
    QList<QUrl> local;
    for (const KFileItem &i : items)
        local << i.mostLocalUrl();
    auto *mime = new QMimeData;
    KUrlMimeData::setUrls(urls(items), local, mime);
    KIO::setClipboardDataCut(mime, cut);
    QApplication::clipboard()->setMimeData(mime);
}

bool canPaste()
{
    const QMimeData *mime = QApplication::clipboard()->mimeData();
    return mime && KIO::canPasteMimeData(mime);
}

void paste(const QUrl &dest, QWidget *window)
{
    const QMimeData *mime = QApplication::clipboard()->mimeData();
    if (!mime)
        return;
    const bool cut = KIO::isClipboardDataCut(mime);
    KIO::Job *job = KIO::paste(mime, dest);
    KJobWidgets::setWindow(job, window);
    if (cut)
        QApplication::clipboard()->clear();
}

void trash(const QList<QUrl> &list, QWidget *window)
{
    auto *job = new KIO::DeleteOrTrashJob(list, Iface::Trash, Iface::DefaultConfirmation, window);
    job->start();
}

void del(const QList<QUrl> &list, QWidget *window)
{
    auto *job = new KIO::DeleteOrTrashJob(list, Iface::Delete, Iface::DefaultConfirmation, window);
    job->start();
}

void restore(const QList<QUrl> &list, QWidget *window)
{
    KIO::Job *job = KIO::restoreFromTrash(list);
    KJobWidgets::setWindow(job, window);
    autoErrors(job);
}

void emptyTrash(QWidget *window)
{
    auto *job = new KIO::DeleteOrTrashJob({}, Iface::EmptyTrash, Iface::DefaultConfirmation, window);
    job->start();
}

void rename(const KFileItem &item, const QString &newName, QWidget *window)
{
    const QUrl from = item.url();
    QUrl to = from.adjusted(QUrl::RemoveFilename);
    to.setPath(to.path() + newName);
    KIO::Job *job = KIO::moveAs(from, to, KIO::HideProgressInfo);
    KJobWidgets::setWindow(job, window);
    autoErrors(job);
    KIO::FileUndoManager::self()->recordJob(KIO::FileUndoManager::Rename, {from}, to, job);
}

void batchRename(const KFileItemList &items, QWidget *window)
{
    QDialog dlg(window);
    dlg.setWindowTitle(QStringLiteral("Rename %1 items").arg(items.size()));
    dlg.setStyleSheet(Style::chromeQss() + QStringLiteral("QDialog { background: #0F1115; } QListWidget { background: #171A21; border: 1px solid #262B36; border-radius: 8px; color: #E8EAF0; }"));
    auto *lay = new QVBoxLayout(&dlg);
    auto *numbered = new QRadioButton(QStringLiteral("Number them"));
    auto *replace = new QRadioButton(QStringLiteral("Find and replace"));
    numbered->setChecked(true);
    auto *pattern = new QLineEdit(QStringLiteral("Photo #"));
    auto *start = new QSpinBox;
    start->setRange(0, 999999);
    start->setValue(1);
    auto *find = new QLineEdit;
    find->setPlaceholderText(QStringLiteral("Find"));
    auto *with = new QLineEdit;
    with->setPlaceholderText(QStringLiteral("Replace with"));
    auto *hint = new QLabel(QStringLiteral("# is replaced by the number; use ## for 01, 02…"));
    hint->setObjectName(QStringLiteral("sub"));
    auto *preview = new QListWidget;
    for (QWidget *w : {static_cast<QWidget *>(numbered), static_cast<QWidget *>(pattern), static_cast<QWidget *>(start),
                       static_cast<QWidget *>(hint), static_cast<QWidget *>(replace), static_cast<QWidget *>(find),
                       static_cast<QWidget *>(with), static_cast<QWidget *>(preview)})
        lay->addWidget(w);
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Cancel);
    QPushButton *ok = buttons->addButton(QStringLiteral("Rename"), QDialogButtonBox::AcceptRole);
    ok->setObjectName(QStringLiteral("primary"));
    lay->addWidget(buttons);
    QObject::connect(buttons, &QDialogButtonBox::accepted, &dlg, &QDialog::accept);
    QObject::connect(buttons, &QDialogButtonBox::rejected, &dlg, &QDialog::reject);

    auto newName = [&](const KFileItem &item, int i) -> QString {
        if (replace->isChecked()) {
            QString name = item.name();
            return find->text().isEmpty() ? name : name.replace(find->text(), with->text());
        }
        const QString suffix = item.isDir() ? QString() : QMimeDatabase().suffixForFileName(item.name());
        QString p = pattern->text();
        const int hashes = int(p.count(QLatin1Char('#')));
        const QString num = QStringLiteral("%1").arg(start->value() + i, qMax(1, hashes), 10, QLatin1Char('0'));
        const int at = int(p.indexOf(QLatin1Char('#')));
        if (at < 0)
            p += QLatin1Char(' ') + num;
        else
            p.remove(QLatin1Char('#')).insert(at, num);
        if (!suffix.isEmpty())
            p += QLatin1Char('.') + suffix;
        return p;
    };
    auto refresh = [&] {
        preview->clear();
        for (int i = 0; i < items.size() && i < 200; ++i)
            preview->addItem(items[i].name() + QStringLiteral("  →  ") + newName(items[i], i));
    };
    for (QLineEdit *e : {pattern, find, with})
        QObject::connect(e, &QLineEdit::textChanged, &dlg, refresh);
    QObject::connect(start, &QSpinBox::valueChanged, &dlg, refresh);
    QObject::connect(numbered, &QRadioButton::toggled, &dlg, refresh);
    refresh();
    dlg.resize(520, 480);
    if (dlg.exec() != QDialog::Accepted)
        return;
    for (int i = 0; i < items.size(); ++i) {
        const QString name = newName(items[i], i);
        if (name != items[i].name() && !name.isEmpty())
            rename(items[i], name, window);
    }
}

void drop(QDropEvent *event, const QUrl &dest, QWidget *window)
{
    KIO::DropJob *job = KIO::drop(event, dest);
    KJobWidgets::setWindow(job, window);
    autoErrors(job);
}

void openTerminal(const QUrl &dir, QWidget *)
{
    auto *job = new KTerminalLauncherJob(QString());
    job->setWorkingDirectory(dir.isLocalFile() ? dir.toLocalFile() : QDir::homePath());
    job->start();
}

void properties(const KFileItemList &items, QWidget *window)
{
    if (!items.isEmpty())
        KPropertiesDialog::showDialog(items, window, false);
}

void undo(QWidget *window)
{
    KIO::FileUndoManager::self()->uiInterface()->setParentWidget(window);
    KIO::FileUndoManager::self()->undo();
}

} // namespace Ops
