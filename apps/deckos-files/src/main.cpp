#include "foldermodel.h"
#include "folderpane.h"
#include "mainwindow.h"
#include "style.h"

#include <functional>
#include <memory>
#include <QApplication>
#include <QCommandLineParser>
#include <QDBusConnection>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QImage>
#include <QLinearGradient>
#include <QPainter>
#include <QStyleFactory>
#include <QTimer>

#include <KAboutData>
#include <KDBusService>

namespace {

QElapsedTimer startClock;

// --demo: a throwaway folder tree with photos (for thumbnails), documents and one folder of
// 20,000 files for the speed check. Real files, so the real KIO code paths run.
QString makeDemoTree()
{
    const QString root = QDir::tempPath() + QStringLiteral("/deckos-files-demo");
    QDir(root).removeRecursively();
    QDir d;
    for (const char *sub : {"Documents", "Downloads", "Music", "Pictures/2026 Summer", "Projects/deckos", "Games", "Videos", "Many files"})
        d.mkpath(root + QLatin1Char('/') + QString::fromLatin1(sub));
    auto touch = [](const QString &path, const QByteArray &data = QByteArray(" ")) {
        QFile f(path);
        if (f.open(QIODevice::WriteOnly))
            f.write(data);
    };
    const QStringList docs = {QStringLiteral("Budget 2026.ods"), QStringLiteral("Report final.pdf"), QStringLiteral("Notes.md"),
                              QStringLiteral("Letter to landlord.odt"), QStringLiteral("passport-scan.png"), QStringLiteral("todo.txt"),
                              QStringLiteral("Quarterly report.docx"), QStringLiteral("receipts.zip")};
    for (const QString &f : docs)
        touch(root + QStringLiteral("/Documents/") + f, QByteArray(4096 * (f.size() % 7 + 1), 'x'));
    for (const QString &f : {QStringLiteral("deckos-0.3.5-x86_64.iso"), QStringLiteral("setup.sh"), QStringLiteral("wallpaper.jpg")})
        touch(root + QStringLiteral("/Downloads/") + f);
    for (const QString &f : {QStringLiteral("README.md"), QStringLiteral("main.cpp"), QStringLiteral("CMakeLists.txt")})
        touch(root + QStringLiteral("/Projects/deckos/") + f);
    for (int i = 1; i <= 12; ++i)
        touch(root + QStringLiteral("/Music/%1 - Track %1.flac").arg(i, 2, 10, QLatin1Char('0')));
    // Photos: gradients in the DeckOS palette, so thumbnails have something to show.
    const QList<QColor> hues = {QColor(0x4C, 0x8D, 0xFF), QColor(0x7A, 0x5C, 0xFF), QColor(0x3D, 0xD6, 0x8C), QColor(0xF5, 0xB8, 0x4B),
                                QColor(0xFF, 0x6B, 0x6B), QColor(0x2A, 0xC3, 0xDE)};
    for (int i = 0; i < 18; ++i) {
        QImage img(640, 427, QImage::Format_RGB32);
        QPainter p(&img);
        QLinearGradient g(0, 0, 640, 427);
        g.setColorAt(0, hues[i % hues.size()]);
        g.setColorAt(1, hues[(i + 2) % hues.size()].darker(160));
        p.fillRect(img.rect(), g);
        p.setBrush(QColor(255, 255, 255, 60));
        p.setPen(Qt::NoPen);
        p.drawEllipse(QPoint(160 + i * 23 % 300, 140 + i * 17 % 160), 60 + i * 3, 60 + i * 3);
        p.end();
        img.save(root + QStringLiteral("/Pictures/2026 Summer/IMG_2026%1.jpg").arg(510 + i, 4, 10, QLatin1Char('0')), "JPG", 85);
        if (i < 6)
            img.save(root + QStringLiteral("/Pictures/beach-%1.png").arg(i + 1));
    }
    for (int i = 0; i < 20000; ++i)
        touch(root + QStringLiteral("/Many files/file %1.txt").arg(i));
    touch(root + QStringLiteral("/.hidden-config"));
    return root;
}

void shoot(QWidget *w, const QString &dir, const QString &name)
{
    w->grab().save(dir + QLatin1Char('/') + name + QStringLiteral(".png"));
    qInfo("deckos-files screenshot: %s.png", qPrintable(name));
}

// Runs fn once the active pane has finished listing (and gives thumbnails a moment).
void whenListed(MainWindow *w, int settleMs, std::function<void()> fn)
{
    auto *model = w->activePane()->model();
    auto run = [settleMs, fn] { QTimer::singleShot(settleMs, fn); };
    if (!model->isLoading() && model->rowCount() > 0) {
        run();
        return;
    }
    auto conn = std::make_shared<QMetaObject::Connection>();
    *conn = QObject::connect(model, &FolderModel::loadingFinished, w, [conn, run] {
        QObject::disconnect(*conn);
        run();
    });
}

void runScreenshots(MainWindow *w, const QString &root, const QString &out)
{
    QDir().mkpath(out);
    auto steps = std::make_shared<QList<std::function<void()>>>();
    auto next = std::make_shared<std::function<void()>>();
    *next = [steps, next] {
        if (steps->isEmpty()) {
            QApplication::quit();
            return;
        }
        steps->takeFirst()();
    };
    auto open = [w, next](const QString &path, int settle, std::function<void()> then) {
        w->activePane()->setUrl(QUrl::fromLocalFile(path));
        whenListed(w, settle, [then, next] {
            then();
            (*next)();
        });
    };
    *steps << [=] { open(root + QStringLiteral("/Pictures/2026 Summer"), 2500, [=] { shoot(w, out, QStringLiteral("1-grid-thumbnails")); }); };
    *steps << [=] { open(root, 600, [=] { shoot(w, out, QStringLiteral("2-grid-home")); }); };
    *steps << [=] {
        w->setViewMode(FolderView::Details);
        open(root + QStringLiteral("/Documents"), 600, [=] { shoot(w, out, QStringLiteral("3-details")); });
    };
    *steps << [=] {
        QElapsedTimer t;
        t.start();
        w->setViewMode(FolderView::List);
        open(root + QStringLiteral("/Many files"), 300, [=] {
            qInfo("deckos-files timing: listed %d files in %lld ms", w->activePane()->model()->rowCount(), t.elapsed() - 300);
            shoot(w, out, QStringLiteral("4-list-20000"));
        });
    };
    *steps << [=] {
        w->setViewMode(FolderView::Grid);
        w->toggleSplit();
        w->setPreviewsVisible(true);
        open(root + QStringLiteral("/Pictures"), 2000, [=] {
            w->selectUrls({QUrl::fromLocalFile(root + QStringLiteral("/Pictures/beach-2.png"))});
            QTimer::singleShot(1500, [=] { shoot(w, out, QStringLiteral("5-split-previews")); });
        });
    };
    *steps << [=] {
        w->toggleSplit();
        w->setPreviewsVisible(false);
        w->openTab(QUrl::fromLocalFile(root + QStringLiteral("/Music")));
        w->setViewMode(FolderView::Details);
        whenListed(w, 600, [=] {
            shoot(w, out, QStringLiteral("6-tabs"));
            (*next)();
        });
    };
    *steps << [=] {
        w->activePane()->setUrl(QUrl::fromLocalFile(root));
        whenListed(w, 300, [=] {
            w->search(QStringLiteral("report"));
            QTimer::singleShot(3000, [=] {
                shoot(w, out, QStringLiteral("7-search"));
                (*next)();
            });
        });
    };
    (*next)();
}

} // namespace

int main(int argc, char **argv)
{
    startClock.start();
    QApplication app(argc, argv);
    KAboutData about(QStringLiteral("deckos-files"), QStringLiteral("DeckOS Files"), QStringLiteral(DECKOS_VERSION),
                     QStringLiteral("The DeckOS file manager"), KAboutLicense::MIT);
    about.setOrganizationDomain(QByteArrayLiteral("deckos.org"));
    about.setDesktopFileName(QStringLiteral("org.deckos.files"));
    KAboutData::setApplicationData(about);

    QCommandLineParser parser;
    parser.addPositionalArgument(QStringLiteral("urls"), QStringLiteral("Folders to open"));
    parser.addOption({QStringLiteral("new-window"), QStringLiteral("Open a new window")});
    parser.addOption({QStringLiteral("select"), QStringLiteral("Select the given files in their folder")});
    parser.addOption({QStringLiteral("daemon"), QStringLiteral("Start without a window (D-Bus activation)")});
    parser.addOption({QStringLiteral("demo"), QStringLiteral("Open a generated demo folder tree")});
    parser.addOption({QStringLiteral("screenshot"), QStringLiteral("With --demo: save screenshots to DIR and quit"), QStringLiteral("dir")});
    about.setupCommandLine(&parser);
    parser.process(app);
    about.processCommandLine(&parser);

    const bool demo = parser.isSet(QStringLiteral("demo"));
    if (demo) {
        // Offscreen CI has no Plasma platform theme: pick the DeckOS fonts and icons by hand.
        if (const QString theme = qEnvironmentVariable("DECKOS_ICON_THEME", QStringLiteral("Papirus-Dark")); !theme.isEmpty())
            QIcon::setThemeName(theme);
        QIcon::setFallbackThemeName(QStringLiteral("breeze-dark"));
        QApplication::setFont(QFont(QStringLiteral("Inter"), 10));
        if (QStyleFactory::keys().contains(QStringLiteral("Breeze")))
            QApplication::setStyle(QStringLiteral("Breeze"));
    }
    Style::apply(app);

    auto urlsFrom = [](const QStringList &args, const QString &cwd) {
        QList<QUrl> urls;
        for (const QString &a : args)
            urls << QUrl::fromUserInput(a, cwd, QUrl::AssumeLocalFile);
        return urls;
    };
    auto openWindow = [](const QList<QUrl> &urls, bool select) {
        if (select && !urls.isEmpty()) {
            FileManager1().ShowItems([&] {
                QStringList s;
                for (const QUrl &u : urls)
                    s << u.toString();
                return s;
            }(), QString());
            return;
        }
        auto *w = new MainWindow(urls);
        w->show();
        w->raise();
        w->activateWindow();
    };

    if (demo) {
        const QString root = makeDemoTree();
        auto *w = new MainWindow({QUrl::fromLocalFile(root)});
        w->resize(1400, 860);
        w->show();
        QTimer::singleShot(0, w, [] { qInfo("deckos-files timing: first window in %lld ms", startClock.elapsed()); });
        const QString out = parser.value(QStringLiteral("screenshot"));
        if (!out.isEmpty())
            whenListed(w, 300, [=] { runScreenshots(w, root, out); });
        return app.exec();
    }

    // One process: a second launch opens its window in this one, which is instant.
    KDBusService service(KDBusService::Unique | KDBusService::NoExitOnFailure);
    QObject::connect(&service, &KDBusService::activateRequested, &app, [&](const QStringList &args, const QString &cwd) {
        QCommandLineParser p;
        p.addPositionalArgument(QStringLiteral("urls"), QString());
        p.addOption({QStringLiteral("new-window"), QString()});
        p.addOption({QStringLiteral("select"), QString()});
        p.addOption({QStringLiteral("daemon"), QString()});
        p.parse(args);
        if (!p.isSet(QStringLiteral("daemon")))
            openWindow(urlsFrom(p.positionalArguments(), cwd), p.isSet(QStringLiteral("select")));
    });

    auto *fm1 = new FileManager1(&app);
    QDBusConnection bus = QDBusConnection::sessionBus();
    bus.registerObject(QStringLiteral("/org/freedesktop/FileManager1"), fm1, QDBusConnection::ExportScriptableSlots);
    bus.registerService(QStringLiteral("org.freedesktop.FileManager1"));

    if (parser.isSet(QStringLiteral("daemon")))
        QApplication::setQuitOnLastWindowClosed(false);
    else
        openWindow(urlsFrom(parser.positionalArguments(), QDir::currentPath()), parser.isSet(QStringLiteral("select")));
    return app.exec();
}
