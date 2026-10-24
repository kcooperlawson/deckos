#include "terminalpane.h"
#include "style.h"

#include <QDesktopServices>
#include <QDir>
#include <QFile>
#include <QFontDatabase>
#include <QPainter>
#include <QVBoxLayout>

#include <qtermwidget.h>

namespace {

void addSchemeDirs()
{
    static bool done = false;
    if (done)
        return;
    done = true;
    for (const QString &d : {QStringLiteral("/usr/share/deckos-terminal/color-schemes"), QStringLiteral(DECKOS_SOURCE_SCHEMES)}) {
        if (QFile::exists(d + QStringLiteral("/DeckOS.colorscheme"))) {
            QTermWidget::addCustomColorSchemeDir(d);
            break;
        }
    }
}

QFont baseFont()
{
    for (const QString &family : {QStringLiteral("JetBrains Mono"), QStringLiteral("JetBrainsMono Nerd Font")}) {
        if (QFontDatabase::hasFamily(family))
            return QFont(family, 11);
    }
    QFont f = QFontDatabase::systemFont(QFontDatabase::FixedFont);
    f.setPointSize(11);
    return f;
}

} // namespace

TerminalPane::TerminalPane(const QString &dir, const QStringList &command, QWidget *parent)
    : QFrame(parent)
{
    addSchemeDirs();
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(1, 1, 1, 1);  // room for the active outline

    m_term = new QTermWidget(0, this);
    m_term->setColorScheme(QStringLiteral("DeckOS"));
    m_term->setTerminalFont(baseFont());
    m_term->setHistorySize(20000);
    m_term->setScrollBarPosition(QTermWidget::ScrollBarRight);
    m_term->setMargin(8);
    m_term->setBlinkingCursor(true);
    m_term->setBoldIntense(true);
    m_term->setConfirmMultilinePaste(true);
    m_term->setTrimPastedTrailingNewlines(true);
    m_term->setMotionAfterPasting(2);  // scroll to the bottom
    m_term->setAutoClose(false);  // the tab decides (closing the last pane closes it)
    m_term->setEnvironment({QStringLiteral("TERM=xterm-256color"), QStringLiteral("COLORTERM=truecolor"),
                            QStringLiteral("TERM_PROGRAM=deckos-terminal")});
    m_term->setWorkingDirectory(dir.isEmpty() ? QDir::homePath() : dir);
    if (!command.isEmpty()) {
        m_term->setShellProgram(command.first());
        m_term->setArgs(command.mid(1));
    } else {
        m_term->setShellProgram(qEnvironmentVariable("SHELL", QStringLiteral("/bin/bash")));
    }
    layout->addWidget(m_term);

    connect(m_term, &QTermWidget::termGetFocus, this, [this] { Q_EMIT focused(this); });
    connect(m_term, &QTermWidget::finished, this, [this] {
        if (!m_hold)
            Q_EMIT finished(this);
    });
    connect(m_term, &QTermWidget::titleChanged, this, &TerminalPane::refresh);
    connect(m_term, &QTermWidget::currentDirectoryChanged, this, &TerminalPane::refresh);
    connect(m_term, &QTermWidget::bell, this, [this] { Q_EMIT bell(this); });
    connect(m_term, &QTermWidget::urlActivated, this, [](const QUrl &url, bool) { QDesktopServices::openUrl(url); });

    m_term->startShellProgram();
    refresh();
}

QString TerminalPane::currentDir() const
{
    return m_info.dir.isEmpty() ? QDir::homePath() : m_info.dir;
}

void TerminalPane::setActive(bool active)
{
    if (m_active == active)
        return;
    m_active = active;
    update();
}

void TerminalPane::refresh()
{
    const ProjectInfo next = Project::inspect(m_term->getShellPID(), m_term->getForegroundProcessId());
    if (next == m_info)
        return;
    m_info = next;
    Q_EMIT infoChanged();
}

void TerminalPane::zoom(int step)
{
    if (step == 0) {
        m_zoom = 0;
        m_term->setTerminalFont(baseFont());
    } else if (step > 0) {
        ++m_zoom;
        m_term->zoomIn();
    } else {
        --m_zoom;
        m_term->zoomOut();
    }
}

void TerminalPane::focusTerminal()
{
    m_term->setFocus(Qt::OtherFocusReason);
}

void TerminalPane::paintEvent(QPaintEvent *)
{
    QPainter p(this);
    p.fillRect(rect(), Style::Bg);
    if (m_active) {
        p.setPen(QPen(Style::accent(), 1));
        p.drawRect(rect().adjusted(0, 0, -1, -1));
    }
}
