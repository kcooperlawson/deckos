"""DecKoOS Hub as the one place for settings: search across everything (the sidebar's box) and "More settings",
Plasma's panels that DecKoOS uses as they are, grouped and named for what they do. Both read hub_settings."""
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import QGridLayout

import hub_settings  # noqa: E402
import hub_system as sysinfo  # noqa: E402
from hub_pages import Page  # noqa: E402
from hub_widgets import Card, Empty, RowItem, button, label  # noqa: E402


def open_entry(hub, entry):
    kind, target = entry["go"]
    if kind == "hub":
        hub.navigate(target)
    elif sysinfo.DEMO:
        hub.toast(f"Would open {entry['title']}", "info")
    elif kind == "plasma":
        cmd = hub_settings.plasma_command(target)
        QProcess.startDetached(cmd[0], cmd[1:])
    else:
        QProcess.startDetached("deckos", ["do", target])


def entry_row(hub, entry, show_group=False):
    detail = entry["summary"] + (f"  ·  {entry['group']}" if show_group and entry["group"] else "")
    go = {"hub": "Open", "plasma": "Open", "action": "Do it"}[entry["go"][0]]
    b = button(go, slot=lambda: open_entry(hub, entry), icon="arrow-right" if go == "Open" else "play")
    r = RowItem(entry["icon"], entry["title"], detail, right=(b,))
    r.setCursor(Qt.PointingHandCursor)
    r.mousePressEvent = lambda _e: open_entry(hub, entry)
    return r


class MorePage(Page):
    title = "More settings"
    subtitle = "Bluetooth, sound devices, keyboard, network, shortcuts and the rest, from Plasma's System Settings."

    def build(self):
        self.head_actions.addWidget(button("All of System Settings", icon="external", slot=lambda: (
            self.hub.toast("Would open System Settings", "info") if sysinfo.DEMO
            else QProcess.startDetached("systemsettings", []))))
        items = [e for e in hub_settings.entries() if e["go"][0] == "plasma"]
        for group in hub_settings.PLASMA_GROUPS:
            rows = [e for e in items if e["group"] == group]
            if not rows:
                continue
            card = Card(group, None, None)
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, e in enumerate(rows):
                grid.addWidget(entry_row(self.hub, e), i // 2, i % 2)
            card.body.addLayout(grid)
            self.lay.addWidget(card)


class SearchPage(Page):
    title = "Search"
    subtitle = "DecKoOS Hub, Plasma's settings and things DecKoOS can do."

    def build(self):
        self.results = Card(None, None, None)
        self.lay.addWidget(self.results)

    def show_results(self, query):
        while self.results.body.count():
            w = self.results.body.takeAt(0).widget()
            if w:
                w.deleteLater()
        found = hub_settings.search(query)
        self.title_label.setText(f"“{query}”")
        if not found:
            self.results.body.addWidget(Empty("search", "Nothing found",
                                              "Try another word: “screen”, “sound”, “controller”, “update”…"))
            return
        for e in found:
            self.results.body.addWidget(entry_row(self.hub, e, show_group=True))
        self.results.body.addWidget(label("Enter opens the first one.", "muted"))
