#!/usr/bin/env python3
"""Stage 2: verification + precise localization.

For each stage-1 candidate (clip, master, rate, offset):
  - decode master at half-res gray (once per master)
  - estimate spatial scale (crop+resize factor) via multi-scale template matching
    of Canny edge maps (robust to tint/brightness/contrast/watermarks)
  - for several clip frames, search master native-rate frames around the predicted
    time; collect per-frame best NCC and master position
  - robust fit of  master_t = rate * clip_t + t0 ; report t0, rate, NCC stats
Output: work/out/verify.json
"""
import os, json, sys
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))
SEARCH = 18          # native master frames search radius (±0.75 s)
MAXVFRAMES = 8       # clip frames used per candidate
RES_TOL = 0.45       # seconds; temporal residual inlier threshold


def load_master_half(mpath):
    cap = cv2.VideoCapture(mpath)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (320, 240), interpolation=cv2.INTER_AREA)
        frames.append(g)
    cap.release()
    return np.stack(frames)


def edges(img):
    b = cv2.GaussianBlur(img, (3, 3), 0)
    e = cv2.Canny(b, 40, 120)
    e = cv2.dilate(e, np.ones((3, 3), np.uint8))
    return e.astype(np.float32) / 255.0


def feat(img):
    """Primary matching feature: float luma (CCOEFF normalizes brightness/contrast)."""
    return img.astype(np.float32)


def scale_grid(cw, ch):
    smin = max(96.0 / cw, 72.0 / ch)
    smax = min(320.0 / cw, 240.0 / ch)
    smin = min(smin, smax) * 0.90
    grid = []
    s = smin
    while s <= smax * 1.001:
        grid.append(s)
        s *= 1.06
    if not grid or grid[-1] < smax:
        grid.append(smax)
    return np.array(grid)


def best_match(mframe_f, templ_f):
    if templ_f.shape[0] > mframe_f.shape[0] or templ_f.shape[1] > mframe_f.shape[1]:
        return -1.0, None
    r = cv2.matchTemplate(mframe_f, templ_f, cv2.TM_CCOEFF_NORMED)
    _, mx, _, ml = cv2.minMaxLoc(r)
    return float(mx), ml


def clip_frame_gray(cpath, idx):
    cap = cv2.VideoCapture(cpath)
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    cap.release()
    if not ok:
        return None
    return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)


def verify_candidate(cpath, mframes_half, mpath, cand, nclipframes):
    mrate, moff = cand['rate'], cand['off']
    fmap = {int(k): v[0] for k, v in cand['fmap'].items()}
    keys = sorted(fmap)
    if not keys:
        return None
    pick = [keys[int(i)] for i in np.linspace(0, len(keys) - 1, min(MAXVFRAMES, len(keys))).astype(int)]
    pick = sorted(set(pick))
    # native clip frame indices (3fps -> 24fps: *8)
    cdata = []
    for c3 in pick:
        g = clip_frame_gray(cpath, c3 * 8)
        if g is not None and g.std() > 5:
            cdata.append((c3 * 8, g))
    if not cdata:
        return None
    ch, cw = cdata[0][1].shape
    mf_half_cache = [feat(f) for f in mframes_half]
    grid = scale_grid(cw, ch)
    # --- scale estimation using up to 2 frames on their predicted master frames
    scale_votes = []
    for ci, (cidx, g) in enumerate(cdata[:2]):
        mpred = int(round(mrate * cidx + 8 * moff))
        mpred = min(max(mpred, 0), len(mframes_half) - 1)
        me = feat(mframes_half[mpred])
        scores = []
        for s in grid:
            t = cv2.resize(g, (max(int(round(cw * s)), 8), max(int(round(ch * s)), 8)),
                           interpolation=cv2.INTER_AREA)
            ncc, _ = best_match(me, feat(t))
            scores.append(ncc)
        scale_votes.append(np.array(scores))
    sv = np.mean(scale_votes, axis=0)
    # refine around best grid scale with finer step
    s0 = grid[int(np.argmax(sv))]
    fine = np.arange(s0 * 0.94, s0 * 1.06, 0.01)
    ci_, g_ = cdata[0]
    mpred = int(round(mrate * ci_ + 8 * moff)); mpred = min(max(mpred,0), len(mframes_half)-1)
    me = feat(mframes_half[mpred])
    fscores = []
    for s in fine:
        t = cv2.resize(g_, (max(int(round(cw*s)),8), max(int(round(ch*s)),8)), interpolation=cv2.INTER_AREA)
        ncc,_ = best_match(me, feat(t)); fscores.append(ncc)
    fine = np.array(fine); fscores=np.array(fscores)
    all_s = np.concatenate([grid, fine]); all_v = np.concatenate([sv, fscores])
    top_scales = all_s[np.argsort(-all_v)[:3]]
    # pre-render templates at the top scales
    templs = []
    for s in top_scales:
        ts = []
        for cidx, g in cdata:
            t = cv2.resize(g, (max(int(round(cw * s)), 8), max(int(round(ch * s)), 8)),
                           interpolation=cv2.INTER_AREA)
            ts.append(feat(t))
        templs.append(ts)

    def frame_search(rate, off8, window):
        """Per-frame best match around prediction; returns per_frame list."""
        pf = []
        for fi, (cidx, g) in enumerate(cdata):
            ct = cidx / 24.0
            mpred = rate * cidx + off8
            lo = int(max(np.floor(mpred) - window, 0))
            hi = int(min(np.ceil(mpred) + window, len(mframes_half) - 1))
            best = (-1.0, None, None, None)
            for si, s in enumerate(top_scales):
                te = templs[si][fi]
                for mf in range(lo, hi + 1):
                    ncc, loc = best_match(mf_half_cache[mf], te)
                    if ncc > best[0]:
                        best = (ncc, mf, s, loc)
            pf.append(dict(cidx=int(cidx), ct=ct, ncc=best[0], mf=best[1],
                           scale=best[2], loc=best[3]))
        return pf

    def ransac_fit(pf, tol=RES_TOL, iters=300, seed=1):
        good = [p for p in pf if p['ncc'] >= 0.35 and p['mf'] is not None]
        if len(good) < 2:
            return None, good
        ct = np.array([p['ct'] for p in good])
        mt = np.array([p['mf'] / 24.0 for p in good])
        rng = np.random.default_rng(seed)
        n = len(ct); best = None
        for _ in range(iters):
            i, j = rng.choice(n, 2, replace=False)
            if abs(ct[i] - ct[j]) < 0.4:
                continue
            r = (mt[j] - mt[i]) / (ct[j] - ct[i])
            if not (0.5 <= r <= 1.6):
                continue
            t = mt[i] - r * ct[i]
            il = np.abs(mt - (r * ct + t)) <= tol
            sc = (il.sum(), -np.abs(mt[il] - (r * ct[il] + t)).mean())
            if best is None or sc > best[0]:
                best = (sc, il, r, t)
        if best is None:
            return None, good
        _, inl, rate, t0 = best
        if inl.sum() >= 2:
            A = np.vstack([ct[inl], np.ones(int(inl.sum()))]).T
            rate, t0 = np.linalg.lstsq(A, mt[inl], rcond=None)[0]
            inl = np.abs(mt - (rate * ct + t0)) <= tol
        return (inl, rate, t0, ct, mt, good), good

    # pass 0: seed with stage-1 rate; if that fails, seed rate=1 through centroid
    seeds = [(mrate, 8 * moff)]
    cmean = float(np.mean([c for c, _ in cdata]))
    seeds.append((1.0, mrate * cmean + 8 * moff - 1.0 * cmean))
    fit = None; per_frame = None
    for srate, soff8 in seeds:
        pf = frame_search(srate, soff8, 24)
        fr, good = ransac_fit(pf)
        if fr is not None and fr[0].sum() >= 2:
            fit, per_frame = fr, pf
            break
        if per_frame is None:
            per_frame = pf
    if fit is None:
        return dict(ncc_med=float(np.median([p['ncc'] for p in per_frame])),
                    frac_good=0.0, t0=None, rate=None, per_frame=per_frame)
    # pass 1: re-search around the fitted line, tighter window, then refit
    inl, rate, t0, ct, mt, good = fit
    pf = frame_search(rate, t0 * 24, 12)
    fr, good = ransac_fit(pf)
    if fr is not None and fr[0].sum() >= 2:
        inl, rate, t0, ct, mt, good = fr
        per_frame = pf
    ncc_in = [p['ncc'] for p, ok in zip(good, inl) if ok]
    inl_frames = [p for p, ok in zip(good, inl) if ok]
    if inl_frames:
        sc = float(np.median([p['scale'] for p in inl_frames]))
        xs = [p['loc'][0] for p in inl_frames]; ys = [p['loc'][1] for p in inl_frames]
        x, y = int(np.median(xs)) * 2, int(np.median(ys)) * 2
        w, h = int(round(cw * sc)) * 2, int(round(ch * sc)) * 2
        crop = [x, y, w, h]
        coverage = float((w / 2 * (h / 2)) / (320 * 240))
    else:
        crop = None
        coverage = 0.0
    return dict(ncc_med=float(np.median(ncc_in)) if ncc_in else 0.0,
                ncc_all=float(np.median([p['ncc'] for p in per_frame])),
                frac_good=float(len(good) / len(per_frame)),
                n_inlier=int(inl.sum()), n_used=len(per_frame),
                t0=float(t0), rate=float(rate), crop=crop, coverage=coverage,
                per_frame=per_frame)


def worker(task):
    mid, jobs = task
    mpath = os.path.join(ROOT, 'masters', f'master_{mid:02d}.mp4')
    mframes = load_master_half(mpath)
    res = {}
    for cname, cand, ncf in jobs:
        cpath = os.path.join(CLIPS_DIR, cname)
        try:
            r = verify_candidate(cpath, mframes, mpath, cand, ncf)
        except Exception as e:
            r = dict(error=str(e))
        res[cname] = r
        print(f"  {cname} vs master_{mid:02d}: ncc={r.get('ncc_med'):.3f} "
              f"t0={r.get('t0')} rate={r.get('rate')}", flush=True)
    return mid, res


def main():
    cand_json = sys.argv[1] if len(sys.argv) > 1 else 'stage1.json'
    out_json = sys.argv[2] if len(sys.argv) > 2 else 'verify.json'
    only = set(sys.argv[3:])
    with open(os.path.join(OUT, cand_json)) as f:
        s1 = json.load(f)
    # group candidates by master; strong stage-1 -> top2, weak -> top4
    groups = {}
    for cname, info in s1.items():
        if only and cname not in only:
            continue
        cands = info['candidates'] or []
        strong = cands and cands[0]['uniq_frames'] >= 0.6 * info.get('n_frames', 10**9) \
            and cands[0]['mean_dist'] <= 12
        for cand in cands[:(2 if strong else 4)]:
            if cand['uniq_frames'] < 3:
                continue
            groups.setdefault(cand['master'], []).append((cname, cand, info.get('n_frames', 30)))
    tasks = sorted(groups.items())
    allres = {}
    with ProcessPoolExecutor(max_workers=12) as ex:
        for mid, res in ex.map(worker, tasks):
            for k, v in res.items():
                allres.setdefault(k, {})[f'm{mid:02d}'] = v
    with open(os.path.join(OUT, out_json), 'w') as f:
        json.dump(allres, f)
    print('saved', os.path.join(OUT, out_json), 'clips:', len(allres))


if __name__ == '__main__':
    main()
