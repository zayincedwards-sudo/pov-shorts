"""Free: check one Veo clip against the still: start/end distance (must return to the still), how much moves,
and a contact sheet + motion map for review by eye.

  python tools/clip_check.py <episode_dir> <N>
"""
import subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

ep, n = sys.argv[1], int(sys.argv[2])
c = f'{ep}/clips/clip_{n:02d}.mp4'
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', c, '-vf', 'scale=320:180', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
F = np.frombuffer(raw, np.uint8).reshape(-1, 180, 320, 3).astype(np.float32)
S = np.asarray(Image.open(f'{ep}/still.png').convert('RGB').resize((320, 180))).astype(np.float32)
d = np.abs(F - S).mean((1, 2, 3))
std = F.mean(3).std(0)
# camera drift check: distance of a static region (wall, top-left) from the still over time
wall = np.abs(F[:, 10:60, 60:110] - S[10:60, 60:110]).mean((1, 2, 3))
print(f'clip {n}: frames {len(F)} | to still: first {d[0]:.2f} last {d[-1]:.2f} max {d.max():.2f} | moving std>4 {(std > 4).mean():.3f} std>10 {(std > 10).mean():.3f} | wall drift max {wall.max():.2f}')
Image.fromarray(np.clip(std / np.percentile(std, 99.5) * 255, 0, 255).astype(np.uint8)).resize((960, 540)).save(f'{ep}/clips/clip_{n:02d}_motion.png')
idx = np.linspace(0, len(F) - 1, 8).astype(int)
sheet = Image.new('RGB', (320 * 4, 180 * 2))
for k, i in enumerate(idx):
    im = Image.fromarray(F[i].astype(np.uint8)); ImageDraw.Draw(im).text((4, 4), f'{i / 24:.1f}s', fill=(255, 255, 0))
    sheet.paste(im, ((k % 4) * 320, (k // 4) * 180))
sheet.save(f'{ep}/clips/clip_{n:02d}_sheet.jpg')
