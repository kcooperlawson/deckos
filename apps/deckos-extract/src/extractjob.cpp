#include "extractjob.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QStorageInfo>

#include <signal.h>

namespace {

QString program()
{
    // 7zip's 7z first; p7zip's 7za / 7z work the same way.
    for (const char *name : {"7z", "7za", "7zz"})
        if (const QString p = QStandardPaths::findExecutable(QString::fromLatin1(name)); !p.isEmpty())
            return p;
    return {};
}

// "Game" in a folder that already has one becomes "Game (2)".
QString freeName(const QString &dir, const QString &name)
{
    QString candidate = dir + QLatin1Char('/') + name;
    for (int n = 2; QFileInfo::exists(candidate); ++n)
        candidate = dir + QLatin1Char('/') + name + QStringLiteral(" (%1)").arg(n);
    return candidate;
}

} // namespace

ExtractJob::ExtractJob(const ArchiveSet &set, const QString &destRoot, QObject *parent)
    : QObject(parent)
    , m_set(set)
    , m_destRoot(destRoot)
{
}

ExtractJob::~ExtractJob()
{
    if (m_proc) {
        m_proc->disconnect(this);
        m_proc->kill();
        m_proc->waitForFinished(2000);
    }
    if (!m_staging.isEmpty() && !finished())
        QDir(m_staging).removeRecursively();
}

qint64 ExtractJob::secondsLeft() const
{
    if (m_speed <= 0 || m_unpacked <= 0 || m_percent <= 0)
        return -1;
    return qint64(m_unpacked * (100 - m_percent) / 100.0 / m_speed);
}

QStringList ExtractJob::passwordArgs() const
{
    // Always a password: without one 7-Zip waits on stdin for it. A wrong one only matters to encrypted archives.
    return {QStringLiteral("-p") + (m_password.isEmpty() ? QStringLiteral("-") : m_password)};
}

void ExtractJob::start()
{
    if (m_state != Queued)
        return;
    if (m_set.first.isEmpty()) {
        fail(tr("The first part is missing, so the archive can't be opened."));
        return;
    }
    if (!m_set.missing.isEmpty()) {
        QStringList names;
        for (int n : std::as_const(m_set.missing))
            names << (n < 0 ? QStringLiteral(".rar") : QString::number(n));
        fail(tr("Part %1 is missing. Put every part in the same folder and try again.").arg(names.join(QStringLiteral(", "))));
        return;
    }
    if (program().isEmpty()) {
        fail(tr("7-Zip isn't installed. Install the 7zip package and try again."));
        return;
    }
    list();
}

void ExtractJob::list()
{
    setState(Reading);
    m_output.clear();
    auto *p = new QProcess(this);
    m_proc = p;
    p->setProcessChannelMode(QProcess::MergedChannels);
    connect(p, &QProcess::readyRead, this, [this, p] { m_output += p->readAll(); });
    connect(p, &QProcess::finished, this, [this, p](int code) {
        m_output += p->readAll();
        p->deleteLater();
        onListed(code);
    });
    p->start(program(), QStringList{QStringLiteral("l"), QStringLiteral("-slt"), QStringLiteral("-ba")} << passwordArgs() << m_set.first);
}

void ExtractJob::onListed(int code)
{
    if (m_state == Cancelled)
        return;
    const QString out = QString::fromUtf8(m_output);
    if (out.contains(QLatin1String("Wrong password")) || out.contains(QLatin1String("encrypted archive"))) {
        m_encrypted = true;
        setState(NeedsPassword);
        Q_EMIT finishedRun();
        return;
    }
    if (code != 0) {
        fail(explain(out));
        return;
    }
    qint64 total = 0;
    int files = 0;
    bool encrypted = false;
    static const QRegularExpression size(QStringLiteral(R"(^Size = (\d+)$)"), QRegularExpression::MultilineOption);
    for (auto it = size.globalMatch(out); it.hasNext();) {
        total += it.next().captured(1).toLongLong();
        ++files;
    }
    if (out.contains(QLatin1String("\nEncrypted = +")))
        encrypted = true;
    m_unpacked = total;
    m_files = files;
    if (encrypted && m_password.isEmpty()) {
        // The names were readable but the files aren't: ask now, not halfway through 40 GB.
        m_encrypted = true;
        setState(NeedsPassword);
        Q_EMIT finishedRun();
        return;
    }
    const QStorageInfo disk(m_destRoot);
    if (disk.isValid() && total > 0 && disk.bytesAvailable() < total) {
        fail(tr("Not enough space: this needs %1 and the drive has %2 free.")
                 .arg(QLocale().formattedDataSize(total), QLocale().formattedDataSize(disk.bytesAvailable())));
        return;
    }
    extract();
}

void ExtractJob::extract()
{
    QDir().mkpath(m_destRoot);
    m_staging = freeName(m_destRoot, QStringLiteral(".") + m_set.name + QStringLiteral(".extracting"));
    if (!QDir().mkpath(m_staging)) {
        fail(tr("Can't write to %1.").arg(m_destRoot));
        return;
    }
    setState(Running);
    m_output.clear();
    m_percent = 0;
    m_pausedMs = 0;
    m_clock.start();
    auto *p = new QProcess(this);
    m_proc = p;
    p->setProcessChannelMode(QProcess::MergedChannels);
    connect(p, &QProcess::readyRead, this, &ExtractJob::onOutput);
    connect(p, &QProcess::finished, this, [this, p](int code) {
        m_output += p->readAll();
        p->deleteLater();
        onExtracted(code);
    });
    // -bsp1: progress on stdout; -bso0: no file list; -y: never ask (names inside are new to the staging folder).
    p->start(program(), QStringList{QStringLiteral("x"), QStringLiteral("-bsp1"), QStringLiteral("-bso0"), QStringLiteral("-bse1"),
                                    QStringLiteral("-y"), QStringLiteral("-o") + m_staging}
                            << passwordArgs() << m_set.first);
}

void ExtractJob::onOutput()
{
    const QByteArray chunk = m_proc->readAll();
    m_output += chunk;
    if (m_output.size() > 256 * 1024)  // only the end matters for errors
        m_output = m_output.right(64 * 1024);
    // Progress is redrawn in place with backspaces: the last "NN%" in the chunk is now.
    static const QRegularExpression pct(QStringLiteral(R"((\d{1,3})%)"));
    int found = -1;
    for (auto it = pct.globalMatch(QString::fromLatin1(chunk)); it.hasNext();)
        found = it.next().captured(1).toInt();
    if (found < 0 || found == m_percent)
        return;
    m_percent = qBound(0, found, 100);
    const double secs = (m_clock.elapsed() - m_pausedMs) / 1000.0;
    if (secs > 0.5 && m_unpacked > 0) {
        const double now = m_unpacked * (m_percent / 100.0) / secs;
        m_speed = m_speed <= 0 ? now : m_speed * 0.7 + now * 0.3;
    }
    Q_EMIT changed();
}

void ExtractJob::onExtracted(int code)
{
    if (m_state == Cancelled)
        return;
    const QString out = QString::fromUtf8(m_output);
    if (code != 0 || out.contains(QLatin1String("ERROR"))) {
        QDir(m_staging).removeRecursively();
        m_staging.clear();
        if (out.contains(QLatin1String("Wrong password"))) {
            m_encrypted = true;
            m_password.clear();
            m_error = tr("That password didn't work.");
            setState(NeedsPassword);
            Q_EMIT finishedRun();
            return;
        }
        fail(explain(out));
        return;
    }
    place();
}

// One folder inside (most game and movie releases): that folder is the result. Anything else gets a folder named
// after the archive.
void ExtractJob::place()
{
    const QFileInfoList inside = QDir(m_staging).entryInfoList(QDir::AllEntries | QDir::NoDotAndDotDot | QDir::Hidden);
    QString target;
    bool ok;
    if (inside.size() == 1 && inside.first().isDir()) {
        target = freeName(m_destRoot, inside.first().fileName());
        ok = QDir().rename(inside.first().absoluteFilePath(), target);
        QDir().rmdir(m_staging);
    } else {
        target = freeName(m_destRoot, m_set.name);
        ok = QDir().rename(m_staging, target);
    }
    if (!ok) {
        fail(tr("Extracted, but couldn't move the files out of %1.").arg(m_staging));
        return;
    }
    m_staging.clear();
    m_result = target;
    m_percent = 100;
    if (m_trashAfter)
        for (const QString &part : std::as_const(m_set.parts))
            QFile::moveToTrash(part);
    setState(Done);
    Q_EMIT finishedRun();
}

QString ExtractJob::explain(const QString &out) const
{
    if (out.contains(QLatin1String("Unexpected end of archive")) || out.contains(QLatin1String("Missing volume")))
        return tr("A part is missing or didn't finish downloading.");
    if (out.contains(QLatin1String("CRC Failed")) || out.contains(QLatin1String("Data Error")))
        return tr("Some data is damaged. Download the broken part again, or repair it with its recovery files.");
    if (out.contains(QLatin1String("No space left")))
        return tr("The drive filled up.");
    if (out.contains(QLatin1String("Cannot open the file as")) || out.contains(QLatin1String("Can not open the file as")))
        return tr("This isn't an archive 7-Zip can read, or it's damaged.");
    if (out.contains(QLatin1String("Permission denied")))
        return tr("No permission to write there.");
    // Otherwise 7-Zip's own last error line.
    const QStringList lines = out.split(QRegularExpression(QStringLiteral("[\r\n\b]+")), Qt::SkipEmptyParts);
    for (auto it = lines.crbegin(); it != lines.crend(); ++it) {
        const QString l = it->trimmed();
        if (!l.isEmpty() && !l.endsWith(QLatin1Char('%')) && l != QLatin1String("ERRORS:"))
            return l;
    }
    return tr("7-Zip stopped with an error.");
}

void ExtractJob::fail(const QString &message)
{
    m_error = message;
    setState(Failed);
    Q_EMIT finishedRun();
}

void ExtractJob::setState(State s)
{
    m_state = s;
    if (s != Failed && s != NeedsPassword)
        m_error.clear();
    Q_EMIT changed();
}

void ExtractJob::pause()
{
    if (m_state != Running || !m_proc)
        return;
    ::kill(pid_t(m_proc->processId()), SIGSTOP);
    m_pauseClock.start();
    setState(Paused);
}

void ExtractJob::resume()
{
    if (m_state != Paused || !m_proc)
        return;
    ::kill(pid_t(m_proc->processId()), SIGCONT);
    m_pausedMs += m_pauseClock.elapsed();
    setState(Running);
}

void ExtractJob::cancel()
{
    if (finished())
        return;
    const bool wasActive = active();
    setState(Cancelled);
    if (m_proc) {
        m_proc->disconnect(this);
        ::kill(pid_t(m_proc->processId()), SIGCONT);  // a stopped process can't take the kill
        m_proc->kill();
        m_proc->waitForFinished(3000);
        m_proc->deleteLater();
    }
    if (!m_staging.isEmpty()) {
        QDir(m_staging).removeRecursively();
        m_staging.clear();
    }
    if (wasActive)
        Q_EMIT finishedRun();
}

void ExtractJob::retry()
{
    if (m_state != Failed && m_state != Cancelled)
        return;
    m_set = Archives::group({m_set.first.isEmpty() ? m_set.parts.first() : m_set.first}).value(0, m_set);  // parts may have arrived
    m_percent = 0;
    m_speed = 0;
    setState(Queued);
}

void ExtractJob::setPassword(const QString &password)
{
    m_password = password;
    if (m_state == NeedsPassword)
        setState(Queued);
}

void ExtractJob::setDemo(State state, int percent, qint64 unpacked, double speed, const QString &error)
{
    m_state = state;
    m_percent = percent;
    m_unpacked = unpacked;
    m_speed = speed;
    m_error = error;
    if (state == Done)
        m_result = m_destRoot + QLatin1Char('/') + m_set.name;
    Q_EMIT changed();
}
