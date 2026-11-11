"""Gentle background score + SFX for "The Painting Thief" (all synthesised, no samples).

Soft felt-piano arpeggios over warm pads and a quiet upright-bass pulse
(F major, ~76 BPM). It thins out on day 3, pauses on the reveal with a
soft bell, and resolves on a final chord.

Usage: python3 music.py <out_dir>   -> music.wav, sfx.wav (44.1 kHz stereo)
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 42.0
N = int(SR * DURATION)
rng = np.random.default_rng(3)
REVEAL = 33.0
END_CHORD = 39.4


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


def env_ad(n, attack, decay):
    t = np.arange(n) / SR
    return np.clip(t / max(attack, 1e-4), 0, 1) * np.exp(-t / decay)


def noise_hit(dur, lo, hi, decay):
    n = int(dur * SR)
    x = fft_filter(rng.standard_normal(n), lo, hi)
    return x / (np.abs(x).max() + 1e-9) * env_ad(n, 0.001, decay)


def piano(freq, dur, vel=1.0):
    """Soft felt piano: few partials, slow-ish decay, gentle hammer."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for h, a in ((1, 1), (2, .38), (3, .14), (4, .06), (5, .03)):
        x += a * np.sin(2 * np.pi * freq * h * (1 + .0004 * h * h) * t) * np.exp(-t * (1.1 + .9 * h))
    x *= np.clip(t / .012, 0, 1) * vel
    return x


def bell(freq, dur, decay=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ratios = [(1, 1.0), (2.0, .4), (2.76, .25), (5.4, .1)]
    return sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / (decay / r ** .5)) for r, a in ratios) * np.clip(t / .002, 0, 1)


def pad(notes, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        for det in (-.08, .07):
            f = midi(m + det)
            out += np.sin(2 * np.pi * f * t) + .3 * np.sin(2 * np.pi * 2 * f * t) + .1 * np.sin(2 * np.pi * 3 * f * t)
    out = fft_filter(out, 90, 1800)
    fade = np.minimum(np.clip(t / 1.0, 0, 1), np.clip((dur - t) / 1.0, 0, 1))
    return out / (np.abs(out).max() + 1e-9) * fade


def bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + .25 * np.sin(2 * np.pi * 2 * freq * t)
    return x * np.clip(t / .01, 0, 1) * np.exp(-t * 2.2)


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
OFFSET = .25
BAR = (REVEAL - OFFSET) / 10          # ~3.28s per bar -> ~73 BPM; the reveal lands on a downbeat
E8 = BAR / 8
prog = [(41, [65, 69, 72, 76]),       # Fmaj7
        (38, [62, 65, 69, 72, 76]),   # Dm9
        (34, [62, 65, 69, 70]),       # Bbmaj7
        (36, [64, 67, 70, 72])]       # C7sus-ish
arp_up = [0, 1, 2, 3, 2, 1, 2, 3]

bi = 0
bs = OFFSET
while bs < END_CHORD - .1:
    root, chord = prog[bi % 4]
    post = bs >= REVEAL - .01
    day3 = 18.0 <= bs < REVEAL - .01
    music.add(pad([m - 12 for m in chord[:3]], BAR + 1.0), bs, .07 if not post else .05)
    music.add(bass(midi(root), BAR * .9), bs, .32)
    music.add(bass(midi(root + 7), BAR * .45), bs + BAR / 2, .18)
    for k in range(8):
        tt = bs + k * E8
        if tt >= END_CHORD - .1:
            break
        if day3 and k % 2:          # thinner, a little more tense on day 3
            continue
        note = chord[arp_up[k] % len(chord)]
        vel = .9 if k == 0 else .6 + .2 * rng.random()
        music.add(piano(midi(note), 2.0, vel), tt + rng.uniform(-.008, .008), .13, -.15 + .1 * (k % 3))
    # small glockenspiel motif every other bar
    if bi % 2 == 1 and not day3 and bs > 4:
        for k, m in enumerate([chord[-1] + 12, chord[-2] + 12, chord[1] + 12]):
            music.add(bell(midi(m), 1.6, .6), bs + (4 + k) * E8, .05, .35)
    # soft brush on the off-beats (very quiet)
    if 8 <= bs < REVEAL - .01:
        for k in range(1, 8, 2):
            music.add(noise_hit(.12, 4000, 11000, .035), bs + k * E8, .025, .2)
    bs += BAR
    bi += 1

# reveal: everything breathes out, a soft bell chord
for i, m in enumerate([77, 81, 84, 89]):
    music.add(bell(midi(m), 3.0, 1.2), REVEAL + .02 + i * .09, .07, -.3 + .2 * i)
# final chord
for m in (41, 53, 60, 65, 69, 72, 76):
    music.add(piano(midi(m), 3.5, .8), END_CHORD + (m - 41) * .004, .16)
music.add(pad([53, 60, 65, 69], 3.0), END_CHORD, .08)

tt = np.arange(N) / SR
fade = np.clip(tt / .8, 0, 1) * np.clip((DURATION - tt) / 1.6, 0, 1)
mix = np.stack([music.L, music.R]) * fade
mix = mix / (np.abs(mix).max() + 1e-9) * .6

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


def paper():
    out = np.zeros(int(.35 * SR))
    for i in range(5):
        h = noise_hit(.05, 1200, 7000, .012)
        j = int((.02 + i * .055) * SR)
        out[j:j + len(h)] += h * (1 - i * .15)
    return out


def clack():
    n = int(.25 * SR)
    t_ = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 320 * t_) * np.exp(-t_ * 40) + .5 * np.sin(2 * np.pi * 710 * t_) * np.exp(-t_ * 60)
    return tone + noise_hit(.25, 800, 5000, .02) * .6


def latch():
    n = int(.3 * SR)
    t_ = np.arange(n) / SR
    metal = sum(np.sin(2 * np.pi * f * t_) * np.exp(-t_ * d) for f, d in ((1850, 25), (2730, 30), (4100, 40)))
    return metal * .4 + noise_hit(.3, 2000, 9000, .015)


def rustle(dur=.8):
    x = noise_hit(dur, 1500, 8000, dur / 2) * (.5 + .5 * np.abs(np.sin(np.arange(int(dur * SR)) / SR * 40)))
    return x


def steps(t0, t1, rate=1.9, gain=.22):
    t = t0
    while t < t1:
        sfx.add(noise_hit(.08, 150, 1800, .02), t, gain, 0)
        t += 1 / rate


events = [
    (.2, whoosh(.8), .25, 0),
    (4.45, clack(), .5, .2),        # sign set down
    (8.0, paper(), .6, -.2), (8.1, pop(), .3, 0),
    (13.55, latch(), .5, .3),       # toolbox opens
    (15.0, rustle(.9), .35, .3),    # rag unfolded
    (16.0, pop(), .45, 0),          # NOTHING!
    (18.0, paper(), .6, -.2), (18.1, pop(), .3, 0),
    (19.1, rustle(.5), .2, 0),      # painting off the hook
    (21.0, pop(), .4, 0), (23.4, pop(), .4, 0),
    (28.7, pop(), .4, 0), (30.6, pop(), .4, 0),
    (33.0, whoosh(.6), .2, 0),
    (38.5, whoosh(.5), .25, 0), (38.95, pop(), .45, 0),
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
steps(.4, 3.6); steps(20.0, 21.0); steps(27.0, 28.2); steps(28.0, 28.8, 2.2)
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
