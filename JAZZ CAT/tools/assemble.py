"""Free: build the finished ambience video from the loop clips, the music pieces and the rain loop.

  python tools/assemble.py <episode_dir> [--minutes 265] [--music-dir <dir>] [--rain build/rain_354.wav]

Picture (rules from ANALYSIS.md):
  - clips/clip_NN.mp4 joined in order; each clip's last frame is dropped because it equals the next clip's first
    frame (both are the still), so the joins have no held frame. Veo's own audio is discarded.
  - scaled to 1920x1080, encoded ONCE to loop.mp4 (closed GOP), then repeated by stream copy for the runtime.
  - GATE joins: the frame difference across every join must sit inside the clip's own frame-to-frame range.
Sound:
  - music: every audio file in --music-dir (default <episode>/music), in name order, 2 s of silence between pieces,
    low-passed to about 1.2 kHz ("jazz from another room": 99% of the reference's music energy is under 1,184 Hz),
    then looped. The reference's bed is about 10 min; ours is whatever the pieces add up to.
  - rain: the seamless loop from tools/rain.py, looped independently, 17 dB under the music.
  - loudness: two-pass loudnorm to -14 LUFS integrated, true peak -1.5 dBTP (the reference clips at +0.9; we don't).
Outputs <episode>/render/: loop.mp4, bed.m4a, final.mp4, joins.json.
"""
import argparse, glob, json, os, subprocess
import numpy as np


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit(f'FAILED: {" ".join(cmd)[:300]}\n{r.stderr[-1500:]}')
    return r


def probe(p, entry):
    return run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', entry, '-of', 'csv=p=0', p]).stdout.strip()


def frames_gray(p, w=160, h=90):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-vf', f'scale={w}:{h},format=gray', '-f', 'rawvideo', '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def picture(ep, out):
    clips = sorted(glob.glob(os.path.join(ep, 'clips', 'clip_*.mp4')))
    if not clips:
        raise SystemExit('no clips in ' + os.path.join(ep, 'clips'))
    fps = probe(clips[0], 'stream=r_frame_rate'); r = eval(fps)
    D = round(8 / r, 4)                                   # crossfade: 8 frames (1/3 s at 24 fps) at every join
    durs = [float(probe(c, 'format=duration')) for c in clips]
    # Chain clip1..clipN, then clip1 again, with a crossfade at every join; then cut [D, D + L) so the loop's own end
    # crossfades into its start too (the wrap-around is just another join).
    seq = list(range(len(clips))) + [0]
    inputs = sum((['-i', c] for c in clips), [])
    chains = [f'[{i}:v]scale=1920:1080:flags=lanczos,setsar=1,fps={fps}' + (',split=2[s0a][s0b]' if i == 0 else f'[s{i}a]') for i in range(len(clips))]
    labels = [f's{i}a' for i in range(len(clips))] + ['s0b']
    off, prev, xf = 0.0, labels[0], []
    for k in range(1, len(seq)):
        off += durs[seq[k - 1]] - D
        nxt = f'x{k}'
        xf.append(f'[{prev}][{labels[k]}]xfade=transition=fade:duration={D}:offset={off:.4f}[{nxt}]')
        prev = nxt
    L = sum(durs) - len(clips) * D
    graph = ';'.join(chains + xf) + f';[{prev}]trim=start={D}:duration={L:.4f},setpts=PTS-STARTPTS[v]'
    run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', '[v]', '-an',
         '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-g', str(int(round(r)) * 2),
         '-flags', '+cgop', '-movflags', '+faststart', out])
    # GATE: no frame step at any join (or the wrap) may exceed what the clips do on their own
    F = frames_gray(out); n = len(F)
    step = np.abs(np.diff(F, axis=0)).mean((1, 2))
    joins, t = [], 0.0
    for k in range(1, len(clips)):
        t += durs[k - 1] - D
        joins.append(int(round((t - D) * r)))             # crossfade k starts here in the trimmed loop
    win = set(j + d for j in joins for d in range(-2, int(round(D * r)) + 3))
    normal = np.array([s for i, s in enumerate(step) if i not in win])
    lim = float(np.percentile(normal, 99)) * 1.5 + 0.5
    wrap = float(np.abs(F[-1] - F[0]).mean())
    res = dict(frames=n, fps=fps, seconds=round(n / r, 3), crossfade_s=D, step_p50=round(float(np.median(step)), 3),
               limit=round(lim, 3), wrap_diff=round(wrap, 3),
               joins=[dict(frame=j, max_step=round(float(step[max(0, j - 2):j + int(round(D * r)) + 2].max()), 3)) for j in joins])
    res['pass'] = all(x['max_step'] <= lim for x in res['joins']) and wrap <= lim
    return res


def bed(music_dir, tmp):
    pieces = sorted(p for p in glob.glob(os.path.join(music_dir, '*')) if p.lower().endswith(('.mp3', '.wav', '.m4a', '.flac', '.ogg')))
    if not pieces:
        raise SystemExit('no music in ' + music_dir)
    lst = os.path.join(tmp, 'music_list.txt')
    gap = os.path.join(tmp, 'gap.wav')
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', '2', gap])
    norm = []
    for i, p in enumerate(pieces):
        q = os.path.join(tmp, f'piece_{i:02d}.wav')
        run(['ffmpeg', '-v', 'error', '-y', '-i', p, '-ar', '44100', '-ac', '2', q]); norm += [q, gap]
    open(lst, 'w').write(''.join(f"file '{os.path.abspath(q)}'\n" for q in norm))
    music = os.path.join(tmp, 'music_loop.wav')
    # muffle: 2 x 2-pole low-pass ~1.2 kHz plus a little low-mid warmth, as heard through a wall
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
         '-af', 'lowpass=f=1300:p=2,lowpass=f=1300:p=2,equalizer=f=180:t=q:w=1:g=2', music])
    return music


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep'); ap.add_argument('--minutes', type=float, default=265)
    ap.add_argument('--music-dir'); ap.add_argument('--rain', default=os.path.join(os.path.dirname(__file__), '..', 'build', 'rain_354.wav'))
    ap.add_argument('--rain-db', type=float, default=-17.0)
    ap.add_argument('--deliver-crf', type=int, default=30, help='re-encode the loop for delivery; 30 = about 0.8 Mbps, under the 2 GiB GitHub cap at 4.5 h')
    ap.add_argument('--abr', default='128k')
    a = ap.parse_args()
    rd = os.path.join(a.ep, 'render'); tmp = os.path.join(rd, 'tmp'); os.makedirs(tmp, exist_ok=True)
    loop = os.path.join(rd, 'loop.mp4')
    j = picture(a.ep, loop)
    json.dump(j, open(os.path.join(rd, 'joins.json'), 'w'), indent=1)
    print('GATE joins:', 'PASS' if j['pass'] else 'FAIL', json.dumps({k: v for k, v in j.items() if k != 'joins'}), [x['max_step'] for x in j['joins']])
    if not j['pass']:
        raise SystemExit('join gate failed: redo the clip on either side of the worst join (veo_clips.py --redo N)')
    secs = a.minutes * 60
    music = bed(a.music_dir or os.path.join(a.ep, 'music'), tmp)
    # music and rain loop independently; measure music loudness to place the rain 17 dB under it
    mix = os.path.join(tmp, 'mix.wav')
    # level match: loudness of music vs rain, computed on the source loops
    def lufs(p):
        r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', p, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
        return float(r.rsplit('I:', 1)[1].split('LUFS')[0])
    gain = (lufs(music) + a.rain_db) - lufs(a.rain)
    run(['ffmpeg', '-v', 'error', '-y', '-stream_loop', '-1', '-i', music, '-stream_loop', '-1', '-i', a.rain,
         '-filter_complex', f'[0:a]atrim=0:{secs},asetpts=N/SR/TB[m];[1:a]atrim=0:{secs},asetpts=N/SR/TB,volume={gain:.2f}dB[r];[m][r]amix=inputs=2:normalize=0:duration=first[a]',
         '-map', '[a]', '-t', str(secs), mix])
    # two-pass loudnorm to -14 LUFS / -1.5 dBTP
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', mix, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=7:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
    bedf = os.path.join(rd, 'bed.m4a')
    run(['ffmpeg', '-v', 'error', '-y', '-i', mix, '-af',
         f"loudnorm=I=-14:TP=-1.5:LRA=7:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000",
         '-c:a', 'aac', '-b:a', a.abr, bedf])
    # picture: repeat the encoded loop by stream copy
    dl = os.path.join(rd, 'loop_deliver.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-i', loop, '-c:v', 'libx264', '-preset', 'slow', '-tune', 'animation', '-crf', str(a.deliver_crf),
         '-pix_fmt', 'yuv420p', '-g', '240', '-flags', '+cgop', '-an', dl])
    loop = dl
    reps = int(np.ceil(secs / j['seconds'])) + 1
    lst = os.path.join(tmp, 'loop_list.txt')
    open(lst, 'w').write(''.join(f"file '{os.path.abspath(loop)}'\n" for _ in range(reps)))
    final = os.path.join(rd, 'final.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-i', bedf, '-map', '0:v', '-map', '1:a',
         '-c', 'copy', '-t', str(secs), '-movflags', '+faststart', final])
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', final, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    summ = out[out.rindex('Summary:'):]
    print(f'final: {final}  ({secs / 60:.1f} min, picture loop {j["seconds"]} s, rain gain {gain:+.1f} dB)')
    print(' '.join(summ.split())[:300])


if __name__ == '__main__':
    main()
