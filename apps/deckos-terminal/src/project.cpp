#include "project.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>

namespace {

QByteArray readSmall(const QString &path)
{
    QFile f(path);
    return f.open(QIODevice::ReadOnly) ? f.read(4096) : QByteArray();
}

// The git directory for a work tree: `.git` is a folder, or a file pointing at one (worktrees, submodules).
QString gitDir(const QString &root)
{
    const QString dotGit = root + QStringLiteral("/.git");
    const QFileInfo fi(dotGit);
    if (fi.isDir())
        return dotGit;
    const QByteArray link = readSmall(dotGit).trimmed();
    if (!link.startsWith("gitdir: "))
        return QString();
    const QString target = QString::fromUtf8(link.mid(8));
    return QDir::isAbsolutePath(target) ? target : QDir::cleanPath(root + QLatin1Char('/') + target);
}

QString branchOf(const QString &root)
{
    const QString dir = gitDir(root);
    if (dir.isEmpty())
        return QString();
    const QByteArray head = readSmall(dir + QStringLiteral("/HEAD")).trimmed();
    if (head.startsWith("ref: refs/heads/"))
        return QString::fromUtf8(head.mid(16));
    return QString::fromLatin1(head.left(7));  // detached: the commit
}

} // namespace

QString ProjectInfo::label() const
{
    QString s = name;
    if (!branch.isEmpty())
        s += QStringLiteral(" ⎇ ") + branch;
    if (!command.isEmpty())
        s += QStringLiteral(" · ") + command;
    return s;
}

namespace Project {

QString cwdOf(int pid)
{
    return pid > 0 ? QFileInfo(QStringLiteral("/proc/%1/cwd").arg(pid)).symLinkTarget() : QString();
}

QString commandOf(int pid)
{
    const QList<QByteArray> args = readSmall(QStringLiteral("/proc/%1/cmdline").arg(pid)).split('\0');
    if (args.isEmpty() || args.first().isEmpty())
        return QString();
    // `node /usr/bin/npm run dev` is "npm run": an interpreter gives way to the script it runs
    static const QStringList interpreters = {QStringLiteral("sh"), QStringLiteral("bash"), QStringLiteral("zsh"), QStringLiteral("dash"),
                                             QStringLiteral("python"), QStringLiteral("python3"), QStringLiteral("node"),
                                             QStringLiteral("perl"), QStringLiteral("ruby")};
    QString cmd = QFileInfo(QString::fromUtf8(args.first())).fileName();
    bool interpreted = interpreters.contains(cmd);
    for (qsizetype i = 1; i < args.size(); ++i) {
        if (args[i].isEmpty() || args[i].startsWith('-'))
            continue;
        const QString arg = QString::fromUtf8(args[i]);
        const QString shortArg = arg.contains(QLatin1Char('/')) ? QFileInfo(arg).fileName() : arg;
        if (interpreted) {
            cmd = shortArg;
            interpreted = false;
            continue;
        }
        cmd += QLatin1Char(' ') + shortArg;
        break;
    }
    return cmd;
}

ProjectInfo inspect(int shellPid, int foregroundPid)
{
    ProjectInfo p;
    p.dir = cwdOf(foregroundPid > 0 ? foregroundPid : shellPid);
    if (p.dir.isEmpty())
        p.dir = cwdOf(shellPid);
    for (QString d = p.dir; !d.isEmpty() && d != QLatin1String("/"); d = QFileInfo(d).path()) {
        if (QFileInfo::exists(d + QStringLiteral("/.git"))) {
            p.root = d;
            break;
        }
    }
    if (!p.root.isEmpty()) {
        p.name = QFileInfo(p.root).fileName();
        p.branch = branchOf(p.root);
    } else if (p.dir == QDir::homePath()) {
        p.name = QStringLiteral("~");
    } else {
        p.name = p.dir.isEmpty() ? QStringLiteral("Terminal") : QFileInfo(p.dir).fileName();
        if (p.name.isEmpty())
            p.name = p.dir;
    }
    if (foregroundPid > 0 && foregroundPid != shellPid)
        p.command = commandOf(foregroundPid);
    return p;
}

} // namespace Project
