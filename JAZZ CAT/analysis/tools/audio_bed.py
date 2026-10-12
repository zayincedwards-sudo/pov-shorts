"""Read an ambience soundtrack: loudness over time, track boundaries, repeats, the rain layer and the music's tone.

  python audio_bed.py <audio> <out_json>

- level: RMS in dB every 0.5 s; dips of >= 6 dB below the local median mark track changes (gaps between songs)
- repeats: chroma self-similarity (2 s frames) finds stretches of music that come back later (a looped bed or a
  re-used song) and the lag they come back at
- rain: energy above 6 kHz in the quietest 5% of moments = the rain bed under the music; its share of the full mix
- tone: spectral roll-off (95%) and centroid, low and high band shares (an "old record in another room" reads as a
  low roll-off and a thin low end); stereo width from the original file
- tempo per segment between boundaries
Free; numpy, scipy, librosa only.
"""
import json, subprocess, sys
import numpy as np
import librosa

SR = 22050


def load(path, mono=True):
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-ac', '1' if mono else '2', '-ar', str(SR), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    return x if mono else x.reshape(-1, 2)


def main():
    src, dst = sys.argv[1:3]
    st = load(src, mono=False); y = st.mean(1)
    dur = len(y) / SR
    hop = SR // 2
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9)
    t = np.arange(len(db)) * 0.5
    # boundaries: dips well below a 60 s rolling median
    k = 120
    med = np.array([np.median(db[max(0, i - k // 2):i + k // 2]) for i in range(len(db))])
    dip = db < med - 6
    bounds = []
    i = 0
    while i < len(dip):
        if dip[i]:
            j = i
            while j < len(dip) and dip[j]:
                j += 1
            bounds.append(dict(start=round(t[i], 1), end=round(t[min(j, len(t) - 1)], 1), depth_db=round(float((med[i:j] - db[i:j]).max()), 1)))
            i = j
        else:
            i += 1
    edges = [0.0] + [round((b['start'] + b['end']) / 2, 1) for b in bounds] + [round(dur, 1)]
    segs = []
    for a, b in zip(edges[:-1], edges[1:]):
        if b - a < 20:
            continue
        seg = y[int(a * SR):int(b * SR)]
        tempo = float(np.atleast_1d(librosa.beat.beat_track(y=seg, sr=SR)[0])[0])
        segs.append(dict(start=a, end=b, length=round(b - a, 1), tempo=round(tempo, 1),
                         level_db=round(float(np.median(db[int(a * 2):int(b * 2)])), 1)))
    # repeats via chroma self-similarity at 2 s resolution
    chop = SR * 2
    chroma = librosa.feature.chroma_stft(y=y, sr=SR, hop_length=chop, n_fft=8192)
    C = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    S = C.T @ C
    n = S.shape[0]
    lag_score = []
    for L in range(15, n - 15):                         # lags 30 s and up
        dg = np.diag(S, L)
        w = 15                                          # 30 s window of sustained similarity
        if len(dg) < w:
            break
        run = np.convolve(dg, np.ones(w) / w, mode='valid')
        lag_score.append((float(run.max()), L * 2, int(run.argmax()) * 2))
    lag_score.sort(reverse=True)
    base = float(np.median([s for s, _, _ in lag_score])) if lag_score else 0
    # spectrum
    Sx = np.abs(librosa.stft(y[: SR * 600], n_fft=4096, hop_length=4096)) ** 2
    f = librosa.fft_frequencies(sr=SR, n_fft=4096)
    tot = Sx.sum(0) + 1e-12
    hi = Sx[f > 6000].sum(0) / tot
    lo = Sx[f < 150].sum(0) / tot
    q = np.argsort(tot)[: max(1, len(tot) // 20)]
    roll = librosa.feature.spectral_rolloff(S=Sx, sr=SR, roll_percent=0.95)[0]
    cent = librosa.feature.spectral_centroid(S=Sx, sr=SR)[0]
    L_, R_ = st[:, 0], st[:, 1]
    side = np.sqrt(np.mean(((L_ - R_) / 2) ** 2)); mid = np.sqrt(np.mean(((L_ + R_) / 2) ** 2))
    res = dict(file=src, duration_s=round(dur, 1),
               level=dict(median_db=round(float(np.median(db)), 1), p5=round(float(np.percentile(db, 5)), 1),
                          p95=round(float(np.percentile(db, 95)), 1)),
               boundaries=bounds, segments=segs,
               repeats=dict(baseline=round(base, 3),
                            top=[dict(score=round(s, 3), lag_s=l, at_s=a) for s, l, a in lag_score[:10]]),
               spectrum_first10min=dict(rolloff95_hz=round(float(np.median(roll))), centroid_hz=round(float(np.median(cent))),
                                        share_above_6k=round(float(np.median(hi)), 4),
                                        share_above_6k_in_quietest5pct=round(float(np.median(hi[q])), 4),
                                        share_below_150=round(float(np.median(lo)), 4)),
               stereo=dict(side_to_mid_db=round(float(20 * np.log10(side / mid + 1e-9)), 1)),
               level_series=[[float(a), round(float(b), 1)] for a, b in zip(t[::4], db[::4])])
    json.dump(res, open(dst, 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'level_series'}, indent=1))


if __name__ == '__main__':
    main()
