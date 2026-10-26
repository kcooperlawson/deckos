"""DecKoOS Store: apps from the Arch/CachyOS repos, Flathub and the AUR, in one place.

Same look as DecKoOS Hub: slate surfaces, 1px borders, Inter, DecKoOS line icons, accent gradient.
    deckos-store            the real thing
    deckos-store --demo     canned apps and fake installs, for working on the UI anywhere
    deckos-store --app ID   open on one app (its AppStream id; DecKoOS Menu's "Get it")
    deckos-store --search TERM   open on a search
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hub"))  # shares the Hub's style and widgets

from PySide6.QtCore import QObject, QProcess, QSize, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QFont, QIcon  # noqa: E402
from PySide6.QtSvgWidgets import QSvgWidget  # noqa: E402
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout,  # noqa: E402
                               QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout,
                               QWidget)

import hub_style as S  # noqa: E402
from hub_widgets import Card, Empty, Meter, RowItem, Toast, button, icon_label, label, row  # noqa: E402
from store_catalog import (CATEGORIES, DEMO, SOURCE_NAMES, SOURCE_ORDER, Catalog, Installed,  # noqa: E402
                           aur_search, norm)
from store_jobs import Jobs  # noqa: E402
from store_widgets import AppCard, AppIcon, CardGrid, Screenshots, badge  # noqa: E402


def ask_assistant(question):
    """DecKoOS Assistant's chat box, asked about something that went wrong (the Hub has the same)."""
    if not DEMO:
        QProcess.startDetached("deckos-assistant", ["--ask", question[-6000:]])

PAGE_SIZE = 48


class Bridge(QObject):
    """Results from worker threads, delivered on the UI thread."""
    loaded = Signal()
    aur = Signal(int, object)


def arg(name):
    """The value after `name` on the command line, or ""."""
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else ""


def scrolling(widget):
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setWidget(widget)
    return sc


class Store(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("DecKoOS Store")
        self.setWindowIcon(QIcon.fromTheme("deckos-store", QIcon(str(S.BRANDING / "store-logo.svg"))))
        self.resize(1200, 820)
        self.setMinimumSize(960, 640)
        self.catalog, self.installed, self.jobs = Catalog(), Installed(), Jobs(self)
        self.bridge = Bridge()
        self.bridge.loaded.connect(self.catalog_ready)
        self.bridge.aur.connect(self.aur_results)
        self.jobs.changed.connect(self.job_changed)
        self.jobs.done.connect(self.job_done)
        self.history, self.current, self.search_token = [], None, 0
        self.start_app, self.start_search = arg("--app"), arg("--search")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.build_sidebar())
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self.build_topbar())
        self.stack = QStackedWidget()
        main.addWidget(self.stack, 1)
        outer.addLayout(main, 1)
        self.toast_box = Toast(self)

        self.show_loading()
        threading.Thread(target=self._load, daemon=True).start()

    # ---- frame

    def build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 20, 14, 16)
        sl.setSpacing(2)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = S.brand_widget("store-logo.svg")
        logo.setFixedSize(34, 34)
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("DecKoOS Store", "brand", wrap=False))
        names.addWidget(label("Apps for your PC", "muted", wrap=False))
        brand.addLayout(names, 1)
        sl.addLayout(brand)
        sl.addSpacing(16)
        self.nav = QButtonGroup(self)
        self.nav_buttons = {}
        entries = [("home", "Home", "home")] + [(k, t, i) for k, t, i, _m in CATEGORIES]
        for key, title, ic in entries:
            self.add_nav(sl, key, title, ic)
            if key == "home":
                sl.addSpacing(8)
                sl.addWidget(label("  CATEGORIES", "kicker"))
                sl.addSpacing(2)
        sl.addSpacing(10)
        sl.addWidget(label("  YOUR APPS", "kicker"))
        sl.addSpacing(2)
        self.add_nav(sl, "installed", "Installed", "check")
        sl.addStretch(1)
        self.status = label("Loading apps…", "muted")
        sl.addWidget(self.status)
        sl.addSpacing(4)
        sl.addWidget(row(button("Refresh apps", slot=self.refresh_catalog, icon="refresh",
                                tip="Re-read the app lists (Flathub's is downloaded again)")))
        return side

    def add_nav(self, layout, key, title, ic):
        b = QPushButton("  " + title.replace("&", "&&"))
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        b.setIcon(S.icon(ic, S.SUBTEXT, 18, active=S.TEXT))
        b.setIconSize(QSize(18, 18))
        b.clicked.connect(lambda _c, k=key: self.open_section(k))
        self.nav.addButton(b)
        self.nav_buttons[key] = b
        layout.addWidget(b)

    def build_topbar(self):
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(26, 16, 26, 6)
        h.setSpacing(10)
        self.back_btn = button("", slot=self.back, icon="chevron-left", tip="Back")
        self.back_btn.setFixedWidth(40)
        self.back_btn.setEnabled(False)
        h.addWidget(self.back_btn)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search apps, games and packages")
        self.search.addAction(S.icon("search", S.SUBTEXT, 16), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(38)
        self.search.setStyleSheet(f"QLineEdit {{ background: {S.SURFACE}; border: 1px solid {S.BORDER}; "
                                  f"border-radius: 9px; padding: 6px 10px; font-size: 10.5pt; }}"
                                  f"QLineEdit:focus {{ border-color: {S.P.accent}; }}")
        self.search_timer = QTimer(self, singleShot=True, interval=280, timeout=self.run_search)
        self.search.textChanged.connect(lambda _t: self.search_timer.start())
        self.search.returnPressed.connect(self.run_search)
        h.addWidget(self.search, 1)
        self.working = label("", "muted", wrap=False)
        h.addWidget(self.working)
        return bar

    def toast(self, text, kind="info", ms=5000):
        self.toast_box.show_message(text, kind, ms)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast_box.isVisible():
            self.toast_box.move(self.width() - self.toast_box.width() - 22, self.height() - self.toast_box.height() - 20)

    # ---- pages

    def show_page(self, widget, nav=None, remember=True):
        if self.current is not None and remember:
            self.history.append(self.current)
        self.current = (widget, nav)
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        for i in reversed(range(self.stack.count())):  # keep the history's pages, drop the rest
            w = self.stack.widget(i)
            if w is not widget and all(w is not h[0] for h in self.history):
                self.stack.removeWidget(w)
                w.deleteLater()
        if nav and nav in self.nav_buttons:
            self.nav_buttons[nav].setChecked(True)
        self.back_btn.setEnabled(bool(self.history))

    def back(self):
        if self.history:
            widget, nav = self.history.pop()
            self.current = None
            self.show_page(widget, nav, remember=False)

    def page(self, title, subtitle=""):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 14, 30, 28)
        lay.setSpacing(14)
        if title:
            lay.addWidget(label(title, "title"))
        if subtitle:
            lay.addWidget(label(subtitle, "sub"))
        return w, lay

    def show_loading(self):
        w, lay = self.page("")
        lay.addStretch(1)
        lay.addWidget(Empty("store", "Loading apps…", "Reading the Arch, CachyOS and Flathub app lists. The first "
                                                     "time takes a few seconds."))
        lay.addStretch(2)
        self.show_page(scrolling(w), "home", remember=False)

    def _load(self):
        self.installed.refresh()
        self.catalog.load()
        self.bridge.loaded.emit()

    def catalog_ready(self):
        self.status.setText(self.catalog.status)
        self.history.clear()
        self.current = None
        self.open_section("home")
        if self.start_app or self.start_search:  # asked for on the command line; only the first load
            app = self.catalog.apps.get(norm(self.start_app)) if self.start_app else None
            term = self.start_search or self.start_app
            self.start_app = self.start_search = ""
            if app:
                self.open_app(app)
            else:
                self.search.blockSignals(True)
                self.search.setText(term)
                self.search.blockSignals(False)
                self.run_search()

    def refresh_catalog(self):
        if self.installed.flathub_ready:
            self.jobs.add("flathub-refresh", "refresh-flathub", "flathub", "", "Flathub app list")
        else:
            self.reload()

    def reload(self):
        self.status.setText("Loading apps…")
        threading.Thread(target=self._load, daemon=True).start()

    def open_section(self, key):
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        if key == "home":
            self.show_page(self.home_page(), "home")
        elif key == "installed":
            apps = sorted((a for a in self.catalog.apps.values() if self.installed.app_installed(a)),
                          key=lambda a: a.name.lower())
            self.show_page(self.list_page("Installed", f"{len(apps)} apps from the Store's catalog. Command-line "
                                                       "tools and libraries aren't listed.", apps), "installed")
        else:
            cat = next(c for c in CATEGORIES if c[0] == key)
            apps = self.catalog.in_category(key)
            self.show_page(self.list_page(cat[1], f"{len(apps):,} app{'' if len(apps) == 1 else 's'}", apps), key)

    def card(self, app):
        c = AppCard(app, self.installed)
        c.clicked.connect(self.open_app)
        return c

    def home_page(self):
        w, lay = self.page("")
        hero = QFrame()
        hero.setAttribute(Qt.WA_StyledBackground, True)
        hero.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {S.P.accent}, "
                           f"stop:1 {S.P.grad_b}); border-radius: 14px;")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(28, 24, 28, 24)
        hv.setSpacing(4)
        t = label("Apps for DecKoOS", "title")
        t.setStyleSheet("color: white; background: transparent;")
        hv.addWidget(t)
        s = label("Games, creative tools and everything else, from Arch and CachyOS, Flathub and the AUR. "
                  "Install with one click; updates come with DecKoOS.", "sub")
        s.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        hv.addWidget(s)
        lay.addWidget(hero)

        if not self.installed.flathub_ready:
            fh = Card("Flathub", "Thousands more apps", "store")
            fh.body.addWidget(label("Flathub isn't set up on this PC yet. It adds apps like Spotify, Discord and "
                                    "Bottles that aren't in the Arch repos.", "sub"))
            fh.body.addWidget(row(button("Set up Flathub", "primary", lambda: self.jobs.add(
                "flathub-setup", "setup-flathub", "flathub", "", "Flathub"), icon="plus")))
            lay.addWidget(fh)

        lay.addWidget(label("EDITOR'S PICKS", "kicker"))
        grid = CardGrid()
        grid.set_cards([self.card(a) for a in self.catalog.featured()])
        lay.addWidget(grid)

        lay.addSpacing(6)
        lay.addWidget(label("BROWSE", "kicker"))
        cats = QGridLayout()
        cats.setSpacing(10)
        for i, (key, title, ic, _m) in enumerate(CATEGORIES):
            tile = QFrame()
            tile.setObjectName("tile")
            tile.setAttribute(Qt.WA_StyledBackground, True)
            tile.setCursor(Qt.PointingHandCursor)
            th = QHBoxLayout(tile)
            th.setContentsMargins(16, 14, 16, 14)
            th.setSpacing(12)
            th.addWidget(icon_label(ic, S.P.accent, 22))
            tv = QVBoxLayout()
            tv.setSpacing(0)
            tv.addWidget(label(title, "cardTitle", wrap=False))
            n = sum(1 for a in self.catalog.apps.values() if a.section() == key)
            tv.addWidget(label(f"{n:,} app{'' if n == 1 else 's'}", "muted", wrap=False))
            th.addLayout(tv, 1)
            tile.mousePressEvent = lambda _e, k=key: self.open_section(k)
            cats.addWidget(tile, i // 3, i % 3)
        for c in range(3):
            cats.setColumnStretch(c, 1)
        lay.addLayout(cats)
        lay.addStretch(1)
        return scrolling(w)

    def list_page(self, title, subtitle, apps, aur_slot=False):
        w, lay = self.page(title, subtitle)
        grid = CardGrid()
        shown = [PAGE_SIZE]
        grid.set_cards([self.card(a) for a in apps[:PAGE_SIZE]])
        lay.addWidget(grid)
        if not apps and not aur_slot:
            lay.addWidget(Empty("store", "Nothing here yet", "Apps you install from the Store show up here."
                                if title == "Installed" else "No apps in this category."))
        more = button("Show more", slot=None, icon="plus")

        def show_more():
            shown[0] += PAGE_SIZE
            grid.set_cards([self.card(a) for a in apps[:shown[0]]])
            more.setVisible(len(apps) > shown[0])
        more.clicked.connect(show_more)
        more.setVisible(len(apps) > PAGE_SIZE)
        lay.addWidget(row(more))
        if aur_slot:
            self.aur_box = QVBoxLayout()
            self.aur_box.setSpacing(6)
            lay.addLayout(self.aur_box)
        lay.addStretch(1)
        return scrolling(w)

    # ---- search

    def run_search(self):
        term = self.search.text().strip()
        if not term:
            if self.current and getattr(self.current[0], "search_page", False):
                self.open_section("home")
            return
        apps = self.catalog.search(term)
        page = self.list_page(f"Results for “{term}”", f"{len(apps)} app{'' if len(apps) == 1 else 's'}" if apps else "No apps in the catalog "
                              "match; the AUR is being searched too.", apps, aur_slot=True)
        page.search_page = True
        replacing = self.current and getattr(self.current[0], "search_page", False)
        self.show_page(page, None, remember=not replacing)
        self.nav.setExclusive(False)
        for b in self.nav_buttons.values():
            b.setChecked(False)
        self.nav.setExclusive(True)
        self.aur_box.addWidget(label("Searching the AUR…", "muted"))
        self.search_token += 1
        token, known = self.search_token, {a.sources.get("repo") for a in apps}

        def work():
            try:
                res = [r for r in aur_search(term) if r[0] not in known]
            except Exception as e:  # noqa: BLE001 (network errors of every kind)
                res = e
            self.bridge.aur.emit(token, res)
        threading.Thread(target=work, daemon=True).start()

    def aur_results(self, token, res):
        if token != self.search_token:
            return
        box = self.aur_box
        while box.count():
            item = box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if isinstance(res, Exception):
            box.addWidget(label("Couldn't reach the AUR.", "muted"))
            return
        if not res:
            return
        card = Card("From the AUR", "Community packages", "package")
        card.body.addWidget(label("Built from scripts the community writes; Arch doesn't check them. Read the "
                                  "package page if you're unsure, and prefer an Arch or Flathub version.", "sub"))
        for name, version, desc, votes in res:
            key = f"aur:{name}"
            installed = name in self.installed.aur
            # Plain, not the bright primary: community packages aren't checked, so they shouldn't look like the safe pick
            btn = button("Installed" if installed else "Install", None,
                         lambda _c=False, n=name: self.jobs.add(f"aur:{n}", "install", "aur", n, n),
                         icon=None if installed else "download")
            btn.setEnabled(not installed and not self.jobs.busy(key))
            link = button("", slot=lambda _c=False, n=name: QProcess.startDetached(
                "xdg-open", [f"https://aur.archlinux.org/packages/{n}"]), icon="external", tip="Package page")
            card.body.addWidget(RowItem("package", f"{name}  <span style='color:{S.MUTED}'>{version} · "
                                                   f"{votes} votes</span>", desc, right=[link, btn]))
        box.addWidget(card)

    # ---- app page

    def open_app(self, app):
        w, lay = self.page("")
        head = QHBoxLayout()
        head.setSpacing(18)
        ic = AppIcon(96)
        ic.show_app(app)
        head.addWidget(ic, 0, Qt.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(3)
        info.addWidget(label(app.name, "title"))
        meta = " · ".join(x for x in (app.developer, app.version and f"Version {app.version}") if x)
        if meta:
            info.addWidget(label(meta, "sub"))
        info.addWidget(label(app.summary))
        badges = QHBoxLayout()
        badges.setSpacing(6)
        for s in SOURCE_ORDER:
            if s in app.sources:
                badges.addWidget(badge(s, small=False))
        badges.addStretch(1)
        info.addSpacing(4)
        info.addLayout(badges)
        head.addLayout(info, 1)
        self.actions = QVBoxLayout()
        self.actions.setSpacing(8)
        head.addLayout(self.actions)
        lay.addLayout(head)

        self.progress_box = QWidget()
        pv = QVBoxLayout(self.progress_box)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(5)
        self.progress = Meter(6)
        self.progress_text = label("", "sub")
        pv.addWidget(self.progress)
        details = button("Details", slot=lambda: self.log_view.setVisible(not self.log_view.isVisible()))
        pv.addWidget(row(self.progress_text, details))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(150)
        self.log_view.hide()
        pv.addWidget(self.log_view)
        lay.addWidget(self.progress_box)

        shots = Screenshots()
        lay.addWidget(shots)
        shots.show_urls(app.screenshots)

        about = Card("About", None, "info")
        desc = label(app.description or app.summary)
        desc.setTextFormat(Qt.RichText)
        desc.setOpenExternalLinks(True)
        about.body.addWidget(desc)
        lay.addWidget(about)

        facts = Card("Information", None, "package")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        rows = [("Available from", ", ".join(SOURCE_NAMES[s] for s in SOURCE_ORDER if s in app.sources)),
                ("Package", app.sources.get("repo", "")), ("Flathub ID", app.sources.get("flathub", "")),
                ("License", app.license), ("Developer", app.developer),
                ("Website", f"<a href='{app.homepage}' style='color:{S.P.accent}'>{app.homepage}</a>"
                 if app.homepage else "")]
        for i, (k, v) in enumerate(r for r in rows if r[1]):
            grid.addWidget(label(k, "sub", wrap=False), i, 0, Qt.AlignTop)
            val = label(v)
            val.setOpenExternalLinks(True)
            grid.addWidget(val, i, 1)
        grid.setColumnStretch(1, 1)
        facts.body.addLayout(grid)
        lay.addWidget(facts)
        lay.addStretch(1)

        self.app_open = app
        self.show_page(scrolling(w), None)
        self.paint_actions()

    def paint_actions(self):
        """Install / Open / Remove for the app page, matching what's installed and running."""
        app = getattr(self, "app_open", None)
        if app is None:
            return
        try:
            while self.actions.count():
                item = self.actions.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        except RuntimeError:  # page already closed
            return
        job = self.jobs.by_key.get(app.key)
        source = app.best_source(self.installed)
        inst = source and self.installed.has(source, app.sources[source])
        if job and job.ok is None:
            b = button("Working…", "primary")
            b.setEnabled(False)
            self.actions.addWidget(b)
        elif inst:
            self.actions.addWidget(button("Open", "primary", lambda: self.launch(app, source), icon="play"))
            self.actions.addWidget(button("Remove", slot=lambda: self.jobs.add(
                app.key, "remove", source, app.sources[source], app.name), icon="trash"))
            self.actions.addWidget(label(f"Installed from {SOURCE_NAMES[source]}", "muted", wrap=False))
        else:
            available = [s for s in SOURCE_ORDER if s in app.sources and (s != "flathub" or self.installed.flathub_ready)]
            if not available:
                self.actions.addWidget(label("Set up Flathub (Home page) to install this.", "muted", wrap=False))
                return
            pick = QComboBox()
            for s in available:
                pick.addItem(SOURCE_NAMES[s] + ("  (recommended)" if s == available[0] and len(available) > 1 else ""), s)
            pick.setVisible(len(available) > 1)
            self.actions.addWidget(button("Install", "primary", lambda: self.jobs.add(
                app.key, "install", pick.currentData(), app.sources[pick.currentData()], app.name), icon="download"))
            self.actions.addWidget(pick)
            if len(available) == 1:
                self.actions.addWidget(label(f"From {SOURCE_NAMES[available[0]]}", "muted", wrap=False))
        if job and job.ok is False and job.text != "Cancelled.":
            log = "\n".join(job.log[-40:])
            self.actions.addWidget(button("Ask DecKoOS Assistant", slot=lambda: ask_assistant(
                f"On DecKoOS, {'installing' if job.action == 'install' else 'removing'} {app.name} from "
                f"{SOURCE_NAMES.get(job.source, job.source)} failed. Explain what went wrong and how to fix it. "
                f"The end of its output:\n{log}"), icon="ai"))
        self.actions.addStretch(1)
        self.paint_progress()

    def paint_progress(self):
        app = getattr(self, "app_open", None)
        job = self.jobs.by_key.get(app.key) if app else None
        try:
            self.progress_box.setVisible(job is not None)
        except RuntimeError:
            return
        if job:
            self.progress.set(job.progress, None if job.ok is not False else S.DANGER)
            self.progress_text.setText(job.text)
            self.log_view.setPlainText("\n".join(job.log))
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def launch(self, app, source):
        if source == "flathub":
            QProcess.startDetached("flatpak", ["run", app.sources["flathub"]])
        elif app.desktop_id:
            if not QProcess.startDetached("kstart", ["--application", app.desktop_id]):
                QProcess.startDetached("gio", ["launch", f"/usr/share/applications/{app.desktop_id}"])
        self.toast(f"Opening {app.name}…")

    # ---- jobs

    def job_changed(self, key):
        active = [j for j in self.jobs.by_key.values() if j.ok is None]
        self.working.setText(f"{len(active)} task{'s' if len(active) != 1 else ''} running" if active else "")
        app = getattr(self, "app_open", None)
        if app and key == app.key:
            if self.jobs.by_key[key].progress == 0 or self.jobs.by_key[key].ok is not None:
                self.paint_actions()
            else:
                self.paint_progress()

    def job_done(self, key, ok, msg):
        self.toast(msg, "ok" if ok else "bad", 6000)
        if key in ("flathub-setup", "flathub-refresh"):
            if ok and key == "flathub-setup":
                self.jobs.add("flathub-refresh", "refresh-flathub", "flathub", "", "Flathub app list")
            else:
                self.reload()
            return
        job = self.jobs.by_key[key]
        if DEMO and ok and job.action in ("install", "remove"):
            self.installed.demo_apply(job.action, job.source, job.ident)
        self.installed.refresh()
        self.paint_actions()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Store")
    app.setDesktopFileName("deckos-store")
    app.setFont(QFont("Inter", 10))
    app.setStyleSheet(S.qss())
    w = Store()
    w.show()
    if "--screenshot" in sys.argv:  # --demo --screenshot DIR: every section, for checking layouts anywhere
        out = Path(sys.argv[sys.argv.index("--screenshot") + 1])
        out.mkdir(parents=True, exist_ok=True)
        keys = list(w.nav_buttons)

        def shoot(i=0):
            if i:
                w.grab().save(str(out / f"store-{keys[i - 1]}.png"))
            if i == len(keys):
                app.exit(0)
                return
            w.open_section(keys[i])
            QTimer.singleShot(900, lambda: shoot(i + 1))
        QTimer.singleShot(900, shoot)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
