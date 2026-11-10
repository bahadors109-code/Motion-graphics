"""Procedural background music + sound effects for «چیزی که جلوی چشم بود».

Everything is synthesised here with numpy (no samples, no copyrighted
material): a sneaky pizzicato "mystery" groove in D minor at 96 BPM that
drops out for the guard's line, builds into the reveal and lands on a
comic major-key sting.

Usage: python3 music.py <out_dir>
Writes music.wav and sfx.wav (44.1 kHz stereo, length = DURATION).
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 43.0
BPM = 96
BEAT = 60.0 / BPM
N = int(SR * DURATION)
rng = np.random.default_rng(7)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_ad(n, attack, decay):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / decay)


def pluck(freq, dur, bright=1.0, decay=0.35):
    """Pizzicato-ish pluck: harmonic stack, upper partials die faster."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, 9):
        f = freq * h
        if f > SR / 2.2:
            break
        amp = (1.0 / h ** 1.3) * (bright if h > 2 else 1.0)
        out += amp * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t * (1 / decay) * (1 + 0.6 * h))
    out *= np.clip(t / 0.004, 0, 1)
    return out


def bell(freq, dur, decay=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ratios = [(1, 1.0), (2.0, 0.5), (2.76, 0.35), (5.4, 0.18), (8.93, 0.08)]
    out = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / (decay / r ** 0.5)) for r, a in ratios)
    return out * np.clip(t / 0.002, 0, 1)


def fft_filter(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** 4)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(X * g, len(x))


def noise_hit(dur, lo, hi, decay):
    n = int(dur * SR)
    x = fft_filter(rng.standard_normal(n), lo, hi)
    return x / (np.abs(x).max() + 1e-9) * env_ad(n, 0.001, decay)


def pad_chord(notes, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        for det in (-0.12, 0.0, 0.11):
            f = midi(m + det)
            # soft saw from a few harmonics
            for h in range(1, 7):
                out += np.sin(2 * np.pi * f * h * t + rng.uniform(0, 6.28)) / h
    out = fft_filter(out, 80, 1400)
    fade = np.minimum(np.clip(t / 1.2, 0, 1), np.clip((dur - t) / 1.2, 0, 1))
    return out / (np.abs(out).max() + 1e-9) * fade


class Track:
    def __init__(self):
        self.L = np.zeros(N)
        self.R = np.zeros(N)

    def add(self, sig, at, gain=1.0, pan=0.0):
        i = int(at * SR)
        if i >= N:
            return
        sig = sig[: N - i]
        lg = gain * np.sqrt(0.5 * (1 - pan))
        rg = gain * np.sqrt(0.5 * (1 + pan))
        self.L[i:i + len(sig)] += sig * lg
        self.R[i:i + len(sig)] += sig * rg


def section_gain(t):
    """Arrangement map: which layers play when (output-video time)."""
    return t


music = Track()

# ---------------------------------------------------------------- harmony
# D minor sneaky progression, one chord per bar (4 beats)
BAR = 4 * BEAT
prog = [
    (50, [62, 65, 69]),  # Dm
    (50, [62, 65, 69]),  # Dm
    (46, [58, 62, 65]),  # Bb
    (45, [57, 61, 64]),  # A
]
# walking pizz bass figures (semitones from chord root), 8th notes
bass_fig = [0, None, 7, None, 12, 11, 7, None]

GUARD_START, GUARD_END = 22.5, 25.3   # music drops for guard's line
REVEAL = 36.75                        # «خودِ دوچرخه‌ها بودن!»
END_CHORD = 40.9

t = 0.25
bar_i = 0
while t < REVEAL - 0.05:
    root, chord = prog[bar_i % 4]
    in_gap = GUARD_START <= t < GUARD_END
    # bass
    for k, step in enumerate(bass_fig):
        bt = t + k * BEAT / 2
        if bt >= REVEAL - 0.05 or step is None:
            continue
        if GUARD_START <= bt < GUARD_END:
            continue
        music.add(pluck(midi(root - 12 + step), 0.6, 0.7, 0.22), bt, 0.55, -0.15)
    # pad (quiet, always – carries the mystery under the guard line)
    music.add(pad_chord(chord, BAR + 0.6), t, 0.10 if not in_gap else 0.16, 0.0)
    # high staccato "tip-toe" melody after the intro
    if t > 5.2 and not in_gap:
        mel = [chord[2] + 12, None, chord[1] + 12, None, chord[0] + 12, chord[1] + 12, None, chord[2] + 12]
        if bar_i % 2:
            mel = [None, chord[0] + 12, None, chord[2] + 12, None, chord[1] + 13, chord[1] + 12, None]
        for k, m in enumerate(mel):
            mt = t + k * BEAT / 2
            if m is None or mt >= REVEAL - 0.1 or GUARD_START <= mt < GUARD_END:
                continue
            music.add(pluck(midi(m), 0.35, 1.1, 0.09), mt, 0.16, 0.35)
    # brushes / shaker on off-beats
    if t > 5.2:
        for k in range(8):
            ht = t + k * BEAT / 2
            if ht >= REVEAL - 0.1 or GUARD_START <= ht < GUARD_END:
                continue
            acc = 0.09 if k % 2 else 0.04
            music.add(noise_hit(0.12, 5000, 12000, 0.03), ht, acc, 0.25)
        # soft kick on 1 & 3
        for k in (0, 4):
            kt = t + k * BEAT / 2
            if kt >= REVEAL - 0.1 or GUARD_START <= kt < GUARD_END:
                continue
            n = int(0.3 * SR)
            tt = np.arange(n) / SR
            kick = np.sin(2 * np.pi * (45 + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 12)
            music.add(kick, kt, 0.35)
    t += BAR
    bar_i += 1

# tick-tock clock during the guard's line (tension)
tt_ = GUARD_START + 0.1
k = 0
while tt_ < GUARD_END - 0.1:
    music.add(noise_hit(0.05, 2500 if k % 2 else 3500, 8000, 0.01), tt_, 0.22, -0.3 if k % 2 else 0.3)
    tt_ += BEAT / 2
    k += 1

# riser into the reveal
rn = int((REVEAL - 31.0) * SR)
rt = np.arange(rn) / SR
riser = fft_filter(rng.standard_normal(rn), 400, 6000) * (rt / rt[-1]) ** 2.5
music.add(riser / np.abs(riser).max(), 31.0, 0.10)

# reveal sting: bright D major arpeggio on bells + low hit
for i, m in enumerate([74, 78, 81, 86]):
    music.add(bell(midi(m), 2.5, 0.8), REVEAL + i * 0.07, 0.22, -0.3 + 0.2 * i)
music.add(pluck(midi(38), 1.5, 0.6, 0.5), REVEAL, 0.6)
music.add(pad_chord([62, 66, 69, 74], 4.2), REVEAL, 0.13)

# playful outro: tip-toe pizz in D major, then a final "ta-da" chord
outro = [(0, 74), (0.5, 78), (1.0, 81), (1.5, 78), (2.0, 76), (2.5, 73)]
for dt, m in outro:
    music.add(pluck(midi(m), 0.4, 1.0, 0.1), REVEAL + 1.2 + dt * BEAT, 0.18, 0.3)
for m in (38, 50, 62, 66, 69, 74):
    music.add(pluck(midi(m), 2.0, 0.9, 0.6), END_CHORD, 0.22 if m > 45 else 0.45)

# master fade in/out + normalise
tt = np.arange(N) / SR
fade = np.clip(tt / 0.6, 0, 1) * np.clip((DURATION - tt) / 1.2, 0, 1)
mix = np.stack([music.L, music.R]) * fade
mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.4) * 0.5

# ---------------------------------------------------------------- SFX
sfx = Track()


def whoosh(dur=0.45):
    n = int(dur * SR)
    x = rng.standard_normal(n)
    t_ = np.arange(n) / SR
    # sweep by blending a lowpassed and a highpassed copy
    lo = fft_filter(x, 200, 1500)
    hi = fft_filter(x, 1500, 7000)
    w = t_ / dur
    y = lo * (1 - w) + hi * w
    e = np.sin(np.pi * np.clip(t_ / dur, 0, 1)) ** 2
    return y / np.abs(y).max() * e


def pop():
    n = int(0.12 * SR)
    t_ = np.arange(n) / SR
    return np.sin(2 * np.pi * (500 + 900 * np.exp(-t_ * 40)) * t_) * np.exp(-t_ * 35)


def sand(dur=0.9):
    return noise_hit(dur, 1500, 9000, dur / 2.5) * (0.6 + 0.4 * rng.random(int(dur * SR)))


def paper():
    out = np.zeros(int(0.35 * SR))
    for i in range(5):
        h = noise_hit(0.05, 1200, 7000, 0.012)
        j = int((0.02 + i * 0.055) * SR)
        out[j:j + len(h)] += h * (1 - i * 0.15)
    return out


# (time, signal, gain, pan) – times match the animation timeline
events = [
    (0.2, whoosh(0.8), 0.35, 0),
    (5.75, whoosh(), 0.3, 0.3),
    (8.3, sand(1.1), 0.35, 0.2),
    (11.0, pop(), 0.5, 0.0),          # «شن؟!»
    (13.0, paper(), 0.6, -0.2),       # calendar flip
    (13.1, pop(), 0.35, 0),
    (14.6, sand(0.8), 0.3, 0.2),
    (17.6, paper(), 0.6, -0.2),
    (17.7, pop(), 0.35, 0),
    (18.6, sand(2.5), 0.32, 0.2),     # sieve
    (20.3, pop(), 0.35, 0),           # «الک ویژه»
    (22.4, noise_hit(0.25, 60, 600, 0.08), 0.8, 0),  # sack thrown down
    (22.75, pop(), 0.45, 0),          # speech bubble
    (25.6, whoosh(0.35), 0.25, 0),    # shrug
    (27.6, pop(), 0.35, 0),           # «مرز»
    (28.0, whoosh(), 0.35, -0.3),
    (29.7, bell(midi(88), 0.8, 0.25), 0.25, 0.3),   # cash
    (29.85, bell(midi(93), 0.9, 0.3), 0.25, 0.3),
    (31.4, whoosh(0.9), 0.35, 0),     # into flashback
    (33.9, whoosh(0.6), 0.25, 0),     # sacks fade away
    (39.2, whoosh(0.5), 0.3, 0),
    (39.6, pop(), 0.5, 0),            # final text
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
sfx_mix = np.stack([sfx.L, sfx.R])
sfx_mix = sfx_mix / (np.abs(sfx_mix).max() + 1e-9) * 0.6


def write(path, stereo):
    data = (np.clip(stereo, -1, 1).T * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


out = sys.argv[1] if len(sys.argv) > 1 else "."
write(f"{out}/music.wav", mix)
write(f"{out}/sfx.wav", sfx_mix)
print("wrote", out)
