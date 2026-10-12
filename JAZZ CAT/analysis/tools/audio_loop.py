"""Prove a sound-bed loop length on the waveform: cross-correlate a window at time A against the region around A+lag,
in the full mix, the music band (< 2 kHz) and the rain band (> 5 kHz) separately.

  python audio_loop.py <audio> <lag_guess_s> [<lag_guess_s> ...]

Prints the refined lag to the sample and the correlation peak per band, at several start points. Free.
"""
import subprocess, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 22050


def load(p):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def ncc(a, b):
    """Normalised cross-correlation of short a sliding over longer b."""
    a = (a - a.mean()) / (a.std() * len(a))
    c = fftconvolve(b, a[::-1], mode='valid')
    n = len(a)
    c1 = np.r_[0, np.cumsum(b)]; c2 = np.r_[0, np.cumsum(b ** 2)]
    m = (c1[n:] - c1[:-n]) / n
    s = np.sqrt(np.maximum((c2[n:] - c2[:-n]) / n - m ** 2, 0))
    return c / (s + 1e-12)


y = load(sys.argv[1]); dur = len(y) / SR
bands = {'mix': y,
         'music<2k': sosfiltfilt(butter(6, 2000, 'low', fs=SR, output='sos'), y),
         'rain>5k': sosfiltfilt(butter(6, 5000, 'high', fs=SR, output='sos'), y)}
W, SEARCH = 10.0, 8.0
for g in map(float, sys.argv[2:]):
    print(f'== lag guess {g:.1f}s')
    for start in np.linspace(20, dur - g - W - SEARCH - 1, 5):
        out = []
        for name, x in bands.items():
            a = x[int(start * SR):int((start + W) * SR)]
            lo = int((start + g - SEARCH) * SR); hi = int((start + g + SEARCH + W) * SR)
            if hi > len(x):
                continue
            r = ncc(a, x[lo:hi]); k = int(r.argmax())
            out.append(f'{name} lag={(lo + k) / SR - start:9.4f}s r={r[k]:.3f}')
        print(f'  @{start:7.1f}s  ' + ' | '.join(out))
