#include "snapshotbar.h"
#include "style.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QMessageBox>
#include <QProcess>
#include <QPushButton>
#include <QRegularExpression>
#include <QTimer>
#include <QToolButton>

#include <algorithm>

std::optional<Snapshot> SnapshotMarker::feed(const QString &text)
{
    static const QRegularExpression marker(
        QStringLiteral("\\x1B\\]7766;deckos-snapshot=(home|root):(\\d{1,9})(?:\\x07|\\x1B\\\\)"));
    if (m_tail.isEmpty() && !text.contains(QChar(0x1B)))
        return std::nullopt;  // most output: nothing to look for
    const QString data = m_tail + text;
    std::optional<Snapshot> found;
    qsizetype end = 0;
    for (auto it = marker.globalMatch(data); it.hasNext();) {
        const auto m = it.next();
        found = Snapshot{m.captured(1), m.captured(2).toInt()};
        end = m.capturedEnd();
    }
    // A marker cut by the chunk's end, anywhere in it, is shorter than 64 characters: keep that much
    // (after the last whole one) if an escape is in it.
    const QString rest = data.mid(std::max(end, data.size() - 63));
    m_tail = rest.contains(QChar(0x1B)) ? rest : QString();
    return found;
}

SnapshotBar::SnapshotBar(QWidget *parent)
    : QFrame(parent)
{
    setObjectName(QStringLiteral("snapbar"));
    setAttribute(Qt::WA_StyledBackground, true);
    setStyleSheet(QStringLiteral("#snapbar { background: %1; border-top: 1px solid %2; }")
                      .arg(Style::Surface.name(), Style::Border.name()));
    auto *row = new QHBoxLayout(this);
    row->setContentsMargins(12, 6, 8, 6);
    row->setSpacing(10);
    auto *icon = new QLabel(this);
    icon->setPixmap(Style::pixmap(QStringLiteral("snapshot"), Style::accent(), 18, devicePixelRatioF()));
    row->addWidget(icon);
    m_text = new QLabel(this);
    m_text->setStyleSheet(QStringLiteral("color: %1;").arg(Style::Text.name()));
    row->addWidget(m_text, 1);
    m_undo = new QPushButton(Style::icon(QStringLiteral("undo")), tr("Undo"), this);
    connect(m_undo, &QPushButton::clicked, this, &SnapshotBar::undo);
    row->addWidget(m_undo);
    auto *close = new QToolButton(this);
    close->setIcon(Style::icon(QStringLiteral("close")));
    close->setAutoRaise(true);
    close->setToolTip(tr("Hide (the snapshot stays)"));
    connect(close, &QToolButton::clicked, this, &QWidget::hide);
    row->addWidget(close);
    hide();
}

void SnapshotBar::offer(const Snapshot &snapshot)
{
    ++m_offer;
    m_snapshot = snapshot;
    m_restart = false;
    m_undo->setText(tr("Undo"));
    m_undo->setEnabled(true);
    m_undo->show();
    m_text->setText(snapshot.config == QLatin1String("home")
                        ? tr("Snapshot #%1 is from before that command: Undo puts the deleted files back.").arg(snapshot.number)
                        : tr("Snapshot #%1 is from before that command: Undo takes the system back to it, at the next restart.")
                              .arg(snapshot.number));
    show();
}

void SnapshotBar::undo()
{
    if (m_restart) {
        QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("reboot")});
        return;
    }
    const QString n = QString::number(m_snapshot.number);
    QStringList cmd{QStringLiteral("deckos"), QStringLiteral("restore"), n};
    if (m_snapshot.config != QLatin1String("home")) {
        if (QMessageBox::question(window(), tr("Undo that command?"),
                                  tr("DecKoOS goes back to snapshot #%1 when you restart: everything in the system "
                                     "changed since then goes back too. Your home folder stays as it is.\n\n"
                                     "The system as it is now is kept, so you can change your mind.").arg(n))
            != QMessageBox::Yes)
            return;
        cmd = {QStringLiteral("pkexec"), QStringLiteral("deckos"), QStringLiteral("undo"), n};
    }
    m_undo->setEnabled(false);
    auto *proc = new QProcess(this);
    connect(proc, &QProcess::finished, this, [this, proc, n](int code, QProcess::ExitStatus status) {
        proc->deleteLater();
        m_undo->setEnabled(true);
        const bool ok = status == QProcess::NormalExit && code == 0;
        if (!ok) {
            say(m_snapshot.config == QLatin1String("home")
                    ? tr("Couldn't put the files back: run deckos restore %1 to see why.").arg(n)
                    : tr("Couldn't undo it: run sudo deckos undo %1 to see why.").arg(n),
                false);
        } else if (m_snapshot.config == QLatin1String("home")) {
            m_undo->hide();
            say(tr("Put back: the deleted files are where they were."), true);
        } else {
            m_restart = true;
            m_undo->setText(tr("Restart now"));
            say(tr("Restart to finish: DecKoOS goes back to snapshot #%1.").arg(n), false);
        }
    });
    proc->start(cmd.first(), cmd.mid(1));
}

void SnapshotBar::say(const QString &text, bool hideSoon)
{
    m_text->setText(text);
    if (hideSoon) {
        const int offer = m_offer;  // not if another command was snapshotted meanwhile
        QTimer::singleShot(6000, this, [this, offer] {
            if (offer == m_offer)
                hide();
        });
    }
}
