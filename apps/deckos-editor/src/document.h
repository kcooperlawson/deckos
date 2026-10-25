// A file as DeckOS Editor holds it: the text, where it lives and how it was written (line endings,
// a final newline, a byte-order mark), so saving writes it back the same way it came in.
#pragma once

#include <QDateTime>
#include <QString>

class Document
{
public:
    enum class Load { Ok, Missing, TooBig, Binary, NotUtf8, Unreadable };
    enum class Save { Ok, NeedsAdmin, Failed };

    static constexpr qint64 MaxSize = 64LL * 1024 * 1024;  // a text editor, not a disk viewer

    // Reads `path`. On Ok, text() is the content with \n line endings.
    Load load(const QString &path);
    // Writes `text` (with \n endings) to `path` atomically, in the file's original style. A file this
    // user can't write gives NeedsAdmin; saveAsAdmin() then goes through pkexec.
    Save save(const QString &text, const QString &path = {});
    bool saveAsAdmin(const QString &text, QString *error);

    QString path() const { return m_path; }
    QString text() const { return m_text; }
    QString lastError() const { return m_error; }
    bool crlf() const { return m_crlf; }
    void setCrlf(bool on) { m_crlf = on; }
    bool bom() const { return m_bom; }
    // Did the file change on disk since we loaded or saved it?
    bool changedOnDisk() const;
    void forgetDiskState();  // after the user chose to keep their version

    // The bytes save() writes for `text`: line endings and BOM as loaded (tested on its own)
    QByteArray encode(const QString &text) const;

private:
    void remember();

    QString m_path;
    QString m_text;
    QString m_error;
    bool m_crlf = false;
    bool m_bom = false;
    QDateTime m_mtime;
    qint64 m_size = -1;
};
