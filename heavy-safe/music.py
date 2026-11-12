"""Comic heist score + SFX for "The Heavy Safe" (all synthesised, no samples).

G minor funk groove (~100 BPM): plucky bass, muted guitar chops, hats and
brass stabs while the thieves sneak in and fight the dial; a heavy
'oom-pah' tuba stomp while they haul the safe; a drum roll as the door
opens, then a sad trombone on the bricks; a bright, light morning tune for
the merchant and his diamonds.

Usage: python3 music.py <out_dir>   -> music.wav, sfx.wav (44.1 kHz stereo)
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 47.0
N = int(SR * DURATION)
rng = np.random.default_rng(17)
HAUL0, HAUL1 = 14.0, 23.0
ROLL0, OPEN = 23.4, 25.0
SAD = 26.6
MORNING = 32.0
END_CHORD = 45.0


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


def bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * freq * h * t) / h * np.exp(-t * (3 + h)) for h in range(1, 7))
    return np.tanh(x * 1.6) * np.clip(t / .004, 0, 1)


def chop(freqs, dur=.12):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sign(np.sin(2 * np.pi * f * t)) for f in freqs)
    return fft_filter(x, 500, 3000) / len(freqs) * np.exp(-t * 30)


def brass(notes, dur, bright=2500):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(sum(np.sin(2 * np.pi * midi(m) * h * t) / h for h in range(1, 9)) for m in notes)
    x = fft_filter(x, 120, bright)
    env = np.clip(t / .03, 0, 1) * np.clip((dur - t) / .08, 0, 1)
    return x / (np.abs(x).max() + 1e-9) * env


def tuba(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * freq * h * t) / h ** 1.2 for h in range(1, 7))
    return fft_filter(x, None, 900) * np.clip(t / .03, 0, 1) * np.exp(-t * 3)


def trombone_slide(f0, f1, dur, vib=0.):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.geomspace(f0, f1, n) * (1 + vib * np.sin(2 * np.pi * 6 * t) * (t > dur * .4))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum(np.sin(ph * h) / h for h in range(1, 8))
    return fft_filter(x, 100, 1800) * np.clip(t / .04, 0, 1) * np.clip((dur - t) / .15, 0, 1)


def kick(g=1.):
    n = int(.4 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (48 * t + 80 / 25 * (1 - np.exp(-t * 25)))) * np.exp(-t * 7) * g


def snare():
    return noise_hit(.2, 1500, 8000, .05) * .8 + noise_hit(.2, 150, 400, .03) * .4


def piano(freq, dur=1.6, vel=1.):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return sum(a * np.sin(2 * np.pi * freq * h * t) * np.exp(-t * (1.2 + h)) for h, a in ((1, 1), (2, .4), (3, .15))) * vel * np.clip(t / .008, 0, 1)


def glock(freq, dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + .3 * np.sin(2 * np.pi * 2.76 * freq * t) * np.exp(-t * 6)) * np.exp(-t * 2.6)


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
BEAT = 60 / 100
E16 = BEAT / 4
# --- sneaky funk: 0 .. 14
riff = [(0, 0), (3, 0), (6, 3), (8, 5), (10, 0), (12, 7), (14, 6)]
t = .25
bar = 0
while t < HAUL0 - .05:
    root = 43 if bar % 2 == 0 else 46            # G / Bb
    for st, semi in riff:
        music.add(bass(midi(root - 12 + semi), E16 * 1.8), t + st * E16, .4)
    for st in range(0, 16, 2):
        music.add(noise_hit(.05, 7000, 14000, .012), t + st * E16, .05 if st % 4 else .08, .3)
    for st in (4, 12):
        music.add(snare(), t + st * E16, .22)
        music.add(chop([midi(root + 12), midi(root + 15), midi(root + 19)]), t + st * E16 + E16, .12, -.3)
    music.add(kick(.9), t, .4); music.add(kick(.7), t + 10 * E16, .35)
    if bar % 2 == 1 and t > 5:
        music.add(brass([root + 12, root + 15, root + 19], .3), t + 14 * E16, .1, .2)
    t += 16 * E16
    bar += 1
# --- the haul: oom-pah stomp 14 .. 23
t = HAUL0
k = 0
while t < HAUL1 - .05:
    music.add(tuba(midi(31 if k % 2 == 0 else 26), BEAT * .9), t, .5)
    music.add(kick(1.0), t, .35)
    music.add(brass([55, 58, 62], BEAT * .4, 1600), t + BEAT, .08)
    t += 2 * BEAT
    k += 1
# --- hideout: drum roll, door, sad trombone
k = 0
while ROLL0 + k * .045 < OPEN - .05:
    music.add(snare(), ROLL0 + k * .045, .06 + .3 * (k * .045 / (OPEN - ROLL0)))
    k += 1
music.add(brass([55, 59, 62, 67], 1.0, 3200), OPEN, .3)
music.add(kick(1.2), OPEN, .5)
for i, (f0, f1, d) in enumerate([(311, 294, .45), (294, 277, .45), (277, 262, .45), (262, 233, 1.4)]):   # wah wah wah wahhh
    music.add(trombone_slide(f0, f1, d, vib=.025 if i == 3 else 0), SAD + .5 + i * .5, .35)
# --- morning: light piano + glock
chords = [[67, 71, 74], [64, 67, 72], [69, 72, 76], [62, 66, 69]]       # G Em(C) Am D
t = MORNING + .2
k = 0
while t < END_CHORD - .05:
    ch = chords[k % 4]
    for j, m in enumerate(ch + [ch[1]]):
        music.add(piano(midi(m)), t + j * BEAT / 2, .1)
    music.add(bass(midi(ch[0] - 24), BEAT * 1.8), t, .25)
    if k % 2 == 1:
        music.add(glock(midi(ch[-1] + 12)), t + BEAT, .06, .3)
    t += 2 * BEAT
    k += 1
for i, m in enumerate([79, 83, 86, 91]):          # sparkle when the diamonds pour
    music.add(glock(midi(m), 1.6), 38.0 + i * .08, .08, -.2 + .15 * i)
for m in (43, 55, 62, 67, 71, 74):
    music.add(piano(midi(m), 3.0, .9), END_CHORD + (m - 43) * .003, .14)

tt = np.arange(N) / SR
fade = np.clip(tt / .5, 0, 1) * np.clip((DURATION - tt) / 1.4, 0, 1)
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
    return noise_hit(.05, 1500, 7000, .008) + noise_hit(.05, 300, 1200, .006) * .5


def dial(dur):
    out = np.zeros(int(dur * SR))
    k = 0
    while k < len(out) - 3000:
        h = noise_hit(.03, 2500, 8000, .004)
        out[k:k + len(h)] += h
        k += int((.07 + .05 * rng.random()) * SR)
    return out


def thud(g=1.):
    n = int(.5 * SR)
    t_ = np.arange(n) / SR
    return (np.sin(2 * np.pi * 55 * t_) * np.exp(-t_ * 9) + noise_hit(.5, 80, 600, .05) * .5) * g


def roll(dur):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), 60, 500)
    return x / np.abs(x).max() * (.6 + .4 * np.sign(np.sin(2 * np.pi * 6 * t_))) * np.clip(t_ / .2, 0, 1) * np.clip((dur - t_) / .3, 0, 1)


def creak(dur=.9):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    f = 180 + 60 * np.sin(2 * np.pi * 1.3 * t_)
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (rng.random(n) > .3)
    return fft_filter(x.astype(float), 300, 2500) * np.sin(np.pi * t_ / dur)


def paper(dur=.4):
    return noise_hit(dur, 1500, 8000, dur / 3) * (.5 + .5 * (rng.random(int(dur * SR)) > .5))


def strain():     # "nnngh" effort grunt-ish low glide
    n = int(.7 * SR)
    t_ = np.arange(n) / SR
    f = 120 + 30 * t_
    return fft_filter(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)), 200, 1200) * np.sin(np.pi * t_ / .7) * .5


events = [
    (.2, whoosh(.8), .2, 0), (6.0, whoosh(.4), .2, 0), (6.3, dial(7.5), .3, -.2),
    (9.2, whoosh(.3), .15, 0),
    (14.6, strain(), .4, 0), (16.3, thud(1.0), .5, 0), (17.4, paper(.5), .3, .2),
    (19.0, pop(), .3, 0), (20.6, roll(2.4), .3, .3),
    (23.0, whoosh(.5), .2, 0), (24.6, creak(.9), .4, 0), (26.6, paper(.5), .3, 0),
    (32.0, whoosh(.6), .25, 0), (32.3, creak(.6), .2, .4), (37.4, paper(.4), .35, 0),
    (43.0, whoosh(.5), .22, 0), (43.3, pop(), .4, 0), (44.4, pop(), .35, 0),
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
for k in range(5):                                   # diamonds clinking on the desk
    sfx.add(glock(midi(96 + k % 3), .3) * np.exp(-np.arange(int(.3 * SR)) / SR * 20), 38.1 + k * .2, .2, .2)
for at in np.arange(.5, 3.8, .45):                   # sneaking steps
    sfx.add(noise_hit(.06, 200, 2000, .015), at, .15, .3)
for at in np.arange(32.2, 33.8, .5):
    sfx.add(noise_hit(.08, 150, 2000, .02), at, .2, .3)
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
