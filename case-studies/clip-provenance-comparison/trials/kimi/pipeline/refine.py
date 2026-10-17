#!/usr/bin/env python3
"""Final refinement: for each accepted match, re-estimate t0/rate precisely
using 12 clip frames, the verified crop scale, and a narrow temporal window.
Usage: refine.py <decisions.json> <out.json>
"""
import os, json, sys
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify import load_master_half, best_match, feat  # noqa

NFRAMES = 12


def clip_gray_at(cpath, idx):
    cap = cv2.VideoCapture(cpath)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
    ok, f = cap.read()
    cap.release()
    return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if ok else None


def refine_one(cpath, mframes, t0, rate, crop_w_native, seed=0):
    cap = cv2.VideoCapture(cpath)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    picks = np.linspace(int(total * 0.04), int(total * 0.96), NFRAMES).astype(int)
    pts = []
    for ci in picks:
        g = clip_gray_at(cpath, ci)
        if g is None or g.std() < 5:
            continue
        ch, cw = g.shape
        scale = (crop_w_native / 2.0) / cw
        best = (-1.0, None)
        for sf in (scale * 0.97, scale, scale * 1.03):
            t = cv2.resize(g, (max(int(round(cw * sf)), 8), max(int(round(ch * sf)), 8)),
                           interpolation=cv2.INTER_AREA)
            te = feat(t)
            mpred = rate * ci + 24 * t0
            lo = int(max(np.floor(mpred) - 10, 0))
            hi = int(min(np.ceil(mpred) + 10, len(mframes) - 1))
            for mf in range(lo, hi + 1):
                ncc, loc = best_match(feat(mframes[mf]), te)
                if ncc > best[0]:
                    best = (ncc, mf, sf, loc)
        if best[1] is not None:
            pts.append((ci / 24.0, best[1] / 24.0, best[0], best[2], best[3]))
    if len(pts) < 3:
        return None
    ct = np.array([p[0] for p in pts]); mt = np.array([p[1] for p in pts])
    ncc = np.array([p[2] for p in pts])
    # weighted RANSAC-ish: plain RANSAC then weighted LSQ on inliers
    rng = np.random.default_rng(seed)
    best = None
    n = len(ct)
    for _ in range(400):
        i, j = rng.choice(n, 2, replace=False)
        if abs(ct[i] - ct[j]) < 0.4:
            continue
        r = (mt[j] - mt[i]) / (ct[j] - ct[i])
        if not (0.6 <= r <= 1.5):
            continue
        t = mt[i] - r * ct[i]
        il = np.abs(mt - (r * ct + t)) <= 0.20
        sc = il.sum()
        if best is None or sc > best[0]:
            best = (sc, il, r, t)
    if best is None:
        return None
    _, inl, rate, t0 = best
    if inl.sum() >= 2:
        W = ncc[inl] ** 2
        A = np.vstack([ct[inl], np.ones(int(inl.sum()))]).T
        Aw = A * np.sqrt(W)[:, None]
        rate, t0 = np.linalg.lstsq(Aw, mt[inl] * np.sqrt(W), rcond=None)[0]
        inl = np.abs(mt - (rate * ct + t0)) <= 0.20
    resid = mt[inl] - (rate * ct[inl] + t0)
    sc = float(np.median([p[3] for p, ok in zip(pts, inl) if ok]))
    return dict(t0=float(t0), rate=float(rate), ncc=float(np.median(ncc[inl])),
                n_inlier=int(inl.sum()), n_used=len(pts),
                resid_std=float(resid.std()) if len(resid) > 1 else 0.0,
                scale=sc)


def worker(task):
    mid, jobs = task
    mframes = load_master_half(os.path.join(ROOT, 'masters', f'master_{mid:02d}.mp4'))
    out = {}
    for cname, t0, rate, crop_w in jobs:
        try:
            r = refine_one(os.path.join(CLIPS_DIR, cname), mframes, t0, rate, crop_w,
                           seed=hash(cname) % 10000)
        except Exception as e:
            r = dict(error=str(e))
        out[cname] = r
    return mid, out


def main():
    dec = json.load(open(os.path.join(OUT, sys.argv[1])))
    out_path = sys.argv[2]
    groups = {}
    for r in dec:
        if r['tier'] in ('confident', 'uncertain', 'uncertain-static') and r['master'] is not None:
            crop_w = r['crop'][2] if r.get('crop') else 640
            groups.setdefault(r['master'], []).append((r['clip'], r['t0'], r['rate'], crop_w))
    results = {}
    with ProcessPoolExecutor(max_workers=12) as ex:
        for mid, res in ex.map(worker, sorted(groups.items())):
            results.update(res)
    with open(os.path.join(OUT, out_path), 'w') as f:
        json.dump(results, f)
    print('saved', out_path, len(results))


if __name__ == '__main__':
    main()
