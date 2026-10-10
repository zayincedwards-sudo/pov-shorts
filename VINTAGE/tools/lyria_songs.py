"""PAID: generate the instrumental jazz pieces for the music bed on Lyria (USD 0.08 per song, pricing page 10 Oct 2026).

  python tools/lyria_songs.py <episode_dir> [--only 1,3] [--redo 2]

Reads "songs" (a list of prompts) from <episode_dir>/scene.json, writes <episode_dir>/music/NN.mp3, logs each call to
<episode_dir>/music/spend.log. Finished songs are cached; a rerun re-buys only those named in --redo.
The reference's bed is about five instrumental pieces, 64-129 BPM, mastered alike (ANALYSIS.md).
"""
import base64, json, os, sys, time, urllib.error, urllib.request

URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'
MODEL = 'lyria-3.5'
PRICE = 0.08


def key():
    k = os.environ.get('GEMINI_API_KEY')
    envf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    if not k and os.path.exists(envf):
        for line in open(envf):
            if line.startswith('GEMINI_API_KEY=') and line.strip() != 'GEMINI_API_KEY=':
                k = line.split('=', 1)[1].strip()
    if not k:
        sys.exit('No GEMINI_API_KEY in the environment or VINTAGE/.env')
    return k


def find_audio(o):
    """Return the last base64 audio payload anywhere in the response."""
    found = []
    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get('data'), str) and len(x['data']) > 1000 and ('audio' in json.dumps({k: v for k, v in x.items() if k != 'data'}) or x.get('type') == 'audio'):
                found.append(x)
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(o)
    if not found and isinstance(o.get('output_audio'), dict):
        found.append(o['output_audio'])
    return found[-1] if found else None


def main():
    ep = sys.argv[1]
    opt = lambda f: [int(x) for x in sys.argv[sys.argv.index(f) + 1].split(',')] if f in sys.argv else []
    only, redo = opt('--only'), opt('--redo')
    songs = json.load(open(os.path.join(ep, 'scene.json')))['songs']
    k = key(); os.makedirs(os.path.join(ep, 'music'), exist_ok=True)
    log = open(os.path.join(ep, 'music', 'spend.log'), 'a')
    for i, p in enumerate(songs, 1):
        dst = os.path.join(ep, 'music', f'{i:02d}.mp3')
        if (only and i not in only) or (os.path.exists(dst) and i not in redo):
            continue
        body = json.dumps({'model': MODEL, 'input': p}).encode()
        req = urllib.request.Request(URL, data=body, headers={'x-goog-api-key': k, 'Content-Type': 'application/json'})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=600).read())
        except urllib.error.HTTPError as e:
            sys.exit(f'song {i}: HTTP {e.code}: {e.read().decode("utf-8", "replace")[:1200]}')
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} song {i} {MODEL} est USD {PRICE:.2f}\n"); log.flush()
        a = find_audio(r)
        if not a:
            open(dst + '.response.json', 'w').write(json.dumps(r)[:20000])
            print(f'song {i}: no audio in response (saved {dst}.response.json)', flush=True); continue
        open(dst, 'wb').write(base64.b64decode(a['data']))
        print(f'song {i}: saved {dst}', flush=True)


if __name__ == '__main__':
    main()
