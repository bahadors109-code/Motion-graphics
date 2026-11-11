"""Soft noir-jazz score + SFX for "The Witness Who Saw Too Much" (all synthesised).

Brushed swing drums, walking upright bass, muted piano comping and a
little vibraphone, D minor at ~88 BPM. Stop-time when the pen stops
(21.85s), a held chord over the window POV, a soft sting on the reveal.

Usage: python3 music.py <out_dir>   -> music.wav, sfx.wav (44.1 kHz stereo)
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 50.0
N = int(SR * DURATION)
rng = np.random.default_rng(11)
STOP, RESUME = 21.85, 27.0       # pen stops -> sparse until the questions start
POV0, POV1 = 31.5, 35.0
REVEAL = 39.3
END_CHORD = 47.6


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


def upright(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + .45 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t * 6) + .15 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-t * 10)
    return x * np.clip(t / .008, 0, 1) * np.exp(-t * 3.2)


def epiano(freq, dur, vel=1.):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * freq * t) + .3 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t * 4)
         + .08 * np.sin(2 * np.pi * 7 * freq * t) * np.exp(-t * 25))
    return x * np.clip(t / .006, 0, 1) * np.exp(-t * 2.4) * vel


def vibes(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    trem = 1 + .3 * np.sin(2 * np.pi * 5.5 * t)
    x = np.sin(2 * np.pi * freq * t) + .25 * np.sin(2 * np.pi * 4 * freq * t) * np.exp(-t * 8)
    return x * trem * np.exp(-t * 1.6) * np.clip(t / .003, 0, 1)


def ride():
    return noise_hit(.5, 5500, 14000, .16) * .6 + noise_hit(.5, 3000, 6000, .05) * .2


def brush_swish(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), 2500, 9000)
    return x / np.abs(x).max() * np.sin(np.pi * t / dur) ** 2


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
BEAT = 60 / 88
SW = BEAT * 2 / 3                       # swung 8th
# Dm9 | Gm9 | Em7b5 | A7b9   (roots + upper voicing)
prog = [(38, [53, 57, 60, 64]), (43, [53, 58, 62, 65]), (40, [55, 58, 62, 65]), (45, [55, 58, 61, 64])]
walks = [[0, 3, 5, 7], [0, 2, 3, 5], [0, 3, 6, 4], [0, 4, 7, 6]]
motif = [(0, 77), (1.5, 76), (2, 74), (3, 72)]

t = .3
bar = 0
while t < END_CHORD - .05:
    root, chord = prog[bar % 4]
    for beat in range(4):
        bt = t + beat * BEAT
        if bt >= END_CHORD - .05:
            break
        sparse = STOP <= bt < RESUME
        pov = POV0 <= bt < POV1
        intro = bt < 7.0
        if pov:
            continue
        # walking bass (half-time while sparse)
        if not sparse or beat % 2 == 0:
            music.add(upright(midi(root + walks[bar % 4][beat] - 12 + 12), BEAT * .95), bt, .45 if not intro else .35)
        # ride pattern: ding  ding-da ding  ding-da
        if not sparse:
            music.add(ride(), bt, .07 if not intro else .04, .3)
            if beat % 2 == 1:
                music.add(ride(), bt + SW, .045, .3)
            if beat % 2 == 1 and not intro:
                music.add(brush_swish(.18), bt - .02, .05, -.2)   # brush on 2 & 4
        # piano comping: charleston rhythm (1 and the "and" of 2)
        if beat == 0 or (beat == 1 and not sparse):
            at = bt if beat == 0 else bt + SW
            for m in chord:
                music.add(epiano(midi(m), 1.2, .8), at + rng.uniform(0, .012), .055, -.15)
    # vibraphone motif every other bar in the storytelling sections
    if bar % 2 == 1 and 7.0 <= t < STOP - 1:
        for off, m in motif:
            music.add(vibes(midi(m - (0 if bar % 4 == 1 else 2)), 1.6), t + off * BEAT, .06, .35)
    t += 4 * BEAT
    bar += 1

# stop-time hit when the pen stops
for m in (50, 57, 60, 65):
    music.add(epiano(midi(m), 2.2, 1.0), STOP, .09)
music.add(upright(midi(38), 1.2), STOP, .6)
# held, eerie chord over the window POV
for m in (50, 56, 60, 65, 69):
    music.add(vibes(midi(m), 3.6), POV0 + .05, .05)
# reveal sting + soft outro chord
for i, m in enumerate([62, 65, 68, 73]):
    music.add(vibes(midi(m), 3.0), REVEAL + i * .06, .07, -.3 + .2 * i)
music.add(upright(midi(37), 2.0), REVEAL, .5)
for m in (38, 53, 57, 60, 64, 69):
    music.add(epiano(midi(m), 3.0, .9), END_CHORD + (m - 38) * .004, .12)
music.add(vibes(midi(74), 3.0), END_CHORD + .3, .06)

tt = np.arange(N) / SR
fade = np.clip(tt / .8, 0, 1) * np.clip((DURATION - tt) / 1.6, 0, 1)
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


def scribble(dur):
    n = int(dur * SR)
    out = np.zeros(n)
    k = 0
    while k < n:
        h = noise_hit(.06 + rng.random() * .05, 2500, 8000, .03, .01)
        out[k:k + len(h)] += h[: n - k] * (.5 + .5 * rng.random())
        k += int((.07 + rng.random() * .06) * SR)
    return out


def siren(dur):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    f = 700 + 250 * np.sin(2 * np.pi * .7 * t_)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return fft_filter(x, 300, 1500) * np.clip(t_ / 1, 0, 1) * np.clip((dur - t_) / 1.5, 0, 1)


def gulp():
    n = int(.35 * SR)
    t_ = np.arange(n) / SR
    return np.sin(2 * np.pi * (240 - 300 * t_) * t_) * np.exp(-t_ * 10)


def steps(t0, t1, rate=3.2, gain=.18):
    t_ = t0
    while t_ < t1:
        sfx.add(noise_hit(.07, 200, 2500, .015), t_, gain, .3)
        t_ += 1 / rate


events = [
    (0.0, siren(6.5), .12, -.6),
    (.2, whoosh(.8), .2, 0),
    (7.25, whoosh(.6), .3, 0),                       # into the flashback
    (8.0, pop(), .3, 0), (12.4, pop(), .3, 0),
    (12.4, whoosh(.5), .15, .4),                     # thief runs
    (17.7, whoosh(.4), .2, 0),
    (18.2, whoosh(.5), .25, 0), (18.3, pop(), .3, 0),
    (21.85, noise_hit(.35, 300, 4000, .12), .25, 0),  # pen stops
    (22.6, whoosh(.7), .2, -.3), (24.4, whoosh(.7), .2, .3),
    (27.2, pop(), .3, 0), (29.6, pop(), .3, 0),
    (31.5, whoosh(.6), .25, 0),
    (35.3, pop(), .3, 0),
    (38.6, gulp(), .5, .2),
    (45.6, whoosh(.5), .22, 0), (45.9, pop(), .4, 0), (46.6, pop(), .35, 0),
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
for t0, t1 in ((8.1, 12.3), (12.6, 15.7), (18.4, 21.8)):
    sfx.add(scribble(t1 - t0), t0, .12, -.25)
steps(.6, 4.6)
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
