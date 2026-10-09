"""Estimate a picture loop length from storyboard frames (sampled ~10 s apart, so the loop is aliased).

  python sb_loop.py <info.json> <sheet_dir> [x0 x1 y0 y1]

Takes the closest frame pairs (true repeats look alike) and scores every candidate loop length L by how many of
those pairs sit a whole number of loops apart (within one 30 fps frame), against what chance gives. Free.
"""
import importlib.util, os, sys
import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('sbm', os.path.join(here, 'storyboard.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
fr, per = m.frames(sys.argv[1], sys.argv[2], 'sb0')
x0, x1, y0, y1 = map(int, sys.argv[3:7]) if len(sys.argv) > 6 else (0, 321, 0, 180)
ts = np.array([t for t, _ in fr])
R = np.stack([x[y0:y1, x0:x1] for _, x in fr]).reshape(len(fr), -1).astype(np.float32)
sq = (R ** 2).sum(1); D = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2 * R @ R.T, 0) / R.shape[1])
iu = np.triu_indices(len(R), 1); d = D[iu]; dt = ts[iu[1]] - ts[iu[0]]
order = np.argsort(d); close = dt[order[:3000]]; rand = dt[order[len(order) // 2:len(order) // 2 + 3000]]
tol = 1 / 30
best = []
for L in np.arange(3.0, 400.0, 0.005):
    f = lambda x: np.mean(np.abs(((x / L) - np.round(x / L)) * L) < tol)
    c = f(close)
    if c > 0.05:
        best.append((c / max(f(rand), 1e-3), c, L))
best.sort(reverse=True)
print('closest-pair dist p0.1/p1/p50:', np.percentile(d, [0.1, 1, 50]).round(2))
for r, c, L in best[:12]:
    print(f'L={L:8.3f}s  hit={c:.2f}  vs chance x{r:.1f}')
