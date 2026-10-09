"""Fetch only what the loop instruments need, in ranged 4 MB chunks (gotchas: ~17 MB/s ranged vs 0.2 MB/s whole-file).

  python fetch_parts.py <info.json> <format_id> <out_file> [--mb N]

Reads the stream URL and http_headers for <format_id> from a fresh yt-dlp info JSON and writes the first N MB
(default: the whole stream). A cut-short WebM/MP4 decodes cleanly up to the cut. Free; no API calls.
"""
import json, os, sys, urllib.request

CHUNK = 4 * 1024 * 1024


def main():
    info, fid, dst = sys.argv[1:4]
    limit = None
    if '--mb' in sys.argv:
        limit = int(float(sys.argv[sys.argv.index('--mb') + 1]) * 1024 * 1024)
    d = json.load(open(info, encoding='utf-8'))
    f = next(x for x in d['formats'] if x['format_id'] == fid)
    size = f.get('filesize') or f.get('filesize_approx')
    end = min(size, limit) if limit and size else (limit or size)
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    have = os.path.getsize(dst) if os.path.exists(dst) else 0
    with open(dst, 'ab') as out:
        pos = have
        while end is None or pos < end:
            hi = pos + CHUNK - 1 if end is None else min(pos + CHUNK, end) - 1
            req = urllib.request.Request(f['url'] + f'&range={pos}-{hi}', headers=f.get('http_headers', {}))
            data = urllib.request.urlopen(req, timeout=60).read()
            if not data:
                break
            out.write(data)
            pos += len(data)
            if len(data) < CHUNK and (end is None or pos < end):
                break
    print(f'{dst}: {os.path.getsize(dst) / 1e6:.1f} MB of {(size or 0) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
