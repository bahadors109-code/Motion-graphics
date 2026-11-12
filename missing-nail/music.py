"""Mysterious waltz + SFX for "The Missing Nail" (all synthesised, no samples).

A minor, 3/4 at ~84 BPM: pizzicato bass on the downbeat, celesta chords on
2 and 3, a soft string bed. Under the flashlight it turns into a slow
heartbeat pulse; the flashback is a music-box version of the tune; a soft
sting lands on the punchline.

Usage: python3 music.py <out_dir>   -> music.wav, sfx.wav (44.1 kHz stereo)
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 47.5
N = int(SR * DURATION)
rng = np.random.default_rng(13)
TORCH0, TORCH1 = 23.0, 32.0
FLASH0, FLASH1 = 32.0, 43.0
END_CHORD = 45.2


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def fft_filter(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** 4)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(X * g, len(x))


def noise_hit(dur, lo, hi, decay, attack=.001):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), lo, hi)
    return x / (np.abs(x).max() + 1e-9) * np.clip(t / attack, 0, 1) * np.exp(-t / decay)


def pizz(freq, dur=.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * freq * h * t) / h ** 1.3 * np.exp(-t * (4 + 2 * h)) for h in range(1, 7)) * np.clip(t / .003, 0, 1)


def celesta(freq, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + .35 * np.sin(2 * np.pi * 4 * freq * t) * np.exp(-t * 8)) * np.exp(-t * 2.2) * np.clip(t / .002, 0, 1)


def musicbox(freq, dur=1.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + .5 * np.sin(2 * np.pi * 3.01 * freq * t) * np.exp(-t * 5) + .2 * np.sin(2 * np.pi * 5.4 * freq * t) * np.exp(-t * 12)) * np.exp(-t * 2.8)


def strings(notes, dur, bright=1500):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        for det in (-.1, .1):
            out += sum(np.sin(2 * np.pi * midi(m + det) * h * t + rng.uniform(0, 6)) / h for h in range(1, 6))
    out = fft_filter(out, 90, bright)
    fade = np.minimum(np.clip(t / .7, 0, 1), np.clip((dur - t) / .7, 0, 1))
    return out / (np.abs(out).max() + 1e-9) * fade


def heartbeat():
    n = int(.6 * SR)
    t = np.arange(n) / SR
    b = lambda d: np.sin(2 * np.pi * 50 * (t - d)) * np.exp(-np.maximum(t - d, 0) * 18) * (t >= d)
    return b(0) + .7 * b(.22)


class Track:
    def __init__(self):
        self.L = np.zeros(N)
        self.R = np.zeros(N)

    def add(self, sig, at, gain=1.0, pan=0.0):
        i = int(at * SR)
        if i >= N or i < 0:
            return
        sig = sig[: N - i]
        self.L[i:i + len(sig)] += sig * gain * np.sqrt(.5 * (1 - pan))
        self.R[i:i + len(sig)] += sig * gain * np.sqrt(.5 * (1 + pan))


music = Track()
BEAT = 60 / 84
BAR = 3 * BEAT
prog = [(45, [69, 72, 76]), (41, [69, 72, 77]), (38, [69, 74, 77]), (40, [68, 71, 76])]   # Am F Dm E
tune = [76, 77, 76, 74, 72, 74, 72, 71, 69, 71, 72, 74]                                  # 3 notes per bar, 4 bars

t = .3
bar = 0
while t < END_CHORD - .05:
    root, chord = prog[bar % 4]
    torch = TORCH0 <= t < TORCH1
    flash = FLASH0 <= t < FLASH1
    if torch:
        music.add(heartbeat(), t, .45)
        music.add(strings([root, root + 7], BAR + .6, 900), t, .08)
    elif flash:
        for k in range(3):
            music.add(musicbox(midi(tune[(bar % 4) * 3 + k] + 12)), t + k * BEAT, .1, .2)
        music.add(strings([m - 12 for m in chord], BAR + .6, 1300), t, .06)
    else:
        music.add(pizz(midi(root - 12)), t, .4)
        for k in (1, 2):
            for m in chord:
                music.add(celesta(midi(m)), t + k * BEAT, .045, .25)
        music.add(strings([m - 12 for m in chord], BAR + .6), t, .07)
        if t > 6 and bar % 2 == 1:
            for k in range(3):
                music.add(celesta(midi(tune[(bar % 4) * 3 + k] + 12), 1.2), t + k * BEAT, .05, -.3)
    t += BAR
    bar += 1

# soft sting on the punchline (flashback end) and the final chord
for i, m in enumerate([69, 72, 76, 81]):
    music.add(celesta(midi(m + 12), 2.5), 42.6 + i * .07, .08)
for m in (45, 57, 64, 69, 72, 76):
    music.add(pizz(midi(m), 2.0) if m < 60 else celesta(midi(m), 3.0), END_CHORD, .3 if m < 60 else .08)
music.add(strings([57, 64, 69], 2.3), END_CHORD, .08)

tt = np.arange(N) / SR
fade = np.clip(tt / .6, 0, 1) * np.clip((DURATION - tt) / 1.4, 0, 1)
mix = np.stack([music.L, music.R]) * fade
mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.3) * .58

# ---------------------------------------------------------------- SFX
sfx = Track()


def whoosh(dur=.45):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    x = rng.standard_normal(n)
    lo, hi = fft_filter(x, 200, 1500), fft_filter(x, 1500, 7000)
    w = t_ / dur
    y = lo * (1 - w) + hi * w
    return y / np.abs(y).max() * np.sin(np.pi * np.clip(w, 0, 1)) ** 2


def pop():
    n = int(.12 * SR)
    t_ = np.arange(n) / SR
    return np.sin(2 * np.pi * (500 + 900 * np.exp(-t_ * 40)) * t_) * np.exp(-t_ * 35)


def click():
    return noise_hit(.06, 1500, 7000, .01) + noise_hit(.06, 300, 1200, .008) * .5


def tape_pull(dur):
    n = int(dur * SR)
    x = fft_filter(rng.standard_normal(n), 1500, 8000)
    x /= np.abs(x).max()
    return x * (.5 + .5 * (rng.random(n) > .6)) * np.clip(np.arange(n) / SR / .05, 0, 1) * np.clip((dur - np.arange(n) / SR) / .1, 0, 1)


def roll(dur):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), 200, 1800)
    return x / np.abs(x).max() * (.6 + .4 * np.abs(np.sin(2 * np.pi * 1.4 * t_)))


def wind(dur):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), 150, 900)
    return x / np.abs(x).max() * (.6 + .4 * np.sin(2 * np.pi * .4 * t_)) * np.clip(t_ / .8, 0, 1) * np.clip((dur - t_) / .8, 0, 1)


def steps(t0, t1, rate=1.8, gain=.18):
    t_ = t0
    while t_ < t1:
        sfx.add(noise_hit(.08, 150, 2000, .02), t_, gain, .3)
        t_ += 1 / rate


events = [
    (.2, whoosh(.8), .2, 0), (6.0, whoosh(.4), .2, 0), (7.8, wind(5.5), .15, .5),
    (8.0, pop(), .3, 0), (10.4, pop(), .3, 0),
    (14.0, whoosh(.4), .2, 0), (14.5, pop(), .35, 0), (16.2, whoosh(.5), .2, 0),
    (17.7, pop(), .3, 0), (20.0, pop(), .3, 0),
    (23.0, click(), .5, .3),                         # flashlight on
    (25.0, pop(), .35, 0), (25.8, pop(), .35, 0), (26.7, pop(), .35, 0),
    (32.0, whoosh(.7), .25, 0), (32.4, tape_pull(2.2), .22, -.2), (34.8, roll(2.5), .25, .2), (37.4, tape_pull(1.0), .3, .2),
    (38.8, whoosh(.4), .2, 0), (38.9, noise_hit(.4, 200, 1500, .1), .3, .3), (41.4, noise_hit(.4, 200, 1500, .1), .35, .3),
    (43.0, whoosh(.5), .22, 0), (43.3, pop(), .4, 0), (45.15, pop(), .35, 0),
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
steps(6.2, 9.4)
sfx_mix = np.stack([sfx.L, sfx.R])
sfx_mix = sfx_mix / (np.abs(sfx_mix).max() + 1e-9) * .6


def write(path, stereo):
    data = (np.clip(stereo, -1, 1).T * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


out = sys.argv[1] if len(sys.argv) > 1 else '.'
write(f'{out}/music.wav', mix)
write(f'{out}/sfx.wav', sfx_mix)
print('wrote', out)
