// DeckOS Files: copy/paste and drag-and-drop through the real window, actions and KIO, offscreen.
// Copies a.txt from src/ to dst/ three ways (Copy + Paste actions, Cut + Paste, a drop onto the
// view) and checks the files on disk. Run: QT_QPA_PLATFORM=offscreen ./clipboard_test
#include "folderpane.h"
#include "foldermodel.h"
#include "folderview.h"
#include "mainwindow.h"

#include <QAbstractItemView>
#include <QAction>
#include <QApplication>
#include <QClipboard>
#include <QDir>
#include <QDropEvent>
#include <QElapsedTimer>
#include <QFile>
#include <QMimeData>
#include <QTemporaryDir>
#include <QTimer>

#include <KUrlMimeData>

namespace {

int failures = 0;

void check(bool ok, const char *what)
{
    fprintf(stderr, "%s %s\n", ok ? "PASS" : "FAIL", what);
    failures += ok ? 0 : 1;
}

// Spin the event loop until cond() holds or ms pass (KIO jobs and listings are asynchronous).
bool waitFor(const std::function<bool()> &cond, int ms = 8000)
{
    QElapsedTimer t;
    t.start();
    while (!cond() && t.elapsed() < ms)
        QApplication::processEvents(QEventLoop::AllEvents, 50);
    return cond();
}

QAction *action(QWidget *w, const QString &text)
{
    for (QAction *a : w->actions())
        if (a->text() == text)
            return a;
    return nullptr;
}

void touch(const QString &path)
{
    QFile f(path);
    f.open(QIODevice::WriteOnly);
    f.write("deckos");
}

} // namespace

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QTemporaryDir tmp;
    const QString src = tmp.path() + QStringLiteral("/src"), dst = tmp.path() + QStringLiteral("/dst");
    QDir().mkpath(src);
    QDir().mkpath(dst);
    touch(src + QStringLiteral("/a.txt"));
    touch(src + QStringLiteral("/b.txt"));
    touch(src + QStringLiteral("/c.txt"));

    MainWindow w({QUrl::fromLocalFile(src)});
    w.resize(1000, 700);
    w.show();
    FolderPane *pane = w.activePane();
    check(waitFor([&] { return pane->model()->rowCount() == 3; }), "the folder lists its 3 files");

    // 1. Copy, then Paste in another folder
    w.selectUrls({QUrl::fromLocalFile(src + QStringLiteral("/a.txt"))});
    check(pane->selectedItems().size() == 1, "selecting a.txt selects one item");
    QAction *copy = action(&w, QStringLiteral("Copy")), *cut = action(&w, QStringLiteral("Cut")),
            *paste = action(&w, QStringLiteral("Paste"));
    check(copy && cut && paste, "Copy, Cut and Paste actions exist");
    if (!copy || !paste)
        return 1;
    copy->trigger();
    const QMimeData *mime = QApplication::clipboard()->mimeData();
    check(mime && mime->hasUrls() && !mime->urls().isEmpty(), "Copy puts the file on the clipboard");
    pane->setUrl(QUrl::fromLocalFile(dst));
    waitFor([&] { return !pane->model()->isLoading(); }, 3000);
    check(paste->isEnabled(), "Paste is enabled");
    paste->trigger();
    check(waitFor([&] { return QFile::exists(dst + QStringLiteral("/a.txt")); }), "Paste copies a.txt into dst");
    check(QFile::exists(src + QStringLiteral("/a.txt")), "the original stays after a copy");

    // 2. Cut, then Paste
    pane->setUrl(QUrl::fromLocalFile(src));
    waitFor([&] { return !pane->model()->isLoading() && pane->model()->rowCount() == 3; });
    w.selectUrls({QUrl::fromLocalFile(src + QStringLiteral("/b.txt"))});
    cut->trigger();
    pane->setUrl(QUrl::fromLocalFile(dst));
    waitFor([&] { return !pane->model()->isLoading(); }, 3000);
    paste->trigger();
    check(waitFor([&] { return QFile::exists(dst + QStringLiteral("/b.txt")) && !QFile::exists(src + QStringLiteral("/b.txt")); }),
          "Cut + Paste moves b.txt");

    // 3. A drop of c.txt onto the dst view (what a drag from another app or pane ends in)
    auto *dropMime = new QMimeData;
    KUrlMimeData::setUrls({QUrl::fromLocalFile(src + QStringLiteral("/c.txt"))}, {}, dropMime);
    QAbstractItemView *visible = nullptr;  // the grid/list or the details view, whichever is showing
    for (QAbstractItemView *v : pane->view()->findChildren<QAbstractItemView *>())
        if (v->isVisible())
            visible = v;
    check(visible != nullptr, "the folder view is showing");
    QWidget *viewport = visible->viewport();
    const QPoint where(viewport->width() - 20, viewport->height() - 20);  // empty space: the folder itself
    // What a real drag delivers: enter, move, then the drop (Ctrl held: copy, no menu)
    QDragEnterEvent enter(where, Qt::CopyAction, dropMime, Qt::LeftButton, Qt::ControlModifier);
    QApplication::sendEvent(viewport, &enter);
    check(enter.isAccepted(), "the view accepts the drag");
    QDragMoveEvent move(where, Qt::CopyAction, dropMime, Qt::LeftButton, Qt::ControlModifier);
    QApplication::sendEvent(viewport, &move);
    check(move.isAccepted(), "the view accepts the drag over empty space");
    QDropEvent drop(where, Qt::CopyAction, dropMime, Qt::LeftButton, Qt::ControlModifier);
    QApplication::sendEvent(viewport, &drop);
    check(waitFor([&] { return QFile::exists(dst + QStringLiteral("/c.txt")); }), "a drop copies c.txt into dst");

    fprintf(stderr, "%d failure(s)\n", failures);
    QTimer::singleShot(0, &app, [&] { app.exit(failures ? 1 : 0); });
    return app.exec();
}
