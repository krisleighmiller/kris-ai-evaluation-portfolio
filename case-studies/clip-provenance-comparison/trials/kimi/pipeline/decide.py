#!/usr/bin/env python3
"""Decision stage: merge verification results from the stage-1 path and the ORB
path, classify each clip as confident / uncertain / unidentified, and emit the
todo list of clips that should go through (another) ORB search.

Usage: decide.py <verify1.json> <verify2.json|-> <out_prefix> [--emit-todo todo.json]
"""
import os, json, sys
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))

RATE_LO, RATE_HI = 0.65, 1.45
NCC_CONF = 0.70     # confident threshold (calibrated: synth correct >= 0.64, FP <= 0.62)
NCC_ACC = 0.55      # accept (uncertain) threshold


def clip_static_score(cname):
    """Mean abs diff between evenly sampled frames; low => static content."""
    cap = cv2.VideoCapture(os.path.join(CLIPS_DIR, cname))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    picks = np.linspace(0, total - 1, 8).astype(int)
    frames = []
    for p in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(p))
        ok, f = cap.read()
        if ok:
            frames.append(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (64, 48)).astype(np.float32))
    cap.release()
    if len(frames) < 3:
        return 999.0
    diffs = [np.abs(frames[i + 1] - frames[i]).mean() for i in range(len(frames) - 1)]
    return float(np.mean(diffs))


def collect(resdict):
    """Flatten {clip: {mXX: result}} to per-clip candidate list."""
    out = {}
    for cname, res in resdict.items():
        for mk, r in (res or {}).items():
            if r is None or r.get('t0') is None:
                continue
            mid = int(mk[1:])
            rate = r.get('rate')
            entry = dict(master=mid, ncc=r['ncc_med'], t0=r['t0'], rate=rate,
                         frac_good=r.get('frac_good', 0), n_inlier=r.get('n_inlier', 0),
                         crop=r.get('crop'), coverage=r.get('coverage', 1.0), src=mk)
            out.setdefault(cname, []).append(entry)
    return out


def main():
    v1 = json.load(open(os.path.join(OUT, sys.argv[1])))
    v2f = sys.argv[2]
    v2 = json.load(open(os.path.join(OUT, v2f))) if v2f != '-' else {}
    prefix = sys.argv[3]
    emit_todo = None
    if '--emit-todo' in sys.argv:
        emit_todo = sys.argv[sys.argv.index('--emit-todo') + 1]

    by_clip = {}
    for src, dd in (('s1', collect(v1)), ('orb', collect(v2))):
        for cname, lst in dd.items():
            by_clip.setdefault(cname, []).extend(lst)

    # all clips
    all_clips = sorted(set(list(v1.keys()) + list(v2.keys())))
    rows = []
    todo = []
    for cname in all_clips:
        cands = by_clip.get(cname, [])
        # dedupe by (master): keep highest ncc per master
        best_per_master = {}
        for c in cands:
            k = c['master']
            if k not in best_per_master or c['ncc'] > best_per_master[k]['ncc']:
                best_per_master[k] = c
        cands = sorted(best_per_master.values(), key=lambda c: -c['ncc'])
        plausible = [c for c in cands
                     if c['rate'] is not None and RATE_LO <= c['rate'] <= RATE_HI
                     and c['n_inlier'] >= 3 and c['frac_good'] >= 0.4
                     and c.get('coverage', 1.0) >= 0.06]
        decision = None
        if plausible and plausible[0]['ncc'] >= NCC_ACC:
            best = plausible[0]
            second = plausible[1] if len(plausible) > 1 else None
            margin = best['ncc'] - (second['ncc'] if second else 0.0)
            if best['ncc'] >= NCC_CONF and (second is None or second['ncc'] < NCC_CONF or margin >= 0.05):
                tier = 'confident'
            else:
                tier = 'uncertain'
            decision = (tier, best)
        else:
            # static-content fallback: any high-ncc candidate regardless of rate
            static = clip_static_score(cname) < 2.0
            high = [c for c in cands if c['ncc'] >= 0.72]
            if static and high:
                decision = ('uncertain-static', high[0])
        if decision:
            tier, best = decision
            rows.append(dict(clip=cname, tier=tier, master=best['master'],
                             t0=best['t0'], rate=best['rate'], ncc=best['ncc'],
                             frac_good=best['frac_good'], n_inlier=best['n_inlier'],
                             crop=best['crop'], coverage=best.get('coverage'),
                             n_candidates=len(cands)))
            if tier != 'confident':
                todo.append(cname)
        else:
            rows.append(dict(clip=cname, tier='unidentified', master=None,
                             t0=None, rate=None, ncc=(cands[0]['ncc'] if cands else None),
                             frac_good=None, n_inlier=None, crop=None,
                             n_candidates=len(cands)))
            todo.append(cname)

    with open(os.path.join(OUT, f'{prefix}_decisions.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    if emit_todo:
        with open(os.path.join(OUT, emit_todo), 'w') as f:
            json.dump(todo, f)
    tiers = {}
    for r in rows:
        tiers[r['tier']] = tiers.get(r['tier'], 0) + 1
    print(prefix, tiers, 'todo:', len(todo))


if __name__ == '__main__':
    main()
