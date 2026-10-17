#!/usr/bin/env python3
"""Geometry rescue for ORB-strong but template-rejected candidates.

For each (clip, master) job: extract ORB keypoints+positions from sample clip
frames, match against that master's DB descriptors, estimate the similarity
transform (RANSAC) between clip and master frames -> crop scale. Then re-run
template verification at that scale and refit the time map.

Usage: orb_geo.py jobs.json out.json   with jobs = [[cname, master], ...]
"""
import os, json, sys
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
SIG = os.path.join(ROOT, 'work', 'sig')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify import load_master_half, best_match, feat  # noqa
from orb_match import load_db, match_descriptors, clip_orb_frames, orb  # noqa

DB = None
def get_db_u64():
    global DB
    if DB is None:
        d, f, m = load_db()
        DB = (d.view(np.uint64).reshape(len(d), 4), d, f, m)
    return DB


def clip_orb_with_kp(cpath, picks):
    cap = cv2.VideoCapture(cpath)
    out = []
    for p in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(p))
        ok, f = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        sc = 512 / max(h, w)
        gg = cv2.resize(g, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA) if sc < 1 else g
        kp, d = orb.detectAndCompute(gg, None)
        if d is not None and len(kp) > 10:
            pts = np.array([k.pt for k in kp], dtype=np.float32)
            out.append((int(p), pts, d, gg.shape, g.shape))
    cap.release()
    return out


def estimate_scale(job):
    cname, mid = job
    db_u64, db_u8, db_frames, db_mids = get_db_u64()
    msel = db_mids == mid
    cpath = os.path.join(CLIPS_DIR, cname)
    cap = cv2.VideoCapture(cpath)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    picks = np.linspace(int(total * 0.1), int(total * 0.9), 5).astype(int)
    frames = clip_orb_with_kp(cpath, picks)
    if not frames:
        return job, None
    scales = []
    for cidx, pts, descs, gshape, nshape in frames:
        bi, bd, sd = match_descriptors(descs, db_u64)
        good = (bd <= 60) & (bd <= 0.8 * sd)
        gi = np.where(good)[0]
        # restrict to the master
        m_ok = db_mids[bi[gi]] == mid
        gi = gi[m_ok]
        if len(gi) < 12:
            continue
        # group by master frame; use the frame with most matches
        mf_ids = db_frames[bi[gi]]
        vals, counts = np.unique(mf_ids, return_counts=True)
        best_mf = vals[np.argmax(counts)]
        sel2 = mf_ids == best_mf
        gi2 = gi[sel2]
        if len(gi2) < 10:
            continue
        # master keypoint positions: need to re-extract ORB for that master frame
        # (DB has no positions) -> extract on the fly
        cap = cv2.VideoCapture(os.path.join(ROOT, 'masters', f'master_{mid:02d}.mp4'))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(best_mf))
        ok, mf = cap.read(); cap.release()
        if not ok:
            continue
        mg = cv2.cvtColor(mf, cv2.COLOR_BGR2GRAY)
        mh, mw = mg.shape
        msc = 384 / max(mh, mw)
        mgg = cv2.resize(mg, (int(mw * msc), int(mh * msc)), interpolation=cv2.INTER_AREA)
        mkp, md = orb.detectAndCompute(mgg, None)
        if md is None:
            continue
        # match clip descs (gi2 subset) against THIS frame's descriptors directly
        qd = descs[gi2]
        bi2, bd2, sd2 = match_descriptors(qd, md.view(np.uint64).reshape(len(md), 4))
        good2 = (bd2 <= 60) & (bd2 <= 0.8 * sd2)
        gj = np.where(good2)[0]
        if len(gj) < 10:
            continue
        src = pts[gi2[gj]]
        mpts = np.array([k.pt for k in mkp], dtype=np.float32)[bi2[gj]]
        M, inl = cv2.estimateAffinePartial2D(src, mpts, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.5)
        if M is None or inl is None or inl.sum() < 8:
            continue
        s_aff = float(np.sqrt(abs(np.linalg.det(M[:, :2]))))
        # verify-scale: clip native px -> master-half (320x240) px
        clip_sc = gshape[1] / nshape[1]      # orb extraction scale (width ratio)
        mast_sc = 320 / mgg.shape[1]         # master orb width -> master-half width
        s_verify = s_aff * mast_sc / clip_sc
        scales.append((s_verify, int(inl.sum()), int(best_mf)))
    if not scales:
        return job, None
    # robust median scale weighted by inliers
    scales.sort(key=lambda x: -x[1])
    return job, scales[0]


def reverify(job, geo, mframes):
    cname, mid = job
    s_verify, ninl, mf0 = geo
    # seed time map from orb_candidates round2 (best candidate for this master)
    cpath = os.path.join(CLIPS_DIR, cname)
    cap = cv2.VideoCapture(cpath)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    picks = np.linspace(int(total * 0.05), int(total * 0.95), 8).astype(int)
    cand = json.load(open(os.path.join(OUT, 'orb2_candidates.json')))[cname]['candidates']
    cc = [c for c in cand if c['master'] == mid]
    if not cc:
        cc = cand
    rate0, t0_3 = cc[0]['rate'], cc[0]['off']  # off in 3fps units
    per_frame = []
    for ci in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(ci))
        ok, f = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        ch, cw = g.shape
        t = cv2.resize(g, (max(int(round(cw * s_verify)), 8), max(int(round(ch * s_verify)), 8)),
                       interpolation=cv2.INTER_AREA)
        te = feat(t)
        mpred = rate0 * ci + 8 * t0_3
        lo = int(max(np.floor(mpred) - 24, 0)); hi = int(min(np.ceil(mpred) + 24, len(mframes) - 1))
        best = (-1.0, None, None)
        for mf in range(lo, hi + 1):
            ncc, loc = best_match(feat(mframes[mf]), te)
            if ncc > best[0]:
                best = (ncc, mf, loc)
        per_frame.append((ci / 24.0, best[1], best[0], best[2]))
    cap.release()
    good = [(ct, mf, n, l) for ct, mf, n, l in per_frame if mf is not None and n >= 0.3]
    if len(good) < 3:
        return dict(ncc=float(np.median([p[2] for p in per_frame])) if per_frame else 0.0,
                    ok=False, geo_inl=ninl)
    ct = np.array([g[0] for g in good]); mt = np.array([g[1] / 24.0 for g in good])
    nc = np.array([g[2] for g in good])
    # RANSAC line
    rng = np.random.default_rng(0); bestf = None
    for _ in range(300):
        i, j = rng.choice(len(ct), 2, replace=False)
        if abs(ct[i] - ct[j]) < 0.4:
            continue
        r = (mt[j] - mt[i]) / (ct[j] - ct[i])
        if not (0.5 <= r <= 1.6):
            continue
        t = mt[i] - r * ct[i]
        il = np.abs(mt - (r * ct + t)) <= 0.45
        if bestf is None or il.sum() > bestf[0].sum():
            bestf = (il, r, t)
    if bestf is None:
        return dict(ncc=float(np.median(nc)), ok=False, geo_inl=ninl)
    il, rate, t0 = bestf
    if il.sum() >= 2:
        A = np.vstack([ct[il], np.ones(int(il.sum()))]).T
        rate, t0 = np.linalg.lstsq(A, mt[il], rcond=None)[0]
        il = np.abs(mt - (rate * ct + t0)) <= 0.45
    locs = [g[3] for g, ok in zip(good, il) if ok and g[3] is not None]
    if locs:
        x = int(np.median([l[0] for l in locs])) * 2
        y = int(np.median([l[1] for l in locs])) * 2
        cw = per_frame and 1  # placeholder
        crop = [x, y]
    else:
        crop = None
    return dict(ncc=float(np.median(nc[il])) if il.sum() else float(np.median(nc)),
                t0=float(t0), rate=float(rate), n_inlier=int(il.sum()),
                n_used=len(per_frame), geo_inl=ninl, scale=s_verify, ok=True)


def worker(jobs):
    res = {}
    bym = {}
    for j in jobs:
        bym.setdefault(j[1], []).append(j)
    for mid, js in bym.items():
        mframes = load_master_half(os.path.join(ROOT, 'masters', f'master_{mid:02d}.mp4'))
        for j in js:
            job, geo = estimate_scale(j)
            if geo is None:
                res[j[0]] = dict(ok=False, reason='no geometry')
                print(f"{j[0]} m{mid:02d}: no geometry", flush=True)
                continue
            r = reverify(j, geo, mframes)
            res[j[0]] = r
            print(f"{j[0]} m{mid:02d}: scale={geo[0]:.3f} geo_inl={geo[1]} -> "
                  f"ncc={r['ncc']:.3f} t0={r.get('t0')} rate={r.get('rate')} inl={r.get('n_inlier')}", flush=True)
    return res


def main():
    jobs = json.load(open(os.path.join(OUT, sys.argv[1])))
    out_path = sys.argv[2]
    results = {}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for res in ex.map(worker, [jobs[i::8] for i in range(8)]):
            results.update(res)
    with open(os.path.join(OUT, out_path), 'w') as f:
        json.dump(results, f)
    print('saved', out_path, len(results))


if __name__ == '__main__':
    main()
