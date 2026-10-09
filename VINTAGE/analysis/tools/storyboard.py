"""Read a video's picture across its whole runtime from YouTube's storyboard sprites (i.ytimg.com, not bot-walled).

  python storyboard.py <info.json> <sheet_dir> <out_json> [--fmt sb0]

Splits every sheet into frames (sb0: 321x180, one frame about every 10 s), then measures:
  - distance of every frame from the first frame and from the median frame (does the scene ever change?)
  - frame-to-frame change (cuts, fades, overlays)
  - a per-pixel temporal std map (which parts of the frame move) -> <out>_motion.png
  - mean luminance over time (day/night shifts, fades at the ends)
Free; no API calls.
"""
import glob, json, os, sys
import numpy as np
from PIL import Image


def frames(info, sheet_dir, fmt):
    d = json.load(open(info, encoding='utf-8'))
    f = next(x for x in d['formats'] if x['format_id'] == fmt)
    w, h, rows, cols = f['width'], f['height'], f['rows'], f['columns']
    total = d['duration']
    sheets = sorted(glob.glob(os.path.join(sheet_dir, f'{fmt}_*.jpg')))
    per = f['fragments'][0]['duration'] / (rows * cols)       # seconds per tile
    out = []
    for si, p in enumerate(sheets):
        im = np.asarray(Image.open(p).convert('RGB'), dtype=np.float32)
        for r in range(rows):
            for c in range(cols):
                t = (si * rows * cols + r * cols + c) * per
                if t >= total:
                    continue
                tile = im[r * h:(r + 1) * h, c * w:(c + 1) * w]
                if tile.shape[:2] != (h, w) or tile.mean() < 1:     # padding tiles on the last sheet
                    continue
                out.append((t, tile))
    return out, per


def main():
    info, sheet_dir, dst = sys.argv[1:4]
    fmt = sys.argv[sys.argv.index('--fmt') + 1] if '--fmt' in sys.argv else 'sb0'
    fr, per = frames(info, sheet_dir, fmt)
    ts = np.array([t for t, _ in fr]); st = np.stack([x for _, x in fr])
    med = np.median(st, axis=0)
    d_first = np.abs(st - st[0]).mean(axis=(1, 2, 3))
    d_med = np.abs(st - med).mean(axis=(1, 2, 3))
    d_step = np.r_[0, np.abs(np.diff(st, axis=0)).mean(axis=(1, 2, 3))]
    lum = st.mean(axis=(1, 2, 3))
    std = st.std(axis=0).mean(axis=2)
    norm = np.clip(std / max(np.percentile(std, 99.5), 1e-6) * 255, 0, 255).astype(np.uint8)
    Image.fromarray(norm).resize((norm.shape[1] * 4, norm.shape[0] * 4), Image.NEAREST).save(dst.replace('.json', '_motion.png'))
    Image.fromarray(med.astype(np.uint8)).save(dst.replace('.json', '_median.png'))
    moving = float((std > 6).mean())
    big = [(round(float(t)), round(float(s), 1)) for t, s in zip(ts, d_step) if s > 3 * np.median(d_step) + 4]
    res = dict(fmt=fmt, frames=len(fr), seconds_per_frame=round(per, 3), duration=float(ts[-1]),
               dist_from_first=dict(median=round(float(np.median(d_first)), 2), max=round(float(d_first.max()), 2)),
               dist_from_median=dict(median=round(float(np.median(d_med)), 2), p99=round(float(np.percentile(d_med, 99)), 2),
                                     max=round(float(d_med.max()), 2), argmax_s=round(float(ts[d_med.argmax()]))),
               step=dict(median=round(float(np.median(d_step[1:])), 2), max=round(float(d_step.max()), 2)),
               jumps=big[:50],
               lum=dict(first=round(float(lum[0]), 1), median=round(float(np.median(lum)), 1), last=round(float(lum[-1]), 1),
                        min=round(float(lum.min()), 1), max=round(float(lum.max()), 1)),
               moving_share_std_gt6=round(moving, 3),
               series=[[round(float(t)), round(float(a), 2), round(float(b), 2), round(float(l), 1)]
                       for t, a, b, l in zip(ts, d_med, d_step, lum)])
    json.dump(res, open(dst, 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'series'}, indent=1))


if __name__ == '__main__':
    main()
