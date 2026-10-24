// One terminal: a QTermWidget in the DeckOS look, plus what it's doing (ProjectInfo). The active
// pane in a split gets an accent outline.
#pragma once

#include "project.h"

#include <QFrame>
#include <QStringList>

class QTermWidget;

class TerminalPane : public QFrame
{
    Q_OBJECT
public:
    // command empty: the user's shell. dir empty: home.
    explicit TerminalPane(const QString &dir, const QStringList &command = {}, QWidget *parent = nullptr);

    QTermWidget *term() const { return m_term; }
    const ProjectInfo &info() const { return m_info; }
    QString currentDir() const;

    void setActive(bool active);
    bool isActive() const { return m_active; }

    void refresh();  // re-read the project and command; emits infoChanged when they change
    void zoom(int step);  // +1, -1, 0 (back to the default size)
    void focusTerminal();
    void setHold(bool hold) { m_hold = hold; }  // --hold: keep the output after the command ends

Q_SIGNALS:
    void infoChanged();
    void focused(TerminalPane *pane);
    void finished(TerminalPane *pane);
    void bell(TerminalPane *pane);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QTermWidget *m_term;
    ProjectInfo m_info;
    bool m_active = false;
    int m_zoom = 0;
    bool m_hold = false;
};
