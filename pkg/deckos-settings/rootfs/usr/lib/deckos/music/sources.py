"""Where DecKoOS Music's sound comes from, behind one shape (`Source`): the Spotify app, followed and controlled
through MPRIS with playerctl (no sign-in; Spotify keeps playing in its own app, free or Premium), and local files,
played here with Qt Multimedia. The window shows whichever is playing; both report `changed` with a `Now` state.
"""
import random
import re
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
        self.clock = QTimer(self, interval=500, timeout=self.advance)
        if demo:
            self.now = demo
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
                self.changed.emit(now)
            elif not line.strip():  # an empty line: Spotify went away
                self.now = Now("spotify")
                self.changed.emit(self.now)

    def advance(self):
        if self.now.playing:
            self.now.position = min(self.now.length or 1e9, self.now.position + 0.5)

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
        self.now.position = seconds
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
