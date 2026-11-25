#include "mainwindow.h"
#include "style.h"

#include <QApplication>
#include <QDir>
#include <QFileInfo>
#include <QStyleFactory>
#include <QTimer>
#include <QUrl>

#include <KAboutData>
#include <KDBusService>

namespace {

struct Launch {
    QStringList files;
    QString dest;  // --to DIR, or --here: the first archive's folder
    bool here = false;
    bool demo = false;
    QString screenshot;
};

Launch parseArgs(const QStringList &args, const QString &cwd)
{
    Launch l;
    for (qsizetype i = 1; i < args.size(); ++i) {
        const QString &a = args[i];
        if (a == QLatin1String("--to") && i + 1 < args.size())
            l.dest = QDir(cwd).absoluteFilePath(args[++i]);
        else if (a == QLatin1String("--here"))
            l.here = true;
        else if (a == QLatin1String("--demo"))
            l.demo = true;
        else if (a == QLatin1String("--screenshot") && i + 1 < args.size())
            l.screenshot = args[++i];
        else if (a.startsWith(QLatin1String("file://")))
            l.files << QUrl(a).toLocalFile();
        else if (!a.startsWith(QLatin1Char('-')))
            l.files << QDir(cwd).absoluteFilePath(a);
    }
    if (l.here && !l.files.isEmpty())
        l.dest = QFileInfo(l.files.first()).absolutePath();
    return l;
}

} // namespace

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    KAboutData about(QStringLiteral("deckos-extract"), QStringLiteral("DecKoOS Extract"), QStringLiteral(DECKOS_VERSION),
                     QStringLiteral("Extracts archives, split ones too"), KAboutLicense::MIT);
    about.setOrganizationDomain(QByteArrayLiteral("deckos.org"));
    about.setDesktopFileName(QStringLiteral("org.deckos.extract"));
    KAboutData::setApplicationData(about);

    const Launch launch = parseArgs(QApplication::arguments(), QDir::currentPath());
    if (launch.demo) {
        // Offscreen CI has no Plasma platform theme: pick the DecKoOS font and style by hand.
        QApplication::setFont(QFont(QStringLiteral("Inter"), 10));
        if (QStyleFactory::keys().contains(QStringLiteral("Breeze")))
            QApplication::setStyle(QStringLiteral("Breeze"));
    }
    Style::apply(app);

    if (launch.demo) {
        auto *w = new MainWindow(true);
        w->resize(900, 680);
        w->addDemo();
        w->show();
        if (!launch.screenshot.isEmpty()) {
            QTimer::singleShot(600, w, [w, out = launch.screenshot] {
                QDir().mkpath(out);
                w->grab().save(out + QStringLiteral("/1-queue.png"));
                qInfo("deckos-extract screenshot: 1-queue.png");
                QApplication::exit(0);
            });
        }
        return app.exec();
    }

    // One window: archives opened later join its queue.
    auto *w = new MainWindow;
    KDBusService service(KDBusService::Unique | KDBusService::NoExitOnFailure);
    QObject::connect(&service, &KDBusService::activateRequested, w, [w](const QStringList &args, const QString &cwd) {
        const Launch l = parseArgs(args, cwd);
        w->add(l.files, l.dest);
        w->show();
        w->raise();
        w->activateWindow();
    });
    w->show();
    w->add(launch.files, launch.dest);
    return app.exec();
}
