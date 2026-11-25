#include "jobcard.h"
#include "extractjob.h"
#include "style.h"

#include <QDir>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QLocale>
#include <QPainter>
#include <QPainterPath>
#include <QPushButton>
#include <QToolButton>
#include <QVBoxLayout>

namespace {

constexpr int Notch = 12;
constexpr int Segments = 40;
constexpr int MeterH = 8;

QString shortPath(const QString &path)
{
    const QString home = QDir::homePath();
    return path.startsWith(home) ? QStringLiteral("~") + path.mid(home.size()) : path;
}

QString duration(qint64 s)
{
    if (s < 60)
        return QObject::tr("under a minute left");
    if (s < 3600)
        return QObject::tr("%1 min left").arg((s + 59) / 60);
    return QObject::tr("%1 h %2 min left").arg(s / 3600).arg((s % 3600) / 60);
}

// The DecKo plate: cut corners top right and bottom left.
QPainterPath plate(const QRectF &r)
{
    QPainterPath p;
    p.moveTo(r.left(), r.top());
    p.lineTo(r.right() - Notch, r.top());
    p.lineTo(r.right(), r.top() + Notch);
    p.lineTo(r.right(), r.bottom());
    p.lineTo(r.left() + Notch, r.bottom());
    p.lineTo(r.left(), r.bottom() - Notch);
    p.closeSubpath();
    return p;
}

QToolButton *iconButton(const QString &icon, const QString &tip, QWidget *parent)
{
    auto *b = new QToolButton(parent);
    b->setIcon(Style::icon(icon));
    b->setIconSize(QSize(18, 18));
    b->setToolTip(tip);
    b->setAutoRaise(true);
    return b;
}

} // namespace

JobCard::JobCard(ExtractJob *job, QWidget *parent)
    : QFrame(parent)
    , m_job(job)
{
    setAttribute(Qt::WA_TranslucentBackground);
    auto *outer = new QVBoxLayout(this);
    outer->setContentsMargins(18, 14, 18, 14 + MeterH + 10);  // the meter is painted under the text
    outer->setSpacing(4);

    auto *top = new QHBoxLayout;
    top->setSpacing(12);
    auto *icon = new QLabel(this);
    icon->setFixedSize(40, 40);
    icon->setAlignment(Qt::AlignCenter);
    icon->setPixmap(Style::pixmap(QStringLiteral("package"), Style::accent(), 22, devicePixelRatioF()));
    icon->setStyleSheet(QStringLiteral("background: rgba(%1,%2,%3,40); border-radius: 2px;")
                            .arg(Style::accent().red()).arg(Style::accent().green()).arg(Style::accent().blue()));
    top->addWidget(icon, 0, Qt::AlignTop);

    auto *text = new QVBoxLayout;
    text->setSpacing(2);
    m_name = new QLabel(this);
    m_name->setObjectName(QStringLiteral("title"));
    m_name->setTextFormat(Qt::PlainText);
    m_detail = new QLabel(this);
    m_detail->setObjectName(QStringLiteral("sub"));
    m_detail->setTextFormat(Qt::PlainText);
    text->addWidget(m_name);
    text->addWidget(m_detail);
    top->addLayout(text, 1);

    m_open = new QPushButton(tr("Open folder"), this);
    m_open->setObjectName(QStringLiteral("primary"));
    m_retry = iconButton(QStringLiteral("refresh"), tr("Try again"), this);
    m_pause = iconButton(QStringLiteral("pause"), tr("Pause"), this);
    m_stop = iconButton(QStringLiteral("close"), tr("Cancel"), this);
    for (QWidget *w : {static_cast<QWidget *>(m_open), static_cast<QWidget *>(m_retry), static_cast<QWidget *>(m_pause),
                       static_cast<QWidget *>(m_stop)})
        top->addWidget(w, 0, Qt::AlignTop);
    outer->addLayout(top);

    m_passRow = new QWidget(this);
    auto *pr = new QHBoxLayout(m_passRow);
    pr->setContentsMargins(52, 6, 0, 0);
    m_pass = new QLineEdit(m_passRow);
    m_pass->setEchoMode(QLineEdit::Password);
    m_pass->setPlaceholderText(tr("Password"));
    auto *unlock = new QPushButton(tr("Unlock"), m_passRow);
    unlock->setObjectName(QStringLiteral("primary"));
    pr->addWidget(m_pass, 1);
    pr->addWidget(unlock);
    outer->addWidget(m_passRow);

    m_status = new QLabel(this);
    m_status->setObjectName(QStringLiteral("sub"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    m_status->setContentsMargins(52, 4, 0, 0);
    outer->addWidget(m_status);

    auto submit = [this] {
        if (m_pass->text().isEmpty())
            return;
        m_job->setPassword(m_pass->text());
        m_pass->clear();
        Q_EMIT retried();
    };
    connect(unlock, &QPushButton::clicked, this, submit);
    connect(m_pass, &QLineEdit::returnPressed, this, submit);
    connect(m_pause, &QToolButton::clicked, this, [this] {
        m_job->state() == ExtractJob::Paused ? m_job->resume() : m_job->pause();
    });
    connect(m_stop, &QToolButton::clicked, this, [this] {
        if (m_job->finished() || m_job->state() == ExtractJob::NeedsPassword)
            Q_EMIT removeRequested(this);
        else
            m_job->cancel();
    });
    connect(m_retry, &QToolButton::clicked, this, [this] {
        m_job->retry();
        Q_EMIT retried();
    });
    connect(m_open, &QPushButton::clicked, this, [this] { Q_EMIT openRequested(m_job->result()); });
    connect(job, &ExtractJob::changed, this, &JobCard::refresh);
    refresh();
}

void JobCard::refresh()
{
    const ArchiveSet &s = m_job->set();
    m_name->setText(s.name);
    const QLocale loc;
    QStringList bits;
    if (s.split())
        bits << tr("%n parts", nullptr, int(s.parts.size()));
    bits << loc.formattedDataSize(s.bytes);
    if (m_job->unpackedBytes() > 0)
        bits << tr("%1 unpacked").arg(loc.formattedDataSize(m_job->unpackedBytes()));
    bits << QStringLiteral("→ ") + shortPath(m_job->destRoot());
    m_detail->setText(bits.join(QStringLiteral("  ·  ")));

    const auto st = m_job->state();
    QString status;
    switch (st) {
    case ExtractJob::Queued: status = tr("Waiting its turn"); break;
    case ExtractJob::Reading: status = tr("Reading the archive…"); break;
    case ExtractJob::Running: {
        status = QStringLiteral("%1%").arg(m_job->percent());
        if (m_job->bytesPerSecond() > 0)
            status += QStringLiteral("  ·  ") + loc.formattedDataSize(qint64(m_job->bytesPerSecond())) + QStringLiteral("/s");
        if (const qint64 left = m_job->secondsLeft(); left >= 0)
            status += QStringLiteral("  ·  ") + duration(left);
        break;
    }
    case ExtractJob::Paused: status = tr("Paused at %1%").arg(m_job->percent()); break;
    case ExtractJob::NeedsPassword:
        status = m_job->error().isEmpty() ? tr("This archive is locked with a password.") : m_job->error();
        break;
    case ExtractJob::Done: status = tr("Done  ·  %1").arg(shortPath(m_job->result())); break;
    case ExtractJob::Failed: status = m_job->error(); break;
    case ExtractJob::Cancelled: status = tr("Cancelled. Nothing was left behind."); break;
    }
    m_status->setText(status);
    m_status->setStyleSheet(st == ExtractJob::Failed ? QStringLiteral("color: %1;").arg(Style::Danger.name())
                            : st == ExtractJob::NeedsPassword ? QStringLiteral("color: %1;").arg(Style::Warning.name())
                                                              : QString());

    m_passRow->setVisible(st == ExtractJob::NeedsPassword);
    m_open->setVisible(st == ExtractJob::Done);
    m_retry->setVisible(st == ExtractJob::Failed || st == ExtractJob::Cancelled);
    m_pause->setVisible(st == ExtractJob::Running || st == ExtractJob::Paused);
    m_pause->setIcon(Style::icon(st == ExtractJob::Paused ? QStringLiteral("play") : QStringLiteral("pause")));
    m_pause->setToolTip(st == ExtractJob::Paused ? tr("Resume") : tr("Pause"));
    const bool removable = m_job->finished() || st == ExtractJob::NeedsPassword;
    m_stop->setToolTip(removable ? tr("Remove from the list") : tr("Cancel"));
    update();
}

void JobCard::paintEvent(QPaintEvent *)
{
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    const QRectF r = QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5);
    const auto st = m_job->state();
    const bool lit = st == ExtractJob::Running || st == ExtractJob::Reading;
    p.fillPath(plate(r), Style::Surface);
    if (lit) {
        QLinearGradient g(r.topLeft(), r.bottomRight());
        g.setColorAt(0, Style::accent());
        g.setColorAt(1, Style::accentPartner());
        p.setPen(QPen(QBrush(g), 1));
    } else {
        p.setPen(QPen(Style::Border, 1));
    }
    p.drawPath(plate(r));

    // The segmented meter: LEDs along the bottom, lit up to the percent.
    const QColor done = st == ExtractJob::Failed      ? Style::Danger
                        : st == ExtractJob::Paused    ? Style::Warning
                        : st == ExtractJob::Cancelled ? Style::Muted
                                                      : QColor();
    const qreal left = 18 + 52, right = width() - 18 - Notch;
    const qreal y = height() - 14 - MeterH;
    const qreal gap = 3, w = (right - left - gap * (Segments - 1)) / Segments;
    const int on = st == ExtractJob::Done ? Segments : int(m_job->percent() / 100.0 * Segments + 0.5);
    for (int i = 0; i < Segments; ++i) {
        const QRectF seg(left + i * (w + gap), y, w, MeterH);
        QColor c;
        if (i < on) {
            if (done.isValid()) {
                c = done;
            } else {
                const qreal t = Segments > 1 ? qreal(i) / (Segments - 1) : 0;
                const QColor a = Style::accent(), b = Style::accentPartner();
                c = QColor::fromRgbF(a.redF() + (b.redF() - a.redF()) * t, a.greenF() + (b.greenF() - a.greenF()) * t,
                                     a.blueF() + (b.blueF() - a.blueF()) * t);
            }
        } else {
            c = Style::Border;
        }
        p.fillRect(seg, c);
    }
}
