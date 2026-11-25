#include "mainwindow.h"
#include "archiveset.h"
#include "extractjob.h"
#include "jobcard.h"
#include "style.h"

#include <QCheckBox>
#include <QCloseEvent>
#include <QComboBox>
#include <QDesktopServices>
#include <QDir>
#include <QDragEnterEvent>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QLabel>
#include <QMessageBox>
#include <QMimeData>
#include <QPainter>
#include <QPushButton>
#include <QScrollArea>
#include <QStackedWidget>
#include <QStandardPaths>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>

#include <KConfigGroup>
#include <KNotification>
#include <KSharedConfig>

namespace {

enum DestMode { NextToArchive, Downloads, Folder };

KConfigGroup settings()
{
    return KSharedConfig::openConfig(QStringLiteral("deckos-extractrc"))->group(QStringLiteral("General"));
}

// The empty queue: a dashed drop target.
class DropZone : public QWidget
{
public:
    using QWidget::QWidget;

protected:
    void paintEvent(QPaintEvent *) override
    {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const QRectF r = QRectF(rect()).adjusted(24.5, 12.5, -24.5, -24.5);
        p.setPen(QPen(Style::Border, 1.5, Qt::DashLine));
        p.drawRoundedRect(r, Style::Radius, Style::Radius);
        const qreal dpr = devicePixelRatioF();
        const QPixmap icon = Style::pixmap(QStringLiteral("download"), Style::accent(), 44, dpr);
        const QPointF c = r.center();
        p.drawPixmap(QPointF(c.x() - 22, c.y() - 70), icon);
        QFont f = font();
        f.setPointSizeF(f.pointSizeF() * 1.35);
        f.setWeight(QFont::DemiBold);
        p.setFont(f);
        p.setPen(Style::Text);
        p.drawText(QRectF(r.left(), c.y() - 14, r.width(), 30), Qt::AlignCenter, tr("Drop archives here"));
        p.setFont(font());
        p.setPen(Style::Subtext);
        p.drawText(QRectF(r.left(), c.y() + 18, r.width(), 22), Qt::AlignCenter,
                   tr("Any part of a split archive brings the rest: .part1.rar, .r00, .7z.001, .z01"));
        p.drawText(QRectF(r.left(), c.y() + 40, r.width(), 22), Qt::AlignCenter, tr("RAR, 7z, zip, tar, ISO and more"));
    }
};

} // namespace

MainWindow::MainWindow(bool demo, QWidget *parent)
    : QWidget(parent)
    , m_demo(demo)
{
    setWindowTitle(tr("DecKoOS Extract"));
    setWindowIcon(QIcon::fromTheme(QStringLiteral("deckos-extract"), QIcon::fromTheme(QStringLiteral("ark"))));
    setAcceptDrops(true);
    setStyleSheet(Style::chromeQss() + QStringLiteral(R"(
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QComboBox { background: #171A21; border: 1px solid #262B36; border-radius: 7px; padding: 5px 10px; color: #E8EAF0; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: #171A21; color: #E8EAF0; selection-background-color: #2A2F3B; border: 1px solid #262B36; }
QCheckBox { spacing: 8px; color: #E8EAF0; }
)"));
    resize(820, 600);
    QTimer::singleShot(0, this, [this] { Style::attachBeat(this); });

    auto *root = new QVBoxLayout(this);
    root->setContentsMargins(0, 0, 0, 0);
    root->setSpacing(0);

    auto *header = new QWidget(this);
    auto *hl = new QHBoxLayout(header);
    hl->setContentsMargins(24, 20, 24, 12);
    auto *titles = new QVBoxLayout;
    titles->setSpacing(2);
    auto *kicker = new QLabel(Style::kicker(tr("DecKoOS")), header);
    kicker->setObjectName(QStringLiteral("kicker"));
    auto *title = new QLabel(tr("Extract"), header);
    QFont tf = title->font();
    tf.setPointSizeF(tf.pointSizeF() * 1.8);
    tf.setWeight(QFont::DemiBold);
    title->setFont(tf);
    titles->addWidget(kicker);
    titles->addWidget(title);
    hl->addLayout(titles);
    hl->addStretch(1);
    auto *addBtn = new QPushButton(Style::icon(QStringLiteral("plus")), tr("Add archives"), header);
    addBtn->setObjectName(QStringLiteral("primary"));
    hl->addWidget(addBtn);
    root->addWidget(header);

    auto *options = new QWidget(this);
    auto *ol = new QHBoxLayout(options);
    ol->setContentsMargins(24, 0, 24, 14);
    ol->setSpacing(10);
    auto *toLabel = new QLabel(tr("Extract to"), options);
    toLabel->setObjectName(QStringLiteral("sub"));
    m_dest = new QComboBox(options);
    m_dest->addItem(Style::icon(QStringLiteral("folder")), tr("Next to the archive"));
    m_dest->addItem(Style::icon(QStringLiteral("download")), tr("Downloads"));
    m_dest->addItem(Style::icon(QStringLiteral("folder-plus")), tr("Choose a folder…"));
    m_trash = new QCheckBox(tr("Move archives to the trash after"), options);
    m_openAfter = new QCheckBox(tr("Open the folder when done"), options);
    ol->addWidget(toLabel);
    ol->addWidget(m_dest);
    ol->addSpacing(12);
    ol->addWidget(m_trash);
    ol->addWidget(m_openAfter);
    ol->addStretch(1);
    root->addWidget(options);

    auto *line = new QFrame(this);
    line->setFixedHeight(1);
    line->setStyleSheet(QStringLiteral("background: #262B36;"));
    root->addWidget(line);

    m_stack = new QStackedWidget(this);
    m_stack->addWidget(new DropZone(m_stack));
    auto *scroll = new QScrollArea(m_stack);
    scroll->setWidgetResizable(true);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    auto *holder = new QWidget(scroll);
    m_list = new QVBoxLayout(holder);
    m_list->setContentsMargins(24, 16, 24, 16);
    m_list->setSpacing(10);
    m_list->addStretch(1);
    scroll->setWidget(holder);
    m_stack->addWidget(scroll);
    root->addWidget(m_stack, 1);

    auto *footer = new QWidget(this);
    footer->setStyleSheet(QStringLiteral("background: #0B0D11;"));
    auto *fl = new QHBoxLayout(footer);
    fl->setContentsMargins(24, 8, 24, 8);
    m_summary = new QLabel(footer);
    m_summary->setObjectName(QStringLiteral("sub"));
    auto *clear = new QPushButton(tr("Clear finished"), footer);
    fl->addWidget(m_summary, 1);
    fl->addWidget(clear);
    root->addWidget(footer);

    // Settings
    const KConfigGroup g = settings();
    m_folder = g.readEntry("Folder", QString());
    const int mode = g.readEntry("Destination", int(NextToArchive));
    m_dest->setCurrentIndex(mode == Folder && m_folder.isEmpty() ? NextToArchive : mode);
    if (!m_folder.isEmpty())
        m_dest->setItemText(Folder, QDir(m_folder).dirName());
    m_trash->setChecked(g.readEntry("TrashAfter", false));
    m_openAfter->setChecked(g.readEntry("OpenAfter", false));

    connect(addBtn, &QPushButton::clicked, this, [this] {
        const QStringList files = QFileDialog::getOpenFileNames(
            this, tr("Add archives"), QStandardPaths::writableLocation(QStandardPaths::DownloadLocation),
            tr("Archives (*.rar *.r[0-9][0-9] *.7z *.zip *.z[0-9][0-9] *.[0-9][0-9][0-9] *.tar *.tar.* *.tgz *.txz *.gz *.xz *.zst *.bz2 *.iso *.cab);;All files (*)"));
        add(files);
    });
    connect(m_dest, &QComboBox::activated, this, [this](int i) {
        if (i == Folder)
            chooseFolder();
        saveSettings();
    });
    connect(m_trash, &QCheckBox::toggled, this, [this] { saveSettings(); });
    connect(m_openAfter, &QCheckBox::toggled, this, [this] { saveSettings(); });
    connect(clear, &QPushButton::clicked, this, [this] {
        for (JobCard *c : QList<JobCard *>(m_cards))
            if (c->job()->state() == ExtractJob::Done || c->job()->state() == ExtractJob::Cancelled)
                remove(c);
    });
    updateSummary();
}

void MainWindow::chooseFolder()
{
    const QString dir = QFileDialog::getExistingDirectory(this, tr("Extract to"), m_folder.isEmpty() ? QDir::homePath() : m_folder);
    if (dir.isEmpty()) {
        if (m_folder.isEmpty())
            m_dest->setCurrentIndex(NextToArchive);
        return;
    }
    m_folder = dir;
    m_dest->setItemText(Folder, QDir(dir).dirName());
}

void MainWindow::saveSettings() const
{
    if (m_demo)
        return;
    KConfigGroup g = settings();
    g.writeEntry("Destination", m_dest->currentIndex());
    g.writeEntry("Folder", m_folder);
    g.writeEntry("TrashAfter", m_trash->isChecked());
    g.writeEntry("OpenAfter", m_openAfter->isChecked());
    g.sync();
}

QString MainWindow::destinationFor(const QString &first) const
{
    switch (m_dest->currentIndex()) {
    case Downloads: return QStandardPaths::writableLocation(QStandardPaths::DownloadLocation);
    case Folder:
        if (!m_folder.isEmpty())
            return m_folder;
        break;
    }
    return QFileInfo(first).absolutePath();
}

void MainWindow::add(const QStringList &paths, const QString &dest)
{
    const QList<ArchiveSet> sets = Archives::group(paths);
    if (sets.isEmpty()) {
        if (!paths.isEmpty())
            QMessageBox::information(this, tr("Nothing to extract"), tr("None of those look like archives DecKoOS Extract can open."));
        return;
    }
    for (const ArchiveSet &s : sets) {
        // The same set twice (dropped again while it runs) only once.
        bool dup = false;
        for (JobCard *c : std::as_const(m_cards))
            if (c->job()->set().parts == s.parts && !c->job()->finished())
                dup = true;
        if (dup)
            continue;
        auto *job = new ExtractJob(s, dest.isEmpty() ? destinationFor(s.first.isEmpty() ? s.parts.first() : s.first) : dest, this);
        auto *card = new JobCard(job, this);
        m_cards << card;
        m_list->insertWidget(m_list->count() - 1, card);
        connect(job, &ExtractJob::changed, this, &MainWindow::updateSummary);
        connect(job, &ExtractJob::finishedRun, this, [this, job] {
            if (job->state() == ExtractJob::Done && m_openAfter->isChecked() && !m_demo)
                QDesktopServices::openUrl(QUrl::fromLocalFile(job->result()));
            if (!isActiveWindow() && !m_demo && (job->state() == ExtractJob::Done || job->state() == ExtractJob::Failed ||
                                                job->state() == ExtractJob::NeedsPassword)) {
                const QString text = job->state() == ExtractJob::Done ? tr("%1 is ready.").arg(job->set().name)
                                                                      : job->set().name + QStringLiteral(": ") + job->error();
                KNotification::event(job->state() == ExtractJob::Done ? QStringLiteral("deckos-extract") : QStringLiteral("dialog-warning"),
                                     tr("DecKoOS Extract"), text.trimmed());
            }
            QTimer::singleShot(0, this, &MainWindow::next);
        });
        connect(card, &JobCard::removeRequested, this, &MainWindow::remove);
        connect(card, &JobCard::openRequested, this, [](const QString &folder) {
            QDesktopServices::openUrl(QUrl::fromLocalFile(folder));
        });
        connect(card, &JobCard::retried, this, &MainWindow::next);
    }
    m_stack->setCurrentIndex(m_cards.isEmpty() ? 0 : 1);
    updateSummary();
    if (!m_demo)
        next();
}

void MainWindow::next()
{
    for (JobCard *c : std::as_const(m_cards))
        if (c->job()->active())
            return;
    for (JobCard *c : std::as_const(m_cards)) {
        if (c->job()->state() == ExtractJob::Queued) {
            c->job()->setTrashAfter(m_trash->isChecked());
            c->job()->start();
            return;
        }
    }
}

void MainWindow::remove(JobCard *card)
{
    card->job()->cancel();
    m_cards.removeOne(card);
    card->job()->deleteLater();
    card->deleteLater();
    m_stack->setCurrentIndex(m_cards.isEmpty() ? 0 : 1);
    updateSummary();
}

void MainWindow::updateSummary()
{
    int done = 0, waiting = 0, problems = 0;
    const ExtractJob *running = nullptr;
    for (JobCard *c : std::as_const(m_cards)) {
        switch (c->job()->state()) {
        case ExtractJob::Done: ++done; break;
        case ExtractJob::Queued: ++waiting; break;
        case ExtractJob::Failed:
        case ExtractJob::NeedsPassword: ++problems; break;
        case ExtractJob::Reading:
        case ExtractJob::Running:
        case ExtractJob::Paused: running = c->job(); break;
        default: break;
        }
    }
    QStringList bits;
    if (m_cards.isEmpty())
        bits << tr("Nothing queued");
    if (done)
        bits << tr("%n done", nullptr, done);
    if (running)
        bits << tr("1 extracting");
    if (waiting)
        bits << tr("%n waiting", nullptr, waiting);
    if (problems)
        bits << tr("%n need you", nullptr, problems);
    m_summary->setText(bits.join(QStringLiteral("  ·  ")));
    setWindowTitle(running && running->state() == ExtractJob::Running
                       ? QStringLiteral("%1% · %2 — DecKoOS Extract").arg(running->percent()).arg(running->set().name)
                       : tr("DecKoOS Extract"));
}

void MainWindow::dragEnterEvent(QDragEnterEvent *e)
{
    if (e->mimeData()->hasUrls())
        e->acceptProposedAction();
}

void MainWindow::dropEvent(QDropEvent *e)
{
    QStringList paths;
    for (const QUrl &u : e->mimeData()->urls())
        if (u.isLocalFile())
            paths << u.toLocalFile();
    add(paths);
}

void MainWindow::closeEvent(QCloseEvent *e)
{
    bool busy = false;
    for (JobCard *c : std::as_const(m_cards))
        busy |= c->job()->active() || c->job()->state() == ExtractJob::Queued;
    if (busy && !m_demo &&
        QMessageBox::question(this, tr("Stop extracting?"),
                              tr("Closing stops what's extracting and clears what's waiting. Finished folders stay.")) != QMessageBox::Yes) {
        e->ignore();
        return;
    }
    for (JobCard *c : std::as_const(m_cards))
        c->job()->cancel();
    e->accept();
}

void MainWindow::addDemo()
{
    const QString dl = QDir::homePath() + QStringLiteral("/Downloads");
    struct D { const char *name; int parts; double gb; ExtractJob::State st; int pct; double unpacked; double speed; const char *err; };
    const D demo[] = {
        {"Open Source Game Collection", 14, 38.6, ExtractJob::Running, 62, 41.2, 612e6, ""},
        {"Blender Demo Files", 1, 4.1, ExtractJob::Queued, 0, 0, 0, ""},
        {"Family Photos 2024", 3, 2.7, ExtractJob::NeedsPassword, 0, 0, 0, ""},
        {"Linux ISO Mirror", 8, 11.9, ExtractJob::Failed, 37, 12.4, 0, "Part 6 is missing. Put every part in the same folder and try again."},
        {"Soundtrack FLAC", 1, 1.3, ExtractJob::Done, 100, 1.4, 0, ""},
    };
    for (const D &d : demo) {
        ArchiveSet s;
        s.name = QString::fromUtf8(d.name);
        s.first = dl + QLatin1Char('/') + s.name + QStringLiteral(".part1.rar");
        for (int i = 0; i < d.parts; ++i)
            s.parts << dl + QStringLiteral("/%1.part%2.rar").arg(s.name).arg(i + 1);
        s.bytes = qint64(d.gb * 1e9);
        auto *job = new ExtractJob(s, dl, this);
        auto *card = new JobCard(job, this);
        m_cards << card;
        m_list->insertWidget(m_list->count() - 1, card);
        connect(job, &ExtractJob::changed, this, &MainWindow::updateSummary);
        job->setDemo(d.st, d.pct, qint64(d.unpacked * 1e9), d.speed, QString::fromUtf8(d.err));
    }
    m_stack->setCurrentIndex(1);
    updateSummary();
}
