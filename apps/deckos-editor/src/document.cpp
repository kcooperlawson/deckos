#include "document.h"

#include <QFile>
#include <QFileInfo>
#include <QProcess>
#include <QSaveFile>
#include <QStringDecoder>
#include <QTemporaryFile>

Document::Load Document::load(const QString &path)
{
    QFile f(path);
    if (!f.exists())
        return Load::Missing;
    if (f.size() > MaxSize)
        return Load::TooBig;
    if (!f.open(QIODevice::ReadOnly)) {
        m_error = f.errorString();
        return Load::Unreadable;
    }
    QByteArray data = f.readAll();
    // A NUL in the first 8 KB means a binary file (what git and grep check, too)
    if (data.left(8192).contains('\0'))
        return Load::Binary;
    m_bom = data.startsWith("\xEF\xBB\xBF");
    if (m_bom)
        data.remove(0, 3);
    QStringDecoder utf8(QStringDecoder::Utf8, QStringDecoder::Flag::Stateless);
    QString text = utf8(data);
    if (utf8.hasError())
        return Load::NotUtf8;
    // The file's own line endings decide how it's saved: CRLF if most lines have it
    const qsizetype crlfs = text.count(QStringLiteral("\r\n"));
    const qsizetype lfs = text.count(QLatin1Char('\n'));
    m_crlf = crlfs > 0 && crlfs * 2 >= lfs;
    text.replace(QStringLiteral("\r\n"), QStringLiteral("\n"));
    m_text = text;
    m_path = QFileInfo(path).absoluteFilePath();
    remember();
    return Load::Ok;
}

QByteArray Document::encode(const QString &text) const
{
    QString out = text;
    if (m_crlf)
        out.replace(QLatin1Char('\n'), QStringLiteral("\r\n"));
    QByteArray bytes = out.toUtf8();
    if (m_bom)
        bytes.prepend("\xEF\xBB\xBF");
    return bytes;
}

Document::Save Document::save(const QString &text, const QString &path)
{
    const QString target = path.isEmpty() ? m_path : QFileInfo(path).absoluteFilePath();
    const QFileInfo info(target);
    // A file we can't write (or a new one in a folder we can't write): the user can choose admin
    if ((info.exists() && !info.isWritable()) || (!info.exists() && !QFileInfo(info.absolutePath()).isWritable())) {
        m_error = QStringLiteral("You don't have permission to change this file.");
        return Save::NeedsAdmin;
    }
    // QSaveFile writes next to the file and renames it over: a crash mid-save never leaves half a
    // file. It keeps the file's permissions; following a symlink saves the real file.
    QSaveFile f(info.isSymLink() ? info.symLinkTarget() : target);
    f.setDirectWriteFallback(true);  // folders that don't allow new files (some mounts)
    if (!f.open(QIODevice::WriteOnly) || f.write(encode(text)) < 0 || !f.commit()) {
        m_error = f.errorString();
        return Save::Failed;
    }
    m_path = target;
    m_text = text;
    remember();
    return Save::Ok;
}

bool Document::saveAsAdmin(const QString &text, QString *error)
{
    // The new content goes to a private temporary file; pkexec copies it over the file's content,
    // so the file keeps its owner and permissions (cp onto an existing file rewrites it in place).
    QTemporaryFile tmp;
    if (!tmp.open() || tmp.write(encode(text)) < 0 || !tmp.flush()) {
        *error = tmp.errorString();
        return false;
    }
    QProcess cp;
    cp.start(QStringLiteral("pkexec"), {QStringLiteral("cp"), QStringLiteral("--no-preserve=mode,ownership"),
                                        QStringLiteral("--"), tmp.fileName(), m_path});
    if (!cp.waitForFinished(-1) || cp.exitStatus() != QProcess::NormalExit || cp.exitCode() != 0) {
        // 126/127: the password prompt was dismissed or failed
        *error = cp.exitCode() == 126 || cp.exitCode() == 127 ? QStringLiteral("The password prompt was closed.")
                                                              : QString::fromLocal8Bit(cp.readAllStandardError()).trimmed();
        return false;
    }
    m_text = text;
    remember();
    return true;
}

void Document::remember()
{
    const QFileInfo info(m_path);
    m_mtime = info.lastModified();
    m_size = info.exists() ? info.size() : -1;
}

bool Document::changedOnDisk() const
{
    if (m_path.isEmpty())
        return false;
    const QFileInfo info(m_path);
    if (!info.exists())
        return m_size >= 0;
    return info.lastModified() != m_mtime || info.size() != m_size;
}

void Document::forgetDiskState()
{
    remember();
}
