"""Where DecKoOS Music's sound comes from, behind one shape (`Source`): the Spotify app, followed and controlled
through MPRIS with playerctl (no sign-in; Spotify keeps playing in its own app, free or Premium), and local files,
played here with Qt Multimedia. The window shows whichever is playing; both report `changed` with a `Now` state.
"""
import random
import re
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QProcess, QTimer, QUrl, Signal
try:  # only local playback needs it; Spotify's side (and its tests) work without
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:
    QAudioOutput = QMediaPlayer = None

SEP = "\x1f"  # between playerctl's fields: nothing in a title uses it


@dataclass
class Now:
    source: str = ""  # spotify | local
    title: str = ""
    artist: str = ""
    album: str = ""
    art: str = ""  # a URL or a file path
    length: float = 0.0  # seconds
    position: float = 0.0
    playing: bool = False
    available: bool = False  # the source exists (Spotify is running; there's local music)
    extra: dict = field(default_factory=dict)


def spotify_art(url):
    """Spotify's MPRIS sometimes gives the old open.spotify.com/image/ID address; i.scdn.co serves the same picture."""
    return re.sub(r"^https?://open\.spotify\.com/image/", "https://i.scdn.co/image/", url or "")


def parse_playerctl(line):
    """A line from `playerctl --follow metadata --format` (FORMAT below) into a Now, or None."""
    parts = line.rstrip("\n").split(SEP)
    if len(parts) != 7:
        return None
    status, title, artist, album, art, length, position = parts
    try:
        length_s = int(length or 0) / 1e6
        pos_s = int(position or 0) / 1e6
    except ValueError:
        length_s = pos_s = 0.0
    return Now("spotify", title, artist, album, spotify_art(art), length_s, pos_s, status == "Playing", True)


FORMAT = SEP.join(["{{status}}", "{{title}}", "{{artist}}", "{{album}}", "{{mpris:artUrl}}", "{{mpris:length}}",
                   "{{position}}"])


class Source(QObject):
    changed = Signal(object)  # Now

    def play_pause(self):
        pass

    def next(self):
        pass

    def previous(self):
        pass

    def seek(self, seconds):
        pass

    def position_now(self):
        """Where the song is now, in seconds (for lyrics: finer than the half-second clock)."""
        return float(self.now.position)

    def resync(self):
        pass


class Spotify(Source):
    """The Spotify app, through playerctl: --follow reports each change (no polling); the position between changes
    is counted here. `players` is playerctl's list: "spotify,%any" follows Spotify first, else whatever plays
    (a browser, VLC...)."""

    def __init__(self, demo=None, players="spotify"):
        super().__init__()
        self.now = Now("spotify")
        self.demo = demo
        self.players = players
        self.proc = None
        self.asked = None  # a `playerctl position` on its way
        # where the song was when last heard (base, at monotonic time stamp): the position counts on from there
        self.base, self.stamp = self.now.position, time.monotonic()
        self.clock = QTimer(self, interval=500, timeout=self.advance)
        if demo:
            self.now = demo
            self.base = demo.position
            QTimer.singleShot(0, lambda: self.changed.emit(self.now))
        else:
            self.follow()
        self.clock.start()

    def follow(self):
        self.proc = QProcess(self)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(lambda *_: QTimer.singleShot(3000, self.follow))  # Spotify closed: look again
        self.proc.start("playerctl", [f"--player={self.players}", "--follow", "metadata", "--format", FORMAT])

    def read(self):
        for line in bytes(self.proc.readAllStandardOutput()).decode(errors="replace").splitlines():
            now = parse_playerctl(line)
            if now:
                self.now = now
                self.base, self.stamp = now.position, time.monotonic()
                self.changed.emit(now)
            elif not line.strip():  # an empty line: Spotify went away
                self.now = Now("spotify")
                self.changed.emit(self.now)

    def advance(self):
        self.now.position = self.position_now()

    def position_now(self):
        if not self.now.playing:
            return float(self.base)
        return min(self.now.length or 1e9, self.base + time.monotonic() - self.stamp)

    def resync(self):
        """Asks the player where it really is (seeking in Spotify, or a slow clock, moves it): playerctl answers in
        a moment, without holding anything up."""
        if self.demo or (self.asked and self.asked.state() != QProcess.NotRunning):
            return
        self.asked = QProcess(self)
        sent = time.monotonic()

        def heard(*_):
            try:
                pos = float(bytes(self.asked.readAllStandardOutput()).decode().strip())
            except ValueError:
                return
            self.base, self.stamp = pos, (sent + time.monotonic()) / 2  # halfway through the ask
        self.asked.finished.connect(heard)
        self.asked.start("playerctl", [f"--player={self.players}", "position"])

    def _ctl(self, *args):
        if not self.demo:
            QProcess.startDetached("playerctl", [f"--player={self.players}", *args])

    def play_pause(self):
        if self.demo:
            self.now.playing = not self.now.playing
            self.changed.emit(self.now)
        self._ctl("play-pause")

    def next(self):
        self._ctl("next")

    def previous(self):
        self._ctl("previous")

    def seek(self, seconds):
        self.now.position = self.base = seconds
        self.stamp = time.monotonic()
        self._ctl("position", f"{seconds:.1f}")


class Local(Source):
    """Your own files: a queue, played with Qt Multimedia (FFmpeg underneath, so every common format plays)."""

    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer(self)
        self.out = QAudioOutput(self)
        self.player.setAudioOutput(self.out)
        self.queue, self.index, self.shuffle, self.repeat = [], -1, False, False
        self.now = Now("local")
        self.player.positionChanged.connect(self.moved)
        self.player.playbackStateChanged.connect(lambda *_: self.emit())
        self.player.mediaStatusChanged.connect(self.status)

    def play_tracks(self, tracks, start=0):
        self.queue = list(tracks)
        if self.shuffle:
            first = self.queue.pop(start)
            random.shuffle(self.queue)
            self.queue.insert(0, first)
            start = 0
        self.go(start)

    def go(self, i):
        if not 0 <= i < len(self.queue):
            self.player.stop()
            return
        self.index = i
        t = self.queue[i]
        self.player.setSource(QUrl.fromLocalFile(t["path"]))
        self.player.play()
        self.emit()

    def status(self, st):
        if st == QMediaPlayer.EndOfMedia:
            if self.index + 1 < len(self.queue):
                self.go(self.index + 1)
            elif self.repeat and self.queue:
                self.go(0)

    def position_now(self):
        return self.player.position() / 1000

    def moved(self, ms):
        self.now.position = ms / 1000
        # (no signal for every position: the window reads it each frame)

    def emit(self):
        t = self.queue[self.index] if 0 <= self.index < len(self.queue) else {}
        self.now = Now("local", t.get("title", ""), t.get("artist", ""), t.get("album", ""), t.get("cover", ""),
                       (t.get("duration") or self.player.duration() / 1000 or 0), self.player.position() / 1000,
                       self.player.playbackState() == QMediaPlayer.PlayingState, bool(self.queue), {"track": t})
        self.changed.emit(self.now)

    def play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self.queue:
            self.player.play()

    def next(self):
        self.go(self.index + 1 if self.index + 1 < len(self.queue) else 0)

    def previous(self):
        if self.player.position() > 3000:  # like every player: back to the start first, then the song before
            self.player.setPosition(0)
        else:
            self.go(max(0, self.index - 1))

    def seek(self, seconds):
        self.player.setPosition(int(seconds * 1000))

    def set_volume(self, v):
        self.out.setVolume(max(0.0, min(1.0, v)))
