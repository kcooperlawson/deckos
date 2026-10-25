// Offscreen checks of DeckOS Editor's file handling, find and editing, on temporary files.
#include "document.h"
#include "editorview.h"
#include "findbar.h"

#include <QFile>
#include <QFileInfo>
#include <QTemporaryDir>
#include <QTest>
#include <QTextBlock>

#include <KSyntaxHighlighting/Repository>

class EditorTest : public QObject
{
    Q_OBJECT

    QTemporaryDir m_dir;
    KSyntaxHighlighting::Repository m_repo;

    QString write(const QString &name, const QByteArray &data)
    {
        const QString path = m_dir.filePath(name);
        QFile f(path);
        f.open(QIODevice::WriteOnly);
        f.write(data);
        return path;
    }
    static QByteArray read(const QString &path)
    {
        QFile f(path);
        f.open(QIODevice::ReadOnly);
        return f.readAll();
    }

private slots:
    void keepsLineEndingsBomAndFinalNewline()
    {
        const QString path = write(QStringLiteral("win.ini"), "\xEF\xBB\xBF[a]\r\nb=1\r\n");
        Document doc;
        QCOMPARE(doc.load(path), Document::Load::Ok);
        QVERIFY(doc.crlf());
        QVERIFY(doc.bom());
        QCOMPARE(doc.text(), QStringLiteral("[a]\nb=1\n"));
        QCOMPARE(doc.save(QStringLiteral("[a]\nb=2\n")), Document::Save::Ok);
        QCOMPARE(read(path), QByteArray("\xEF\xBB\xBF[a]\r\nb=2\r\n"));

        const QString plain = write(QStringLiteral("no-newline.txt"), "one\ntwo");
        QCOMPARE(doc.load(plain), Document::Load::Ok);
        QVERIFY(!doc.crlf());
        QCOMPARE(doc.save(doc.text()), Document::Save::Ok);
        QCOMPARE(read(plain), QByteArray("one\ntwo"));  // no newline added that wasn't there
    }

    void refusesWhatIsNotText()
    {
        Document doc;
        QCOMPARE(doc.load(write(QStringLiteral("a.bin"), QByteArray("ELF\0\0\1", 6))), Document::Load::Binary);
        QCOMPARE(doc.load(write(QStringLiteral("latin1.txt"), "caf\xE9\n")), Document::Load::NotUtf8);
        QCOMPARE(doc.load(m_dir.filePath(QStringLiteral("missing.txt"))), Document::Load::Missing);
    }

    void saveKeepsPermissionsAndFollowsSymlinks()
    {
        const QString script = write(QStringLiteral("run.sh"), "#!/bin/sh\necho hi\n");
        QFile::setPermissions(script, QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
        Document doc;
        QCOMPARE(doc.load(script), Document::Load::Ok);
        QCOMPARE(doc.save(QStringLiteral("#!/bin/sh\necho bye\n")), Document::Save::Ok);
        QVERIFY(QFileInfo(script).isExecutable());

        const QString link = m_dir.filePath(QStringLiteral("link.sh"));
        QVERIFY(QFile::link(script, link));
        QCOMPARE(doc.load(link), Document::Load::Ok);
        QCOMPARE(doc.save(QStringLiteral("#!/bin/sh\necho linked\n")), Document::Save::Ok);
        QVERIFY(QFileInfo(link).isSymLink());  // still a link, and the real file got the text
        QCOMPARE(read(script), QByteArray("#!/bin/sh\necho linked\n"));
    }

    void readOnlyFileAsksForAdmin()
    {
        const QString path = write(QStringLiteral("locked.conf"), "a=1\n");
        QFile::setPermissions(path, QFileDevice::ReadOwner);
        Document doc;
        QCOMPARE(doc.load(path), Document::Load::Ok);
        QCOMPARE(doc.save(QStringLiteral("a=2\n")), Document::Save::NeedsAdmin);
        QCOMPARE(read(path), QByteArray("a=1\n"));
    }

    void noticesChangesOnDisk()
    {
        const QString path = write(QStringLiteral("watched.txt"), "one\n");
        Document doc;
        QCOMPARE(doc.load(path), Document::Load::Ok);
        QVERIFY(!doc.changedOnDisk());
        QTest::qWait(1100);  // mtime resolution on some file systems
        write(QStringLiteral("watched.txt"), "one two\n");
        QVERIFY(doc.changedOnDisk());
        doc.forgetDiskState();
        QVERIFY(!doc.changedOnDisk());
    }

    void findMatches()
    {
        const QString text = QStringLiteral("Self self selfish\nmyself");
        QCOMPARE(FindBar::matches(text, QStringLiteral("self"), false, false, false).size(), 4);
        QCOMPARE(FindBar::matches(text, QStringLiteral("self"), true, false, false).size(), 3);
        QCOMPARE(FindBar::matches(text, QStringLiteral("self"), false, false, true).size(), 2);
        QCOMPARE(FindBar::matches(text, QStringLiteral("^my"), false, true, false).size(), 1);
        QCOMPARE(FindBar::matches(text, QStringLiteral("a.b"), false, false, false).size(), 0);  // literal, not a pattern
        QString error;
        QVERIFY(FindBar::matches(text, QStringLiteral("(oops"), false, true, false, &error).isEmpty());
        QVERIFY(!error.isEmpty());
    }

    void editing()
    {
        EditorView view(&m_repo);
        view.setPlainText(QStringLiteral("def f():\n    return 1\n"));
        view.pickDefinitionFor(QStringLiteral("x.py"));
        QCOMPARE(view.definition().name(), QStringLiteral("Python"));
        QCOMPARE(view.indentWidth(), 4);

        // Enter after ':' indents one step more
        view.goToLine(1);
        view.moveCursor(QTextCursor::EndOfLine);
        QTest::keyClick(&view, Qt::Key_Return);
        QCOMPARE(view.textCursor().block().text(), QStringLiteral("    "));
        view.document()->undo();

        // Ctrl+/ comments and uncomments, keeping indentation
        view.goToLine(2);
        view.toggleComment();
        QCOMPARE(view.document()->findBlockByNumber(1).text(), QStringLiteral("    # return 1"));
        view.toggleComment();
        QCOMPARE(view.document()->findBlockByNumber(1).text(), QStringLiteral("    return 1"));

        // Alt+Up swaps the line with the one above
        view.goToLine(2);
        view.moveLines(-1);
        QCOMPARE(view.document()->findBlockByNumber(0).text(), QStringLiteral("    return 1"));
        QCOMPARE(view.document()->findBlockByNumber(1).text(), QStringLiteral("def f():"));

        // A #! line names the language when the name doesn't
        EditorView script(&m_repo);
        script.setPlainText(QStringLiteral("#!/usr/bin/env bash\necho hi\n"));
        script.pickDefinitionFor(QStringLiteral("deploy"));
        QCOMPARE(script.definition().name(), QStringLiteral("Bash"));

        // Two-space files stay two-space
        EditorView yaml(&m_repo);
        yaml.setPlainText(QStringLiteral("a:\n  b:\n    c: 1\n  d: 2\n"));
        yaml.pickDefinitionFor(QStringLiteral("x.yaml"));
        QCOMPARE(yaml.indentWidth(), 2);
    }
};

QTEST_MAIN(EditorTest)
#include "editor_test.moc"
