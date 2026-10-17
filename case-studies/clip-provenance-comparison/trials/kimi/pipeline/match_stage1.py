#!/usr/bin/env python3
"""Stage 1: coarse matching via pHash correspondences + RANSAC temporal line fit.

For each clip: for every sampled frame (3 fps), find top-K master frames by
Hamming distance (min over 3x3 region-hash pairs). Then fit a robust linear map
master_frame = rate * clip_frame + offset (per master) via RANSAC.
Output: work/out/stage1.json
"""
import os, json
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIG = os.path.join(ROOT, 'work', 'sig')
OUT = os.path.join(ROOT, 'work', 'out')
os.makedirs(OUT, exist_ok=True)

FPS = 3
NMASTERS = 45
MFRAMES = 120          # master frames at 3fps (40 s)
TOPK = 12
DIST_MAX = 26          # max Hamming for a correspondence
TOL = 2.5              # temporal inlier tolerance (frames at 3fps)
RATE_MIN, RATE_MAX = 0.75, 1.33


CLIPS_SIG = os.environ.get('CLIPS_SIG', 'clips_sig.npz')
STAGE1_OUT = os.environ.get('STAGE1_OUT', 'stage1.json')

def load(kind):
    name = CLIPS_SIG if kind == 'clips' else f'{kind}_sig.npz'
    z = np.load(os.path.join(SIG, name))
    return z['names'], z['hashes'], z['stds'], z['offsets'], z['n_frames']


def dist_matrix(clip_hashes, master_hashes):
    """clip_hashes (C,3) u64, master_hashes (M,3) u64 -> (C,M) min-over-pairs uint8."""
    C = clip_hashes.shape[0]
    M = master_hashes.shape[0]
    best = np.full((C, M), 64, dtype=np.uint8)
    for a in range(3):
        ca = clip_hashes[:, a][:, None]          # (C,1)
        for b in range(3):
            x = np.bitwise_xor(ca, master_hashes[:, b][None, :])  # (C,M)
            d = np.bitwise_count(x).astype(np.uint8)
            np.minimum(best, d, out=best)
    return best


def ransac_master(cidx, midx, dists, iters=1500, seed=0):
    """Fit midx = rate*cidx + off. Returns (inlier_mask, rate, off)."""
    rng = np.random.default_rng(seed)
    n = len(cidx)
    if n < 4:
        return None
    cidx = cidx.astype(np.float64); midx = midx.astype(np.float64)
    best_in = None; best_rate = 1.0; best_off = 0.0
    for _ in range(iters):
        i, j = rng.choice(n, 2, replace=False)
        if cidx[i] == cidx[j]:
            continue
        rate = (midx[j] - midx[i]) / (cidx[j] - cidx[i])
        if not (RATE_MIN <= rate <= RATE_MAX):
            continue
        off = midx[i] - rate * cidx[i]
        resid = np.abs(midx - (rate * cidx + off))
        inl = resid <= TOL
        if best_in is None or inl.sum() > best_in.sum() or (
                inl.sum() == best_in.sum() and dists[inl].mean() < dists[best_in].mean()):
            best_in, best_rate, best_off = inl, rate, off
    # least-squares refit on inliers
    if best_in is not None and best_in.sum() >= 2:
        A = np.vstack([cidx[best_in], np.ones(best_in.sum())]).T
        rate, off = np.linalg.lstsq(A, midx[best_in], rcond=None)[0]
        resid = np.abs(midx - (rate * cidx + off))
        best_in = resid <= TOL
        best_rate, best_off = rate, off
    return best_in, best_rate, best_off


def match_clip(chashes, cstds, mhashes, seed=0):
    D = dist_matrix(chashes, mhashes)               # (C, Mtotal)
    C, Mtot = D.shape
    # mask degenerate (flat) clip frames
    ok = cstds > 8.0
    # top-K per frame
    K = min(TOPK, Mtot)
    part = np.argpartition(D, K, axis=1)[:, :K]     # (C,K)
    corrs = []  # (cidx, master_id, local_idx, dist)
    for c in range(C):
        if not ok[c]:
            continue
        for j in part[c]:
            d = D[c, j]
            if d <= DIST_MAX:
                corrs.append((c, j // MFRAMES, j % MFRAMES, int(d)))
    if not corrs:
        return None, D
    corrs = np.array(corrs)
    # per-master vote counts
    counts = np.bincount(corrs[:, 1], minlength=NMASTERS)
    top_masters = np.argsort(-counts)[:6]
    results = []
    for m in top_masters:
        if counts[m] < 4:
            continue
        sel = corrs[:, 1] == m
        cidx, midx, dd = corrs[sel, 0], corrs[sel, 2], corrs[sel, 3]
        r = ransac_master(cidx, midx, dd, seed=seed)
        if r[0] is None:
            continue
        inl, rate, off = r
        uniq_frames = len(np.unique(cidx[inl]))
        # per-clip-frame best master local position (min dist among inlier corrs)
        fmap = {}
        for c, ml, d in zip(cidx[inl], midx[inl], dd[inl]):
            c = int(c)
            if c not in fmap or d < fmap[c][1]:
                fmap[c] = (int(ml), int(d))
        results.append(dict(master=int(m), rate=float(rate), off=float(off),
                            inliers=int(inl.sum()), uniq_frames=uniq_frames,
                            mean_dist=float(dd[inl].mean()),
                            votes=int(counts[m]),
                            fmap={str(k): v for k, v in fmap.items()}))
    results.sort(key=lambda r: (-r['uniq_frames'], r['mean_dist']))
    return results, D


def main():
    mnames, mhashes, mstds, moff, mn = load('masters')
    cnames, chashes, cstds, coff, cn = load('clips')
    out = {}
    for ci, name in enumerate(cnames):
        ch = chashes[coff[ci]:coff[ci] + cn[ci]]
        cs = cstds[coff[ci]:coff[ci] + cn[ci]]
        res, D = match_clip(ch, cs, mhashes, seed=ci)
        out[name] = dict(n_frames=int(cn[ci]), candidates=res)
        best = res[0] if res else None
        if best:
            print(f"{name}: master_{best['master']:02d} rate={best['rate']:.3f} "
                  f"off={best['off']:.1f} frames={best['uniq_frames']}/{cn[ci]} "
                  f"d={best['mean_dist']:.1f}", flush=True)
        else:
            print(f"{name}: NO CANDIDATE", flush=True)
    with open(os.path.join(OUT, STAGE1_OUT), 'w') as f:
        json.dump(out, f, indent=1)
    print('saved', os.path.join(OUT, STAGE1_OUT))


if __name__ == '__main__':
    main()
