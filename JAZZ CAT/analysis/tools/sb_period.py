"""Fine search for a picture loop length L from storyboard frames alone (aliased ~10 s sampling).
For each L, pairs of frames whose time difference is within 0.25 s of a whole number of loops should look alike;
score = their mean distance over the mean distance of all pairs (lower is better).

  python sb_period.py <info.json> <sheet_dir> <Lmin> <Lmax> [max_lag_frames]
Free.
"""
import importlib.util, os, sys
import numpy as np
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('sbm', os.path.join(here, 'storyboard.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
fr, per = m.frames(sys.argv[1], sys.argv[2], 'sb0')
lo, hi = float(sys.argv[3]), float(sys.argv[4]); K = int(sys.argv[5]) if len(sys.argv) > 5 else 200
ts = np.array([t for t, _ in fr])
R = np.stack([x[60:175, 170:300] for _, x in fr]).reshape(len(fr), -1).astype(np.float32)
I, J = [], []
for k in range(1, K + 1):
    i = np.arange(len(R) - k); I.append(i); J.append(i + k)
I = np.concatenate(I); J = np.concatenate(J)
d = np.empty(len(I), np.float32)
for s in range(0, len(I), 20000):
    d[s:s + 20000] = np.sqrt(((R[I[s:s + 20000]] - R[J[s:s + 20000]]) ** 2).mean(1))
dt = ts[J] - ts[I]
out = []
for L in np.arange(lo, hi, 0.005):
    ph = np.abs((dt / L - np.round(dt / L)) * L)
    sel = ph < 0.25
    if sel.sum() > 40:
        out.append((float(d[sel].mean() / d.mean()), float(L), int(sel.sum())))
out.sort()
for sc, L, n in out[:10]:
    print(f'L={L:8.3f}s  score={sc:.3f}  pairs={n}')
