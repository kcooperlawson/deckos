// One archive set in the queue: a notched plate with its name, parts and size, a segmented meter, what it's doing
// and the buttons that fit (pause, cancel, retry, open the folder, the password field).
#pragma once

#include <QFrame>

class ExtractJob;
class QLabel;
class QLineEdit;
class QPushButton;
class QToolButton;
class QWidget;

class JobCard : public QFrame
{
    Q_OBJECT
public:
    explicit JobCard(ExtractJob *job, QWidget *parent = nullptr);
    ExtractJob *job() const { return m_job; }

Q_SIGNALS:
    void removeRequested(JobCard *card);
    void openRequested(const QString &folder);
    void retried();

protected:
    void paintEvent(QPaintEvent *) override;

private:
    void refresh();

    ExtractJob *m_job;
    QLabel *m_name;
    QLabel *m_detail;
    QLabel *m_status;
    QToolButton *m_pause;
    QToolButton *m_stop;
    QToolButton *m_retry;
    QPushButton *m_open;
    QWidget *m_passRow;
    QLineEdit *m_pass;
};
