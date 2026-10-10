"""Free: grade a still toward the reference's dusk look (darker, warmer, richer) and size it for Veo.

  python tools/grade.py <in.png> <out.png> [--gamma 1.35] [--sat 1.25] [--warm 1.08] [--size 1280x720]
Reference targets (ANALYSIS.md, frame v_01): mean luminance 53, near-black 40%, saturation 155, mean RGB 77/51/31.
"""
import argparse
import numpy as np
from PIL import Image, ImageEnhance

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--gamma', type=float, default=1.35); ap.add_argument('--sat', type=float, default=1.25)
ap.add_argument('--warm', type=float, default=1.08); ap.add_argument('--size', default='1280x720')
a = ap.parse_args()
w, h = map(int, a.size.split('x'))
im = Image.open(a.src).convert('RGB').resize((w, h), Image.LANCZOS)
x = np.asarray(im).astype(np.float32) / 255
x = x ** a.gamma
x[..., 0] *= a.warm; x[..., 2] /= a.warm
im = Image.fromarray((np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8))
im = ImageEnhance.Color(im).enhance(a.sat)
im.save(a.dst)
v = np.asarray(im.resize((640, 358))).astype(float); L = v.mean(2)
hsv = np.asarray(im.resize((640, 358)).convert('HSV')).astype(float)
print(f'{a.dst}: lum {L.mean():.1f} near-black {(L < 40).mean() * 100:.1f}% sat {hsv[..., 1].mean():.1f} RGB {v.reshape(-1, 3).mean(0).round(0)}')
