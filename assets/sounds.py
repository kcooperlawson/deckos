"""DecKoOS Sounds: the system sound theme, synthesised here (no recordings, nothing borrowed), into
pkg/deckos-settings/rootfs/usr/share/sounds/deckos/ (freedesktop sound theme: index.theme + stereo/NAME.oga).

Two voices, like the brand: glass (clean near-harmonic tones with a soft shimmer) for everyday sounds, and a
metal plate (inharmonic partials of a struck plate, with a short "bolt" tick) as the accent for bigger events:
login, devices, errors. Quiet by design: peaks at -9 dBFS, most sounds under half a second.

    python3 assets/sounds.py [--play NAME] [--only NAME,...]

Needs numpy and ffmpeg (Vorbis). Re-run after changing it and commit the .oga files with it.
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

RATE = 48000
OUT = Path(__file__).resolve().parents[1] / "pkg/deckos-settings/rootfs/usr/share/sounds/deckos"
RNG = np.random.default_rng(7)  # the same "random" noise every run, so outputs only change when this file does


def note(name):
    """'C6' -> Hz (A4 = 440)."""
    steps = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    n, octave = name[:-1], int(name[-1])
    semis = steps[n[0]] + (1 if "#" in n else -1 if "b" in n[1:] else 0) + (octave - 4) * 12
    return 440.0 * 2 ** (semis / 12)


def silence(sec):
    return np.zeros((int(RATE * sec), 2))


def env(n, attack, decay):
    t = np.arange(n) / RATE
    a = np.clip(t / max(attack, 1e-4), 0, 1) ** 1.5
    return a * np.exp(-t / decay)


def glass(freq, dur=0.45, decay=0.16, level=1.0):
    """A clean bell-like tone: partials near 1, 2, 3 and a soft high shimmer, the two channels a hair apart."""
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for ratio, amp, dec in ((1.0, 1.0, 1.0), (2.005, 0.32, 0.55), (3.01, 0.12, 0.35), (4.2, 0.05, 0.22)):
        for ch, detune in ((0, 1.0), (1, 1.0015)):
            out[:, ch] += amp * np.sin(2 * np.pi * freq * ratio * detune * t) * env(n, 0.004, decay * dec)
    return out * level


def plate(freq, dur=0.6, decay=0.22, level=1.0, tick=0.35):
    """A struck metal plate: inharmonic partials (a thin plate's modes) and a short bolt tick of filtered noise."""
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for ratio, amp, dec in ((1.0, 1.0, 1.0), (2.32, 0.55, 0.6), (4.25, 0.3, 0.4), (6.63, 0.16, 0.25),
                            (9.38, 0.08, 0.15)):
        for ch, detune in ((0, 0.999), (1, 1.001)):
            out[:, ch] += amp * np.sin(2 * np.pi * freq * ratio * detune * t + ch * 0.3) * env(n, 0.001, decay * dec)
    if tick:
        k = int(RATE * 0.012)
        noise = RNG.standard_normal(k)
        noise = np.convolve(noise, np.ones(6) / 6, mode="same")  # a little darker than white noise
        click = noise * np.exp(-np.arange(k) / (RATE * 0.0025)) * tick
        out[:k, 0] += click
        out[:k, 1] += click
    return out * level


def seq(*parts, gap=0.0):
    """Sounds one after another, each starting `gap` (or its own given offset) after the last began."""
    total = 0.0
    placed = []
    for p in parts:
        if isinstance(p, tuple):
            offset, sound = p
        else:
            offset, sound = gap, p
        placed.append((total, sound))
        total += offset
    n = max(int(RATE * start) + len(s) for start, s in placed)
    out = np.zeros((n, 2))
    for start, s in placed:
        i = int(RATE * start)
        out[i:i + len(s)] += s
    return out


def chord(*sounds):
    return seq(*[(0.0, s) for s in sounds])


# The sounds, by freedesktop name. Everyday ones are glass; bigger events get the plate.
def sounds():
    up = lambda a, b, g=0.09: seq((g, glass(note(a))), glass(note(b)))  # noqa: E731
    down = lambda a, b, g=0.09: seq((g, glass(note(a))), glass(note(b)))  # noqa: E731
    success = seq((0.07, glass(note("C6"), 0.35)), (0.07, glass(note("E6"), 0.35)), glass(note("G6"), 0.6, 0.22))
    login = seq((0.0, plate(note("C4"), 1.2, 0.35, 0.55)),
                (0.06, silence(0)), (0.0, glass(note("G5"), 1.4, 0.45, 0.5)),
                (0.12, glass(note("C6"), 1.3, 0.42, 0.45)), (0.12, glass(note("E6"), 1.2, 0.4, 0.4)),
                glass(note("G6"), 1.2, 0.38, 0.35))
    logout = seq((0.12, glass(note("G6"), 0.9, 0.3, 0.4)), (0.12, glass(note("E6"), 0.9, 0.3, 0.4)),
                 (0.08, glass(note("C6"), 1.0, 0.32, 0.45)), plate(note("C4"), 1.0, 0.3, 0.45))
    return {
        "bell": glass(note("E6"), 0.4, 0.13),
        "bell-window-system": glass(note("E6"), 0.4, 0.13, 0.8),
        "button-pressed": glass(note("A6"), 0.08, 0.025, 0.5),
        "button-pressed-modifier": glass(note("E6"), 0.08, 0.025, 0.45),
        "audio-volume-change": glass(note("C7"), 0.12, 0.04, 0.6),
        "dialog-information": glass(note("G5"), 0.5, 0.18),
        "dialog-question": up("E5", "A5"),
        "dialog-warning": down("A5", "F5"),
        "dialog-warning-auth": seq((0.08, plate(note("F4"), 0.4, 0.12, 0.5, 0.2)), glass(note("C6"), 0.5, 0.17)),
        "dialog-error": seq((0.0, plate(note("D4"), 0.6, 0.2, 0.6)), (0.05, silence(0)), down("D5", "A4")),
        "dialog-error-serious": seq((0.14, plate(note("D4"), 0.5, 0.17, 0.6)), plate(note("A3"), 0.7, 0.22, 0.65)),
        "dialog-error-critical": seq((0.12, plate(note("D4"), 0.45, 0.15, 0.65)), (0.12, plate(note("D4"), 0.45, 0.15, 0.65)),
                                     plate(note("A3"), 0.8, 0.25, 0.7)),
        "message-new-instant": up("C6", "G6", 0.08),
        "message-sent-instant": glass(note("G6"), 0.25, 0.08, 0.6),
        "message-new-email": seq((0.1, glass(note("G5"))), glass(note("D6"))),
        "message-attention": seq((0.08, glass(note("E6"))), (0.08, glass(note("E6"))), glass(note("B6"))),
        "message-highlight": up("D6", "A6", 0.07),
        "message-contact-in": up("G5", "D6", 0.07),
        "message-contact-out": down("D6", "G5", 0.07),
        "completion-success": success,
        "outcome-success": success,
        "complete-media-burn": success,
        "completion-partial": up("C6", "E6"),
        "completion-rotation": glass(note("E6"), 0.15, 0.05, 0.5),
        "completion-fail": seq((0.1, glass(note("G5"))), (0.1, glass(note("Eb5"))), glass(note("C5"), 0.6, 0.2)),
        "outcome-failure": seq((0.1, glass(note("G5"))), glass(note("C5"), 0.6, 0.2)),
        "complete-media-error": seq((0.0, plate(note("C4"), 0.5, 0.16, 0.5)), (0.04, silence(0)), down("G5", "C5")),
        "device-added": seq((0.05, plate(note("G4"), 0.35, 0.1, 0.55, 0.45)), up("G5", "D6", 0.07)),
        "device-removed": seq((0.16, seq((0.07, glass(note("D6"))), glass(note("G5")))),
                              plate(note("G4"), 0.35, 0.1, 0.5, 0.45)),
        "power-plug": seq((0.05, plate(note("C4"), 0.4, 0.12, 0.5, 0.4)), up("C5", "G5", 0.07)),
        "power-unplug": seq((0.16, seq((0.07, glass(note("G5"))), glass(note("C5")))),
                            plate(note("C4"), 0.4, 0.12, 0.45, 0.4)),
        "media-insert-request": seq((0.12, glass(note("A5"))), glass(note("A5"))),
        "battery-low": seq((0.14, glass(note("E5"), 0.4, 0.14)), glass(note("C5"), 0.5, 0.16)),
        "battery-caution": seq((0.12, glass(note("E5"), 0.35, 0.12)), (0.12, glass(note("C5"), 0.35, 0.12)),
                               plate(note("C4"), 0.5, 0.16, 0.5)),
        "battery-full": success,
        "trash-empty": seq((0.03, plate(note("A4"), 0.3, 0.07, 0.4, 0.6)), (0.04, plate(note("E5"), 0.3, 0.06, 0.3, 0.5)),
                           glass(note("E6"), 0.4, 0.12, 0.5)),
        "screen-capture": seq((0.05, plate(note("C6"), 0.12, 0.03, 0.5, 0.5)), plate(note("G6"), 0.15, 0.04, 0.45, 0.5)),
        "camera-shutter": seq((0.05, plate(note("C6"), 0.12, 0.03, 0.5, 0.5)), plate(note("G6"), 0.15, 0.04, 0.45, 0.5)),
        "alarm-clock-elapsed": seq(*[(0.35, up("E6", "B6", 0.1)) for _ in range(3)]),
        "phone-incoming-call": seq(*[(0.5, seq((0.12, glass(note("G5"))), glass(note("D6")))) for _ in range(3)]),
        "game-over-winner": seq((0.09, glass(note("C6"))), (0.09, glass(note("E6"))), (0.09, glass(note("G6"))),
                                glass(note("C7"), 0.8, 0.3)),
        "game-over-loser": seq((0.14, glass(note("G5"))), (0.14, glass(note("F5"))), glass(note("C5"), 0.8, 0.3)),
        "desktop-login": login,
        "service-login": login,
        "desktop-logout": logout,
        "service-logout": logout,
        "theme-demo": login,
    }


PEAK = 10 ** (-9 / 20)  # -9 dBFS: system sounds sit under whatever's playing


def finish(x):
    fade = min(len(x), int(RATE * 0.03))  # no click at the end
    x[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return x / (np.abs(x).max() or 1) * PEAK


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


INDEX = """[Sound Theme]
Name=DecKoOS
Comment=Glass tones and a bolted-plate accent, made for DecKoOS
Inherits=ocean
Directories=stereo
Example=theme-demo

[stereo]
OutputProfile=stereo
"""


def main(argv):
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    play = argv[argv.index("--play") + 1] if "--play" in argv else None
    (OUT / "stereo").mkdir(parents=True, exist_ok=True)
    (OUT / "index.theme").write_text(INDEX)
    with tempfile.TemporaryDirectory() as tmp:
        for name, x in sounds().items():
            if only and name not in only:
                continue
            wav = Path(tmp) / f"{name}.wav"
            write_wav(wav, finish(x))
            # -bitexact and no metadata: the same input gives the same file, so regenerating doesn't churn git
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "5",
                            "-bitexact", "-map_metadata", "-1", str(OUT / "stereo" / f"{name}.oga")], check=True)
    print(f"wrote {OUT}")
    if play:
        subprocess.run(["pw-play", str(OUT / "stereo" / f"{play}.oga")])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
