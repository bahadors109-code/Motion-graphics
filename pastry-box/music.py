"""Playful 'caper' score + SFX for "The Box That Shouldn't Be Opened" (all synthesised).

Tip-toe staccato bass, pizzicato chords, finger snaps and a glockenspiel
hook in C minor at ~104 BPM. Thins out when the owner walks in, builds
through Friday #4, and lands a sparkly sting when the sleeve goes up.

Usage: python3 music.py <out_dir>   -> music.wav, sfx.wav (44.1 kHz stereo)
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 47.5
N = int(SR * DURATION)
rng = np.random.default_rng(21)
OWNER0, OWNER1 = 18.0, 27.0
SLEEVE = 36.9
END_CHORD = 45.4


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


def pluck(freq, dur, decay=.12, bright=1.):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, 8):
        if freq * h > SR / 2.2:
            break
        out += (bright if h > 2 else 1) / h ** 1.2 * np.sin(2 * np.pi * freq * h * t) * np.exp(-t / decay * (1 + .5 * h))
    return out * np.clip(t / .003, 0, 1)


def reed(freq, dur):
    """bassoon-ish staccato: filtered pulse with a quick envelope"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * freq * h * t) / h * (1 if h % 2 else .4) for h in range(1, 9))
    env = np.clip(t / .015, 0, 1) * np.clip((dur - t) / .04, 0, 1)
    return x * env * .6


def glock(freq, dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + .3 * np.sin(2 * np.pi * 2.76 * freq * t) * np.exp(-t * 6)) * np.exp(-t * 2.6) * np.clip(t / .002, 0, 1)


def snap():
    return noise_hit(.08, 1800, 6000, .012) + noise_hit(.08, 600, 1500, .006) * .4


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
BEAT = 60 / 104
E8 = BEAT / 2
prog = [(36, [60, 63, 67]), (41, [60, 65, 68]), (43, [59, 62, 67]), (36, [60, 63, 67])]   # Cm Fm G Cm
bass_pat = [(0, 0), (1, 7), (2, 12), (3, 7), (4, 0), (6, 10), (7, 11)]                 # tip-toe line (8th steps)
hook = [(0, 75), (1, 74), (2, 75), (4, 79), (6, 77), (7, 75)]

t = .2
bar = 0
while t < END_CHORD - .05:
    root, chord = prog[bar % 4]
    sparse = OWNER0 <= t < OWNER1
    intro = t < 8
    build = 27 <= t < 35.6
    for st, semi in bass_pat:
        bt = t + st * E8
        if bt >= END_CHORD - .05 or (sparse and st % 4):
            continue
        music.add(reed(midi(root + semi), E8 * .55), bt, .32)
    for st in (2, 6):                                  # off-beat pizz chords
        bt = t + st * E8
        if bt >= END_CHORD - .05 or sparse:
            continue
        for m in chord:
            music.add(pluck(midi(m), .4), bt, .06, .2)
    for st in (2, 6):                                  # finger snaps on 2 & 4
        bt = t + st * E8
        if bt < END_CHORD - .05 and not intro:
            music.add(snap(), bt, .16 if not sparse else .1, -.25)
    if build:                                          # shaker 16ths build up during Friday #4
        for k in range(16):
            music.add(noise_hit(.05, 5000, 12000, .012), t + k * E8 / 2, .02 + .02 * ((t - 27) / 8.6), .3)
    if (8 <= t < OWNER0 or t >= 35.6) and bar % 2 == 0:
        for st, m in hook:
            bt = t + st * E8
            if bt < END_CHORD - .05:
                music.add(glock(midi(m)), bt, .07, .35)
    t += 4 * BEAT
    bar += 1

# sleeve reveal sting: glittery arpeggio up
for i, m in enumerate([72, 75, 79, 84, 87, 91]):
    music.add(glock(midi(m), 1.6), SLEEVE + i * .05, .08, -.3 + .12 * i)
music.add(reed(midi(36), .5), SLEEVE, .5)
# final 'ta-da'
for m in (48, 60, 63, 67, 72):
    music.add(pluck(midi(m), 2.0, .5), END_CHORD, .14 if m > 50 else .3)
music.add(glock(midi(84), 2.0), END_CHORD + .1, .08)

tt = np.arange(N) / SR
fade = np.clip(tt / .6, 0, 1) * np.clip((DURATION - tt) / 1.4, 0, 1)
mix = np.stack([music.L, music.R]) * fade
mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.4) * .58

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


def card():  # cardboard lid
    a = noise_hit(.18, 300, 3000, .05); a[:4410] += noise_hit(.1, 1500, 5000, .02) * .5; return a


def chomp():
    out = np.zeros(int(.7 * SR))
    for k in range(3):
        h = noise_hit(.12, 400, 3500, .04)
        j = int(k * .22 * SR)
        out[j:j + len(h)] += h * (1 - k * .2)
    return out


def paper():
    out = np.zeros(int(.35 * SR))
    for i in range(5):
        h = noise_hit(.05, 1200, 7000, .012)
        j = int((.02 + i * .055) * SR)
        out[j:j + len(h)] += h * (1 - i * .15)
    return out


def steps(t0, t1, rate=1.9, gain=.18):
    t_ = t0
    while t_ < t1:
        sfx.add(noise_hit(.07, 200, 2500, .015), t_, gain, -.2)
        t_ += 1 / rate


events = [(.2, whoosh(.8), .2, 0), (4.6 + .1 / .55, card(), .4, .2)]
for k, t0 in enumerate((8.0, 11.333, 14.667)):
    events += [(t0, whoosh(.3), .2, 0), (t0 + .1, card(), .4, .2), (t0 + 1.25, chomp(), .45, .3), (t0 + 2.0, pop(), .3, 0)]
events += [
    (18.0, whoosh(.5), .2, 0), (19.0, pop(), .3, 0), (21.8, pop(), .3, 0), (24.2, pop(), .3, 0),
    (27.0, paper(), .5, -.2), (27.6, card(), .4, .2),
    (28.2, pop(), .15, 0), (28.55, pop(), .15, 0), (28.9, pop(), .15, 0), (29.25, pop(), .15, 0),
    (30.4, whoosh(.5), .2, .2), (31.0, card(), .35, .2), (32.6, pop(), .45, 0),
    (35.6, whoosh(.5), .25, 0), (36.0, noise_hit(.8, 2000, 9000, .2, .3), .15, 0),
    (37.8, whoosh(.6), .25, 0), (39.0, pop(), .25, 0), (39.35, pop(), .25, 0), (39.7, pop(), .25, 0),
    (43.8, whoosh(.5), .22, 0), (44.2, pop(), .4, 0), (45.0, pop(), .35, 0), (44.0, chomp(), .4, .3),
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
steps(.5, 3.8); steps(18.0, 18.9, 2.2)
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
