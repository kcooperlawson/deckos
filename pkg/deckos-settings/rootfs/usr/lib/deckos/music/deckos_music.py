"""DecKoOS Music: Vibe mode. Whatever plays (Spotify, a browser, any player, or your own files played here) takes
over every screen as one stage that moves with the sound.

Opening it plays the way in: the stage opens as a circle out of the cover and spreads across the monitors. Each
monitor is a window onto one world (world.py), so a beat's shockwave leaves the cover and rolls onto the next
screen, comets fly from one monitor to another, and the aurora, the horizon and the song's title run edge to
edge; more monitors, a bigger world. Your library slides in from the side (L). Esc plays the way out; your own
music keeps going in a small player, anything else just carries on in its app.

The sound comes from analysis.py (what the PC actually plays). How it looks (aurora, a 2000s spectrum analyzer,
2000s feedback trails or a calm glow, in your Vibe's colours or the cover's) is looks.py: it follows your Vibe. Everything that moves
is drawn on the graphics card (qml/stage.frag and plain items), and it stops when a game starts.

    deckos-music [--demo] [--demo-screens N] [--offer] [--screenshot DIR [--record SECONDS]] [--style STYLE]

--offer asks first ("Vibe mode?" as a notification): DecKoOS Context does that when music starts.
"""
import hashlib
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import (Property, QFileSystemWatcher, QObject, QPointF, QSize, Qt, QThread, QTimer, QUrl, Signal,
                            Slot)
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QLinearGradient, QPainter
from PySide6.QtNetwork import QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkRequest
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hub")]
import analysis  # noqa: E402
import hub_style as S  # noqa: E402
import library  # noqa: E402
import looks  # noqa: E402
import lyrics  # noqa: E402
import sources  # noqa: E402
import world  # noqa: E402

DEMO = "--demo" in sys.argv
ART_CACHE = library.CACHE / "art"
SOCKET = f"deckos-music-{os.getuid()}"
MODE_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "deckos-mode"
# Beats are drawn as if they came this much sooner: the picture trails the sound (capture ~15 ms, analysis ~24,
# drawing ~16-25) by more than the speakers do (20-45 ms on a 1024-sample PipeWire quantum). Worked out, not measured
# with a microphone.
BEAT_LEAD = 0.03
# Lyrics show a touch early: a line read just as it's sung feels late
LYRIC_LEAD = 0.25
# The demo song's lyrics (made up, like the song), so the demo shows them anywhere
DEMO_LRC = "\n".join(f"[{m:02d}:{sec:05.2f}]{text}" for m, sec, text in [
    (1, 20.0, "Neon on the water"), (1, 24.0, "the city hums in blue"), (1, 28.0, "every light a heartbeat"),
    (1, 32.0, "every beat for you"), (1, 36.0, "Turn it up, turn it up"), (1, 40.0, "till the night lets go"),
    (1, 44.0, "Afterglow, afterglow"), (1, 48.0, "carry me home"), (1, 52.0, ""), (1, 56.0, "Neon on the water"),
    (2, 0.0, "the city hums in blue"), (2, 4.0, "Afterglow, afterglow"), (2, 8.0, "carry me home")])


# ------------------------------------------------------------------ colours from a cover

def palette(img):
    """(base, accent, second) colours from a cover: the base dark enough for white text, the accent the most vivid
    colour that's really in the picture, the second a different hue from it."""
    if img is None or img.isNull():
        return QColor("#141826"), QColor(S.P.accent), QColor("#7A5CFF")
    small = img.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    px = [small.pixelColor(x, y) for x in range(24) for y in range(24)]
    buckets = {}
    for c in px:
        h, s, v, _ = c.getHsvF()
        if s < 0.25 or v < 0.2:
            continue
        key = int((h if h >= 0 else 0) * 12)
        b = buckets.setdefault(key, [0, QColor(c), 0.0])
        b[0] += 1
        if s * v > b[2]:
            b[1], b[2] = QColor(c), s * v
    avg = QColor(sum(c.red() for c in px) // len(px), sum(c.green() for c in px) // len(px),
                 sum(c.blue() for c in px) // len(px))
    base = QColor.fromHsvF(max(avg.hsvHueF(), 0), min(avg.hsvSaturationF() * 0.9, 0.6), 0.16)
    ranked = sorted(buckets.items(), key=lambda kv: -(kv[1][0] * (0.5 + kv[1][2])))
    if not ranked:
        return base, QColor(S.P.accent), QColor("#7A5CFF")
    accent = QColor.fromHsvF(max(ranked[0][1][1].hsvHueF(), 0), max(ranked[0][1][1].hsvSaturationF(), 0.55), 1.0)
    second = next((QColor.fromHsvF(max(b[1].hsvHueF(), 0), max(b[1].hsvSaturationF(), 0.5), 0.95)
                   for k, b in ranked[1:] if min(abs(k - ranked[0][0]), 12 - abs(k - ranked[0][0])) >= 2),
                  QColor.fromHsvF((accent.hsvHueF() + 0.45) % 1, 0.6, 0.95))
    return base, accent, second


def demo_cover(seed=1):
    """A made-up album cover for the demo (no pictures shipped): bold shapes in two colours."""
    img = QImage(600, 600, QImage.Format_RGB32)
    rng = random.Random(seed)
    a = QColor.fromHsvF(rng.random(), 0.75, 0.95)
    b = QColor.fromHsvF((a.hsvHueF() + 0.5) % 1, 0.7, 0.55)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 600, 600)
    g.setColorAt(0, b.darker(180))
    g.setColorAt(1, b)
    p.fillRect(img.rect(), g)
    p.setPen(Qt.NoPen)
    for i in range(6):
        c = QColor(a)
        c.setAlphaF(0.25 + 0.12 * i)
        p.setBrush(c)
        r = 260 - i * 40
        p.drawEllipse(QPointF(300 + rng.randint(-60, 60), 300 + rng.randint(-60, 60)), r, r)
    p.end()
    return img


def cover_image(ref):
    """A library cover: a file, or demo:N."""
    if ref.startswith("demo:"):
        return demo_cover(int(ref.split(":")[1]) + 1)
    return QImage(ref.removeprefix("file://")) if ref else QImage()


class Pictures(QQuickImageProvider):
    """image://deckos/...: the cover now playing (cover/N), library covers (album/REF) and DecKoOS line icons
    (icon/NAME/RRGGBB)."""

    def __init__(self, engine):
        super().__init__(QQuickImageProvider.Image)
        self.engine = engine
        self.albums = {}

    def requestImage(self, ident, size, requested):
        kind, _, rest = ident.partition("/")
        if kind == "cover":
            img = self.engine.art_img
        elif kind == "album":
            if rest not in self.albums:
                img = cover_image(QUrl.fromPercentEncoding(rest.encode()))
                self.albums[rest] = img.scaled(320, 320, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation) \
                    if not img.isNull() else QImage()
            img = self.albums[rest]
        elif kind == "icon":
            name, _, colour = rest.partition("/")
            img = S.pixmap(name, "#" + (colour or "FFFFFF"), 24, 4.0).toImage()
        else:
            img = QImage()
        if img.isNull():
            img = QImage(4, 4, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
        if size is not None:
            size.setWidth(img.width())
            size.setHeight(img.height())
        return img


class Scanner(QThread):
    done = Signal(list)

    def run(self):
        tracks = library.scan()
        for t in tracks:
            t["cover"] = library.cover_for(t)
        self.done.emit(tracks)


DEMO_ALBUMS = [("Neon Harbour", "Lumen Drive"), ("Glass Weather", "Saint Ivory"), ("Low Orbit", "Kairo"),
               ("Paper Suns", "The Avenues"), ("Velvet Static", "Mara Lune"), ("Night Garden", "Holloway"),
               ("Cinder Bloom", "Ostra"), ("Tidal", "Fen & Rye")]


def demo_tracks():
    names = ["Afterglow", "Undertow", "Satellites", "Halcyon", "Copper Sky", "Slow Burn", "Tangent", "Driftwood"]
    return [{"path": f"/demo/{i}/{n}.flac", "title": names[n - 1], "artist": artist, "album": album, "track": n,
             "duration": 180 + n * 13, "cover": f"demo:{i}"}
            for i, (album, artist) in enumerate(DEMO_ALBUMS) for n in range(1, 9)]


# ------------------------------------------------------------------ the engine the stage reads

class Engine(QObject):
    """Everything the stage windows show, the same for all of them: the music's numbers (60 times a second), the
    song, the cover's colours, the world's layout, and when the way in or out started. Every window works out its
    picture from these and the shared clock (`startMs`), so the screens move together."""
    frame = Signal()
    trackChanged = Signal()
    artChanged = Signal()
    worldChanged = Signal()
    stageChanged = Signal()
    libraryChanged = Signal()
    lookChanged = Signal()
    poked = Signal()
    lyricsChanged = Signal()
    lyricFrame = Signal()
    lyricsReady = Signal(str, object)  # the song's key, its parsed lines (from the lookup thread)

    def __init__(self, fake_screens=0):
        super().__init__()
        self.t0 = time.time()
        self.net = QNetworkAccessManager(self)
        self.analyzer = analysis.FakeAnalyzer() if DEMO else analysis.Analyzer()
        self.spotify = sources.Spotify(demo=sources.Now(
            "spotify", "Afterglow (Extended Mix)", "Lumen Drive", "Neon Harbour", "demo:0", 252, 81, True, True)
            if DEMO else None, players="spotify,%any")
        self.local = None  # made on first use: Qt Multimedia starts its backend then
        self.active = self.spotify
        self.tracks, self.album_list = [], []
        self.art_img, self.art_key, self.art_n = QImage(), None, 0
        self.colours = palette(None)
        self.fake_screens = fake_screens
        self.lay = {}
        self._levels = {"bass": 0.0, "mid": 0.0, "high": 0.0, "energy": 0.0, "intensity": 0.0}
        self._bars = [0.0] * 64
        self._peaks = [0.0] * 64  # each bar's recent top, falling slowly (the spectrum's caps)
        self._beats = []  # when beats landed, in stage seconds
        self._travel = 0.0
        self._last_beat, self._last_tick, self._owed = None, time.time(), 0.0
        self._enter, self._leave, self._mode = -10.0, -10.0, "stage"
        self._poke = -10.0
        self.ticker = QTimer(self, interval=16, timeout=self.tick)
        self.choices, self.vibe = looks.load(), looks.current_vibe()
        # `deckos vibe` rewrites the file: watch its folder, so a new Vibe changes the stage while it's up
        self.vibe_watch = QFileSystemWatcher([str(looks.VIBE_FILE.parent)], self)
        self.vibe_watch.directoryChanged.connect(self.reload_vibe)
        # Lyrics: looked up when the song changes (off this thread), followed 30 times a second while shown
        self._lyrics, self._plain, self._lyric_state, self._lyric_key = [], "", "none", ""
        self._lyric_i, self._lyric_through = -1, 0.0
        self.lyricsReady.connect(self.got_lyrics)
        self.lyric_clock = QTimer(self, interval=33, timeout=self.lyric_tick)
        self.resync_clock = QTimer(self, interval=2000, timeout=lambda: self.active.resync())

        self.spotify.changed.connect(lambda n: self.source_changed(self.spotify, n))
        self.relayout()
        app = QGuiApplication.instance()
        app.screenAdded.connect(self.relayout)
        app.screenRemoved.connect(self.relayout)
        # Games come first: the stage steps aside when workload modes says one started
        self.game_check = QTimer(self, interval=3000, timeout=self.check_game)
        self.game_check.start()
        if DEMO:
            self.got_tracks(demo_tracks())
        else:
            self.scanner = Scanner()
            self.scanner.done.connect(self.got_tracks)
            self.scanner.start()

    def now_s(self):
        return time.time() - self.t0

    # ---- the world

    def relayout(self, *_):
        if self.fake_screens:  # --demo-screens: monitors side by side, for screenshots anywhere
            rects = [(i * 1280, 0, 1280, 720) for i in range(self.fake_screens)]
            primary = 0
        else:
            screens = QGuiApplication.screens()
            rects = [(s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height())
                     for s in screens]
            main = main_screen() or QGuiApplication.primaryScreen().name()
            primary = next((i for i, s in enumerate(screens) if s.name() == main), 0)
        # each monitor's real size (EDID, through Qt), so the world is laid out as the desk is, with the gap
        physical = ([(0, 0)] * len(rects) if self.fake_screens else
                    [(s.physicalSize().width(), s.physicalSize().height()) for s in QGuiApplication.screens()])
        self.lay = world.layout(rects, primary, physical, int(self.choices.get("gap", 0)))
        self.worldChanged.emit()

    @Property("QVariantList", notify=worldChanged)
    def screens(self):
        return self.lay["screens"]

    @Property(float, notify=worldChanged)
    def worldWidth(self):
        return float(self.lay["width"])

    @Property(float, notify=worldChanged)
    def worldHeight(self):
        return float(self.lay["height"])

    @Property(int, notify=worldChanged)
    def home(self):
        return self.lay["home"]

    @Property(QPointF, notify=worldChanged)
    def cover(self):
        return QPointF(*self.lay["cover"])

    @Property(bool, constant=True)
    def fake(self):
        return bool(self.fake_screens)

    # ---- the way in and out

    @Property(float, constant=True)
    def startMs(self):
        return self.t0 * 1000

    @Property(float, notify=stageChanged)
    def enterAt(self):
        return self._enter

    @Property(float, notify=stageChanged)
    def leaveAt(self):
        return self._leave

    @Property(str, notify=stageChanged)
    def mode(self):
        return self._mode  # stage | leaving | mini

    @Slot()
    def enter(self):
        if self._mode == "stage" and self._enter > 0 and self._leave < self._enter:
            return
        self._mode, self._enter = "stage", self.now_s() + 0.15
        self.stageChanged.emit()
        self.running()

    @Slot()
    def leave(self):
        if self._mode != "stage":
            return
        self._mode, self._leave = "leaving", self.now_s()
        self.stageChanged.emit()
        QTimer.singleShot(1200, self.left)

    def left(self):
        # Your own music lives in this app: keep it going in the small player. Anything else plays on in its app.
        if self.local and self.local.now.playing:
            self._mode = "mini"
            self.stageChanged.emit()
            self.running()
        else:
            QGuiApplication.quit()

    @Slot()
    def toggle(self):
        self.leave() if self._mode == "stage" else self.enter()

    @Slot()
    def quit(self):
        QGuiApplication.quit()

    def check_game(self):
        try:
            if "game=" in MODE_FILE.read_text():
                self.leave()
        except OSError:
            pass

    # ---- the music's numbers

    def running(self):
        """Listen and move only while the stage is up and something plays (always, in the demo)."""
        on = self._mode == "stage" and (self.active.now.playing or DEMO)
        if on and not self.ticker.isActive():
            self.analyzer.start()
            self._last_tick = time.time()
            self.ticker.start()
        elif not on and self.ticker.isActive():
            self.ticker.stop()
            self.analyzer.stop()
            self._levels = dict.fromkeys(self._levels, 0.0)
            self._bars = [0.0] * 64
            self._peaks = [0.0] * 64
            self.frame.emit()
        if hasattr(self, "lyric_clock"):
            self.follow_lyrics()

    def tick(self):
        now = time.time()
        dt, self._last_tick = min(now - self._last_tick, 0.1), now
        if DEMO:  # the made-up song runs at its own pace: as many hops as the time that passed
            self._owed += dt * analysis.RATE / analysis.HOP
            f = None
            while self._owed >= 1:
                f, self._owed = self.analyzer.step(), self._owed - 1
                if f["beat"]:
                    self._beats.append(self.now_s())
            f = f or self.analyzer.latest
        else:
            f = self.analyzer.latest
            beat = self.analyzer.beat_at
            if beat and beat != self._last_beat:  # dated when it was heard, not when this frame looked
                self._beats.append(beat - self.t0 - BEAT_LEAD)
            self._last_beat = beat
        self._beats = self._beats[-12:]
        self._levels = {k: float(f.get(k, 0.0)) for k in self._levels}
        self._bars = list(f.get("bars") or self._bars)
        self._peaks = [max(b, p - dt * 0.45) for b, p in zip(self._bars, self._peaks)]
        self._travel += dt * (0.35 + 1.4 * self._levels["intensity"])
        self.frame.emit()

    @Property(float, notify=frame)
    def bass(self):
        return self._levels["bass"]

    @Property(float, notify=frame)
    def mid(self):
        return self._levels["mid"]

    @Property(float, notify=frame)
    def high(self):
        return self._levels["high"]

    @Property(float, notify=frame)
    def energy(self):
        return self._levels["energy"]

    @Property(float, notify=frame)
    def intensity(self):
        return self._levels["intensity"]

    @Property(float, notify=frame)
    def travel(self):
        return self._travel

    @Property("QVariantList", notify=frame)
    def bars(self):
        return self._bars

    @Property("QVariantList", notify=frame)
    def peaks(self):
        return self._peaks

    @Property("QVariantList", notify=frame)
    def beats(self):
        return self._beats

    # ---- the song

    def source_changed(self, src, now):
        # The one that's playing is the one shown; the player stays when nothing plays
        if now.playing or src is self.active or not self.active.now.playing:
            self.active = src
        self.load_art(self.active.now.art)
        self.trackChanged.emit()
        self.running()
        self.find_lyrics()

    def ensure_local(self):
        if self.local is None:
            self.local = sources.Local()
            self.local.changed.connect(lambda n: self.source_changed(self.local, n))
        return self.local

    @Property(str, notify=trackChanged)
    def title(self):
        return self.active.now.title

    @Property(str, notify=trackChanged)
    def artist(self):
        return self.active.now.artist

    @Property(str, notify=trackChanged)
    def album(self):
        return self.active.now.album

    @Property(bool, notify=trackChanged)
    def playing(self):
        return self.active.now.playing

    @Property(float, notify=trackChanged)
    def length(self):
        return float(self.active.now.length or 0)

    @Slot(result=float)
    def position(self):
        """Read by the seek bar while it's shown (players report it only now and then)."""
        if self.active is self.local and self.local:
            return float(self.local.now.position)
        return float(self.active.now.position)

    @Slot()
    def playPause(self):
        self.active.play_pause()

    @Slot()
    def next(self):
        self.active.next()

    @Slot()
    def previous(self):
        self.active.previous()

    @Slot(float)
    def seek(self, seconds):
        self.active.seek(seconds)

    @Slot()
    def poke(self):
        """The mouse moved or a key was pressed: the controls show on every screen for a moment."""
        self._poke = self.now_s()
        self.poked.emit()

    @Property(float, notify=poked)
    def pokedAt(self):
        return self._poke

    # ---- the cover and its colours

    def load_art(self, ref):
        if DEMO:
            ref = "demo:0"
        if ref == self.art_key:
            return
        self.art_key = ref
        if ref.startswith("http"):
            cached = ART_CACHE / (hashlib.sha1(ref.encode()).hexdigest() + ".jpg")
            if cached.exists():
                self.set_art(QImage(str(cached)))
                return
            reply = self.net.get(QNetworkRequest(QUrl(ref)))
            reply.finished.connect(lambda r=reply, c=cached, k=ref: self.got_art(r, c, k))
        else:
            self.set_art(cover_image(ref))

    def got_art(self, reply, cached, key):
        data = bytes(reply.readAll())
        reply.deleteLater()
        if key != self.art_key or not data:
            return
        ART_CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        self.set_art(QImage.fromData(data))

    def set_art(self, img):
        self.art_img = img
        self.colours = palette(img if not img.isNull() else None)
        self.art_n += 1
        self.artChanged.emit()

    @Property(str, notify=artChanged)
    def art(self):
        return f"image://deckos/cover/{self.art_n}" if not self.art_img.isNull() else ""

    def shown_colours(self):
        if looks.resolve(self.choices, self.vibe)[1] == "vibe":
            return [QColor(c) for c in looks.vibe_colours(self.vibe)]
        return self.colours

    @Property(QColor, notify=artChanged)
    def base(self):
        return self.shown_colours()[0]

    @Property(QColor, notify=artChanged)
    def accent(self):
        return self.shown_colours()[1]

    @Property(QColor, notify=artChanged)
    def second(self):
        return self.shown_colours()[2]

    # ---- how it looks (looks.py)

    def reload_vibe(self, *_):
        vibe = looks.current_vibe()
        if vibe != self.vibe:
            self.vibe = vibe
            self.lookChanged.emit()
            self.artChanged.emit()

    @Property(str, notify=lookChanged)
    def style(self):
        return looks.resolve(self.choices, self.vibe)[0]

    @Property(str, notify=lookChanged)
    def styleChoice(self):
        return self.choices["style"]

    @Property(str, notify=lookChanged)
    def colourChoice(self):
        return looks.resolve(self.choices, self.vibe)[1]

    @Property(str, notify=lookChanged)
    def vibeName(self):
        return (self.vibe or {}).get("name", "")

    @Property(str, notify=lookChanged)
    def vibeStyle(self):
        return looks.NAMES[looks.resolve({**self.choices, "style": "auto"}, self.vibe)[0]]

    @Slot(str)
    def setStyle(self, style):
        if style in ["auto", *looks.STYLES]:
            self.choices["style"] = style
            self.remember()

    @Slot()
    def cycleStyle(self):
        order = looks.STYLES
        self.setStyle(order[(order.index(self.style) + 1) % len(order)])

    @Slot(str)
    def setColours(self, colours):
        if colours in looks.COLOURS:
            self.choices["colours"] = colours
            self.remember()

    def remember(self):
        if not DEMO:
            looks.save(self.choices)
        self.lookChanged.emit()
        self.artChanged.emit()

    # ---- lyrics (lyrics.py)

    def find_lyrics(self):
        now = self.active.now
        key = f"{now.source}|{now.artist}|{now.title}"
        if key == self._lyric_key:
            return
        self._lyric_key = key
        self._lyrics, self._plain, self._lyric_i = [], "", -1
        if not now.title or self.choices.get("lyrics") == "off":
            self._lyric_state = "off" if now.title else "none"
            self.lyricsChanged.emit()
            self.follow_lyrics()
            return
        self._lyric_state = "loading"
        self.lyricsChanged.emit()
        if DEMO:
            QTimer.singleShot(300, lambda: self.lyricsReady.emit(key, {"synced": DEMO_LRC, "plain": ""}))
            return
        path = (now.extra or {}).get("track", {}).get("path", "")
        artist, title, album, length = now.artist, now.title, now.album, now.length

        def look():  # a thread: lyrics.fetch waits on the network
            own = lyrics.local_lrc(path) if path else ""
            self.lyricsReady.emit(key, {"synced": own, "plain": ""} if own else
                                  lyrics.fetch(artist, title, album, length))
        threading.Thread(target=look, daemon=True).start()

    def got_lyrics(self, key, answer):
        if key != self._lyric_key:
            return  # a song that's already gone
        self._lyrics = lyrics.parse_lrc(answer.get("synced", ""))
        self._plain = answer.get("plain", "")
        self._lyric_state = "synced" if self._lyrics else "plain" if self._plain else "none"
        self._lyric_i = -1
        self.lyricsChanged.emit()
        self.follow_lyrics()

    def follow_lyrics(self):
        """The lyric clock (and asking the player where it is) only while synced lyrics are on screen."""
        on = bool(self._lyrics) and self._mode == "stage" and self.active.now.playing
        for clock in (self.lyric_clock, self.resync_clock):
            if on and not clock.isActive():
                clock.start()
            elif not on:
                clock.stop()
        if on:
            self.active.resync()

    def lyric_tick(self):
        i, through = lyrics.at(self._lyrics, self.active.position_now() + LYRIC_LEAD)
        self._lyric_i, self._lyric_through = i, through
        self.lyricFrame.emit()

    @Property("QVariantList", notify=lyricsChanged)
    def lyricLines(self):
        return [{"t": line["t"], "text": line["text"]} for line in self._lyrics]

    @Property(str, notify=lyricsChanged)
    def lyricsPlain(self):
        return self._plain

    @Property(str, notify=lyricsChanged)
    def lyricsState(self):
        """loading, synced, plain (no times: shown as text), none (not found) or off"""
        return self._lyric_state

    @Property(int, notify=lyricFrame)
    def lyricIndex(self):
        return self._lyric_i

    @Property(float, notify=lyricFrame)
    def lyricThrough(self):
        return self._lyric_through

    @Property(bool, notify=lookChanged)
    def lyricsOn(self):
        return self.choices.get("lyrics") != "off"

    @Slot(bool)
    def setLyrics(self, on):
        self.choices["lyrics"] = "on" if on else "off"
        self.remember()
        self._lyric_key = ""  # look again (or stop)
        self.find_lyrics()

    @Property(int, notify=worldChanged)
    def lyricsScreen(self):
        """The screen lyrics fill when there are two or more (-1: one screen, lyrics go under the cover)."""
        i = world.lyrics_screen(self.lay)
        return -1 if i is None else i

    # ---- the gap between the monitors

    @Property(int, notify=lookChanged)
    def gapMm(self):
        return int(self.choices.get("gap", 0))

    @Slot(int)
    def setGap(self, mm):
        self.choices["gap"] = str(max(0, min(looks.GAP_MAX, int(mm))))
        self.remember()
        self.relayout()

    # ---- your library

    def got_tracks(self, tracks):
        self.tracks = tracks
        self.album_list = library.albums(tracks)
        self.libraryChanged.emit()

    @Property("QVariantList", notify=libraryChanged)
    def albums(self):
        return [{"title": a["title"], "artist": a["artist"],
                 "cover": "image://deckos/album/" + QUrl.toPercentEncoding(a["tracks"][0].get("cover", "")).data()
                 .decode()} for a in self.album_list]

    @Slot(int)
    def playAlbum(self, i):
        if DEMO or not 0 <= i < len(self.album_list):
            return
        if self.spotify.now.playing:
            self.spotify.play_pause()  # one thing at a time
        self.ensure_local().play_tracks(self.album_list[i]["tracks"])

    def close(self):
        self.ticker.stop()
        self.analyzer.stop()


def main_screen():
    """The monitor KDE ranks first (Display Configuration's "Primary"): Qt's primaryScreen on Wayland is just the
    first one it heard of."""
    try:
        out = subprocess.run(["kscreen-doctor", "-o"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return world.main_output(out)


# ------------------------------------------------------------------ one at a time

def ask_running(message):
    """Hand a message to the copy that's already running; True if there was one."""
    s = QLocalSocket()
    s.connectToServer(SOCKET)
    if not s.waitForConnected(300):
        return False
    s.write(message.encode())
    s.waitForBytesWritten(300)
    s.disconnectFromServer()
    return True


def offer():
    """Music started: ask, once, as a notification with a button. Only on yes does the stage open."""
    if ask_running("") or "game=" in (MODE_FILE.read_text() if MODE_FILE.exists() else ""):
        return 0
    try:
        r = subprocess.run(["notify-send", "-a", "DecKoOS Music", "-i", "multimedia-audio-player", "-t", "20000",
                            "-A", "vibe=Vibe mode", "Music's on",
                            "Turn your screens into a stage that moves with it."],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if r.stdout.strip() == "vibe":
        os.execvp(sys.executable, [sys.executable, str(Path(__file__)), *[a for a in sys.argv[1:] if a != "--offer"]])
    return 0


def main():
    if "--offer" in sys.argv:
        return offer()
    shots = sys.argv[sys.argv.index("--screenshot") + 1] if "--screenshot" in sys.argv else None
    if not shots and ask_running("toggle"):  # the shortcut again: in or out of the stage
        return 0
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("DecKoOS Music")
    app.setDesktopFileName("deckos-music")
    fonts = HERE.parent.parent.parent / "share/fonts/deckos"
    for f in [*fonts.glob("*.otf"), *fonts.glob("*.ttf")]:  # Inter Display, Chakra Petch
        QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont("Inter", 10))

    fake = int(sys.argv[sys.argv.index("--demo-screens") + 1]) if "--demo-screens" in sys.argv else 0
    engine = Engine(fake)
    if "--style" in sys.argv:  # for screenshots: this look, without remembering it
        engine.choices["style"] = sys.argv[sys.argv.index("--style") + 1]
    server = QLocalServer()
    if not shots:
        QLocalServer.removeServer(SOCKET)
        server.listen(SOCKET)

        def message():
            c = server.nextPendingConnection()
            c.waitForReadyRead(300)
            if bytes(c.readAll()).decode() == "toggle":
                engine.toggle()
        server.newConnection.connect(message)

    qml = QQmlApplicationEngine()
    qml.addImportPath(str(HERE.parent.parent / "qt6/qml"))  # the DecKo look (org.deckos.vibes), next to this app
    qml.addImageProvider("deckos", Pictures(engine))
    qml.rootContext().setContextProperty("engine", engine)
    qml.load(QUrl.fromLocalFile(str(HERE / "qml/Main.qml")))
    if not qml.rootObjects():
        return 1
    app.aboutToQuit.connect(engine.close)
    engine.enter()

    if shots:  # the stage once it's open, every screen's window side by side as one picture
        out = Path(shots)
        out.mkdir(parents=True, exist_ok=True)
        record = float(sys.argv[sys.argv.index("--record") + 1]) if "--record" in sys.argv else 0

        def whole_frame():
            wins = sorted((w for w in app.topLevelWindows() if w.objectName() == "stage" and w.isVisible()),
                          key=lambda w: w.property("originX"))
            whole = QImage(QSize(int(engine.worldWidth), int(engine.worldHeight)), QImage.Format_RGB32)
            whole.fill(Qt.black)
            p = QPainter(whole)
            for w in wins:
                g = w.grabWindow().scaled(w.width(), w.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                g.setDevicePixelRatio(1)
                p.drawImage(int(w.property("originX")), int(w.property("originY")), g)
            p.end()
            return whole

        def film():  # --record: a clip of the stage (for the website), frames as fast as the GPU hands them back
            import subprocess
            import time
            frames = out / "frames"
            frames.mkdir(exist_ok=True)
            start, n = time.monotonic(), 0
            while time.monotonic() - start < record:
                whole_frame().scaledToWidth(1920, Qt.SmoothTransformation).save(str(frames / f"{n:05d}.jpg"), "JPG", 92)
                n += 1
                app.processEvents()
            fps = n / (time.monotonic() - start)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:.2f}", "-i", str(frames / "%05d.jpg"),
                            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-r", "30",
                            str(out / "music-vibe.mp4")], check=False)
            print(f"{n} frames, {fps:.1f} a second -> {out / 'music-vibe.mp4'}")
            app.exit(0)

        def take():
            wins = sorted((w for w in app.topLevelWindows() if w.objectName() == "stage" and w.isVisible()),
                          key=lambda w: w.property("originX"))
            # Each at the window's own size (a 200% monitor grabs twice as many pixels), placed as in the world
            grabs = [(w, w.grabWindow().scaled(w.width(), w.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
                     for w in wins]
            whole = QImage(QSize(int(engine.worldWidth), int(engine.worldHeight)), QImage.Format_ARGB32)
            whole.fill(Qt.black)
            p = QPainter(whole)
            for w, g in grabs:
                g.setDevicePixelRatio(1)
                p.drawImage(int(w.property("originX")), int(w.property("originY")), g)
            p.end()
            whole.save(str(out / f"music-vibe-{len(grabs)}-screens.png"))
            app.exit(0)
        QTimer.singleShot(4500, film if record else take)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
