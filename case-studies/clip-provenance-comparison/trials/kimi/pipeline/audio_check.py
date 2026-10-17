#!/usr/bin/env python3
"""Independent validation: audio cross-correlation between clip and matched master
at the reported offset. Only positive evidence (audio may be replaced/removed).
Usage: audio_check.py round2_report.json
"""
import os, json, subprocess, sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
SR = 8000


def audio(path, t0=0.0, dur=None):
    cmd = ['ffmpeg', '-v', 'error']
    if t0:
        cmd += ['-ss', f'{t0:.3f}']
    cmd += ['-i', path]
    if dur:
        cmd += ['-t', f'{dur:.3f}']
    cmd += ['-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32)


def check(job):
    cname, mid, t0, rate = job
    cpath = os.path.join(ROOT, 'clips', cname)
    mpath = os.path.join(ROOT, 'masters', f'master_{mid:02d}.mp4')
    ca = audio(cpath)
    if ca is None or len(ca) < SR * 3 or not (0.97 <= rate <= 1.03):
        return cname, None
    # clip duration in master time
    cdur = len(ca) / SR
    ma = audio(mpath, max(t0 - 1.0, 0.0), cdur + 2.0)
    if ma is None or len(ma) < len(ca):
        return cname, None
    a = ca - ca.mean(); b = ma - ma.mean()
    if a.std() < 1e-4 or b.std() < 1e-4:
        return cname, None  # silence
    from scipy.signal import correlate
    cc = correlate(b, a, mode='valid', method='fft')  # cc[lag] = sum_i a[i] b[lag+i]
    b2 = np.concatenate([[0.0], np.cumsum(b * b)])
    Ea = float((a ** 2).sum())
    cen = SR * 1  # expected lag: master window started 1 s early
    lo = max(cen - SR // 2, 0); hi = min(cen + SR // 2, len(cc))
    best = 0.0
    for lag in range(lo, hi):
        Eb = b2[lag + len(a)] - b2[lag]
        if Eb <= 0:
            continue
        s = float(cc[lag] / np.sqrt(Ea * Eb))
        if s > best:
            best = s
    return cname, best


def main():
    rows = json.load(open(os.path.join(OUT, sys.argv[1])))
    jobs = []
    for r in rows:
        if r['master'] is None or r['tier'] == 'unidentified':
            continue
        t0 = r.get('t0_refined', r.get('t0'))
        rate = r.get('rate_refined', r.get('rate'))
        if t0 is None or rate is None:
            continue
        jobs.append((r['clip'], r['master'], t0, rate))
    res = {}
    with ProcessPoolExecutor(max_workers=12) as ex:
        for cname, score in ex.map(check, jobs):
            res[cname] = score
    scores = [s for s in res.values() if s is not None]
    scores = np.array(scores)
    print('clips with usable audio:', len(scores), 'of', len(jobs))
    for th in [0.1, 0.2, 0.3, 0.5]:
        print(f'  audio corr >= {th}: {(scores >= th).sum()}')
    low = sorted([(s, c) for c, s in res.items() if s is not None])[:12]
    print('lowest audio corr:', [(c, round(s, 3)) for s, c in low])
    with open(os.path.join(OUT, 'audio_check.json'), 'w') as f:
        json.dump(res, f)


if __name__ == '__main__':
    main()
