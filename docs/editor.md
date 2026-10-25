# DeckOS Editor

The DeckOS text editor (`apps/deckos-editor/`, package `deckos-editor`): C++/Qt 6 on `QPlainTextEdit`
with KDE's KSyntaxHighlighting (the definitions Kate uses, 300+ languages) in a DeckOS theme
(`data/themes/deckos.theme`). It shares DeckOS Files' `style.cpp` for the look, like DeckOS Terminal.

## What it does

- Tabs (Ctrl+N/O/S/W, Ctrl+Tab, Ctrl+Shift+T reopens), restored next time (`deckos-editorrc`, saved files only).
- One process (`KDBusService`): `deckos-editor FILE` from Files or a terminal opens a tab in the running window.
  `FILE:LINE` and `+LINE FILE` jump to a line; `--new-window` opens another window.
- Find and replace under the text (Ctrl+F / Ctrl+H): every match lit and counted, case / whole words / regex.
- Editing: indentation kept and stepped after `{ ( [` and Python's `:`, Tab/Shift+Tab on selections, smart Home,
  Ctrl+/ comments (the language's marker), Ctrl+D duplicates, Alt+Up/Down moves lines, Ctrl+G go to line,
  bracket partner lit, Alt+Z wraps, Ctrl+wheel zooms. Indentation is guessed from the file (tabs, 2, 4, 8).
- Status line: position, language, indentation, line endings: each a menu that changes it.

## Files, carefully

`Document` (no widgets, tested alone):
- Refuses binaries (a NUL in the first 8 KB), non-UTF-8 text and files over 64 MB rather than mangling them.
- Keeps the file's line endings (CRLF when most lines have it), its byte-order mark and the missing final newline.
- Saves with `QSaveFile`: written beside the file and renamed over, so a crash never leaves half a file; the
  file's permissions stay, and a symlink saves into the file it points at.
- A file this user can't write (`/etc/fstab`) asks "Save as administrator?": the text goes to a private temp
  file and `pkexec cp` copies it over the file's content, so owner and mode stay.
- A file changed on disk reloads by itself when there's nothing unsaved; otherwise a bar offers Reload / Keep mine.

## Testing

`cmake -S apps/deckos-editor -B build -DDECKOS_EDITOR_TESTS=ON && cmake --build build --target editor_test`, then
`QT_QPA_PLATFORM=offscreen build/editor_test`. `deckos-editor --demo --screenshot DIR` writes three screenshots;
the "DeckOS Editor" workflow runs both on every push that touches it.
