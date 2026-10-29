"""DecKoOS What's New: what a feature release brought, once, after the update.

Reads the release notes in /usr/share/deckos/releases/*.toml (one per feature release: name, tagline,
highlights with a screenshot and a "Try it" button, fixes) and shows every release newer than the one
this user last saw, newest first, so skipping a release doesn't skip its news.

    deckos-whatsnew                  the newest release's notes (and everything since the last one seen)
    deckos-whatsnew --if-new         only if there's a release this user hasn't seen (login, after an update)
    deckos-whatsnew --release 0.4.0  one release
    deckos-whatsnew --demo [--screenshot FILE]
"""
import os
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "hub")]

from PySide6.QtCore import QProcess, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QFont, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,  # noqa: E402
                               QWidget)

import hub_style as S  # noqa: E402
from hub_widgets import button, icon_label, label  # noqa: E402

DEMO = "--demo" in sys.argv
SHARE = Path(os.environ.get("DECKOS_RELEASES") or "/usr/share/deckos/releases")
if DEMO or not SHARE.is_dir():  # a checkout's notes, for running from the repo
    SHARE = HERE.parents[2] / "share/deckos/releases"
SEEN = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "deckos/whatsnew-seen"


def vkey(version):
    return tuple(int(x) for x in version.split(".") if x.isdigit())


def installed():
    """This PC's DecKoOS version, or "" (a checkout, the demo: every release counts)."""
    try:
        return Path("/usr/share/deckos/version").read_text().strip() if not DEMO else ""
    except OSError:
        return ""


def releases():
    """Every release's notes up to the installed version, newest first. Notes are written as the
    features land, so a dev-install of a checkout carries the next release's before it exists."""
    out, now = [], installed()
    for f in SHARE.glob("*.toml"):
        try:
            notes = tomllib.loads(f.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            continue
        notes.setdefault("version", f.stem)
        if now and vkey(now) and vkey(notes["version"]) > vkey(now):
            continue
        out.append(notes)
    return sorted(out, key=lambda n: vkey(n["version"]), reverse=True)


def seen():
    try:
        return SEEN.read_text().strip()
    except OSError:
        return ""


def mark_seen(version):
    if DEMO:
        return
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(version + "\n")


QSS = f"""
#hero, #feature {{ background: transparent; border: none; }}  /* notched plates: hub_style */
#hero QLabel {{ background: transparent; color: white; }}
QLabel#heroKicker {{ font-family: "Chakra Petch"; font-size: 9.5pt; font-weight: 700; letter-spacing: 2px; color: rgba(255,255,255,0.8); }}
QLabel#heroName {{ font-family: "Inter Display", "Inter"; font-size: 26pt; font-weight: 700; }}
QLabel#heroTag {{ font-size: 11pt; color: rgba(255,255,255,0.9); }}
#feature QLabel {{ background: transparent; }}
QLabel#shot {{ border-radius: 2px; }}
QLabel#featTitle {{ font-size: 12pt; font-weight: 600; }}
"""


class Feature(QFrame):
    def __init__(self, item):
        super().__init__()
        self.setObjectName("feature")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(icon_label(item.get("icon") or "star", S.P.accent, 20))
        head.addWidget(label(item["title"], "featTitle"), 1)
        lay.addLayout(head)
        lay.addWidget(label(item.get("text", "").replace("`", ""), "sub"))
        if item.get("image"):
            pm = QPixmap(str(SHARE / item["image"]))
            if not pm.isNull():
                shot = QLabel()
                shot.setObjectName("shot")
                width, ratio = min(pm.width(), 620), self.devicePixelRatioF()
                scaled = pm.scaledToWidth(round(width * ratio), Qt.SmoothTransformation)
                scaled.setDevicePixelRatio(ratio)  # sharp on HiDPI screens
                shot.setPixmap(scaled)
                lay.addWidget(shot, 0, Qt.AlignLeft)
        if item.get("try") and item.get("run"):
            run = list(item["run"])
            lay.addWidget(button(item["try"], "primary", lambda: self.launch(run), icon="arrow-right"), 0, Qt.AlignLeft)

    @staticmethod
    def launch(run):
        if not DEMO:
            QProcess.startDetached(run[0], run[1:])


class WhatsNew(QWidget):
    def __init__(self, notes):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("What's new in DecKoOS")
        self.setStyleSheet(S.styled(S._qss() + QSS))
        self.resize(760, 820)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(14)
        for i, rel in enumerate(notes):
            if i:
                lay.addSpacing(18)
            lay.addWidget(self.hero(rel, first=(i == 0)))
            for item in rel.get("highlights", []):
                lay.addWidget(Feature(item))
            fixes = rel.get("fixes") or []
            if fixes:
                card = QFrame()
                card.setObjectName("feature")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(18, 14, 18, 14)
                cl.setSpacing(6)
                head = QHBoxLayout()
                head.addWidget(icon_label("check", S.SUCCESS, 18))
                head.addWidget(label("Also fixed", "featTitle"), 1)
                cl.addLayout(head)
                for f in fixes:
                    cl.addWidget(label("•  " + f, "sub"))
                lay.addWidget(card)
        lay.addStretch(1)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        foot = QHBoxLayout()
        foot.setContentsMargins(24, 10, 24, 18)
        foot.addWidget(label("Open this again from DecKoOS Hub, or with deckos whatsnew.", "muted"), 1)
        foot.addWidget(button("Done", "primary", self.close))
        outer.addLayout(foot)

    @staticmethod
    def hero(rel, first):
        hero = QFrame()
        hero.setObjectName("hero")
        hero.setAttribute(Qt.WA_StyledBackground, True)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(26, 22, 26, 24)
        hl.setSpacing(4)
        kicker = QLabel(("WHAT'S NEW IN DECKOOS " if first else "ALSO NEW: DECKOOS ") + rel["version"])
        kicker.setObjectName("heroKicker")
        name = QLabel(rel.get("name", "DecKoOS " + rel["version"]))
        name.setObjectName("heroName")
        tag = QLabel(rel.get("tagline", ""))
        tag.setObjectName("heroTag")
        tag.setWordWrap(True)
        for w in (kicker, name, tag):
            hl.addWidget(w)
        return hero


def main():
    args = sys.argv[1:]
    all_notes = releases()
    if not all_notes:
        return 0
    if "--release" in args:
        want = args[args.index("--release") + 1]
        notes = [n for n in all_notes if n["version"] == want]
    else:
        last = seen()
        newer = [n for n in all_notes if not last or vkey(n["version"]) > vkey(last)]
        if "--if-new" in args and not newer:
            return 0
        notes = newer or all_notes[:1]
    if not notes:
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS What's New")
    app.setDesktopFileName("deckos-whatsnew")
    app.setFont(QFont("Inter", 10))
    w = WhatsNew(notes)
    w.show()
    mark_seen(all_notes[0]["version"])  # shown once: closing it early still counts
    if "--screenshot" in args:
        out = args[args.index("--screenshot") + 1]

        def shoot():
            page = w.findChild(QScrollArea).widget()
            page.resize(page.width(), page.sizeHint().height())
            page.grab().save(out)
            app.exit(0)
        QTimer.singleShot(600, shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
