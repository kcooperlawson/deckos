#include "style.h"

#include <algorithm>

#include <QApplication>
#include <QDir>
#include <QEvent>
#include <QFile>
#include <QLinearGradient>
#include <QPointer>
#include <QProcess>
#include <QTimer>
#include <QWebSocket>
#include <QWidget>
#include <QHash>
#include <QPainter>
#include <QPainterPath>
#include <QPalette>
#include <QSvgRenderer>

#include <KConfigGroup>
#include <KSharedConfig>

namespace Style {

namespace {

QColor readAccent()
{
    const KConfigGroup general(KSharedConfig::openConfig(QStringLiteral("kdeglobals"), KConfig::NoGlobals), QStringLiteral("General"));
    const QColor c = general.readEntry("AccentColor", QColor());
    return c.isValid() ? c : QColor(0x4C, 0x8D, 0xFF);
}

QString iconDir()
{
    static const QString dir = [] {
        const QStringList candidates = {qEnvironmentVariable("DECKOS_ICONS"), QStringLiteral("/usr/share/deckos/icons"),
                                        QStringLiteral(DECKOS_SOURCE_ICONS)};
        for (const QString &d : candidates) {
            if (!d.isEmpty() && QFile::exists(d + QStringLiteral("/folder.svg")))
                return d;
        }
        return QString();
    }();
    return dir;
}

} // namespace

QColor accent()
{
    static const QColor c = readAccent();
    return c;
}

QColor accentPartner()
{
    const QColor a = accent();
    int h, s, v;
    a.getHsv(&h, &s, &v);
    return QColor::fromHsv((h + 32) % 360, qMin(255, s + 10), v);
}

QColor selectionFill()
{
    QColor c = accent();
    c.setAlpha(56);
    return c;
}

QColor hoverFill()
{
    return Raised;
}

void apply(QApplication &app)
{
    QPalette pal;
    pal.setColor(QPalette::Window, Bg);
    pal.setColor(QPalette::WindowText, Text);
    pal.setColor(QPalette::Base, Bg);
    pal.setColor(QPalette::AlternateBase, Surface);
    pal.setColor(QPalette::Text, Text);
    pal.setColor(QPalette::Button, Surface);
    pal.setColor(QPalette::ButtonText, Text);
    pal.setColor(QPalette::BrightText, Qt::white);
    pal.setColor(QPalette::Highlight, accent());
    pal.setColor(QPalette::HighlightedText, Qt::white);
    pal.setColor(QPalette::ToolTipBase, QColor(0x22, 0x26, 0x2F));
    pal.setColor(QPalette::ToolTipText, Text);
    pal.setColor(QPalette::PlaceholderText, Muted);
    pal.setColor(QPalette::Light, Hover);
    pal.setColor(QPalette::Midlight, Border);
    pal.setColor(QPalette::Mid, Border);
    pal.setColor(QPalette::Dark, Sidebar);
    pal.setColor(QPalette::Shadow, Qt::black);
    pal.setColor(QPalette::Link, accent());
    for (auto role : {QPalette::WindowText, QPalette::Text, QPalette::ButtonText})
        pal.setColor(QPalette::Disabled, role, Muted);
    app.setPalette(pal);
}

QString chromeQss()
{
    const QString acc = accent().name();
    const QString tint = QStringLiteral("rgba(%1,%2,%3,56)").arg(accent().red()).arg(accent().green()).arg(accent().blue());
    return QStringLiteral(R"(
QToolButton { background: transparent; border: none; border-radius: 7px; padding: 5px; color: #E8EAF0; }
QToolButton:hover { background: #1D212A; }
QToolButton:pressed { background: #2A2F3B; }
QToolButton:checked { background: %2; }
QToolButton::menu-indicator { image: none; width: 0; }
QLineEdit#search { background: #171A21; border: 1px solid #262B36; border-radius: 9px; padding: 5px 8px;
    color: #E8EAF0; selection-background-color: %1; }
QLineEdit#search:focus { border-color: %1; }
QFrame#segment { background: #171A21; border: 1px solid #262B36; border-radius: 9px; }
QFrame#segment QToolButton { border-radius: 6px; padding: 4px; }
QLabel { background: transparent; color: #E8EAF0; }
QLabel#sub { color: #8C94A6; }
QLabel#muted { color: #5A6172; font-size: 9pt; }
QLabel#kicker { color: #8C94A6; font-size: 8pt; font-weight: 600; }
QLabel#title { font-size: 12pt; font-weight: 600; }
QSlider::groove:horizontal { height: 4px; background: #262B36; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %1; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; background: #E8EAF0; }
QProgressBar { background: #262B36; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: %1; border-radius: 3px; }
QPushButton { background: #171A21; border: 1px solid #262B36; border-radius: 7px; padding: 6px 12px; color: #E8EAF0; }
QPushButton:hover { background: #2A2F3B; }
QPushButton:pressed { background: #353B49; }
QPushButton:disabled { color: #5A6172; background: #13161C; border-color: #1E222A; }
QPushButton#primary { color: white; font-weight: 600; border: none; padding: 7px 15px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 %1, stop:1 %3); }
QLineEdit { background: #171A21; border: 1px solid #262B36; border-radius: 7px; padding: 5px 8px; color: #E8EAF0; }
QLineEdit:focus { border-color: %1; }
QSpinBox { background: #171A21; border: 1px solid #262B36; border-radius: 7px; padding: 4px 6px; color: #E8EAF0; }
QRadioButton { spacing: 8px; color: #E8EAF0; }
)")
        .arg(acc, tint, accentPartner().name());
}

QPixmap pixmap(const QString &name, const QColor &color, int size, qreal dpr)
{
    static QHash<QString, QByteArray> sources;
    auto it = sources.find(name);
    if (it == sources.end()) {
        QFile f(iconDir() + QLatin1Char('/') + name + QStringLiteral(".svg"));
        QByteArray data = f.open(QIODevice::ReadOnly) ? f.readAll() : QByteArray("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\"/>");
        it = sources.insert(name, data);
    }
    QByteArray svg = *it;
    svg.replace("#000", color.name().toLatin1());
    QPixmap pm(QSize(size, size) * dpr);
    pm.fill(Qt::transparent);
    QPainter p(&pm);
    p.setRenderHint(QPainter::Antialiasing);
    QSvgRenderer(svg).render(&p, QRectF(0, 0, pm.width(), pm.height()));
    p.end();
    pm.setDevicePixelRatio(dpr);
    return pm;
}

QIcon icon(const QString &name)
{
    static QHash<QString, QIcon> cache;
    auto it = cache.constFind(name);
    if (it != cache.constEnd())
        return *it;
    QIcon ic;
    for (int size : {16, 18, 20, 24}) {
        for (qreal dpr : {1.0, 2.0}) {
            ic.addPixmap(pixmap(name, Subtext, size, dpr), QIcon::Normal, QIcon::Off);
            ic.addPixmap(pixmap(name, Text, size, dpr), QIcon::Active, QIcon::Off);
            ic.addPixmap(pixmap(name, Muted, size, dpr), QIcon::Disabled, QIcon::Off);
            ic.addPixmap(pixmap(name, Text, size, dpr), QIcon::Normal, QIcon::On);
            ic.addPixmap(pixmap(name, Text, size, dpr), QIcon::Active, QIcon::On);
            ic.addPixmap(pixmap(name, Text, size, dpr), QIcon::Selected, QIcon::Off);
        }
    }
    cache.insert(name, ic);
    return ic;
}

QIcon themeIcon(const QString &name)
{
    static QHash<QString, QIcon> cache;
    auto it = cache.constFind(name);
    if (it != cache.constEnd())
        return *it;
    QIcon ic = QIcon::fromTheme(name);
    if (ic.isNull())
        ic = QIcon::fromTheme(QStringLiteral("unknown"));
    cache.insert(name, ic);
    return ic;
}

void drawScrew(QPainter &p, const QPointF &c, qreal r)
{
    p.save();
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(0x2A, 0x2F, 0x3B));
    p.drawEllipse(c, r, r);
    p.setPen(QPen(QColor(0x14, 0x17, 0x1D), 0.9));
    p.drawLine(QPointF(c.x() - r * 0.6, c.y() + r * 0.6), QPointF(c.x() + r * 0.6, c.y() - r * 0.6));
    p.restore();
}

QString kicker(const QString &text)
{
    return text.toUpper();
}

namespace {

// The beat: deckos-visualizer's "beat STRENGTH" text messages, listened for only while playerctl says a player plays
class Beat : public QObject
{
public:
    static Beat *get()
    {
        static Beat *beat = new Beat(qApp);
        return beat;
    }
    qreal pulse = 0;
    QList<QPointer<QWidget>> edges;

private:
    explicit Beat(QObject *parent) : QObject(parent)
    {
        decay.setInterval(33);
        connect(&decay, &QTimer::timeout, this, [this] {
            pulse *= 0.84;
            if (pulse < 0.02) {
                pulse = 0;
                decay.stop();
            }
            for (const auto &e : std::as_const(edges))
                if (e && e->isVisible())
                    e->update();
        });
        connect(&players, &QProcess::readyReadStandardOutput, this, [this] {
            for (const QByteArray &line : players.readAllStandardOutput().split('\n')) {
                const int sp = line.lastIndexOf(' ');
                if (sp > 0)
                    playing[QString::fromUtf8(line.left(sp))] = line.mid(sp + 1).trimmed() == "Playing";
            }
            const bool on = std::any_of(playing.cbegin(), playing.cend(), [](bool p) { return p; });
            if (on && !socket) {
                socket = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);
                connect(socket, &QWebSocket::textMessageReceived, this, [this](const QString &m) {
                    if (!m.startsWith(QLatin1String("beat ")))
                        return;
                    pulse = std::min(1.0, 0.55 + 0.45 * m.mid(5).toDouble());
                    decay.start();
                });
                socket->open(QUrl(QStringLiteral("ws://127.0.0.1:47823")));
            } else if (!on && socket) {
                socket->close();
                socket->deleteLater();
                socket = nullptr;
            }
        });
        players.start(QStringLiteral("playerctl"),
                      {QStringLiteral("-a"), QStringLiteral("-F"), QStringLiteral("status"), QStringLiteral("-f"),
                       QStringLiteral("{{playerName}} {{status}}")});
    }
    QTimer decay;
    QProcess players;
    QHash<QString, bool> playing;
    QWebSocket *socket = nullptr;
};

bool reacting()
{
    QFile f(QDir::homePath() + QStringLiteral("/.config/deckos/style.conf"));
    if (!f.open(QIODevice::ReadOnly))
        return false;
    for (const QByteArray &line : f.readAll().split('\n'))
        if (line.trimmed() == "react=on")
            return true;
    return false;
}

// The edge itself: 2 px of the accent's gradient and a soft glow under it, as bright as the beat
class BeatEdge : public QWidget
{
public:
    explicit BeatEdge(QWidget *window) : QWidget(window)
    {
        setAttribute(Qt::WA_TransparentForMouseEvents);
        setAttribute(Qt::WA_NoSystemBackground);
        window->installEventFilter(this);
        place();
    }

protected:
    bool eventFilter(QObject *, QEvent *e) override
    {
        if (e->type() == QEvent::Resize || e->type() == QEvent::ChildAdded)
            place();
        return false;
    }
    void paintEvent(QPaintEvent *) override
    {
        const qreal k = Beat::get()->pulse;
        if (k <= 0)
            return;
        QPainter p(this);
        QColor a = accent(), b = accentPartner();
        a.setAlphaF(k);
        b.setAlphaF(k);
        QLinearGradient line(0, 0, width(), 0);
        line.setColorAt(0, a);
        line.setColorAt(1, b);
        p.fillRect(QRectF(0, 0, width(), 2), line);
        QColor glow = accent();
        for (int y = 2; y < height(); ++y) {  // the glow, fading downwards
            glow.setAlphaF(k * 0.35 * (1.0 - qreal(y) / height()));
            p.fillRect(QRectF(0, y, width(), 1), glow);
        }
    }

private:
    void place()
    {
        setGeometry(0, 0, parentWidget()->width(), 8);
        raise();
    }
};

} // namespace

void attachBeat(QWidget *window)
{
    if (!window || !reacting())
        return;
    Beat::get()->edges.append(new BeatEdge(window));
}

} // namespace Style
