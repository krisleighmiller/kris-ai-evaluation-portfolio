#!/usr/bin/env python3
"""Stage 3: ORB keypoint global retrieval for clips that stage 1/2 couldn't place.

- Master DB: ORB descriptors at 2 fps (max dim 384), brute-force Hamming search
  in numpy (uint64-packed), ratio test.
- Clip: ~10 frames, ORB at two scales, match vs DB -> votes -> per-master RANSAC
  line fit (master_t = rate*clip_t + t0).
Output: work/out/orb_candidates.json  (same schema as stage1.json candidates)
"""
import os, json, sys
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))
TODO_JSON = os.environ.get('TODO_JSON', 'todo.json')
ORB_OUT = os.environ.get('ORB_OUT', 'orb_candidates.json')
SIG = os.path.join(ROOT, 'work', 'sig')
MFPS = 2           # master sampling for ORB db
MSTEP = 12         # native frames between ORB master samples (24fps/2fps)
NFEAT = 400
TOP_MASTERS = int(os.environ.get('ORB_TOPM', '3'))
ORB_LOOSE = os.environ.get('ORB_LOOSE', '') == '1'
ORB_FLIP = os.environ.get('ORB_FLIP', '') == '1'

orb = cv2.ORB_create(nfeatures=NFEAT, scaleFactor=1.2, nlevels=8)


def frames_of_video(path, step_native, maxdim, every_n=1):
    cap = cv2.VideoCapture(path)
    out = []
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx % step_native == 0:
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            h, w = g.shape
            sc = maxdim / max(h, w)
            if sc < 1:
                g = cv2.resize(g, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
            out.append((idx, g))
        idx += 1
    cap.release()
    return out


def extract_db(args):
    mid, mpath = args
    descs, fids, mids = [], [], []
    for nf, g in frames_of_video(mpath, MSTEP, 384):
        kp, d = orb.detectAndCompute(g, None)
        if d is not None and len(d):
            descs.append(d)
            fids.append(np.full(len(d), nf, dtype=np.int32))
            mids.append(np.full(len(d), mid, dtype=np.int16))
    if descs:
        return np.vstack(descs), np.concatenate(fids), np.concatenate(mids)
    z = np.zeros((0, 32), np.uint8)
    return z, np.zeros(0, np.int32), np.zeros(0, np.int16)


def build_db():
    masters = sorted(os.listdir(os.path.join(ROOT, 'masters')))
    args = [(int(m.split('_')[1].split('.')[0]), os.path.join(ROOT, 'masters', m)) for m in masters]
    with ProcessPoolExecutor(max_workers=24) as ex:
        parts = list(ex.map(extract_db, args))
    D = np.vstack([p[0] for p in parts])
    F = np.concatenate([p[1] for p in parts])
    M = np.concatenate([p[2] for p in parts])
    np.savez_compressed(os.path.join(SIG, 'masters_orb.npz'), descs=D, frames=F, mids=M)
    print('db built:', D.shape, flush=True)
    return D, F, M


def load_db():
    z = np.load(os.path.join(SIG, 'masters_orb.npz'))
    return z['descs'], z['frames'], z['mids']


DB = None
FLANN = None
def get_db():
    global DB
    if DB is None:
        d, f, m = load_db()
        DB = (d, f, m)
    return DB


def get_flann():
    global FLANN
    if FLANN is None:
        d, f, m = get_db()
        index_params = dict(algorithm=6, table_number=24, key_size=12, multi_probe_level=2)
        search_params = dict(checks=256)
        fl = cv2.FlannBasedMatcher(index_params, search_params)
        fl.add([d])
        fl.train()
        FLANN = fl
    return FLANN


def match_descriptors_flann(qdesc):
    fl = get_flann()
    matches = fl.knnMatch(qdesc, k=2)
    Q = len(qdesc)
    bi = np.full(Q, -1, dtype=np.int64)
    bd = np.full(Q, 256, dtype=np.int32)
    sd = np.full(Q, 256, dtype=np.int32)
    for qi, ms in enumerate(matches):
        if len(ms) >= 1:
            bi[qi] = ms[0].trainIdx; bd[qi] = ms[0].distance
        if len(ms) >= 2:
            sd[qi] = ms[1].distance
        else:
            sd[qi] = 256
    return bi, bd, sd


def match_descriptors(qdesc, db_u64, qchunk=128, dchunk=65536):
    """qdesc (Q,32) u8. Returns best idx and two best distances per query."""
    q_all = qdesc.view(np.uint64).reshape(len(qdesc), 4)
    N = len(db_u64)
    Q = len(q_all)
    best_d = np.full(Q, 256, dtype=np.int32)
    best_i = np.full(Q, -1, dtype=np.int64)
    second_d = np.full(Q, 256, dtype=np.int32)
    for qs in range(0, Q, qchunk):
        q = q_all[qs:qs + qchunk]
        bd = np.full(len(q), 256, dtype=np.int32)
        bi = np.full(len(q), -1, dtype=np.int64)
        sd = np.full(len(q), 256, dtype=np.int32)
        for s in range(0, N, dchunk):
            blk = db_u64[s:s + dchunk]
            x = np.bitwise_xor(q[:, None, :], blk[None, :, :])
            d = np.bitwise_count(x).sum(axis=2).astype(np.int32)
            blk_best_i = np.argmin(d, axis=1)
            blk_best_d = d[np.arange(len(q)), blk_best_i]
            upd = blk_best_d < bd
            sec_blk = np.partition(d, 1, axis=1)[:, 1] if d.shape[1] > 1 else np.full(len(q), 256)
            sd = np.where(upd, np.minimum(bd, np.minimum(sd, sec_blk)),
                          np.minimum(sd, sec_blk))
            bi = np.where(upd, blk_best_i + s, bi)
            bd = np.where(upd, blk_best_d, bd)
        best_d[qs:qs + len(q)] = bd
        best_i[qs:qs + len(q)] = bi
        second_d[qs:qs + len(q)] = sd
    return best_i, best_d, second_d


def clip_orb_frames(cpath, nframes=None):
    if nframes is None:
        nframes = 14 if ORB_LOOSE else 10
    cap = cv2.VideoCapture(cpath)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    picks = np.linspace(0, total - 1, nframes).astype(int)
    out = []
    for p in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(p))
        ok, f = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if g.std() < 5:
            continue
        descs = []
        for maxdim in (512, 340):
            h, w = g.shape
            sc = maxdim / max(h, w)
            gg = cv2.resize(g, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA) if sc < 1 else g
            kp, d = orb.detectAndCompute(gg, None)
            if d is not None:
                descs.append(d)
        if ORB_FLIP:
            gf = cv2.flip(g, 1)
            h, w = gf.shape
            sc = 512 / max(h, w)
            gg = cv2.resize(gf, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA) if sc < 1 else gf
            kp, d = orb.detectAndCompute(gg, None)
            if d is not None:
                descs.append(d)
        if descs:
            out.append((int(p), np.vstack(descs)))
    cap.release()
    return out


def ransac_fit(ct, mt, iters=800, seed=0, tol=0.35):
    rng = np.random.default_rng(seed)
    n = len(ct)
    if n < 6:
        return None
    best = None
    for _ in range(iters):
        i, j = rng.choice(n, 2, replace=False)
        if abs(ct[i] - ct[j]) < 0.5:
            continue
        rate = (mt[j] - mt[i]) / (ct[j] - ct[i])
        if not (0.6 <= rate <= 1.5):
            continue
        t0 = mt[i] - rate * ct[i]
        inl = np.abs(mt - (rate * ct + t0)) <= tol
        if best is None or inl.sum() > best[0].sum():
            best = (inl, rate, t0)
    if best is None:
        return None
    inl, rate, t0 = best
    if inl.sum() >= 3:
        A = np.vstack([ct[inl], np.ones(int(inl.sum()))]).T
        rate, t0 = np.linalg.lstsq(A, mt[inl], rcond=None)[0]
        inl = np.abs(mt - (rate * ct + t0)) <= tol
    return inl, rate, t0


def process_clip(cname):
    db_u8, db_frames, db_mids = get_db()
    cpath = os.path.join(CLIPS_DIR, cname)
    frames = clip_orb_frames(cpath)
    if not frames:
        return cname, []
    # gather correspondences: per clip frame -> matched master times
    per_master_votes = {}
    corrs = { }  # master -> list of (clip_t, master_t)
    db_u64 = db_u8.view(np.uint64).reshape(len(db_u8), 4)
    for cidx, descs in frames:
        ct = cidx / 24.0
        bi, bd, sd = match_descriptors(np.ascontiguousarray(descs), db_u64)
        good = (bd <= (80 if ORB_LOOSE else 70)) & (bd <= (0.9 if ORB_LOOSE else 0.85) * sd)
        for gi in np.where(good)[0]:
            m = int(db_mids[bi[gi]]); mf = int(db_frames[bi[gi]])
            per_master_votes[m] = per_master_votes.get(m, 0) + 1
            corrs.setdefault(m, []).append((ct, mf / 24.0))
    if not per_master_votes:
        return cname, []
    top = sorted(per_master_votes.items(), key=lambda kv: -kv[1])[:TOP_MASTERS]
    cands = []
    for m, votes in top:
        arr = np.array(corrs[m])
        ct, mt = arr[:, 0], arr[:, 1]
        r = ransac_fit(ct, mt, seed=hash(cname) % 100000)
        if r is None:
            continue
        inl, rate, t0 = r
        uniq = len(np.unique((ct[inl] * 24 / 8).astype(int)))  # uniq 3fps-equiv frames
        min_inl = 6 if ORB_LOOSE else 8
        if inl.sum() < min_inl or uniq < (2 if ORB_LOOSE else 3):
            continue
        # build fmap at 3fps grid for verify.py
        fmap = {}
        for c, mm in zip(ct[inl], mt[inl]):
            c3 = int(round(c * 3))
            m3 = int(round(mm * 3))
            if c3 not in fmap:
                fmap[c3] = (m3, 20)
        cands.append(dict(master=m, rate=float(rate), off=float(t0 * 3),
                          t0_direct=float(t0), inliers=int(inl.sum()),
                          uniq_frames=int(uniq), votes=int(votes),
                          mean_dist=20.0, fmap={str(k): [int(v[0]), v[1]] for k, v in fmap.items()}))
    cands.sort(key=lambda c: -c['inliers'])
    return cname, cands


def descriptors_view(d):
    return np.ascontiguousarray(d)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'builddb':
        build_db()
        return
    if not os.path.exists(os.path.join(SIG, 'masters_orb.npz')):
        build_db()
    with open(os.path.join(OUT, TODO_JSON)) as f:
        clips = json.load(f)
    results = {}
    with ProcessPoolExecutor(max_workers=10) as ex:
        for cname, cands in ex.map(process_clip, clips):
            results[cname] = dict(candidates=cands)
            if cands:
                b = cands[0]
                print(f"{cname}: master_{b['master']:02d} rate={b['rate']:.3f} "
                      f"t0={b['t0_direct']:.2f} inl={b['inliers']} uniq={b['uniq_frames']} v={b['votes']}", flush=True)
            else:
                print(f"{cname}: no orb candidate", flush=True)
    with open(os.path.join(OUT, ORB_OUT), 'w') as f:
        json.dump(results, f)
    print('saved orb_candidates.json')


if __name__ == '__main__':
    main()
