// Archives as the user means them: every part of a split archive is one set, found from any one part.
#pragma once

#include <QList>
#include <QString>
#include <QStringList>

struct ArchiveSet {
    QString first;     // the file 7-Zip opens (part1.rar, .rar before .r00, .001, .zip before .z01)
    QStringList parts; // every part found, in order, first included
    QString name;      // the archive's name without part or archive suffixes ("Game.part03.rar" → "Game")
    qint64 bytes = 0;  // the parts' size on disk
    QList<int> missing; // part numbers absent between the first and the last part found
    bool split() const { return parts.size() > 1; }
};

namespace Archives {

// True for anything DecKoOS Extract opens: archive suffixes and every kind of part.
bool isArchive(const QString &path);

// Groups paths into sets, looking in each file's folder for the parts it wasn't given. A set appears once
// however many of its parts were passed; non-archives are dropped.
QList<ArchiveSet> group(const QStringList &paths);

}
