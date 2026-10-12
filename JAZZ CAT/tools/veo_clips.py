"""PAID: generate the loop clips on Veo. Every clip starts AND ends on the same still, so the clips chain into one
seamless loop (the method inferred from the reference, ANALYSIS.md).

  python tools/veo_clips.py <episode_dir> [--only 1,3] [--redo 2]

Reads <episode_dir>/scene.json (prompts, model, resolution) and <episode_dir>/still.png. Writes
<episode_dir>/clips/clip_NN.mp4 and a log line per call to <episode_dir>/clips/spend.log. Finished clips are cached:
a rerun never re-buys a clip unless it is named in --redo. Key: GEMINI_API_KEY from the environment or JAZZ CAT/.env.
Cost (quoted 10 Oct 2026): Veo 3.1 Lite 720p USD 0.05 per second, so one 8 s clip is USD 0.40.
"""
import base64, json, os, sys, time, urllib.error, urllib.request

BASE = 'https://generativelanguage.googleapis.com/v1beta'
PRICE_PER_S = {'720p': 0.05, '1080p': 0.08}


def key():
    k = os.environ.get('GEMINI_API_KEY')
    if not k:
        envf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
        if os.path.exists(envf):
            for line in open(envf):
                if line.startswith('GEMINI_API_KEY=') and line.strip() != 'GEMINI_API_KEY=':
                    k = line.split('=', 1)[1].strip()
    if not k:
        sys.exit('No GEMINI_API_KEY in the environment or JAZZ CAT/.env')
    return k


def call(url, k, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={'x-goog-api-key': k, 'Content-Type': 'application/json'})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=120).read())
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code} from {url.split("?")[0]}: {e.read().decode("utf-8", "replace")[:1500]}')


def main():
    ep = sys.argv[1]
    opt = lambda f: [int(x) for x in sys.argv[sys.argv.index(f) + 1].split(',')] if f in sys.argv else []
    only, redo = opt('--only'), opt('--redo')
    sc = json.load(open(os.path.join(ep, 'scene.json')))
    v = sc['veo']; k = key()
    img = {'bytesBase64Encoded': base64.b64encode(open(os.path.join(ep, 'still.png'), 'rb').read()).decode(), 'mimeType': 'image/png'}
    os.makedirs(os.path.join(ep, 'clips'), exist_ok=True)
    log = open(os.path.join(ep, 'clips', 'spend.log'), 'a')
    for i, p in enumerate(sc['clip_prompts'], 1):
        dst = os.path.join(ep, 'clips', f'clip_{i:02d}.mp4')
        if only and i not in only:
            continue
        if os.path.exists(dst) and i not in redo:
            print(f'clip {i}: cached'); continue
        body = {'instances': [{'prompt': p + ' ' + sc['clip_prompt_common'], 'image': img, 'lastFrame': img}],
                'parameters': {'aspectRatio': v['aspectRatio'], 'resolution': v['resolution'],
                               'durationSeconds': int(v['durationSeconds']), 'personGeneration': 'allow_adult'}}
        op = call(f"{BASE}/models/{v['model']}:predictLongRunning", k, body)
        cost = PRICE_PER_S[v['resolution']] * float(v['durationSeconds'])
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} clip {i} {v['model']} {v['resolution']} {v['durationSeconds']}s est USD {cost:.2f} op {op.get('name')}\n"); log.flush()
        print(f'clip {i}: started {op.get("name")}', flush=True)
        while True:
            time.sleep(10)
            st = call(f"{BASE}/{op['name']}", k)
            if st.get('done'):
                break
        if 'error' in st:
            print(f'clip {i}: ERROR {st["error"]}', flush=True); continue
        samples = st.get('response', {}).get('generateVideoResponse', {}).get('generatedSamples', [])
        if not samples:
            print(f'clip {i}: no video returned: {json.dumps(st)[:400]}', flush=True); continue
        req = urllib.request.Request(samples[0]['video']['uri'], headers={'x-goog-api-key': k})
        open(dst + '.part', 'wb').write(urllib.request.urlopen(req, timeout=300).read())
        os.replace(dst + '.part', dst)
        print(f'clip {i}: saved {dst}', flush=True)


if __name__ == '__main__':
    main()
