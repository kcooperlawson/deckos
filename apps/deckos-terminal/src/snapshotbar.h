// Snapshot first's Undo bar. In DecKoOS Terminal, the shell (snapshot-first.bash) follows a command it
// snapshotted with a private OSC, ESC ] 7766 ; deckos-snapshot=home:16 BEL, which the emulation
// ignores; SnapshotMarker finds it in the pane's raw output and SnapshotBar offers the undo.
#pragma once

#include <QFrame>
#include <QString>

#include <optional>

class QLabel;
class QPushButton;

struct Snapshot
{
    QString config;  // home: deckos restore N (files, no restart); root: deckos undo N (restart)
    int number = 0;
    bool operator==(const Snapshot &) const = default;
};

class SnapshotMarker
{
public:
    // The output just received; the last marker in it, if any. Output arrives in chunks, so the
    // end of one is kept in case a marker is split across two.
    std::optional<Snapshot> feed(const QString &text);

private:
    QString m_tail;
};

class SnapshotBar : public QFrame
{
    Q_OBJECT
public:
    explicit SnapshotBar(QWidget *parent = nullptr);
    void offer(const Snapshot &snapshot);

private:
    void undo();
    void say(const QString &text, bool hideSoon);

    Snapshot m_snapshot;
    QLabel *m_text;
    QPushButton *m_undo;
    bool m_restart = false;  // the system undo is done: the button restarts
    int m_offer = 0;
};
