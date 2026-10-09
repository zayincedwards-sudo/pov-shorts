"""Teardown kit: scrape, measure and compare a reference YouTube channel. Free: yt-dlp, ffmpeg, local Whisper, numpy,
Pillow. No paid API is called anywhere in this file.

Run from the project root with the Bash tool, typing the full path each time (shell variables do not survive between
Bash calls): python ~/.claude/skills/channel-pipeline/scripts/teardown.py <command> … Everything is written under --out
(default analysis/). Long videos: give the Bash call a 600000 ms timeout.

  python teardown.py scrape <channel_url|@handle> [--limit N] [--shorts] [--comments K]
        flat list (every upload, approximate dates) -> analysis/channel_flat.json; per-video info + thumbnail for
        --limit N videos, half from the top by views and half from the bottom (hits AND flops) ->
        analysis/yt/<id>.info.json, analysis/thumbs/<views>_<id>.jpg; failures -> analysis/missing_ids.txt (rerun)
  python teardown.py table                      analysis/channel_table.json + .csv over EVERY upload: views/day, outlier
                                                ratio (long-form and Shorts against their own medians), title traits
  python teardown.py subs [--top N | --ids a,b]  auto/manual English subs (json3) -> analysis/subs/ (for wpm, openers)
  python teardown.py download <id|url> [--low]   video -> analysis/yt/<id>.mp4 (--low = 360p, for flops)
  python teardown.py transcribe <media>… [--model small.en]
        faster-whisper word timings -> analysis/transcripts/<name>.json (words) + .txt (timestamped lines)
  python teardown.py script <file>…              script stats side by side: transcript .json, script.md or .txt
  python teardown.py cuts <video>…               hard/soft cuts per minute, shot lengths, holds -> analysis/cuts/;
                                                contact sheets -> analysis/frames/ (about a minute per 10 min of 1080p)
  python teardown.py thumbs                      thumbnail stats + sheets ranked by views at 480 px and 210 px

Measure the reference and our own draft with the same command, side by side. Never use our own episode as the
yardstick (house rule 12).
"""
import csv, datetime, glob, json, os, re, shutil, statistics as st, subprocess, sys

OUT = 'analysis'


def out(*parts):
    p = os.path.join(OUT, *parts)
    os.makedirs(os.path.dirname(p) if os.path.splitext(p)[1] else p, exist_ok=True)
    return p


def ytdlp(args, timeout=None):
    """yt-dlp through Python with UTF-8 (a shell redirect on Windows writes the console codepage and mangles titles)."""
    return subprocess.run(['yt-dlp', '--no-warnings'] + args, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout)


def watch_url(vid):
    return vid if vid.startswith('http') else f'https://www.youtube.com/watch?v={vid}'     # ids may start with "-"


def channel_root(url):
    url = url.strip().rstrip('/')
    if not url.startswith('http'):                       # "@handle" or a bare handle
        url = 'https://www.youtube.com/' + (url if url.startswith('@') else '@' + url)
    return re.sub(r'/(videos|shorts|streams|featured)$', '', url)


def _sample(entries, limit):
    """Both ends of the channel: half the slots to the most-viewed uploads and half to the least-viewed, so the table
    always holds flops to compare the hits against (a top-N sample has none)."""
    if not limit or limit >= len(entries): return entries
    top = entries[:(limit + 1) // 2]; bottom = entries[len(entries) - limit // 2:]
    return top + [e for e in bottom if e not in top]


# ---------------------------------------------------------------- scrape
def cmd_scrape(url, limit=None, shorts=False, comments=0):
    root = channel_root(url)
    entries = []
    for tab in ['videos'] + (['shorts'] if shorts else []):
        r = ytdlp(['--flat-playlist', '--dump-single-json', '--extractor-args', 'youtubetab:approximate_date',
                   f'{root}/{tab}'], timeout=600)
        if r.returncode or not r.stdout.strip():
            print(f'flat list failed for /{tab}: {r.stderr.strip()[-300:]}'); continue
        j = json.loads(r.stdout)
        for e in j.get('entries') or []:
            e['_tab'] = tab; entries.append(e)
        json.dump(j, open(out(f'channel_flat_{tab}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not entries: raise SystemExit('no videos found')
    json.dump(entries, open(out('channel_flat.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    entries.sort(key=lambda e: -(e.get('view_count') or 0))
    print(f'{len(entries)} uploads listed; top by views:')
    for e in entries[:10]: print(f"  {e.get('view_count') or 0:>12,}  {e.get('id')}  {str(e.get('title'))[:70]}")
    todo = [e['id'] for e in _sample(entries, limit) if e.get('id')]
    for attempt in (1, 2):
        need = [v for v in todo if not os.path.exists(out('yt', f'{v}.info.json'))]
        if not need: break
        lst = out('ids_batch.txt'); open(lst, 'w', encoding='utf-8').write('\n'.join(watch_url(v) for v in need))
        args = ['--skip-download', '--write-info-json', '--write-thumbnail', '--convert-thumbnails', 'jpg',
                '--ignore-errors', '--sleep-requests', '0.7', '-o', out('yt', '%(id)s.%(ext)s'), '-a', lst]
        print(f'pass {attempt}: fetching info for {len(need)} videos…', flush=True)
        ytdlp(args, timeout=60 * 60)
    if comments:
        top = [v for v in todo[:comments] if os.path.exists(out('yt', f'{v}.info.json'))]
        for v in top:
            ytdlp(['--skip-download', '--write-info-json', '--write-comments', '--extractor-args',
                   'youtube:max_comments=120,all,120,20;comment_sort=top', '--sleep-requests', '1',
                   '-o', out('comments', '%(id)s.%(ext)s'), watch_url(v)], timeout=900)
        print(f'comments for {len(top)} top videos -> {out("comments")}')
    missing = [v for v in todo if not os.path.exists(out('yt', f'{v}.info.json'))]
    open(out('missing_ids.txt'), 'w', encoding='utf-8').write('\n'.join(missing))
    for v in todo:                                       # thumbnails named by views, so a directory listing ranks them
        ip, tp = out('yt', f'{v}.info.json'), out('yt', f'{v}.jpg')
        if os.path.exists(ip) and os.path.exists(tp):
            views = json.load(open(ip, encoding='utf-8')).get('view_count') or 0
            shutil.copy(tp, out('thumbs', f'{views:010d}_{v}.jpg'))
    print(f'info for {len(todo) - len(missing)} of {len(todo)}; missing {len(missing)} (see missing_ids.txt, rerun to fill)')


# ---------------------------------------------------------------- table
def cmd_table():
    """Every upload in the flat list (so medians and outlier ratios cover the whole channel), enriched with the
    per-video info JSON where it was fetched (likes, exact dates, chapters, heatmap). Long videos and Shorts get
    separate medians."""
    today = datetime.date.today(); rows = []
    flat = json.load(open(out('channel_flat.json'), encoding='utf-8')) if os.path.exists(out('channel_flat.json')) else []
    info = {}
    for p in glob.glob(out('yt', '*.info.json')):
        j = json.load(open(p, encoding='utf-8')); info[j.get('id')] = j
    for e in flat or [{'id': k, '_tab': 'videos'} for k in info]:
        j = info.get(e.get('id'), {})
        d = j.get('upload_date') or e.get('upload_date')
        if not d and e.get('timestamp'): d = datetime.datetime.fromtimestamp(e['timestamp'], datetime.timezone.utc).strftime('%Y%m%d')
        age = max(1, (today - datetime.date(int(d[:4]), int(d[4:6]), int(d[6:]))).days) if d else None
        t = j.get('title') or e.get('title') or ''; views = j.get('view_count') or e.get('view_count') or 0
        dur = j.get('duration') or e.get('duration')
        rows.append({'id': e.get('id'), 'title': t, 'tab': e.get('_tab', 'videos'), 'upload_date': d, 'age_days': age,
                     'date_exact': bool(j.get('upload_date')), 'duration': dur, 'views': views,
                     'likes': j.get('like_count'), 'comments': j.get('comment_count'),
                     'views_per_day': round(views / age, 1) if age else None,
                     'chapters': len(j.get('chapters') or []), 'tags': len(j.get('tags') or []),
                     'heatmap': bool(j.get('heatmap')), 'fetched': bool(j),
                     'short': e.get('_tab') == 'shorts' or (dur or 999) <= 180,
                     'title_question': '?' in t, 'title_ellipsis': ('...' in t) or ('…' in t),
                     'title_words': len(t.split()), 'title_caps_words': sum(1 for w in t.split() if len(w) > 2 and w.isupper()),
                     'title_digits': bool(re.search(r'\d', t))})
    if not rows: raise SystemExit('nothing to tabulate: run scrape first')
    for group in (False, True):                          # long-form and Shorts are compared within their own group
        g = [r for r in rows if r['short'] == group]
        med = (st.median(r['views'] for r in g) or 1) if g else 1
        for r in g: r['outlier'] = round(r['views'] / med, 2)
    for r in rows: r['like_pct'] = round(100 * r['likes'] / r['views'], 2) if r['likes'] and r['views'] else None
    rows.sort(key=lambda r: -r['views'])
    json.dump(rows, open(out('channel_table.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(out('channel_table.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    fmt = lambda r: (f"  {r['views']:>12,} {r['outlier']:>7.2f}x {str(r['views_per_day']):>9}/d {(r['duration'] or 0) / 60:5.1f}m "
                     f"{'' if r['fetched'] else '(not fetched) '}{r['id']}  {r['title'][:60]}")
    for label, group in (('long-form', False), ('Shorts', True)):
        g = [r for r in rows if r['short'] == group]
        if not g: continue
        tot = sum(r['views'] for r in g) or 1
        print(f'{label}: {len(g)} videos, median views {st.median(r["views"] for r in g):,.0f}, top-1 share '
              f'{100 * g[0]["views"] / tot:.0f}%, top-3 share {100 * sum(r["views"] for r in g[:3]) / tot:.0f}%')
        print('  top 15 (views, outlier vs median, views/day, minutes):'); [print(fmt(r)) for r in g[:15]]
        if len(g) > 15: print('  bottom 8:'); [print(fmt(r)) for r in g[max(15, len(g) - 8):]]
    print('views/day uses approximate dates where a video was not fetched (date_exact = false)')


# ---------------------------------------------------------------- subs
def json3_words(path):
    """json3 subtitle events -> [(t_seconds, word)] (auto-captions are unpunctuated: use them for pace, not sentences)."""
    j = json.load(open(path, encoding='utf-8')); words = []
    for ev in j.get('events') or []:
        t0 = (ev.get('tStartMs') or 0) / 1000
        for sg in ev.get('segs') or []:
            for w in (sg.get('utf8') or '').split():
                words.append((t0 + (sg.get('tOffsetMs') or 0) / 1000, w))
    return words


def cmd_subs(top=None, ids=None):
    if not ids:
        rows = json.load(open(out('channel_table.json'), encoding='utf-8'))
        ids = [r['id'] for r in rows[:top or len(rows)]]
    for v in ids:
        if glob.glob(out('subs', f'{v}*.json3')): continue
        r = ytdlp(['--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', 'en',
                   '--sub-format', 'json3', '--sleep-requests', '3', '--sleep-subtitles', '4',
                   '-o', out('subs', '%(id)s.%(ext)s'), watch_url(v)], timeout=600)
        if '429' in r.stderr:
            print('subtitle endpoint is rate-limiting (HTTP 429). Retry in an hour, or download the videos and use '
                  '`transcribe` (Whisper) instead.'); break
    print('video          words   wpm  first words')
    for v in ids:
        fs = sorted(glob.glob(out('subs', f'{v}*.json3')))
        if not fs: print(f'{v:12}  (no subs)'); continue
        ws = json3_words(fs[0])
        if len(ws) < 20: continue
        dur = ws[-1][0] - ws[0][0]
        print(f'{v:12} {len(ws):6} {len(ws) / dur * 60 if dur else 0:5.0f}  {" ".join(w for _, w in ws[:14])[:80]}')


# ---------------------------------------------------------------- download
def cmd_download(target, low=False):
    fmt = 'bv*[height<=360]+ba/b[height<=360]' if low else 'bv*[height<=1080]+ba/b[height<=1080]'
    r = ytdlp(['-f', fmt, '--merge-output-format', 'mp4', '-o', out('yt', '%(id)s.%(ext)s'), watch_url(target)], timeout=3600)
    print('ok' if r.returncode == 0 else 'FAILED: ' + r.stderr.strip()[-300:])


# ---------------------------------------------------------------- transcribe
def cmd_transcribe(paths, model_name='small.en'):
    from faster_whisper import WhisperModel
    try: model = WhisperModel(model_name, device='cpu', compute_type='int8', local_files_only=True)
    except Exception:                                    # not cached yet: try the download (fails where HuggingFace is blocked)
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        segs, info = model.transcribe(p, word_timestamps=True, beam_size=5, vad_filter=True, language='en')
        words, lines = [], []
        for s in segs:
            lines.append(f'[{int(s.start // 60)}:{int(s.start % 60):02d}] {s.text.strip()}')
            words += [{'w': w.word.strip(), 's': round(w.start, 2), 'e': round(w.end, 2)} for w in (s.words or [])]
        json.dump({'source': p, 'duration': round(info.duration, 2), 'words': words},
                  open(out('transcripts', stem + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        open(out('transcripts', stem + '.txt'), 'w', encoding='utf-8', newline='\r\n').write('\n'.join(lines) + '\n')
        print(f'{stem}: {len(words)} words, {info.duration / 60:.1f} min -> {out("transcripts", stem + ".json")}')


# ---------------------------------------------------------------- script stats
# real contractions only: n't / 're / 've / 'll / 'd / 'm on any word, and 's only after words where it means "is" or
# "has" (it's, that's, there's, here's, what's, who's, he's, she's, let's…), so possessives ("Fabergé's") don't count
CONTR = re.compile(r"\b(\w+n't|\w+'(re|ve|ll|d|m)|(it|that|there|here|what|who|he|she|let|where|how|everyone|nobody|"
                   r"somebody|someone|everything|nothing|something|this)'s)\b", re.I)
UNCONTR = re.compile(r"\b(it is|that is|there is|here is|is not|are not|do not|does not|did not|cannot|will not|would not|could not|should not|has not|have not|they are|we are|you are|I am|what is|who is)\b", re.I)
NUMWORD = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)\b", re.I)
DIGITS = re.compile(r"\$?\b\d[\d,.]*%?")
MONEY = re.compile(r"\$\s?\d|\bdollars?\b|\bmillion\b|\bbillion\b|\bworth\b|\bprice\b|\bcost", re.I)
YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def _syllables(w):
    w = re.sub(r'[^a-z]', '', w.lower())
    if not w: return 0
    n = len(re.findall(r'[aeiouy]+', w)) - (1 if w.endswith('e') and not w.endswith('le') else 0)
    return max(1, n)


def _load_text(p):
    """-> (text, words_with_times or None)"""
    if p.endswith('.json'):
        j = json.load(open(p, encoding='utf-8')); ws = j['words'] if isinstance(j, dict) else j
        return ' '.join(w['w'] for w in ws), ws
    t = open(p, encoding='utf-8').read()
    if p.endswith('.md'):                                # our script format: narration only
        keep = []
        for line in t.split('\n'):
            if line.startswith('#') or not line.strip(): continue
            line = re.sub(r'\[shot:[^\]]*\]', '', line); line = re.sub(r'\{\w+:[^}]*\}', '', line); keep.append(line.strip())
        t = ' '.join(keep)
    t = re.sub(r'\[\d+:\d\d\]', '', t)                    # timestamps in our .txt transcripts
    return re.sub(r'\s+', ' ', t).strip(), None


def stats(p):
    text, ws = _load_text(p)
    text = text.replace('’', "'").replace('‘', "'")      # curly apostrophes count as contractions too
    words = text.split(); n = max(1, len(words))
    sents = [s for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    sl = [len(s.split()) for s in sents] or [0]
    per100 = lambda k: round(100 * k / n, 2)
    r = {'words': len(words), 'sentences': len(sents), 'sent_median': st.median(sl), 'sent_mean': round(st.mean(sl), 1),
         'sent_p90': sorted(sl)[int(0.9 * (len(sl) - 1))], 'pct_sent_ge20': round(100 * sum(x >= 20 for x in sl) / len(sl)),
         'pct_sent_le5': round(100 * sum(x <= 5 for x in sl) / len(sl)),
         'questions': sum(1 for s in sents if s.rstrip().endswith('?')),
         'you_per100': per100(len(re.findall(r"\byou(r|'re|'ll|'ve)?\b", text, re.I))),
         'i_we_per100': per100(len(re.findall(r"\b(I|I'm|I've|I'd|I'll|we|we're|we've|my|our|us)\b", text, re.I))),
         'contractions_per100': per100(len(CONTR.findall(text))), 'uncontracted_per100': per100(len(UNCONTR.findall(text))),
         'numbers_per100': per100(len(DIGITS.findall(text)) + len(NUMWORD.findall(text))),
         'number_words_per100': per100(len(NUMWORD.findall(text))), 'money_per100': per100(len(MONEY.findall(text))),
         'years_cited': len(YEAR.findall(text)),
         'pct_open_and_but_so': round(100 * sum(1 for s in sents if re.match(r"(And|But|So)\b", s)) / max(1, len(sents))),
         'colons_dashes': len(re.findall(r':|\s[-–—]\s|—', text)),
         'fk_grade': round(0.39 * n / max(1, len(sents)) + 11.8 * sum(_syllables(w) for w in words) / n - 15.59, 1)}
    if ws:
        dur = ws[-1]['e'] - ws[0]['s']
        gaps = [b['s'] - a['e'] for a, b in zip(ws, ws[1:]) if b['s'] - a['e'] > 0.25]
        r.update({'minutes': round(dur / 60, 2), 'wpm_gross': round(n / dur * 60) if dur else None,
                  'wpm_speech': round(n / max(1, dur - sum(gaps)) * 60), 'pauses_per_min': round(len(gaps) / dur * 60, 1) if dur else None,
                  'median_pause': round(st.median(gaps), 2) if gaps else 0})
    return r


def cmd_script(paths):
    cols = [(os.path.basename(p)[:22], stats(p)) for p in paths]
    keys = list(dict.fromkeys(k for _, s in cols for k in s))
    print(f"{'metric':22}" + ''.join(f'{name:>24}' for name, _ in cols))
    for k in keys: print(f'{k:22}' + ''.join(f"{str(s.get(k, '')):>24}" for _, s in cols))


# ---------------------------------------------------------------- cuts
def _duration(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip())


def cmd_cuts(paths, hard=0.25, soft=0.10):
    from PIL import Image, ImageDraw
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]; dur = _duration(p)
        r = subprocess.run(['ffmpeg', '-v', 'info', '-i', p, '-an', '-vf',
                            f"scale=320:-2,select='gt(scene,{soft})',metadata=print", '-f', 'null', '-'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        times, scores = [], []
        for line in r.stderr.splitlines():
            m = re.search(r'pts_time:([\d.]+)', line)
            if m: times.append(float(m.group(1))); continue
            m = re.search(r'lavfi\.scene_score=([\d.]+)', line)
            if m and len(scores) < len(times): scores.append(float(m.group(1)))
        res = {'file': p, 'minutes': round(dur / 60, 2)}
        for name, th in (('hard', hard), ('soft', soft)):
            cuts = [t for t, s in zip(times, scores) if s > th]
            edges = [0.0] + cuts + [dur]; shots = sorted(b - a for a, b in zip(edges, edges[1:]) if b - a > 0.04)
            res[name] = {'cuts_per_min': round(len(cuts) / dur * 60, 1), 'median_shot': round(st.median(shots), 2),
                         'p10': round(shots[int(0.1 * (len(shots) - 1))], 2), 'p90': round(shots[int(0.9 * (len(shots) - 1))], 2),
                         'holds_over_8s': sum(1 for s in shots if s > 8), 'flashes_under_1s': sum(1 for s in shots if s < 1),
                         'cuts_first_30s': sum(1 for t in cuts if t < 30)}
        json.dump(res, open(out('cuts', stem + '_cuts.json'), 'w', encoding='utf-8'), indent=1)   # ours: tracked in git
        print(json.dumps(res, indent=1))
        tmp = out('frames', '_tmp_' + stem)              # inside the project, never the system temp folder
        shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-vf', 'fps=1/2,scale=320:-2', os.path.join(tmp, '%05d.jpg')])
        frames = sorted(glob.glob(os.path.join(tmp, '*.jpg')))
        for k in range(0, len(frames), 48):              # contact sheets, one frame every 2 s, labelled with PIL
            chunk = frames[k:k + 48]
            with Image.open(chunk[0]) as im0: w, h = im0.size
            cols = 8; rows = (len(chunk) + cols - 1) // cols
            sheet = Image.new('RGB', (cols * w, rows * (h + 14)), (20, 20, 20)); d = ImageDraw.Draw(sheet)
            for i, f in enumerate(chunk):
                t = (k + i) * 2; x, y = (i % cols) * w, (i // cols) * (h + 14)
                with Image.open(f) as im: sheet.paste(im, (x, y + 14))
                d.text((x + 2, y), f'{t // 60}:{t % 60:02d}', fill=(255, 255, 0))
            sheet.save(out('frames', f'{stem}_sheet_{k // 48:02d}.jpg'), quality=80)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f'contact sheets -> {out("frames", stem + "_sheet_NN.jpg")} ({(len(frames) + 47) // 48})')


# ---------------------------------------------------------------- thumbnails
def cmd_thumbs():
    import numpy as np
    from PIL import Image, ImageDraw
    files = sorted(glob.glob(out('thumbs', '*.jpg')), reverse=True)        # names start with zero-padded views
    if not files: raise SystemExit('no thumbnails: run scrape first')
    stats_out = []
    for f in files:
        im = Image.open(f).convert('RGB').resize((320, 180)); a = np.asarray(im).astype(float)
        luma = a @ [0.299, 0.587, 0.114]; hsv = np.asarray(im.convert('HSV')).astype(float)
        q = im.quantize(6); pal = q.getpalette()[:18]; counts = sorted(q.getcolors(), reverse=True)
        dom = [(f'#{pal[3 * i]:02x}{pal[3 * i + 1]:02x}{pal[3 * i + 2]:02x}', round(100 * c / (320 * 180))) for c, i in counts]
        name = os.path.basename(f); views, vid = name.split('_', 1)
        stats_out.append({'id': vid[:-4], 'views': int(views), 'white_pct': round(100 * (a.min(axis=2) > 230).mean()),
                          'black_pct': round(100 * (luma < 30).mean()), 'midtone_pct': round(100 * ((luma > 60) & (luma < 195)).mean()),
                          'mean_luma': round(luma.mean()), 'mean_saturation': round(hsv[..., 1].mean()), 'dominant': dom})
    json.dump(stats_out, open(out('thumb_stats.json'), 'w', encoding='utf-8'), indent=1)
    for width, cols in ((480, 4), (210, 6)):
        h = width * 9 // 16; rows = (len(files) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * width, rows * (h + 14)), (30, 30, 30)); d = ImageDraw.Draw(sheet)
        for i, f in enumerate(files):
            x, y = (i % cols) * width, (i // cols) * (h + 14)
            sheet.paste(Image.open(f).convert('RGB').resize((width, h)), (x, y + 14))
            d.text((x + 2, y), f"{int(os.path.basename(f).split('_')[0]):,}", fill=(255, 255, 0))
        sheet.save(out(f'thumbs_by_views_{width}.jpg'), quality=85)
    print(f'{len(files)} thumbnails -> thumb_stats.json, thumbs_by_views_480.jpg, thumbs_by_views_210.jpg (feed size)')
    for s in stats_out[:12]:
        print(f"  {s['views']:>12,}  white {s['white_pct']:3}%  black {s['black_pct']:3}%  mid {s['midtone_pct']:3}%  sat {s['mean_saturation']:3}  {s['id']}")


def main(a):
    global OUT
    if '--out' in a: i = a.index('--out'); OUT = a[i + 1]; a = a[:i] + a[i + 2:]
    opt = lambda k, cast=str, d=None: cast(a[a.index(k) + 1]) if k in a else d
    if not a: raise SystemExit(__doc__)
    c = a[0]
    if c == 'scrape': cmd_scrape(a[1], opt('--limit', int), '--shorts' in a, opt('--comments', int, 0))
    elif c == 'table': cmd_table()
    elif c == 'subs': cmd_subs(opt('--top', int), opt('--ids', lambda s: s.split(',')))
    elif c == 'download': cmd_download(a[1], '--low' in a)
    elif c == 'transcribe': cmd_transcribe([x for x in a[1:] if not x.startswith('--') and x != opt('--model')], opt('--model', str, 'small.en'))
    elif c == 'script': cmd_script(a[1:])
    elif c == 'cuts': cmd_cuts(a[1:])
    elif c == 'thumbs': cmd_thumbs()
    else: raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1:])
