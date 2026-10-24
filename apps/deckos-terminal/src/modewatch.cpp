#include "modewatch.h"

#include <QDBusConnection>
#include <QFile>
#include <QStandardPaths>

ModeWatch::ModeWatch(QObject *parent)
    : QObject(parent)
{
    QDBusConnection::sessionBus().connect(QString(), QStringLiteral("/org/deckos/Mode"), QStringLiteral("org.deckos.Mode"),
                                          QStringLiteral("Changed"), this, SLOT(onChanged(QString, QString)));
    read();
}

void ModeWatch::onChanged(const QString &, const QString &)
{
    read();  // the file has the details the signal doesn't carry
    Q_EMIT changed();
}

void ModeWatch::read()
{
    m_mode = QStringLiteral("normal");
    m_game.clear();
    m_vram = 0;
    m_containers = 0;
    m_indexing = false;
    QFile f(QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/deckos-mode"));
    if (!f.open(QIODevice::ReadOnly))
        return;
    for (const QByteArray &line : f.readAll().split('\n')) {
        const qsizetype eq = line.indexOf('=');
        if (eq <= 0)
            continue;
        const QByteArray key = line.left(eq);
        const QString value = QString::fromUtf8(line.mid(eq + 1));
        if (key == "mode")
            m_mode = value;
        else if (key == "game")
            m_game = value;
        else if (key == "vram")
            m_vram = value.toDouble();
        else if (key == "docker")
            m_containers = value.split(QLatin1Char(' '), Qt::SkipEmptyParts).size();
        else if (key == "baloo")
            m_indexing = value == QLatin1String("1");
    }
}

QString ModeWatch::summary() const
{
    if (!gaming())
        return QString();
    QStringList parts{QStringLiteral("Playing ") + m_game};
    if (m_vram > 0)
        parts << QStringLiteral("%1 GB freed").arg(m_vram / 1e9, 0, 'f', 1);
    if (m_containers > 0)
        parts << QStringLiteral("%1 %2 paused").arg(m_containers).arg(m_containers == 1 ? QStringLiteral("container") : QStringLiteral("containers"));
    return parts.join(QStringLiteral(" · "));
}

void ModeWatch::setDemo(const QString &game, double vramBytes, int containers)
{
    m_mode = QStringLiteral("gaming");
    m_game = game;
    m_vram = vramBytes;
    m_containers = containers;
    Q_EMIT changed();
}
