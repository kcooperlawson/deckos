"""DecKoOS Sounds: the system sound theme, synthesised here (no recordings, nothing borrowed), into
pkg/deckos-settings/rootfs/usr/share/sounds/deckos/ (freedesktop sound theme: index.theme + stereo/NAME.oga).

Two voices, like the brand: glass (clean near-harmonic tones with a soft shimmer) for everyday sounds, and a
metal plate (inharmonic partials of a struck plate, with a short "bolt" tick) as the accent for bigger events:
login, devices, errors. Quiet by design: peaks at -9 dBFS, most sounds under half a second.

Each Vibe has its own set too, the same melodies on its own instruments (`KITS`), into sounds/deckos-SCENE/
(Inherits=deckos): `deckos vibe apply` switches to it while you're on DecKoOS's sounds.

    python3 assets/sounds.py [--kit NAME] [--play NAME] [--only NAME,...]

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


def keys(freq, dur=0.45, decay=0.16, level=1.0, tick=0.0):
    """Rainy street: a warm electric piano, a little slower to speak, with a slow tremolo and tape wobble."""
    n = int(RATE * dur * 1.3)
    t = np.arange(n) / RATE
    wobble = 1 + 0.0025 * np.sin(2 * np.pi * 5.2 * t)
    trem = 1 - 0.18 * (0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t))
    out = np.zeros((n, 2))
    f = freq / 2
    for ratio, amp, dec in ((1.0, 1.0, 1.0), (2.0, 0.4, 0.5), (3.0, 0.08, 0.3), (14.0, 0.02, 0.04)):
        for ch, pan in ((0, 1.0), (1, 0.85)):
            out[:, ch] += amp * pan * np.sin(2 * np.pi * f * ratio * wobble * t) * env(n, 0.008, decay * 1.4 * dec)
    out *= trem[:, None]
    if tick:  # the accent: a soft low thump under it
        out += 0.6 * tick * np.sin(2 * np.pi * 70 * t)[:, None] * env(n, 0.002, 0.05)[:, None]
    return out * level


def synth(freq, dur=0.45, decay=0.16, level=1.0, tick=0.0):
    """City nights: two detuned saws through a closing filter (high harmonics fade first), wide in stereo."""
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for k in range(1, 10):
        amp = 1 / k * np.exp(-t / (decay * 1.2 / (1 + 0.5 * k)))
        for ch, detune in ((0, 0.996), (1, 1.004)):
            out[:, ch] += amp * np.sin(2 * np.pi * freq * k * detune * t)
    out *= env(n, 0.003, decay * 1.5)[:, None] / 2
    if tick:  # the accent: a sub drop
        out += tick * np.sin(2 * np.pi * (55 + 60 * np.exp(-t / 0.03)) * t)[:, None] * env(n, 0.001, 0.12)[:, None]
    return out * level


def air(freq, dur=0.45, decay=0.16, level=1.0, tick=0.0):
    """Midnight: a breathy sine pad, an octave and a fifth floating above, long and quiet."""
    n = int(RATE * dur * 1.6)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    breath = np.convolve(RNG.standard_normal(n), np.ones(40) / 40, mode="same") * 0.05
    for ratio, amp in ((1.0, 1.0), (2.0, 0.25), (3.0, 0.12)):
        for ch, detune in ((0, 0.998), (1, 1.002)):
            out[:, ch] += amp * np.sin(2 * np.pi * freq * ratio * detune * t + ch)
    out[:, 0] += breath
    out[:, 1] += breath[::-1]
    out *= env(n, 0.03, decay * 2.2)[:, None]
    if tick:  # the accent: a deep singing bowl
        bowl = glass(freq / 4, dur * 1.6, decay * 3)[:n]
        out[:len(bowl)] += tick * bowl
    return out * level


def wood(freq, dur=0.45, decay=0.16, level=1.0, tick=0.0):
    """Cozy: a marimba bar (its tuned overtone at 4x, a quick knock at 10x), dry and round."""
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for ratio, amp, dec in ((1.0, 1.0, 1.0), (3.93, 0.35, 0.3), (9.2, 0.12, 0.08)):
        for ch, pan in ((0, 0.9), (1, 1.0)):
            out[:, ch] += amp * pan * np.sin(2 * np.pi * freq * 0.5 * ratio * t) * env(n, 0.001, decay * 0.8 * dec)
    if tick:  # the accent: a woodblock knock
        k = int(RATE * 0.03)
        out[:k] += tick * 0.7 * (np.sin(2 * np.pi * 900 * t[:k]) * np.exp(-t[:k] / 0.006))[:, None]
    return out * level


def struck(voice, strength, shift, freq, dur=0.6, decay=0.22, level=1.0, tick=0.35):
    """A kit's accent, called like plate(): its own voice, lower if asked, with its accent sound under it."""
    return voice(freq * shift, dur, decay, level, strength if tick else 0.0)


# Each Vibe's instruments: (everyday tone, accent for bigger events, name for index.theme)
KITS = {
    "deckos": (glass, plate, "DecKoOS"),
    "lofi": (keys, lambda *a: struck(keys, 0.6, 0.5, *a), "DecKoOS: Rainy street"),
    "neon": (synth, lambda *a: struck(synth, 0.7, 1.0, *a), "DecKoOS: City nights"),
    "midnight": (air, lambda *a: struck(air, 0.5, 1.0, *a), "DecKoOS: Midnight"),
    "cozy": (wood, lambda *a: struck(wood, 0.6, 1.0, *a), "DecKoOS: Cozy"),
}


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


# The sounds, by freedesktop name. Everyday ones are glass; bigger events get the plate (a kit swaps both).
def sounds(glass=glass, plate=plate):
    up = lambda a, b, g=0.09: seq((g, glass(note(a))), glass(note(b)))  # noqa: E731
    down = lambda a, b, g=0.09: seq((g, glass(note(a))), glass(note(b)))  # noqa: E731
    success = seq((0.05, glass(note("C6"), 0.3)), (0.05, glass(note("E6"), 0.3)), (0.05, glass(note("G6"), 0.3)),
                  glass(note("C7"), 0.6, 0.22))
    # The signature: a plate bolt, then a wide rise over two octaves into a high shimmer
    login = seq((0.0, plate(note("C4"), 1.6, 0.45, 0.8, 0.6)),
                (0.10, glass(note("C5"), 1.6, 0.5, 0.45)), (0.13, glass(note("G5"), 1.5, 0.48, 0.45)),
                (0.13, glass(note("E6"), 1.4, 0.45, 0.45)), (0.16, glass(note("C7"), 1.3, 0.42, 0.35)),
                glass(note("G7"), 1.0, 0.3, 0.12))
    logout = seq((0.14, glass(note("C7"), 0.9, 0.3, 0.3)), (0.14, glass(note("E6"), 0.9, 0.3, 0.4)),
                 (0.12, glass(note("G5"), 1.0, 0.32, 0.45)), plate(note("C4"), 1.2, 0.35, 0.7, 0.5))
    return {
        "bell": glass(note("E6"), 0.4, 0.13),
        "bell-window-system": glass(note("E6"), 0.4, 0.13, 0.8),
        "button-pressed": glass(note("A6"), 0.08, 0.025, 0.5),
        "button-pressed-modifier": glass(note("E6"), 0.08, 0.025, 0.45),
        "audio-volume-change": glass(note("C7"), 0.12, 0.04, 0.6),
        "dialog-information": glass(note("G5"), 0.5, 0.18),
        "dialog-question": seq((0.06, glass(note("D5"), 0.3, 0.1, 0.8)), glass(note("A5"), 0.5, 0.18)),
        "dialog-warning": seq((0.16, glass(note("F5"), 0.35, 0.11)), glass(note("F5"), 0.5, 0.16)),
        "dialog-warning-auth": seq((0.08, plate(note("F4"), 0.4, 0.12, 0.5, 0.2)), glass(note("C6"), 0.5, 0.17)),
        "dialog-error": seq((0.09, plate(note("D3"), 0.5, 0.16, 0.9, 0.6)), (0.12, plate(note("Eb3"), 0.6, 0.2, 0.85, 0.5)),
                             glass(note("A4"), 0.7, 0.25, 0.6)),
        "dialog-error-serious": seq((0.14, plate(note("D4"), 0.5, 0.17, 0.6)), plate(note("A3"), 0.7, 0.22, 0.65)),
        "dialog-error-critical": seq((0.12, plate(note("D4"), 0.45, 0.15, 0.65)), (0.12, plate(note("D4"), 0.45, 0.15, 0.65)),
                                     plate(note("A3"), 0.8, 0.25, 0.7)),
        "message-new-instant": seq((0.06, glass(note("E7"), 0.25, 0.07, 0.8)), glass(note("B7"), 0.35, 0.1, 0.7)),
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
        "device-added": seq((0.07, plate(note("G4"), 0.4, 0.1, 0.9, 0.8)), (0.08, glass(note("G5"), 0.3, 0.09)),
                             glass(note("G6"), 0.5, 0.16)),
        "device-removed": seq((0.08, glass(note("G6"), 0.3, 0.09)), (0.12, glass(note("G5"), 0.35, 0.11)),
                              plate(note("G4"), 0.4, 0.1, 0.9, 0.8)),
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
Name={name}
Comment={comment}
Inherits={inherits}
Directories=stereo
Example=theme-demo

[stereo]
OutputProfile=stereo
"""


def main(argv):
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    play = argv[argv.index("--play") + 1] if "--play" in argv else None
    for kit in [argv[argv.index("--kit") + 1]] if "--kit" in argv else KITS:
        write_kit(kit, only)
    if play:
        kit = argv[argv.index("--kit") + 1] if "--kit" in argv else "deckos"
        subprocess.run(["pw-play", str(kit_dir(kit) / "stereo" / f"{play}.oga")])
    return 0


def kit_dir(kit):
    return OUT if kit == "deckos" else OUT.with_name(f"deckos-{kit}")


def write_kit(kit, only):
    tone, accent, title = KITS[kit]
    out = kit_dir(kit)
    (out / "stereo").mkdir(parents=True, exist_ok=True)
    (out / "index.theme").write_text(INDEX.format(
        name=title, inherits="ocean" if kit == "deckos" else "deckos",
        comment="Glass tones and a bolted-plate accent, made for DecKoOS" if kit == "deckos"
        else "DecKoOS's sounds on this Vibe's instruments"))
    with tempfile.TemporaryDirectory() as tmp:
        for name, x in sounds(tone, accent).items():
            if only and name not in only:
                continue
            wav = Path(tmp) / f"{name}.wav"
            write_wav(wav, finish(x))
            # -bitexact and no metadata: the same input gives the same file, so regenerating doesn't churn git
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "5",
                            "-bitexact", "-map_metadata", "-1", str(out / "stereo" / f"{name}.oga")], check=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
