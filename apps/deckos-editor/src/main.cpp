#include "editorview.h"
#include "mainwindow.h"
#include "style.h"

#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QKeyEvent>
#include <QLineEdit>
#include <QRegularExpression>
#include <QStyleFactory>
#include <QTimer>

#include <KAboutData>
#include <KDBusService>
#include <KSyntaxHighlighting/Repository>

namespace {

struct Launch {
    QList<QPair<QString, int>> files;  // path, line (0: wherever)
    bool demo = false;
    bool newWindow = false;
    QString screenshot;
};

// deckos-editor [--new-window] [+LINE] FILE[:LINE] ...  (the +LINE and FILE:LINE forms other editors take)
Launch parseArgs(const QStringList &args, const QString &cwd)
{
    Launch l;
    int pendingLine = 0;
    for (qsizetype i = 1; i < args.size(); ++i) {
        const QString &a = args[i];
        if (a == QLatin1String("--demo")) {
            l.demo = true;
        } else if (a == QLatin1String("--new-window")) {
            l.newWindow = true;
        } else if (a == QLatin1String("--screenshot") && i + 1 < args.size()) {
            l.screenshot = args[++i];
        } else if (a.startsWith(QLatin1Char('+')) && a.mid(1).toInt() > 0) {
            pendingLine = a.mid(1).toInt();
        } else if (!a.startsWith(QLatin1String("--"))) {
            QString path = a.startsWith(QLatin1String("file://")) ? QUrl(a).toLocalFile() : a;
            int line = pendingLine;
            static const QRegularExpression withLine(QStringLiteral("^(.+):(\\d+)(?::\\d+)?$"));
            const auto m = withLine.match(path);
            if (m.hasMatch() && !QFileInfo::exists(QDir(cwd).absoluteFilePath(path))) {
                path = m.captured(1);
                line = m.captured(2).toInt();
            }
            l.files.append({QDir(cwd).absoluteFilePath(path), line});
            pendingLine = 0;
        }
    }
    return l;
}

// --demo: a small project with a few languages, so the screenshots show highlighting, find and an
// unsaved change
QString makeDemoProject()
{
    const QString root = QDir::tempPath() + QStringLiteral("/deckos-editor-demo");
    QDir(root).removeRecursively();
    QDir().mkpath(root);
    auto write = [&root](const char *name, const char *text) {
        QFile f(root + QLatin1Char('/') + QLatin1String(name));
        if (f.open(QIODevice::WriteOnly))
            f.write(text);
    };
    write("gamemode.py",
          "\"\"\"Frees the graphics card while a game runs.\"\"\"\n"
          "import subprocess\n"
          "from pathlib import Path\n\n"
          "STATE = Path(\"/run/user/1000/deckos-mode\")\n\n\n"
          "def running_game():\n"
          "    # Steam's reaper starts every game: its child is the game\n"
          "    out = subprocess.run([\"pgrep\", \"-a\", \"-f\", \"reaper SteamLaunch\"], capture_output=True, text=True)\n"
          "    for line in out.stdout.splitlines():\n"
          "        pid, _, cmd = line.partition(\" \")\n"
          "        if \"AppId=\" in cmd:\n"
          "            return int(pid), cmd.split(\"AppId=\")[1].split()[0]\n"
          "    return None\n\n\n"
          "class Mode:\n"
          "    def __init__(self, vram_free=2 * 1024**3):\n"
          "        self.vram_free = vram_free\n"
          "        self.paused = []\n\n"
          "    def enter(self, game):\n"
          "        \"\"\"Unload AI models and pause containers.\"\"\"\n"
          "        for name in (\"ollama\", \"docker\"):\n"
          "            self.paused.append(name)\n"
          "        STATE.write_text(f\"mode=gaming\\ngame={game}\\n\")\n"
          "        return len(self.paused)\n");
    write("fstab", "# /etc/fstab: static file system information.\n"
                   "UUID=7ca4b8f1-388a-4d5f-b991-c15726e006f3  /      btrfs  rw,noatime,compress=zstd:1,subvol=/@  0 0\n"
                   "UUID=61E1-7852                            /boot/efi  vfat  rw,relatime  0 2\n\n"
                   "# >>> DeckOS drives (managed by 'deckos drives rescan') >>>\n"
                   "UUID=4C3CACD83CACBDF8  /mnt/SSD  ntfs3  uid=1000,gid=1000,windows_names,nofail  0 0\n"
                   "# <<< DeckOS drives <<<\n");
    write("notes.md", "# DeckOS Editor\n\nText, code and config files with **colours** for 300+ languages.\n\n"
                      "- Find and replace with `Ctrl+H`\n- Saves `/etc` files with your password\n");
    return root;
}

void runDemo(MainWindow *w, const QString &root, const QString &out)
{
    w->openFile(root + QStringLiteral("/notes.md"));
    w->openFile(root + QStringLiteral("/fstab"));
    EditorView *py = w->openFile(root + QStringLiteral("/gamemode.py"), 18);
    py->moveCursor(QTextCursor::EndOfLine);
    py->insertPlainText(QStringLiteral("  # Ctrl+/ toggles comments"));
    if (out.isEmpty())
        return;
    QTimer::singleShot(500, w, [=] {
        QDir().mkpath(out);
        w->grab().save(out + QStringLiteral("/1-python.png"));
        qInfo("deckos-editor screenshot: 1-python.png");
        // Find and replace, with every match lit
        QApplication::postEvent(w, new QKeyEvent(QEvent::KeyPress, Qt::Key_H, Qt::ControlModifier));
        QTimer::singleShot(300, w, [=] {
            if (auto *find = w->findChild<QLineEdit *>()) {
                find->setText(QStringLiteral("self"));
            }
            QTimer::singleShot(300, w, [=] {
                w->grab().save(out + QStringLiteral("/2-find.png"));
                qInfo("deckos-editor screenshot: 2-find.png");
                w->openFile(root + QStringLiteral("/fstab"));
                w->showMessage(QStringLiteral("You can read this file; saving it asks for your password."));
                QTimer::singleShot(300, w, [=] {
                    w->grab().save(out + QStringLiteral("/3-config.png"));
                    qInfo("deckos-editor screenshot: 3-config.png");
                    QApplication::exit(0);  // not quit(): the window would ask about the unsaved change
                });
            });
        });
    });
}

} // namespace

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    KAboutData about(QStringLiteral("deckos-editor"), QStringLiteral("DeckOS Editor"), QStringLiteral(DECKOS_VERSION),
                     QStringLiteral("The DeckOS text editor"), KAboutLicense::MIT);
    about.setOrganizationDomain(QByteArrayLiteral("deckos.org"));
    about.setDesktopFileName(QStringLiteral("org.deckos.editor"));
    KAboutData::setApplicationData(about);

    const Launch launch = parseArgs(QApplication::arguments(), QDir::currentPath());
    if (launch.demo) {
        // Offscreen CI has no Plasma platform theme: pick the DeckOS font and style by hand.
        QApplication::setFont(QFont(QStringLiteral("Inter"), 10));
        if (QStyleFactory::keys().contains(QStringLiteral("Breeze")))
            QApplication::setStyle(QStringLiteral("Breeze"));
    }
    Style::apply(app);

    // The DeckOS syntax theme sits beside KDE's: installed, or this checkout's when run from the repo
    auto *repo = new KSyntaxHighlighting::Repository;
    for (const QString &dir : {QStringLiteral("/usr/share/deckos-editor"), QStringLiteral(DECKOS_SOURCE_DATA)})
        if (QFile::exists(dir + QStringLiteral("/themes/deckos.theme")))
            repo->addCustomSearchPath(dir);

    if (launch.demo) {
        const QString root = makeDemoProject();
        auto *w = new MainWindow(repo, false);
        w->resize(1180, 740);
        w->show();
        runDemo(w, root, launch.screenshot);
        return app.exec();
    }

    // One process: another launch opens its files here (as tabs), which is instant
    KDBusService service(KDBusService::Unique | KDBusService::NoExitOnFailure);
    auto *main = new MainWindow(repo);
    QObject::connect(&service, &KDBusService::activateRequested, &app, [repo, main](const QStringList &args, const QString &cwd) {
        const Launch l = parseArgs(args, cwd);
        MainWindow *w = l.newWindow ? new MainWindow(repo, false) : main;
        for (const auto &[path, line] : l.files)
            w->openFile(path, line);
        w->show();
        w->raise();
        w->activateWindow();
    });
    for (const auto &[path, line] : launch.files)
        main->openFile(path, line);
    main->show();
    return app.exec();
}
