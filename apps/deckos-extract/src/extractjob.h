// One archive set through 7-Zip: a quick listing (real size, passwords), then the extraction into a hidden
// working folder beside the destination, then the result moved into place. Nothing half done is left behind.
#pragma once

#include "archiveset.h"

#include <QElapsedTimer>
#include <QObject>
#include <QPointer>
#include <QProcess>

class ExtractJob : public QObject
{
    Q_OBJECT
public:
    enum State { Queued, Reading, Running, Paused, NeedsPassword, Done, Failed, Cancelled };
    Q_ENUM(State)

    ExtractJob(const ArchiveSet &set, const QString &destRoot, QObject *parent = nullptr);
    ~ExtractJob() override;

    const ArchiveSet &set() const { return m_set; }
    State state() const { return m_state; }
    QString destRoot() const { return m_destRoot; }
    QString result() const { return m_result; }  // the folder made, once Done
    QString error() const { return m_error; }
    int percent() const { return m_percent; }
    qint64 unpackedBytes() const { return m_unpacked; }  // 0 until the listing has it
    int fileCount() const { return m_files; }
    double bytesPerSecond() const { return m_speed; }
    qint64 secondsLeft() const;
    bool active() const { return m_state == Reading || m_state == Running || m_state == Paused; }
    bool finished() const { return m_state == Done || m_state == Failed || m_state == Cancelled; }

    void start();
    void pause();
    void resume();
    void cancel();
    void retry();
    void setPassword(const QString &password);
    void setTrashAfter(bool on) { m_trashAfter = on; }

    // --demo: a state to show without running anything.
    void setDemo(State state, int percent, qint64 unpacked, double speed, const QString &error = {});

Q_SIGNALS:
    void changed();
    void finishedRun();  // Done, Failed, Cancelled or waiting for a password: the queue moves on

private:
    void list();
    void extract();
    void onListed(int code);
    void onExtracted(int code);
    void onOutput();
    void place();
    void fail(const QString &message);
    void setState(State s);
    QString explain(const QString &out) const;
    QStringList passwordArgs() const;

    ArchiveSet m_set;
    QString m_destRoot;
    QString m_staging;
    QString m_result;
    QString m_error;
    QString m_password;
    QByteArray m_output;  // everything 7-Zip said, for the error
    QPointer<QProcess> m_proc;
    QElapsedTimer m_clock;
    qint64 m_pausedMs = 0;
    QElapsedTimer m_pauseClock;
    State m_state = Queued;
    int m_percent = 0;
    int m_files = 0;
    qint64 m_unpacked = 0;
    double m_speed = 0;
    bool m_encrypted = false;
    bool m_trashAfter = false;
};
