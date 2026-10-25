// DecKoOS Terminal: copy, paste and Snapshot first's Undo bar through the real window, offscreen.
// Keys go through Qt's shortcut handling as from a keyboard (QTest), into a real bash.
// Run: QT_QPA_PLATFORM=offscreen ./keys_test
#include "mainwindow.h"
#include "modewatch.h"
#include "snapshotbar.h"
#include "tabpage.h"
#include "terminalpane.h"

#include <QApplication>
#include <QClipboard>
#include <QContextMenuEvent>
#include <QElapsedTimer>
#include <QFile>
#include <QLabel>
#include <QMenu>
#include <QPushButton>
#include <QTemporaryDir>

#include <algorithm>
#include <QTest>
#include <QTimer>

#include <qtermwidget.h>

namespace {

int failures = 0;

void check(bool ok, const char *what)
{
    fprintf(stderr, "%s %s\n", ok ? "PASS" : "FAIL", what);
    failures += ok ? 0 : 1;
}

// Spin the event loop until cond() or the timeout.
bool waitFor(const std::function<bool()> &cond, int ms = 8000)
{
    QElapsedTimer t;
    t.start();
    while (!cond() && t.elapsed() < ms)
        QTest::qWait(50);
    return cond();
}

// Everything the shell printed so far (escape sequences included).
QString output;

QString screen(QTermWidget *term)
{
    term->setSelectionStart(0, 0);
    term->setSelectionEnd(term->screenLinesCount(), term->screenColumnsCount());
    return term->selectedText();
}

void clearSelection(QWidget *keys)
{
    QTest::mouseClick(keys, Qt::LeftButton, {}, QPoint(keys->width() - 20, keys->height() - 10));
}

// The display: the widget that gets the keys.
QWidget *display(QTermWidget *term)
{
    QWidget *best = term;
    for (QWidget *w : term->findChildren<QWidget *>())
        if (w->focusPolicy() != Qt::NoFocus && w->width() * w->height() > best->width() * best->height() / 2)
            best = w;
    return best;
}

// Selects the first screen line that contains `text`, from its start.
bool select(QTermWidget *term, const QString &text)
{
    const QStringList lines = screen(term).split(QLatin1Char('\n'));
    for (int row = 0; row < lines.size(); ++row) {
        const int col = lines[row].indexOf(text);
        if (col >= 0 && !lines[row].contains(QStringLiteral("echo"))) {
            term->setSelectionStart(row, col);
            term->setSelectionEnd(row, col + text.size() - 1);
            return true;
        }
    }
    return false;
}

} // namespace

int main(int argc, char **argv)
{
    qputenv("PS1", "$ ");
    QApplication app(argc, argv);
    ModeWatch modes;
    MainWindow w(&modes, QDir::tempPath(), {QStringLiteral("bash"), QStringLiteral("--norc"), QStringLiteral("-i")});
    w.resize(1000, 600);
    w.show();
    if (!QTest::qWaitForWindowExposed(&w))
        return 1;
    TerminalPane *pane = w.currentPage()->activePane();
    QTermWidget *term = pane->term();
    QWidget *keys = display(term);
    keys->setFocus();
    if (qEnvironmentVariableIsSet("KEYS_DEBUG"))
        for (QWidget *w : term->findChildren<QWidget *>())
            fprintf(stderr, "child %s %dx%d\n", w->metaObject()->className(), w->width(), w->height());
    QObject::connect(term, &QTermWidget::receivedData, [](const QString &text) { output += text; });
    QTest::qWait(500);

    // Copy: Ctrl+Shift+C with a selection
    term->sendText(QStringLiteral("echo copy-me-$((40+2))\n"));
    check(waitFor([&] { return output.contains(QStringLiteral("copy-me-42")); }), "the shell runs");
    QGuiApplication::clipboard()->setText(QStringLiteral("old"));
    check(select(term, QStringLiteral("copy-me-42")), "text selected");
    QTest::keyClick(keys, Qt::Key_C, Qt::ControlModifier | Qt::ShiftModifier);
    check(QGuiApplication::clipboard()->text() == QStringLiteral("copy-me-42"), "Ctrl+Shift+C copies the selection");

    // Paste: Ctrl+Shift+V types the clipboard into the shell
    QGuiApplication::clipboard()->setText(QStringLiteral("echo pasted-$((6*7))"));
    QTest::keyClick(keys, Qt::Key_V, Qt::ControlModifier | Qt::ShiftModifier);
    QTest::keyClick(keys, Qt::Key_Return);
    check(waitFor([&] { return output.contains(QStringLiteral("pasted-42")); }), "Ctrl+Shift+V pastes into the shell");

    // Ctrl+C with a selection copies; without one it still interrupts the program
    check(select(term, QStringLiteral("pasted-42")), "text selected again");
    QGuiApplication::clipboard()->setText(QStringLiteral("old"));
    QTest::keyClick(keys, Qt::Key_C, Qt::ControlModifier);
    check(QGuiApplication::clipboard()->text() == QStringLiteral("pasted-42"), "Ctrl+C with a selection copies");
    clearSelection(keys);
    term->sendText(QStringLiteral("sleep 30; echo not-$((0))-interrupted\n"));
    QTest::qWait(400);
    QTest::keyClick(keys, Qt::Key_C, Qt::ControlModifier);
    term->sendText(QStringLiteral("echo interrupted-$((1+1))\n"));
    check(waitFor([&] { return output.contains(QStringLiteral("interrupted-2")); }, 4000)
              && !output.contains(QStringLiteral("not-0-interrupted")),
          "Ctrl+C without a selection interrupts");

    // Ctrl+V pastes too
    QGuiApplication::clipboard()->setText(QStringLiteral("echo ctrlv-$((5+5))"));
    QTest::keyClick(keys, Qt::Key_V, Qt::ControlModifier);
    QTest::keyClick(keys, Qt::Key_Return);
    check(waitFor([&] { return output.contains(QStringLiteral("ctrlv-10")); }), "Ctrl+V pastes");

    // Right-click: a menu with Copy, Paste and the rest; its Paste types the clipboard in
    QGuiApplication::clipboard()->setText(QStringLiteral("echo menu-$((3*3))"));
    int requests = 0;
    QObject::connect(term, &QWidget::customContextMenuRequested, [&] { ++requests; });
    // what the platform sends for a right-click: the press and release, then a context menu event
    const QPoint at(keys->width() / 2, keys->height() / 2);
    QTest::mouseClick(keys, Qt::RightButton, {}, at);
    QContextMenuEvent ctx(QContextMenuEvent::Mouse, at, keys->mapToGlobal(at));
    QApplication::sendEvent(keys, &ctx);
    QMenu *menu = nullptr;
    check(waitFor([&] { return (menu = qobject_cast<QMenu *>(QApplication::activePopupWidget())); }, 3000),
          "right-click opens a menu");
    QStringList names;
    QAction *pasteAction = nullptr;
    if (menu) {
        for (QAction *a : menu->actions()) {
            names << a->text();
            if (a->text() == QStringLiteral("Paste"))
                pasteAction = a;
        }
    }
    fprintf(stderr, "menu: %s\n", qPrintable(names.join(QStringLiteral(" | "))));
    check(names.contains(QStringLiteral("Copy")) && pasteAction && pasteAction->isEnabled(), "the menu has Copy and Paste");
    check(requests == 1, "one menu per right-click");
    if (pasteAction) {
        pasteAction->trigger();
        menu->close();
    }
    QTest::keyClick(keys, Qt::Key_Return);
    check(waitFor([&] { return output.contains(QStringLiteral("menu-9")); }), "the menu's Paste pastes");

    // Snapshot first: the shell's marker shows the Undo bar, and nothing on screen
    auto *bar = pane->findChild<SnapshotBar *>();
    check(bar && !bar->isVisible(), "no Undo bar to begin with");
    // quoted apart, so the command line as typed doesn't contain what the checks look for
    term->sendText(QStringLiteral("printf '\\033]7766;deckos-snap''shot=home:16\\007'; echo marker-sent\n"));
    check(waitFor([&] { return bar && bar->isVisible(); }), "the marker shows the Undo bar");
    if (qEnvironmentVariableIsSet("KEYS_DEBUG")) {
        const qsizetype at = output.lastIndexOf(QStringLiteral("7766"));
        fprintf(stderr, "around the marker: %s\n", output.mid(at - 20, 80).toUtf8().toPercentEncoding(" ;=:'").constData());
    }
    check(waitFor([&] { return output.contains(QStringLiteral("marker-sent\r")); })
              && !screen(term).contains(QStringLiteral("deckos-snapshot")), "the marker isn't printed");

    // Undo on a home snapshot runs deckos restore N (a fake deckos here) and says it's done
    QTemporaryDir fake;
    QFile script(fake.filePath(QStringLiteral("deckos")));
    script.open(QIODevice::WriteOnly);
    script.write(QStringLiteral("#!/bin/sh\necho \"$@\" > %1/ran\n").arg(fake.path()).toUtf8());
    script.close();
    script.setPermissions(script.permissions() | QFileDevice::ExeOwner);
    qputenv("PATH", QByteArray(fake.path().toUtf8() + ':' + qgetenv("PATH")));
    QPushButton *undoButton = nullptr;
    if (bar)
        for (QPushButton *b : bar->findChildren<QPushButton *>())
            if (b->text() == QStringLiteral("Undo"))
                undoButton = b;
    if (undoButton)
        QTest::mouseClick(undoButton, Qt::LeftButton);
    check(waitFor([&] { return QFile::exists(fake.filePath(QStringLiteral("ran"))); }, 4000), "Undo runs deckos");
    QFile ran(fake.filePath(QStringLiteral("ran")));
    check(ran.open(QIODevice::ReadOnly) && ran.readAll().trimmed() == "restore 16", "...as deckos restore 16");
    check(waitFor([&] {
              const auto labels = bar->findChildren<QLabel *>();
              return std::any_of(labels.begin(), labels.end(), [](QLabel *l) { return l->text().startsWith(QStringLiteral("Put back")); });
          }, 4000),
          "the bar says the files are back");

    // A marker split across two reads still counts
    SnapshotMarker m;
    check(!m.feed(QStringLiteral("abc\x1B]77")).has_value(), "half a marker: nothing yet");
    const auto split = m.feed(QStringLiteral("66;deckos-snapshot=root:9\x07 more"));
    check(split && split->config == QStringLiteral("root") && split->number == 9, "the other half completes it");
    check(!m.feed(QStringLiteral("\x1B]7766;deckos-snapshot=evil:1\x07")).has_value(), "unknown configs are ignored");

    fprintf(stderr, "%d failure(s)\n", failures);
    QTimer::singleShot(0, [] { QApplication::exit(failures ? 1 : 0); });
    return app.exec();
}
