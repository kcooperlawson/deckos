// What a terminal pane is doing, from /proc and the files git keeps: no git or ps processes, so it's
// cheap enough to check every couple of seconds.
#pragma once

#include <QString>

struct ProjectInfo {
    QString dir;     // the shell's working folder
    QString root;    // the git work tree it's in, or empty
    QString name;    // the project (git root's folder) or the folder's own name; "~" for home
    QString branch;  // branch name, or a short commit when detached
    QString command; // the foreground command ("cargo build"), empty at the prompt

    bool operator==(const ProjectInfo &) const = default;
    QString label() const;  // "deckos ⎇ main · cargo build"
};

namespace Project {
QString cwdOf(int pid);
QString commandOf(int pid);  // program name plus its first argument that isn't an option
ProjectInfo inspect(int shellPid, int foregroundPid);
}
