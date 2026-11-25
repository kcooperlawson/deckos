#include "archiveset.h"

#include <QDir>
#include <QFileInfo>
#include <QMap>
#include <QRegularExpression>
#include <QSet>

namespace {

// Longest first, so "x.tar.gz" names "x" and not "x.tar".
const QStringList kSuffixes = {
    QStringLiteral(".tar.gz"), QStringLiteral(".tar.xz"), QStringLiteral(".tar.zst"), QStringLiteral(".tar.bz2"),
    QStringLiteral(".tar.lz4"), QStringLiteral(".tgz"), QStringLiteral(".txz"), QStringLiteral(".tbz2"),
    QStringLiteral(".rar"), QStringLiteral(".7z"), QStringLiteral(".zip"), QStringLiteral(".tar"),
    QStringLiteral(".gz"), QStringLiteral(".xz"), QStringLiteral(".zst"), QStringLiteral(".bz2"),
    QStringLiteral(".iso"), QStringLiteral(".cab"), QStringLiteral(".arj"), QStringLiteral(".lzh"),
    QStringLiteral(".wim"), QStringLiteral(".cpio"),
};

enum class Kind { Single, RarPart, RarOld, Numbered, ZipOld };

struct Part {
    Kind kind;
    QString key;  // what every part of the set shares, per folder
    int number;   // the part's place: part1 = 1, .rar = -1 then .r00 = 0, .001 = 1, .z01 = 1 then .zip = 1000
};

const QRegularExpression kRarPart(QStringLiteral(R"(^(.+)\.part(\d+)\.rar$)"), QRegularExpression::CaseInsensitiveOption);
const QRegularExpression kRarOld(QStringLiteral(R"(^(.+)\.r(\d\d)$)"), QRegularExpression::CaseInsensitiveOption);
const QRegularExpression kNumbered(QStringLiteral(R"(^(.+)\.(\d{3})$)"), QRegularExpression::CaseInsensitiveOption);
const QRegularExpression kZipOld(QStringLiteral(R"(^(.+)\.z(\d\d)$)"), QRegularExpression::CaseInsensitiveOption);

QString stripSuffix(const QString &name)
{
    for (const QString &s : kSuffixes)
        if (name.endsWith(s, Qt::CaseInsensitive) && name.size() > s.size())
            return name.left(name.size() - s.size());
    return name;
}

bool hasSuffix(const QString &name)
{
    return stripSuffix(name) != name;
}

// What a file name is, or nothing when it's no archive. `.rar` and `.zip` alone are RarOld / ZipOld so that
// their .r00 / .z01 siblings join them; group() turns a lone one back into a single archive.
std::optional<Part> classify(const QString &name)
{
    if (auto m = kRarPart.match(name); m.hasMatch())
        return Part{Kind::RarPart, m.captured(1).toLower() + QStringLiteral("\x01rp"), m.captured(2).toInt()};
    if (auto m = kRarOld.match(name); m.hasMatch())
        return Part{Kind::RarOld, m.captured(1).toLower() + QStringLiteral("\x01ro"), m.captured(2).toInt()};
    if (auto m = kNumbered.match(name); m.hasMatch() && m.captured(2).toInt() > 0)
        return Part{Kind::Numbered, m.captured(1).toLower() + QStringLiteral("\x01n"), m.captured(2).toInt()};
    if (auto m = kZipOld.match(name); m.hasMatch())
        return Part{Kind::ZipOld, m.captured(1).toLower() + QStringLiteral("\x01zo"), m.captured(2).toInt()};
    if (name.endsWith(QLatin1String(".rar"), Qt::CaseInsensitive))
        return Part{Kind::RarOld, name.chopped(4).toLower() + QStringLiteral("\x01ro"), -1};
    if (name.endsWith(QLatin1String(".zip"), Qt::CaseInsensitive))
        return Part{Kind::ZipOld, name.chopped(4).toLower() + QStringLiteral("\x01zo"), 1000};
    if (hasSuffix(name))
        return Part{Kind::Single, name.toLower() + QStringLiteral("\x01s"), 0};
    return std::nullopt;
}

QString setName(Kind kind, const QString &firstName)
{
    QString n = firstName;
    switch (kind) {
    case Kind::RarPart: n = kRarPart.match(n).captured(1); break;
    case Kind::Numbered: n = kNumbered.match(n).captured(1); break;
    default: break;
    }
    return stripSuffix(n);
}

} // namespace

namespace Archives {

bool isArchive(const QString &path)
{
    return classify(QFileInfo(path).fileName()).has_value();
}

QList<ArchiveSet> group(const QStringList &paths)
{
    QList<ArchiveSet> sets;
    QSet<QString> seen;  // folder + key
    for (const QString &path : paths) {
        const QFileInfo fi(path);
        const auto part = classify(fi.fileName());
        if (!part || !fi.isFile())
            continue;
        const QString dir = fi.absolutePath();
        if (seen.contains(dir + QLatin1Char('/') + part->key))
            continue;
        seen.insert(dir + QLatin1Char('/') + part->key);

        // Every sibling in the same set, by its number.
        QMap<int, QFileInfo> found;
        if (part->kind == Kind::Single) {
            found.insert(0, fi);
        } else {
            for (const QFileInfo &s : QDir(dir).entryInfoList(QDir::Files)) {
                const auto sp = classify(s.fileName());
                if (sp && sp->key == part->key)
                    found.insert(sp->number, s);
            }
        }

        ArchiveSet set;
        const Kind kind = part->kind;
        // .r00 without its .rar, or .z01 without its .zip: 7-Zip can't start there.
        const bool headless = (kind == Kind::RarOld && !found.contains(-1)) || (kind == Kind::ZipOld && !found.contains(1000));
        for (const QFileInfo &s : std::as_const(found)) {
            set.parts << s.absoluteFilePath();
            set.bytes += s.size();
        }
        if (kind == Kind::ZipOld)  // .z01 .z02 … then .zip last on disk, but 7-Zip opens the .zip
            set.first = found.value(1000).absoluteFilePath();
        else
            set.first = set.parts.first();
        if (headless)
            set.first.clear();

        // Gaps: numbering starts at part1 / .r00 / .001 / .z01.
        const int start = (kind == Kind::RarOld) ? 0 : 1;
        int last = start - 1;
        for (auto it = found.keyBegin(); it != found.keyEnd(); ++it)
            if (*it >= start && *it < 1000)
                last = qMax(last, *it);
        if (kind != Kind::Single)
            for (int n = start; n <= last; ++n)
                if (!found.contains(n))
                    set.missing << n;
        if (headless)
            set.missing.prepend(kind == Kind::RarOld ? -1 : 1000);

        set.name = setName(kind, QFileInfo(set.first.isEmpty() ? set.parts.first() : set.first).fileName());
        sets << set;
    }
    return sets;
}

}
