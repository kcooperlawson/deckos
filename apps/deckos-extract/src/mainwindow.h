// DecKoOS Extract's window: the queue of archive sets, run one at a time (big extractions fight over the disk),
// with where to put them and what to do after.
#pragma once

#include <QList>
#include <QWidget>

class ExtractJob;
class JobCard;
class QCheckBox;
class QComboBox;
class QLabel;
class QStackedWidget;
class QVBoxLayout;

class MainWindow : public QWidget
{
    Q_OBJECT
public:
    explicit MainWindow(bool demo = false, QWidget *parent = nullptr);

    // Adds every archive set among `paths` (any part finds the rest) and starts the queue. `dest` overrides the
    // window's choice for these.
    void add(const QStringList &paths, const QString &dest = {});
    void addDemo();

protected:
    void dragEnterEvent(QDragEnterEvent *e) override;
    void dropEvent(QDropEvent *e) override;
    void closeEvent(QCloseEvent *e) override;

private:
    void next();
    void updateSummary();
    void remove(JobCard *card);
    QString destinationFor(const QString &first) const;
    void chooseFolder();
    void saveSettings() const;

    QList<JobCard *> m_cards;
    QVBoxLayout *m_list;
    QStackedWidget *m_stack;
    QLabel *m_summary;
    QComboBox *m_dest;
    QCheckBox *m_trash;
    QCheckBox *m_openAfter;
    QString m_folder;  // the chosen folder, when "Extract to" is a folder
    bool m_demo;
};
