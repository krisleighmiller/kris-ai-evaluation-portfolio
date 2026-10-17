#!/usr/bin/env python3
"""Merge decisions + refinement into the final report (CSV + JSON).
Usage: report.py <decisions.json> <refined.json|-> <out_basename>
"""
import os, json, sys, csv
import subprocess
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))


def clip_dur(cname):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', os.path.join(CLIPS_DIR, cname)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def static_score(cname):
    cap = cv2.VideoCapture(os.path.join(CLIPS_DIR, cname))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    picks = np.linspace(0, total - 1, 6).astype(int)
    frames = []
    for p in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(p))
        ok, f = cap.read()
        if ok:
            frames.append(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (64, 48)).astype(np.float32))
    cap.release()
    if len(frames) < 3:
        return 999.0
    return float(np.mean([np.abs(frames[i + 1] - frames[i]).mean() for i in range(len(frames) - 1)]))


def main():
    dec = json.load(open(os.path.join(OUT, sys.argv[1])))
    ref = json.load(open(os.path.join(OUT, sys.argv[2]))) if sys.argv[2] != '-' else {}
    base = sys.argv[3]
    rows = []
    for r in sorted(dec, key=lambda x: x['clip']):
        row = dict(r)
        rr = ref.get(r['clip'])
        if rr and rr.get('t0') is not None:
            row['t0_refined'] = rr['t0']
            row['rate_refined'] = rr['rate']
            row['ncc_refined'] = rr['ncc']
            row['resid_std'] = rr['resid_std']
            row['n_inlier_refined'] = rr['n_inlier']
            # tier adjustment using refinement quality
            if row['tier'] == 'confident' and (rr['ncc'] < 0.65 or rr['resid_std'] > 0.20
                                             or rr['n_inlier'] < 4):
                row['tier'] = 'uncertain'
            elif row['tier'] == 'uncertain' and rr['ncc'] >= 0.75 and rr['resid_std'] <= 0.15:
                row['tier'] = 'confident'
        dur = clip_dur(r['clip'])
        row['clip_dur'] = dur
        t0 = row.get('t0_refined', row.get('t0'))
        rate = row.get('rate_refined', row.get('rate'))
        if t0 is not None and dur is not None and rate:
            row['master_start_s'] = round(t0, 2)
            row['master_end_s'] = round(t0 + dur * rate, 2)
        if row['master'] is not None:
            ss = static_score(row['clip'])
            row['static_score'] = round(ss, 2)
            if ss < 4.0:
                row['note'] = 'static content: t0 within static span, rate not meaningful'
            elif row.get('rate_refined') and not (0.9 <= row['rate_refined'] <= 1.1):
                row['note'] = 'speed estimate less certain (mixed static/motion or strong rate change)'
        rows.append(row)
    keys = ['clip', 'tier', 'master', 'master_start_s', 'master_end_s', 'rate_refined',
            'ncc_refined', 'resid_std', 'n_inlier_refined', 'clip_dur', 'crop',
            'coverage', 'static_score', 'note', 'ncc', 't0', 'rate', 'frac_good',
            'n_inlier', 'n_candidates']
    with open(os.path.join(OUT, f'{base}.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            w.writerow(row)
    with open(os.path.join(OUT, f'{base}.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    tiers = {}
    for row in rows:
        tiers[row['tier']] = tiers.get(row['tier'], 0) + 1
    print('tiers:', tiers)
    print('saved', base + '.csv')


if __name__ == '__main__':
    main()
