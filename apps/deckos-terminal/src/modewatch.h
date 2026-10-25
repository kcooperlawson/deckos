// DecKoOS workload modes as they change: the org.deckos.Mode.Changed signal that `deckos mode watch`
// emits on the session bus, with the details from $XDG_RUNTIME_DIR/deckos-mode. Nothing polls.
#pragma once

#include <QObject>
#include <QString>

class ModeWatch : public QObject
{
    Q_OBJECT
public:
    explicit ModeWatch(QObject *parent = nullptr);

    bool gaming() const { return m_mode == QLatin1String("gaming"); }
    QString game() const { return m_game; }
    QString summary() const;  // "Playing Cyberpunk 2077 · 9.1 GB freed · 2 containers paused"

    void setDemo(const QString &game, double vramBytes, int containers);

Q_SIGNALS:
    void changed();

private Q_SLOTS:
    void onChanged(const QString &mode, const QString &game);

private:
    void read();

    QString m_mode = QStringLiteral("normal");
    QString m_game;
    double m_vram = 0;
    int m_containers = 0;
    bool m_indexing = false;
};
