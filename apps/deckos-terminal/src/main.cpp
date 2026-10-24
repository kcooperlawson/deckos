#include "mainwindow.h"
#include "modewatch.h"
#include "style.h"
#include "tabpage.h"
#include "terminalpane.h"

#include <QApplication>
#include <QDir>
#include <QFile>
#include <QStyleFactory>
#include <QTimer>

#include <KAboutData>
#include <KDBusService>

#include <qtermwidget.h>

namespace {

struct Launch {
    QString dir;
    QStringList command;  // after -e: the program and its arguments, as Konsole takes them
    bool demo = false;
    bool hold = false;  // keep the window after the command ends (DeckOS Hub's terminal steps)
    QString screenshot;
};

// By hand, because -e takes everything after it (`deckos-terminal -e htop -d 10`).
Launch parseArgs(const QStringList &args, const QString &cwd)
{
    Launch l;
    l.dir = cwd;
    for (qsizetype i = 1; i < args.size(); ++i) {
        const QString &a = args[i];
        if (a == QLatin1String("-e") || a == QLatin1String("--command")) {
            l.command = args.mid(i + 1);
            break;
        } else if ((a == QLatin1String("--workdir") || a == QLatin1String("-w")) && i + 1 < args.size()) {
            l.dir = args[++i];
        } else if (a.startsWith(QLatin1String("--workdir="))) {
            l.dir = a.mid(10);
        } else if (a == QLatin1String("--hold")) {
            l.hold = true;
        } else if (a == QLatin1String("--demo")) {
            l.demo = true;
        } else if (a == QLatin1String("--screenshot") && i + 1 < args.size()) {
            l.screenshot = args[++i];
        }
    }
    if (!l.dir.isEmpty())
        l.dir = QDir(cwd).absoluteFilePath(l.dir);
    return l;
}

// --demo: a project folder with a git branch, a prompt like a configured shell's, and a build in a
// split, so the screenshots show what DeckOS Terminal knows.
QString makeDemoProject()
{
    const QString root = QDir::tempPath() + QStringLiteral("/deckos-terminal-demo");
    QDir(root).removeRecursively();
    QDir().mkpath(root + QStringLiteral("/deckos/.git"));
    QDir().mkpath(root + QStringLiteral("/deckos/apps"));
    QDir().mkpath(root + QStringLiteral("/bin"));
    auto write = [](const QString &path, const QByteArray &data) {
        QFile f(path);
        if (f.open(QIODevice::WriteOnly))
            f.write(data);
    };
    write(root + QStringLiteral("/deckos/.git/HEAD"), "ref: refs/heads/terminal\n");
    for (const char *f : {"README.md", "VERSION", "build.sh", "CLAUDE.md"})
        write(root + QStringLiteral("/deckos/") + QString::fromLatin1(f), "\n");
    // A stand-in for cargo, so a tab has a build running in it.
    write(root + QStringLiteral("/bin/cargo"),
          "#!/bin/sh\nfor c in deckos-core deckos-files deckos-terminal; do\n"
          "  printf '\\033[1;32m   Compiling\\033[0m %s v0.3.16 (~/deckos/apps/%s)\\n' $c $c; sleep 0.2\ndone\nsleep 60\n");
    QFile::setPermissions(root + QStringLiteral("/bin/cargo"), QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
    return root;
}

void type(TerminalPane *pane, const QString &text)
{
    pane->term()->sendText(text);
}

void runDemo(MainWindow *w, ModeWatch *modes, const QString &root, const QString &out)
{
    const QString prompt = QStringLiteral(
        "PS1='\\[\\e[38;2;76;141;255m\\]\\W\\[\\e[0m\\] \\[\\e[38;2;140;148;166m\\]\\$\\[\\e[0m\\] '; "
        "PATH=%1/bin:$PATH; clear\n").arg(root);
    TabPage *home = w->currentPage();
    type(home->activePane(), prompt + QStringLiteral("cd ~; clear; ls\n"));
    TabPage *project = w->openTab(root + QStringLiteral("/deckos"));
    type(project->activePane(), prompt + QStringLiteral("ls -la --color=always\n"));
    QTimer::singleShot(900, w, [=] {
        project->split(Qt::Horizontal);
        type(project->activePane(), prompt + QStringLiteral("cargo build --release\n"));
    });
    QTimer::singleShot(2600, w, [=] {
        project->refresh();
        modes->setDemo(QStringLiteral("Cyberpunk 2077"), 9.1e9, 2);
        if (out.isEmpty())
            return;
        QTimer::singleShot(400, w, [=] {  // the mode chip's new size, laid out
            QDir().mkpath(out);
            w->grab().save(out + QStringLiteral("/1-project-split.png"));
            qInfo("deckos-terminal screenshot: 1-project-split.png");
            QApplication::exit(0);  // not quit(): that asks the window, which asks about the running build
        });
    });
}

} // namespace

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    KAboutData about(QStringLiteral("deckos-terminal"), QStringLiteral("DeckOS Terminal"), QStringLiteral(DECKOS_VERSION),
                     QStringLiteral("The DeckOS terminal"), KAboutLicense::MIT);
    about.setOrganizationDomain(QByteArrayLiteral("deckos.org"));
    about.setDesktopFileName(QStringLiteral("org.deckos.terminal"));
    KAboutData::setApplicationData(about);

    const Launch launch = parseArgs(QApplication::arguments(), QDir::currentPath());
    if (launch.demo) {
        // Offscreen CI has no Plasma platform theme: pick the DeckOS font and style by hand.
        QApplication::setFont(QFont(QStringLiteral("Inter"), 10));
        if (QStyleFactory::keys().contains(QStringLiteral("Breeze")))
            QApplication::setStyle(QStringLiteral("Breeze"));
    }
    Style::apply(app);
    auto *modes = new ModeWatch(&app);

    if (launch.demo) {
        const QString root = makeDemoProject();
        auto *w = new MainWindow(modes, QDir::homePath());
        w->resize(1280, 760);
        w->show();
        runDemo(w, modes, root, launch.screenshot);
        return app.exec();
    }

    // One process: another launch opens its window here, which is instant.
    KDBusService service(KDBusService::Unique | KDBusService::NoExitOnFailure);
    QObject::connect(&service, &KDBusService::activateRequested, &app, [modes](const QStringList &args, const QString &cwd) {
        const Launch l = parseArgs(args, cwd);
        auto *w = new MainWindow(modes, l.dir, l.command, l.hold);
        w->show();
        w->raise();
        w->activateWindow();
    });
    (new MainWindow(modes, launch.dir, launch.command, launch.hold))->show();
    return app.exec();
}
