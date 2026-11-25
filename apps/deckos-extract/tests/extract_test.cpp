// Grouping of every kind of split name, and real 7-Zip runs on archives made here: a split 7z set, a password,
// a missing part, and where results land.
#include "archiveset.h"
#include "extractjob.h"

#include <QDir>
#include <QFile>
#include <QProcess>
#include <QRandomGenerator>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

class ExtractTest : public QObject
{
    Q_OBJECT

    QTemporaryDir m_tmp;

    QString touch(const QString &name, qint64 size = 1)
    {
        const QString path = m_tmp.path() + QLatin1Char('/') + name;
        QDir().mkpath(QFileInfo(path).absolutePath());
        QFile f(path);
        if (!f.open(QIODevice::WriteOnly))
            return {};
        f.write(QByteArray(size, 'x'));
        return path;
    }

    static bool sevenZip(const QStringList &args, const QString &cwd)
    {
        QProcess p;
        p.setWorkingDirectory(cwd);
        p.start(QStringLiteral("7z"), args);
        return p.waitForFinished(60000) && p.exitCode() == 0;
    }

    ExtractJob::State run(ExtractJob &job)
    {
        QSignalSpy spy(&job, &ExtractJob::finishedRun);
        job.start();
        if (job.state() != ExtractJob::Failed)
            spy.wait(60000);
        return job.state();
    }

private Q_SLOTS:
    void groupsRarParts()
    {
        touch(QStringLiteral("a/Game.part1.rar"));
        touch(QStringLiteral("a/Game.part2.rar"));
        const QString third = touch(QStringLiteral("a/Game.part3.rar"));
        touch(QStringLiteral("a/notes.txt"));
        const auto sets = Archives::group({third, m_tmp.path() + QStringLiteral("/a/Game.part1.rar"),
                                           m_tmp.path() + QStringLiteral("/a/notes.txt")});
        QCOMPARE(sets.size(), 1);
        QCOMPARE(sets[0].parts.size(), 3);
        QVERIFY(sets[0].first.endsWith(QLatin1String("Game.part1.rar")));
        QCOMPARE(sets[0].name, QStringLiteral("Game"));
        QVERIFY(sets[0].missing.isEmpty());
    }

    void zeroPaddedAndGaps()
    {
        touch(QStringLiteral("b/Movie.part01.rar"));
        touch(QStringLiteral("b/Movie.part02.rar"));
        touch(QStringLiteral("b/Movie.part04.rar"));
        const auto sets = Archives::group({m_tmp.path() + QStringLiteral("/b/Movie.part04.rar")});
        QCOMPARE(sets.size(), 1);
        QCOMPARE(sets[0].missing, QList<int>{3});
        QVERIFY(sets[0].first.endsWith(QLatin1String("part01.rar")));
    }

    void oldStyleRar()
    {
        touch(QStringLiteral("c/Album.rar"));
        touch(QStringLiteral("c/Album.r00"));
        touch(QStringLiteral("c/Album.r01"));
        const auto sets = Archives::group({m_tmp.path() + QStringLiteral("/c/Album.r01")});
        QCOMPARE(sets.size(), 1);
        QCOMPARE(sets[0].parts.size(), 3);
        QVERIFY(sets[0].first.endsWith(QLatin1String("Album.rar")));
        QCOMPARE(sets[0].name, QStringLiteral("Album"));

        touch(QStringLiteral("d/Lost.r00"));  // no .rar: can't start
        const auto headless = Archives::group({m_tmp.path() + QStringLiteral("/d/Lost.r00")});
        QVERIFY(headless[0].first.isEmpty());
        QVERIFY(!headless[0].missing.isEmpty());
    }

    void numberedAndSingles()
    {
        touch(QStringLiteral("e/Backup.7z.001"));
        touch(QStringLiteral("e/Backup.7z.002"));
        touch(QStringLiteral("e/photos.tar.gz"));
        touch(QStringLiteral("e/single.rar"));
        const auto sets = Archives::group({m_tmp.path() + QStringLiteral("/e/Backup.7z.002"), m_tmp.path() + QStringLiteral("/e/photos.tar.gz"),
                                           m_tmp.path() + QStringLiteral("/e/single.rar")});
        QCOMPARE(sets.size(), 3);
        QCOMPARE(sets[0].name, QStringLiteral("Backup"));
        QVERIFY(sets[0].first.endsWith(QLatin1String(".001")));
        QCOMPARE(sets[1].name, QStringLiteral("photos"));
        QCOMPARE(sets[2].parts.size(), 1);
        QVERIFY(!Archives::isArchive(QStringLiteral("readme.txt")));
    }

    void extractsSplitSet()
    {
        const QString dir = m_tmp.path() + QStringLiteral("/real");
        QDir().mkpath(dir + QStringLiteral("/Stuff"));
        QFile f(dir + QStringLiteral("/Stuff/data.bin"));
        QVERIFY(f.open(QIODevice::WriteOnly));
        // Random, so it neither compresses nor finishes before cancelLeavesNothing can cancel it.
        QByteArray block(1 << 20, Qt::Uninitialized);
        for (int i = 0; i < 64; ++i) {
            for (char &c : block)
                c = char(QRandomGenerator::global()->generate());
            f.write(block);
        }
        f.close();
        QVERIFY(sevenZip({QStringLiteral("a"), QStringLiteral("-mx0"), QStringLiteral("-v20m"), QStringLiteral("set.7z"), QStringLiteral("Stuff")}, dir));
        QDir(dir + QStringLiteral("/Stuff")).removeRecursively();
        const auto sets = Archives::group({dir + QStringLiteral("/set.7z.002")});
        QCOMPARE(sets.size(), 1);
        QVERIFY(sets[0].parts.size() > 1);

        const QString out = dir + QStringLiteral("/out");
        ExtractJob job(sets[0], out);
        QCOMPARE(run(job), ExtractJob::Done);
        // One folder inside: it is the result, not set/Stuff.
        QCOMPARE(job.result(), out + QStringLiteral("/Stuff"));
        QVERIFY(QFile::exists(out + QStringLiteral("/Stuff/data.bin")));
        QVERIFY(job.unpackedBytes() > 0);
        // Nothing hidden left behind.
        QCOMPARE(QDir(out).entryList(QDir::AllEntries | QDir::Hidden | QDir::NoDotAndDotDot), QStringList{QStringLiteral("Stuff")});

        // Again: the second copy doesn't overwrite the first.
        ExtractJob again(sets[0], out);
        QCOMPARE(run(again), ExtractJob::Done);
        QCOMPARE(again.result(), out + QStringLiteral("/Stuff (2)"));
    }

    void missingPartStopsFirst()
    {
        const QString dir = m_tmp.path() + QStringLiteral("/real");
        QVERIFY(Archives::group({dir + QStringLiteral("/set.7z.001")})[0].parts.size() >= 3);
        QFile::rename(dir + QStringLiteral("/set.7z.002"), dir + QStringLiteral("/away"));
        const auto sets = Archives::group({dir + QStringLiteral("/set.7z.001")});
        ExtractJob job(sets[0], dir + QStringLiteral("/out2"));
        QCOMPARE(run(job), ExtractJob::Failed);
        QFile::rename(dir + QStringLiteral("/away"), dir + QStringLiteral("/set.7z.002"));
        QVERIFY(job.error().contains(QLatin1String("Part 2")));
    }

    void asksForPassword()
    {
        const QString dir = m_tmp.path() + QStringLiteral("/locked");
        QDir().mkpath(dir);
        QFile f(dir + QStringLiteral("/secret.txt"));
        QVERIFY(f.open(QIODevice::WriteOnly));
        f.write("hello");
        f.close();
        QVERIFY(sevenZip({QStringLiteral("a"), QStringLiteral("-pRIGHT"), QStringLiteral("-mhe=on"), QStringLiteral("box.7z"), QStringLiteral("secret.txt")}, dir));
        const auto sets = Archives::group({dir + QStringLiteral("/box.7z")});
        ExtractJob job(sets[0], dir + QStringLiteral("/out"));
        QCOMPARE(run(job), ExtractJob::NeedsPassword);
        job.setPassword(QStringLiteral("WRONG"));
        QCOMPARE(run(job), ExtractJob::NeedsPassword);
        job.setPassword(QStringLiteral("RIGHT"));
        QCOMPARE(run(job), ExtractJob::Done);
        // Loose files get a folder named after the archive.
        QVERIFY(QFile::exists(dir + QStringLiteral("/out/box/secret.txt")));
    }

    void cancelLeavesNothing()
    {
        const QString dir = m_tmp.path() + QStringLiteral("/real");
        const auto sets = Archives::group({dir + QStringLiteral("/set.7z.001")});
        const QString out = dir + QStringLiteral("/out3");
        ExtractJob job(sets[0], out);
        job.start();  // a fast disk finishes 64 MB before a test could catch it mid-way: cancel while it reads
        job.cancel();
        QCOMPARE(job.state(), ExtractJob::Cancelled);
        QVERIFY(QDir(out).entryList(QDir::AllEntries | QDir::Hidden | QDir::NoDotAndDotDot).isEmpty());
    }
};

QTEST_GUILESS_MAIN(ExtractTest)
#include "extract_test.moc"
