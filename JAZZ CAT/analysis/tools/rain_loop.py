"""Find the rain layer's own loop: slide 10 s windows of the >5 kHz band across the whole file and list where each
window reappears (normalised cross-correlation peaks well above the noise floor).

  python rain_loop.py <audio> [--hp 5000]
Free.
"""
import importlib.util, os, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('al', os.path.join(here, 'audio_loop.py'))
src = open(os.path.join(here, 'audio_loop.py')).read().split('\ny = load(')[0]   # reuse load + ncc only
ns = {}; exec(compile(src, 'audio_loop', 'exec'), ns)
SR = ns['SR']
hp = float(sys.argv[sys.argv.index('--hp') + 1]) if '--hp' in sys.argv else 5000
y = ns['load'](sys.argv[1])
x = sosfiltfilt(butter(6, hp, 'high', fs=SR, output='sos'), y)
W = 10.0
for start in [30, 250, 500, 900, 1300]:
    a = x[int(start * SR):int((start + W) * SR)]
    r = ns['ncc'](a, x)
    r[max(0, int((start - 1) * SR)):int((start + 1) * SR)] = 0           # drop self-match
    floor = np.percentile(np.abs(r[::50]), 99.9)
    pk = []
    rr = r.copy()
    for _ in range(6):
        k = int(rr.argmax())
        if rr[k] < max(0.3, 3 * floor):
            break
        pk.append((round(k / SR, 3), round(float(rr[k]), 3)))
        rr[max(0, k - SR):k + SR] = 0
    print(f'window @{start}s: floor99.9={floor:.3f}  reappears at', pk, ' lags', [round(p - start, 3) for p, _ in pk])
