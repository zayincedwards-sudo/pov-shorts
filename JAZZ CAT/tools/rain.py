"""Synthesise a seamless rain-on-window loop (free, no API).

  python tools/rain.py <out.wav> [--seconds 354] [--seed 7]

Layers, all stereo and decorrelated L/R:
  - a steady wash: pink noise shaped to rain (high-pass 250 Hz, gentle shelf down above 7 kHz), with a slow
    random swell of +-1.5 dB so it never sounds static
  - drops on the glass: thousands of short decaying ticks (1-6 kHz, 3-25 ms), Poisson-timed, random pan
  - heavier drips: a few per second, lower (300-900 Hz) and longer, like water running off the frame
The loop is made seamless by rendering 4 s extra and crossfading the tail into the head (equal power).
The reference's rain bed is a 354.0 s loop (ANALYSIS.md), so that is the default length.
"""
import argparse, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100


def pink(n, rng):
    # Voss-McCartney style via FFT shaping (1/f power)
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    k = np.arange(len(f)); k[0] = 1
    f /= np.sqrt(k)
    x = np.fft.irfft(f, n)
    return x / np.abs(x).max()


def ticks(n, rate, fmin, fmax, dmin, dmax, rng):
    out = np.zeros((n, 2))
    count = rng.poisson(rate * n / SR)
    pos = rng.integers(0, n, count)
    for p in pos:
        d = int(rng.uniform(dmin, dmax) * SR)
        t = np.arange(d) / SR
        f = rng.uniform(fmin, fmax)
        env = np.exp(-t / (d / SR / 4))
        s = np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * env * rng.uniform(0.2, 1.0)
        s += rng.standard_normal(d) * env * 0.3                 # a little splash noise in each tick
        pan = rng.uniform(0.15, 0.85)
        e = min(n, p + d)
        out[p:e, 0] += s[:e - p] * np.sqrt(1 - pan)
        out[p:e, 1] += s[:e - p] * np.sqrt(pan)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--seconds', type=float, default=354.0); ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    xf = 4.0
    n = int((a.seconds + xf) * SR)
    hp = butter(2, 250, 'high', fs=SR, output='sos'); lp = butter(2, 7000, 'low', fs=SR, output='sos')
    wash = np.stack([sosfilt(lp, sosfilt(hp, pink(n, rng))) for _ in range(2)], 1)
    # slow swell, +-1.5 dB, independent-ish per side
    t = np.arange(n) / SR
    sw = 10 ** ((1.5 * np.sin(2 * np.pi * t / 23.0 + 1.1) * np.sin(2 * np.pi * t / 61.0)) / 20)
    wash *= sw[:, None]
    drops = ticks(n, 900, 1000, 6000, 0.003, 0.025, rng)
    drips = ticks(n, 3, 300, 900, 0.06, 0.18, rng)
    mix = wash * 0.55 + drops * 0.05 + drips * 0.08
    L = int(a.seconds * SR); X = int(xf * SR)
    g = np.sqrt(np.linspace(0, 1, X))[:, None]
    loop = mix[:L].copy()
    loop[:X] = mix[:X] * g + mix[L:L + X] * g[::-1]           # tail flows into head: seamless when repeated
    loop /= np.abs(loop).max() / 0.5                         # peak -6 dBFS; final level is set at the mix
    pcm = (loop * 32767).astype('<i2')
    with wave.open(a.out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(f'{a.out}: {a.seconds:.1f} s seamless rain loop')


if __name__ == '__main__':
    main()
