"""Suspense score + SFX for "The Bait" (all synthesised, no samples).

E minor, ~96 BPM: ticking 16th hats and a low pulsing bass while the thief
picks his target and walks off, a hopeful 'jackpot' lift as he opens the
case, a hard stop on the sign, a stab on the camera, heavy drum steps,
then a satisfying major resolution when the old man shows his badge.

Usage: python3 music.py <out_dir>   -> music.wav, sfx.wav (44.1 kHz stereo)
"""
import sys
import wave

import numpy as np

SR = 44100
DURATION = 46.5
N = int(SR * DURATION)
rng = np.random.default_rng(5)
SIGN, CAM, STEPS, POLICE = 23.0, 26.0, 28.4, 31.0
END_CHORD = 44.3


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


def synth_bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * freq * h * t) / h for h in range(1, 6))
    x = fft_filter(x, None, 600)
    return np.tanh(x * 1.5) * np.clip(t / .005, 0, 1) * np.exp(-t * 5)


def strings(notes, dur, bright=1800):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        for det in (-.1, 0, .1):
            f = midi(m + det)
            out += sum(np.sin(2 * np.pi * f * h * t + rng.uniform(0, 6)) / h for h in range(1, 7))
    out = fft_filter(out, 100, bright)
    fade = np.minimum(np.clip(t / .8, 0, 1), np.clip((dur - t) / .8, 0, 1))
    return out / (np.abs(out).max() + 1e-9) * fade


def stab(notes, dur=1.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = sum(sum(np.sin(2 * np.pi * midi(m) * h * t) / h for h in range(1, 8)) for m in notes)
    return out / np.abs(out).max() * np.exp(-t * 3) * np.clip(t / .004, 0, 1)


def bell(freq, dur=2.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / (1.2 / r ** .5)) for r, a in ((1, 1), (2, .4), (2.76, .25), (5.4, .1)))


def kick(gain=1.):
    n = int(.5 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (45 * t + 90 / 25 * (1 - np.exp(-t * 25)))) * np.exp(-t * 6) * gain


def tom(f=90):
    n = int(.7 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (f * t + f / 10 * (1 - np.exp(-t * 10)))) * np.exp(-t * 4) + noise_hit(.7, 200, 1500, .05) * .2


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
BEAT = 60 / 96
S16 = BEAT / 4
prog = [(40, [64, 67, 71]), (40, [64, 67, 71]), (36, [60, 64, 67]), (38, [62, 66, 69])]   # Em Em C D

t = .3
bar = 0
while t < SIGN - .05:
    root, chord = prog[bar % 4]
    hope = t >= 15.0                       # 'jackpot?' lift while he opens the case
    music.add(strings([m - 12 for m in chord], 4 * BEAT + .8, 2400 if hope else 1400), t, .09 if not hope else .12)
    for st in range(16):
        bt = t + st * S16
        if bt >= SIGN - .05:
            break
        music.add(noise_hit(.04, 6000, 14000, .01), bt, .05 if st % 4 else .08, .3)       # ticking 16ths
        if st % 2 == 0:
            music.add(synth_bass(midi(root - 12 + (7 if st in (6, 14) else 0)), S16 * 1.8), bt, .32)
        if st in (0, 10) and t > 6:
            music.add(kick(.8), bt, .4)
    if hope:
        for k, m in enumerate([76, 79, 83, 79]):
            music.add(bell(midi(m), 1.4), t + k * BEAT, .05, .35)
    t += 4 * BEAT
    bar += 1

# the sign: hard stop + one eerie bell
music.add(bell(midi(83), 3.0), SIGN + .05, .08)
music.add(strings([52, 59, 63], CAM - SIGN + .5, 900), SIGN, .06)
# the camera: stab
music.add(stab([40, 52, 58, 63, 70]), CAM, .4)
music.add(kick(1.2), CAM, .6)
# footsteps: heavy toms, accelerating
for k, at in enumerate([STEPS, STEPS + .62, STEPS + 1.18, STEPS + 1.68, STEPS + 2.12, STEPS + 2.5]):
    music.add(tom(80 + k * 4), at, .45 + k * .05)
music.add(strings([40, 47, 52], POLICE - STEPS + .6, 1200), STEPS, .1)
# police: satisfying major resolution
t = POLICE
k = 0
for root, chord in [(40, [64, 68, 71]), (36, [60, 64, 67]), (43, [62, 67, 71]), (38, [62, 66, 69])] * 2:
    if t >= END_CHORD - .05:
        break
    music.add(strings([m - 12 for m in chord] + [chord[0]], 4 * BEAT + .8, 2600), t, .12)
    for st in range(0, 16, 2):
        music.add(synth_bass(midi(root - 12), S16 * 1.8), t + st * S16, .26)
    music.add(kick(.9), t, .4); music.add(kick(.7), t + 2 * BEAT, .35)
    for b in (1, 3):
        music.add(noise_hit(.2, 1500, 8000, .06), t + b * BEAT, .12, -.2)
    t += 4 * BEAT
    k += 1
for m in (40, 52, 59, 64, 68, 71, 76):
    music.add(bell(midi(m), 3.0) if m > 60 else synth_bass(midi(m), 2.5), END_CHORD, .08 if m > 60 else .3)
music.add(strings([52, 59, 64, 68], 2.4, 2000), END_CHORD, .1)

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


def chime():          # station announcement ding-dong
    return np.concatenate([bell(midi(76), .7)[: int(.45 * SR)], bell(midi(72), 1.6)])


def crowd(dur):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), 250, 1800)
    x /= np.abs(x).max()
    return x * (.6 + .4 * np.sin(2 * np.pi * .3 * t_)) * np.clip(t_ / 1, 0, 1) * np.clip((dur - t_) / 1, 0, 1)


def rolling(dur):
    n = int(dur * SR)
    t_ = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n), 60, 500)
    x /= np.abs(x).max()
    return x * (.7 + .3 * np.sign(np.sin(2 * np.pi * 9 * t_))) * np.clip(t_ / .2, 0, 1) * np.clip((dur - t_) / .3, 0, 1)


def zipper(dur=.7):
    out = np.zeros(int(dur * SR))
    k = 0
    while k < len(out) - 800:
        h = noise_hit(.012, 2500, 9000, .003)
        out[k:k + len(h)] += h
        k += int(.011 * SR)
    return out


def beep():
    n = int(.16 * SR)
    t_ = np.arange(n) / SR
    return np.sin(2 * np.pi * 1760 * t_) * np.clip((.16 - t_) / .02, 0, 1)


def step(gain=1.):
    return noise_hit(.12, 100, 1800, .03) * gain


events = [
    (.4, chime(), .25, 0), (0, crowd(14), .1, 0),
    (6.0, whoosh(.5), .2, 0), (10.1, noise_hit(.15, 800, 5000, .03), .3, .2), (10.4, noise_hit(.1, 1500, 6000, .02), .3, .2),
    (10.6, rolling(3.3), .25, .3),
    (14.0, whoosh(.6), .25, 0), (15.0, zipper(.7), .35, .2), (16.0, pop(), .3, 0),
    (19.6, noise_hit(.3, 100, 1200, .08), .4, 0), (21.0, noise_hit(.3, 400, 3000, .06), .25, 0),
    (23.0, whoosh(.4), .2, 0), (26.0, beep(), .25, .3), (26.2, beep(), .25, .3), (26.0, noise_hit(.5, 3000, 9000, .1, .2), .15, 0),
    (31.0, whoosh(.5), .2, 0), (33.0, noise_hit(.2, 600, 4000, .05), .3, -.2),
    (36.0, whoosh(.4), .15, 0), (38.6, noise_hit(.25, 2000, 8000, .04), .2, 0), (39.3, pop(), .4, 0),
    (42.0, whoosh(.5), .22, 0), (42.4, pop(), .4, 0), (43.95, pop(), .35, 0),
]
for at, sig, g, p in events:
    sfx.add(sig, at, g, p)
for k, at in enumerate([28.4, 29.0, 29.6, 30.15, 30.65, 31.1, 31.55, 32.0, 32.4]):   # approaching footsteps (echoey)
    sfx.add(step(.4 + .07 * k), at, .5, -.4)
    sfx.add(step(.2 + .03 * k), at + .09, .3, .4)
for at in np.arange(6.6, 8.8, .55):
    sfx.add(step(.4), at, .2, -.3)
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
