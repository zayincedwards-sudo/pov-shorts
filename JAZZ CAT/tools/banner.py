"""Free: cut the channel banner (2560x1440) from a still so the chosen point sits in YouTube's always-visible
centre strip (1546x423), plus a preview of that strip.

  python tools/banner.py <still.png> <out_dir> --cx 800 --cy 455 [--scale 2.08]
cx/cy are in the still's own pixels. Grading matches tools/grade.py defaults.
"""
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out')
ap.add_argument('--cx', type=float, required=True); ap.add_argument('--cy', type=float, required=True)
ap.add_argument('--scale', type=float, default=2.08)
a = ap.parse_args()
im = Image.open(a.src).convert('RGB')
x = np.asarray(im).astype(np.float32) / 255; x = x ** 1.25; x[..., 0] *= 1.04; x[..., 2] /= 1.04
im = Image.fromarray((np.clip(x, 0, 1) * 255 + .5).astype(np.uint8))
W, H = 2560, 1440
big = im.resize((round(im.width * a.scale), round(im.height * a.scale)), Image.LANCZOS)
left = int(round(a.cx * a.scale - W / 2)); top = int(round(a.cy * a.scale - H / 2))
left = max(0, min(left, big.width - W)); top = max(0, min(top, big.height - H))
if big.width < W or big.height < H:
    raise SystemExit('scale too small to fill 2560x1440')
ban = big.crop((left, top, left + W, top + H))
ban.save(f'{a.out}/banner_2560x1440.png')
ban.crop(((W - 1546) // 2, (H - 423) // 2, (W + 1546) // 2, (H + 423) // 2)).save(f'{a.out}/banner_safe_area_preview.png')
print('banner crop at', left, top, 'of', big.size)
