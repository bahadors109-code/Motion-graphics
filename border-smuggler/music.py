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
ARGS = dict(a.split('=') for a in sys.argv[2:])
DURATION = float(ARGS.get('dur', 43.0))
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

# ---------------------------------------------------------------- beat
# Boom-bap "detective" groove in D minor. Bar grid is anchored so that the
# reveal (36.75s) lands exactly on a downbeat.
GUARD_START, GUARD_END = 22.5, float(ARGS.get('guardEnd', 25.3))   # break under the guard's line
REVEAL = float(ARGS.get('reveal', 36.75))                        # «خودِ دوچرخه‌ها بودن!» / "was the bicycles themselves!"
END_CHORD = DURATION - 2.0
OFFSET = 0.30
BAR = (REVEAL - OFFSET) / 14          # ≈ 2.604s → ~92 BPM
S16 = BAR / 16
SWING = S16 * 0.18


def kick():
    n = int(0.45 * SR); t_ = np.arange(n) / SR
    body = np.sin(2 * np.pi * (48 * t_ + 110 / 28 * (1 - np.exp(-t_ * 28)))) * np.exp(-t_ * 7)
    click = rng.standard_normal(n) * np.exp(-t_ * 400) * .3
    return np.tanh((body + click) * 1.6)


def snare():
    n = int(0.3 * SR); t_ = np.arange(n) / SR
    nz = fft_filter(rng.standard_normal(n), 1200, 9000)
    nz = nz / np.abs(nz).max() * np.exp(-t_ * 16)
    tone = np.sin(2 * np.pi * 185 * t_) * np.exp(-t_ * 25) * .6
    clap = np.zeros(n)
    for d in (0, .011, .022):
        j = int(d * SR); seg_ = fft_filter(rng.standard_normal(n - j), 900, 4000)
        clap[j:] += seg_ / np.abs(seg_).max() * np.exp(-np.arange(n - j) / SR * 60) * .5
    return (nz * .8 + tone + clap) * .8


def hat(open_=False):
    d = .25 if open_ else .06
    return noise_hit(d, 7000, 16000, .09 if open_ else .018)


def rhodes(freq, dur):
    n = int(dur * SR); t_ = np.arange(n) / SR
    trem = 1 + .25 * np.sin(2 * np.pi * 4.5 * t_)
    x = (np.sin(2 * np.pi * freq * t_) + .25 * np.sin(2 * np.pi * 2 * freq * t_) * np.exp(-t_ * 3)
         + .12 * np.sin(2 * np.pi * 7.1 * freq * t_) * np.exp(-t_ * 22))
    return x * np.exp(-t_ * 1.3) * trem * np.clip(t_ / .005, 0, 1)


def bass(freq, dur):
    n = int(dur * SR); t_ = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t_) + .3 * np.sin(2 * np.pi * 2 * freq * t_) + .1 * np.sin(2 * np.pi * 3 * freq * t_)
    env = np.clip(t_ / .006, 0, 1) * np.clip((dur - t_) / .03, 0, 1) * (0.75 + .25 * np.exp(-t_ * 8))
    return np.tanh(x * env * 1.3)


K, SN, HC, HO = kick(), snare(), hat(), hat(True)
prog = [(38, [62, 65, 69, 72]), (38, [62, 65, 69, 72]), (34, [58, 62, 65, 69]), (33, [57, 61, 64, 67])]
KICKS = [0, 7, 10]               # 16th steps
KICKS_B = [0, 3, 7, 10, 14]      # busier variation every 4th bar
BASS = [(0, 0, 3), (3, 0, 1), (7, 7, 2), (10, 12, 2), (13, 10, 2)]   # (step, semitone, length in 16ths)
LEAD = [[(0, 74), (3, 77), (6, 76), (8, 74), (11, 72), (14, 69)],
        [(2, 74), (4, 77), (7, 81), (10, 79), (12, 77)]]


def in_break(x):
    return GUARD_START <= x < GUARD_END


def step_t(bar_start, st):
    return bar_start + st * S16 + (SWING if st % 2 else 0)


n_bars = int((DURATION - OFFSET) / BAR) + 1
for bi in range(n_bars):
    bs = OFFSET + bi * BAR
    if bs > END_CHORD - .05:
        break
    root, chord = prog[bi % 4]
    intro = bs < 5.4                 # intro: no snare/bass, light drums
    build = 31.3 <= bs < REVEAL - .01  # build-up: thinner, snare roll at the end
    post = bs >= REVEAL - .01
    # drums
    for st in range(16):
        tt_ = step_t(bs, st)
        if tt_ >= END_CHORD - .05 or in_break(tt_):
            continue
        kicks = KICKS_B if bi % 4 == 3 else KICKS
        if st in kicks and not (build and st != 0):
            music.add(K, tt_, .9 if not intro else .55)
        if st in (4, 12) and not intro:
            music.add(SN, tt_, .55, .05)
        if st % 2 == 0:
            music.add(HO if (st == 14 and bi % 2) else HC, tt_, (.22 if st % 4 == 0 else .14) * (.7 if intro else 1), .3)
        elif not intro and not build:
            music.add(HC, tt_, .07, .3)
    # bass
    if not intro:
        for st, semi, ln in BASS:
            tt_ = step_t(bs, st)
            if tt_ >= END_CHORD - .05 or in_break(tt_) or (build and st != 0):
                continue
            music.add(bass(midi(root + semi), ln * S16 * .95), tt_, .5)
    # keys: chord stab on 1 and the "and" of 2
    for st in (0, 6) if not intro else (0,):
        tt_ = step_t(bs, st)
        if tt_ >= END_CHORD - .05 or in_break(tt_):
            continue
        for m in chord:
            music.add(rhodes(midi(m - (0 if not post else -0)), BAR * .45), tt_, .07, -.2)
    # lead motif (sneaky) in the main sections and after the drop
    if (5.4 <= bs < 31.3 or post) and bi % 2 == 1 or post:
        for st, m in LEAD[(bi // 2) % 2]:
            tt_ = step_t(bs, st)
            if tt_ >= END_CHORD - .05 or in_break(tt_):
                continue
            music.add(pluck(midi(m + (4 if post and m in (77, 65) else 0) - 12 * 0), .3, 1.1, .1), tt_, .13, .35)

# snare roll into the drop
roll_start = REVEAL - BAR / 2
k = 0
while roll_start + k * S16 / 2 < REVEAL - .02:
    music.add(SN, roll_start + k * S16 / 2, .15 + .45 * (k / 16), .0)
    k += 1

# break under the guard's line: tick-tock + filtered keys
tt_ = GUARD_START + .05
k = 0
while tt_ < GUARD_END - .1:
    music.add(noise_hit(.05, 2500 if k % 2 else 3500, 8000, .01), tt_, .3, -.3 if k % 2 else .3)
    tt_ += BAR / 8
    k += 1
music.add(rhodes(midi(57), 2.6) + rhodes(midi(61), 2.6) + rhodes(midi(64), 2.6), GUARD_START, .09)
# tape-stop style dip into the break: low boom
n = int(.6 * SR); t_ = np.arange(n) / SR
music.add(np.sin(2 * np.pi * (60 * t_ - 20 * t_ * t_)) * np.exp(-t_ * 4), GUARD_START, .5)

# riser into the reveal
rn = int((REVEAL - 31.3) * SR)
rt = np.arange(rn) / SR
riser = fft_filter(rng.standard_normal(rn), 500, 7000) * (rt / rt[-1]) ** 2.5
music.add(riser / np.abs(riser).max(), 31.3, .12)

# drop: impact + bright bells
music.add(K, REVEAL, 1.0); music.add(SN, REVEAL, .5)
n = int(1.5 * SR); t_ = np.arange(n) / SR
music.add(np.sin(2 * np.pi * 42 * t_) * np.exp(-t_ * 2.5), REVEAL, .7)
for i, m in enumerate([74, 78, 81, 86]):
    music.add(bell(midi(m), 2.5, .8), REVEAL + i * .07, .16, -.3 + .2 * i)

# ending chord
for m in (38, 50, 62, 65, 69, 74):
    music.add(rhodes(midi(m), 2.0), END_CHORD, .12 if m > 45 else .3)
music.add(K, END_CHORD, .8)

tt = np.arange(N) / SR
fade = np.clip(tt / .4, 0, 1) * np.clip((DURATION - tt) / 1.0, 0, 1)
mix = np.stack([music.L, music.R]) * fade
mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.8) * .55

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
    (float(ARGS.get('sack0', 33.7)) + .2, whoosh(0.6), 0.25, 0),     # sacks fade away
    (float(ARGS.get('s7', 39.1)) + .1, whoosh(0.5), 0.3, 0),
    (float(ARGS.get('s7', 39.1)) + .5, pop(), 0.5, 0),            # final text
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
