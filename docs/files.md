# DecKoOS Files: design and architecture

DecKoOS Files (`deckos-files`) is DecKoOS's own file manager and the default for folders
(`inode/directory`), replacing Dolphin. It's a native C++20 / Qt 6 Widgets app on KDE Frameworks 6.
KIO does the work it already does well (listing, copying, trash, network, phones, thumbnails,
archives, search, "Open with"); DecKoOS Files adds the window, the views and the DecKoOS look.

## Goals

1. **Fast.** First window on screen in under 150 ms warm, folders with 50,000+ files that scroll at
   the display's refresh rate, and opening a second window costs nothing (it's the same process).
2. **Complete for daily use.** Everything below works on day one; nothing sends you back to Dolphin.
3. **DecKoOS look.** Slate surfaces, 10px radii, accent selection, DecKoOS line icons for the app's own
   buttons, the system icon theme (DeckOS/Papirus) for files.

Non-goals for v1: an embedded terminal panel, a folder tree panel, per-folder view settings,
plugins of our own (service menus from other apps do show up, through KIO).

## v1 features

| Area | What it does | Built on |
|---|---|---|
| Sidebar | Places (Home, Desktop, Documents, Downloads…), Devices with a usage bar and an eject button, Network (SMB/SFTP/FTP shares, "Add network folder"), Trash with an item count. Drag folders in to pin them | `KFilePlacesModel`, Solid, `QStorageInfo` |
| Tabs | Ctrl+T / Ctrl+W, reopen closed tab (Ctrl+Shift+T), middle-click a folder to open it in a tab, tab bar hidden when there's one tab | `QTabBar` |
| Split view | F3 splits the current tab into two panes; the active pane has an accent outline | `QSplitter` |
| Views | Grid (icons with thumbnails), List (compact columns, like Dolphin's Compact), Details (columns: Name, Size, Modified, Type, sortable, resizable). Ctrl+1/2/3, Ctrl+= / Ctrl+- zoom | own model + `QListView` / `QTreeView` + own delegates |
| Sizes | Files: size. Folders: item count, counted in the background for visible rows only | worker thread, cached |
| Path bar | Breadcrumbs; click empty space, F6 or Ctrl+L to type a path (with completion), Esc to go back to crumbs | `KUrlNavigator` |
| Search | Ctrl+F: search this folder and below. Indexed folders use Baloo (names and contents), others use filename search. Ctrl+I: instant filter of the current folder | Baloo `Query::toSearchUrl`, kio-extras `filenamesearch:/` |
| Previews panel | F11: large thumbnail, name, type, size, modified, image dimensions, number of items for a selection | `KIO::PreviewJob` |
| Thumbnails | Images, video, PDF, fonts… for visible items only, read from the shared thumbnail cache | `KIO::PreviewJob` + kio-extras / ffmpegthumbs |
| File operations | Cut/copy/paste, drag and drop with the copy/move/link menu, trash (Del), delete (Shift+Del, asks), restore from trash, empty trash, undo (Ctrl+Z) for all of them, progress in Plasma's notifications and in the status bar | `KIO::paste`, `KIO::drop`, `KIO::DeleteOrTrashJob`, `KIO::RestoreJob`, `KIO::FileUndoManager` |
| Rename | F2 renames in place (the name is selected without the extension). With several files selected, F2 opens batch rename: "Photo #" numbering or find-and-replace, with a live preview | `KIO::moveAs`, `KIO::batchRename` |
| New | New folder (F10), new file from templates, link | `KNewFileMenu` |
| Open | Double-click / Enter opens with the default app; right-click › Open with; service menus (Ark's compress/extract, "Open as administrator" from kio-admin…) | `KIO::OpenUrlJob`, `KFileItemActions` |
| Properties | Alt+Return: size, permissions, checksums, "Open with" defaults | `KPropertiesDialog` |
| Network & phones | `smb://`, `sftp://`, `ftp://`, `mtp:/` (Android phones), `remote:/` all browse like folders; apps opening a network file get a local path through kio-fuse | KIO workers in kio-extras, kio-fuse |
| Archives | Browse zip/tar/7z as folders (`zip:/`, `tar:/`), extract via Ark's menu | kio-extras, Ark |
| Other | Show hidden files (Ctrl+H, Alt+.), open terminal here (Shift+F4), back/forward/up with mouse side buttons, "Show in folder" from other apps (Firefox downloads, etc.) | `KTerminalLauncherJob`, `org.freedesktop.FileManager1` |

Keyboard shortcuts follow Dolphin: Alt+Left/Right back/forward, Alt+Up or Backspace up, Alt+Home
home, F5 reload, F9 sidebar, Ctrl+N new window, Ctrl+Tab next tab, Ctrl+A select all,
Ctrl+Shift+A invert selection, Ctrl+D add to Places, Ctrl+Q quit.

## Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [‹][›][↑]  ⌂ › Pictures › 2026 ›                 [🔍 Search]  [▦▤☰] [⫼][▣][≡] │  toolbar
│ ┌ Documents ┐┌ Pictures ┐┌ +                                              │  tabs (2+ only)
├────────────┬────────────────────────────────────────────┬────────────────┤
│ PLACES     │                                            │  ┌──────────┐  │
│ ⌂ Home     │   folder grid / list / details             │  │ preview  │  │
│ ▭ Desktop  │                                            │  └──────────┘  │
│ ↓ Downloads│   (split view: two panes side by side,     │  beach.jpg     │
│ DEVICES    │    the active one outlined in accent)      │  JPEG image    │
│ ▤ Games ▕▇▇▁│                                            │  4.2 MB · 4032×│
│ NETWORK    │                                            │                │
│ 🗑 Trash 12 │                                            │                │
├────────────┴────────────────────────────────────────────┴────────────────┤
│ 1,204 items · 3 selected (12.3 MB)                 812 GB free  ─○── zoom │  status bar
└──────────────────────────────────────────────────────────────────────────┘
```

Window `#0F1115`; sidebar, path field and previews panel are `#171A21` plates with `#262B36`
borders and 10px radii. Selection is the accent at ~22% with a 1px accent edge; hover is `#1D212A`.
Section labels are the Hub's small caps "kicker" style. The empty-folder and error states use a
large line icon, a short sentence and a button ("This folder is empty", "Can't reach this share:
check that the PC is on"). The accent follows Plasma's accent colour, like the Hub.

## Architecture

```
main.cpp            QApplication, KAboutData, KDBusService (unique), --demo / --screenshot
MainWindow          toolbar, tab bar, sidebar, previews panel, status bar, all QActions
 └ TabPage          one tab: one or two FolderPanes in a QSplitter, tracks the active pane
    └ FolderPane    KUrlNavigator + FolderView; history; selection; context menu
       ├ FolderModel   flat model over KCoreDirLister (see below), sort + filter, roles
       ├ FolderView    QStackedWidget of a QListView (grid/list) and a QTreeView (details)
       ├ ItemDelegate  paints icons, thumbnails, names, selection; inline rename editor
       └ PreviewLoader KIO::PreviewJob for visible rows, cancels on scroll, pixmap cache
Sidebar             KFilePlacesModel in a QListView with a custom delegate (usage bars, eject)
PreviewPanel        selection info + large preview
Operations          thin wrappers creating KIO jobs, registering them for undo and progress
BatchRenameDialog
FileManager1        org.freedesktop.FileManager1 D-Bus adaptor (ShowFolders/ShowItems/ShowItemProperties)
Style               palette, DecKoOS line icons (QSvgRenderer, recoloured, cached), small QSS for chrome
```

### Why a flat model instead of `KDirModel`

`KDirModel` is a tree model; sorting it means a `QSortFilterProxyModel` on top, which compares
names with `QCollator` on every comparison and re-sorts the whole folder on each batch of new items.
At 50,000 files that's hundreds of milliseconds per batch. `FolderModel` keeps one `QList` of rows
(`KFileItem` + a precomputed `QCollatorSortKey` + cached size/count), sorts once with the keys
(memcmp-cheap comparisons), merges each `itemsAdded` batch in with a sorted insert, and emits
row-level changes so views never reset. This is the same approach Dolphin's `KFileItemModel`
takes. Listing, change notifications (KDirWatch / inotify), caching of recently seen folders and
remote protocols all stay in `KCoreDirLister`.

### Other speed rules

- **No QSS on item views.** Style sheets route every paint through `QStyleSheetStyle`. Views and
  delegates paint with `QPainter` directly; QSS is only used on the toolbar and dialogs.
- Views use `setUniformItemSizes`, `setUniformRowHeights`, batched layout and no per-item widgets.
- Icons come from `KFileItem::iconName()` with delayed MIME detection (extension first), through a
  `QHash<QString, QIcon>` cache. Thumbnails are only requested for visible rows, after scrolling
  settles for 60 ms, and are dropped from memory past a cap (LRU).
- Folder item counts, image dimensions and free space are worked out off the UI thread.
- Heavy objects (`KNewFileMenu`, `KFileItemActions`, `KPropertiesDialog`, Baloo) are created the
  first time they're needed, not at start. No KXmlGui (its XML parsing costs start time).
- **One process.** `KDBusService` in unique mode: launching DecKoOS Files again (a second window,
  "Show in folder" from Firefox) opens a window in the running process, which is instant.

### D-Bus and defaults

- `org.deckos.files.desktop`, `MimeType=inode/directory`, set as the default in
  `/etc/xdg/mimeapps.list` so folders from any app open in DecKoOS Files.
- `org.freedesktop.FileManager1` is claimed while it runs and D-Bus-activatable when it isn't
  (`deckos-files --daemon`: no window until asked).
- The Hub's "Open in Files" buttons launch `deckos-files`.

## Packaging and delivery

- Source: `apps/deckos-files/` (CMake, ECM, `-O2 -flto`, `-DQT_NO_CAST_FROM_ASCII` etc. via
  `KDECompilerSettings`).
- Package: `pkg/deckos-files/PKGBUILD`, `arch=(x86_64)`, built from `../../apps/deckos-files` like
  `deckos-settings` reads `../../VERSION`; `pkgver` is the DecKoOS `VERSION`.
  Depends: `qt6-base qt6-svg kio kio-extras kio-fuse kconfig kcoreaddons kdbusaddons kiconthemes
  kwidgetsaddons baloo solid` (optional: `kio-admin`, `ffmpegthumbs`, `kdegraphics-thumbnailers`).
- **Getting it onto systems:** `deckos-settings` depends on `deckos-files`, so existing installs get
  it from the `[deckos]` repo on their next `deckos update`. `build.sh` builds it into the on-USB
  repo, and the installer installs it together with `deckos-settings`. `deckos dev-install` builds
  it too. CI's package job builds it, so the publish job signs and publishes it with the rest.
- **Dolphin:** dropped from `desktop.txt` and `iso/packages.live` for new installs (kio-extras,
  kio-fuse and the thumbnailers it pulled in are listed explicitly). Existing installs keep Dolphin
  until the user removes it; DecKoOS Files is the default either way.

## Testing without Linux

The app can't run on Windows, so CI does it: `.github/workflows/deckos-files.yml` builds the package
in an Arch container on every push that touches `apps/deckos-files/` or `pkg/deckos-files/`, then
runs `deckos-files --demo --screenshot` under `QT_QPA_PLATFORM=offscreen` and `dbus-run-session`.
`--demo` makes a throwaway folder tree (photos, documents, a few thousand files for the scroll test),
opens it in grid, details, split-with-previews and search states, and saves a PNG of each. The PNGs
are uploaded as the `deckos-files-screenshots` artifact. A timing line (start to first paint,
listing 20,000 files) is printed in the log so speed regressions show up.

## Later

Per-folder view settings, a folder tree panel, an embedded terminal, tags/ratings via Baloo,
a DeckOS-styled properties dialog, dual-pane "commander" keys (F5 copy to other pane, F6 move).
